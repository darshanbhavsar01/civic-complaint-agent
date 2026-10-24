"""Stamp GPS EXIF onto a demo photo so get_photo_location finds it.

Phone photos sent through WhatsApp or a browser usually have the EXIF stripped,
which is exactly the fallback path we demo. For the main demo photo we want GPS
present, so write it in deliberately.

    python demo/add_gps.py pothole.jpg W12
    python demo/add_gps.py garbage.jpg 23.0063 72.6013
    python demo/add_gps.py --list

Writes <name>.gps.jpg next to the input.
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

from PIL import ExifTags, Image

ROOT = Path(__file__).resolve().parent.parent
WARDS = {w["id"]: w for w in json.loads((ROOT / "data" / "amc.json").read_text(encoding="utf-8"))["wards"]}

GPS = ExifTags.IFD.GPSInfo
TAG = {name: num for num, name in ExifTags.GPSTAGS.items()}


def _dms(value: float) -> tuple[Fraction, Fraction, Fraction]:
    """Decimal degrees to the (deg, min, sec) rationals EXIF expects."""
    value = abs(value)
    deg = int(value)
    minutes_f = (value - deg) * 60
    minutes = int(minutes_f)
    seconds = round((minutes_f - minutes) * 60, 4)
    return Fraction(deg, 1), Fraction(minutes, 1), Fraction(seconds).limit_denominator(10000)


def stamp(path: Path, lat: float, lng: float) -> Path:
    with Image.open(path) as img:
        exif = img.getexif()
        gps = {
            TAG["GPSLatitudeRef"]: "N" if lat >= 0 else "S",
            TAG["GPSLatitude"]: _dms(lat),
            TAG["GPSLongitudeRef"]: "E" if lng >= 0 else "W",
            TAG["GPSLongitude"]: _dms(lng),
        }
        exif[GPS] = gps
        out = path.with_suffix(".gps.jpg")
        img.convert("RGB").save(out, "JPEG", quality=88, exif=exif)
    return out


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    if argv[0] == "--list":
        for ward in WARDS.values():
            lat, lng = ward["centroid"]
            print(f"{ward['id']:>4}  {ward['name']:<14} {ward['zone']:<11} {lat}, {lng}")
        return 0

    path = Path(argv[0])
    if not path.exists():
        print(f"No such file: {path}")
        return 1

    if len(argv) == 2 and argv[1].upper() in WARDS:
        ward = WARDS[argv[1].upper()]
        lat, lng = ward["centroid"]
        label = f"{ward['id']} {ward['name']}"
    elif len(argv) == 3:
        lat, lng = float(argv[1]), float(argv[2])
        label = "given coordinates"
    else:
        print(__doc__)
        return 1

    out = stamp(path, lat, lng)
    print(f"{out}  <-  {lat}, {lng}  ({label})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
