"""A BaseLlm that walks a chain of (model, key) pairs for the root agent.

`LlmAgent(model="...")` pins the agent to one model and one key, which is the
single worst failure mode for a live demo on free-tier quota. This wrapper holds
an ordered list of ADK `Gemini` instances - every model in the chain, times every
configured key - and hands the request to the first one that answers.

Retry semantics are deliberately conservative: a request is only re-sent to the
next pair if it failed **before any content was yielded**. Once tokens have
reached the caller, switching models mid-answer would corrupt the reply, so the
error propagates instead.
"""
from __future__ import annotations

from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from pydantic import PrivateAttr

from . import llm as llm_cfg


class FailoverLlm(BaseLlm):
    """Tries each (model, key) pair in order until one produces content."""

    _rungs: list[tuple[str, str, Gemini]] = PrivateAttr(default_factory=list)
    _preferred: int = PrivateAttr(default=0)

    def __init__(self, **kwargs) -> None:
        chain = llm_cfg.model_chain()
        keys = llm_cfg.api_keys()
        super().__init__(model=kwargs.pop("model", None) or chain[0], **kwargs)

        rungs: list[tuple[str, str, Gemini]] = []
        for model_name in chain:
            for index, key in enumerate(keys):
                label = ("primary", "backup")[index] if index < 2 else f"key{index + 1}"
                rungs.append(
                    (model_name, label, Gemini(model=model_name, client_kwargs={"api_key": key}))
                )
        if not rungs:
            # No keys configured: keep one plain rung so the error surfaces from
            # the SDK with its usual message rather than from an empty list here.
            rungs = [(chain[0], "none", Gemini(model=chain[0]))]
        self._rungs = rungs

    @property
    def rungs(self) -> list[tuple[str, str]]:
        """The chain as (model, key_label) pairs, for logging and tests."""
        return [(model, label) for model, label, _ in self._rungs]

    @staticmethod
    def supported_models() -> list[str]:
        """Delegated to Gemini - this wrapper only ever holds Gemini rungs."""
        return Gemini.supported_models()

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Yield from the first rung that answers, trying later rungs on failure."""
        # Start from whatever worked last time; a model that is out of quota stays
        # out for the rest of the session, so retrying it first wastes a call.
        order = list(range(len(self._rungs)))
        order.sort(
            key=lambda i: (
                # Parked rungs last, then the one that worked last time first.
                llm_cfg.is_cooling(self._rungs[i][0], self._rungs[i][1]),
                i != self._preferred,
            )
        )

        last_exc: Exception | None = None
        tried: list[str] = []

        for position, index in enumerate(order):
            model_name, label, delegate = self._rungs[index]
            produced = False
            try:
                async for response in delegate.generate_content_async(llm_request, stream):
                    produced = True
                    yield response
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                tried.append(f"{model_name}/{label}: {type(exc).__name__}")
                if produced:
                    # Content already reached the caller; swapping models now would
                    # splice two different answers together.
                    print(
                        f"[llm] {model_name} via {label} failed mid-response; "
                        "not retrying to avoid a spliced reply"
                    )
                    raise
                if not llm_cfg.is_retryable(exc):
                    print(f"[llm] {model_name} via {label} failed hard: {exc}")
                    raise
                llm_cfg.mark_unavailable(model_name, label)
                print(
                    f"[llm] agent model {model_name} via {label} unavailable "
                    f"({str(exc)[:120]}); trying the next option"
                )
                continue

            self._preferred = index
            if position > 0:
                print(f"[llm] agent fell back to {model_name} via {label}")
            return

        raise RuntimeError(
            f"Every Gemini model and key failed for the agent. Tried: {'; '.join(tried)}"
        ) from last_exc
