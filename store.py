"""Repository layer over the mock AMC dataset.

Two interchangeable backends:
  JsonStore      - reads/writes data/amc.json (local, offline, default)
  FirestoreStore - same interface on Cloud Firestore (Cloud Run)

Select with STORE=json|firestore. Static reference data (wards, departments,
city, zone officers) always comes from the JSON seed; only complaints,
the ID sequence and the geocode cache live in the chosen backend.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SEED_PATH = ROOT / "data" / "amc.json"


def _load_seed() -> dict[str, Any]:
    with SEED_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class BaseStore:
    """Shared reference-data accessors. Subclasses own complaint persistence."""

    def __init__(self) -> None:
        self._seed = _load_seed()
        self._lock = threading.RLock()

    # ---- reference data (read-only, from the seed) ----
    @property
    def city(self) -> dict[str, Any]:
        return self._seed["city"]

    @property
    def wards(self) -> list[dict[str, Any]]:
        return self._seed["wards"]

    @property
    def departments(self) -> dict[str, Any]:
        return self._seed["departments"]

    @property
    def zone_officers(self) -> dict[str, str]:
        return self._seed.get("zone_officers", {})

    def ward(self, ward_id: str) -> dict[str, Any] | None:
        return next((w for w in self.wards if w["id"] == ward_id), None)

    def department(self, issue_type: str) -> dict[str, Any] | None:
        depts = self.departments
        return depts.get(issue_type) or depts.get("other")

    # ---- complaint persistence (subclass responsibility) ----
    def list_complaints(self, ward: str = "", status: str = "") -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_complaint(self, tracking_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def put_complaint(self, complaint: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def next_tracking_id(self) -> str:
        raise NotImplementedError

    def geocode_get(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def geocode_put(self, key: str, value: dict[str, Any]) -> None:
        raise NotImplementedError


class JsonStore(BaseStore):
    """File-backed store. Rewrites the whole document per mutation (fine at demo scale)."""

    def __init__(self, path: Path = SEED_PATH) -> None:
        super().__init__()
        self.path = path
        self._doc = _load_seed()
        self._doc.setdefault("complaints", [])
        self._doc.setdefault("sequence", 1)
        self._geocache: dict[str, dict[str, Any]] = {}

    def _flush(self) -> None:
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(self._doc, fh, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    def list_complaints(self, ward: str = "", status: str = "") -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._doc["complaints"])
        if ward:
            rows = [r for r in rows if r.get("ward") == ward]
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return sorted(rows, key=lambda r: r.get("filedAt", ""), reverse=True)

    def get_complaint(self, tracking_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (r for r in self._doc["complaints"] if r["trackingId"] == tracking_id), None
            )

    def put_complaint(self, complaint: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rows = self._doc["complaints"]
            for i, row in enumerate(rows):
                if row["trackingId"] == complaint["trackingId"]:
                    rows[i] = complaint
                    break
            else:
                rows.append(complaint)
            self._flush()
            return complaint

    def next_tracking_id(self) -> str:
        with self._lock:
            seq = int(self._doc.get("sequence", 1)) + 1
            self._doc["sequence"] = seq
            self._flush()
            return f"AMC-2026-{seq:06d}"

    def geocode_get(self, key: str) -> dict[str, Any] | None:
        return self._geocache.get(key)

    def geocode_put(self, key: str, value: dict[str, Any]) -> None:
        self._geocache[key] = value


class FirestoreStore(BaseStore):
    """Firestore-backed store. Seeds collections on first use so demo data exists."""

    def __init__(self) -> None:
        super().__init__()
        from google.cloud import firestore  # lazy: only needed on Cloud Run

        self._db = firestore.Client()
        self._fs = firestore
        self._complaints = self._db.collection("complaints")
        self._meta = self._db.collection("meta")
        self._geo = self._db.collection("geocache")
        self._geomem: dict[str, dict[str, Any]] = {}
        self._seed_once()

    def _seed_once(self) -> None:
        marker = self._meta.document("seeded")
        if marker.get().exists:
            return
        for row in self._seed.get("complaints", []):
            self._complaints.document(row["trackingId"]).set(row)
        self._meta.document("sequence").set({"value": int(self._seed.get("sequence", 1))})
        marker.set({"done": True})

    def list_complaints(self, ward: str = "", status: str = "") -> list[dict[str, Any]]:
        query = self._complaints
        if ward:
            query = query.where(filter=self._fs.FieldFilter("ward", "==", ward))
        if status:
            query = query.where(filter=self._fs.FieldFilter("status", "==", status))
        rows = [d.to_dict() for d in query.stream()]
        return sorted(rows, key=lambda r: r.get("filedAt", ""), reverse=True)

    def get_complaint(self, tracking_id: str) -> dict[str, Any] | None:
        snap = self._complaints.document(tracking_id).get()
        return snap.to_dict() if snap.exists else None

    def put_complaint(self, complaint: dict[str, Any]) -> dict[str, Any]:
        self._complaints.document(complaint["trackingId"]).set(complaint)
        return complaint

    def next_tracking_id(self) -> str:
        doc = self._meta.document("sequence")

        @self._fs.transactional
        def bump(tx) -> int:
            snap = doc.get(transaction=tx)
            current = int(snap.to_dict()["value"]) if snap.exists else 1
            tx.set(doc, {"value": current + 1})
            return current + 1

        seq = bump(self._db.transaction())
        return f"AMC-2026-{seq:06d}"

    def geocode_get(self, key: str) -> dict[str, Any] | None:
        if key in self._geomem:
            return self._geomem[key]
        snap = self._geo.document(key).get()
        if snap.exists:
            self._geomem[key] = snap.to_dict()
            return self._geomem[key]
        return None

    def geocode_put(self, key: str, value: dict[str, Any]) -> None:
        self._geomem[key] = value
        self._geo.document(key).set(value)


_store: BaseStore | None = None
_store_lock = threading.Lock()


def get_store() -> BaseStore:
    """Process-wide store singleton, chosen by the STORE env var."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                kind = os.getenv("STORE", "json").strip().lower()
                if kind == "firestore":
                    try:
                        _store = FirestoreStore()
                    except Exception as exc:  # noqa: BLE001 - never break the demo
                        print(f"[store] Firestore unavailable ({exc}); falling back to JSON")
                        _store = JsonStore()
                else:
                    _store = JsonStore()
    return _store
