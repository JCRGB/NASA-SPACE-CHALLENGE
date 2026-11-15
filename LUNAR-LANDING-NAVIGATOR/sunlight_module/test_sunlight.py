#!/usr/bin/env python3
"""Standalone validation for the generated Three.js sunlight JSON."""

from __future__ import annotations

import json
import math
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "output" / "sunlight_data.json"


def main() -> int:
    failures: list[str] = []
    if not OUTPUT.is_file():
        print(f"FAIL: output file not found: {OUTPUT}")
        return 1
    try:
        with OUTPUT.open(encoding="utf-8") as stream:
            data = json.load(stream, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: invalid JSON: {exc}")
        return 1

    metadata = data.get("metadata") if isinstance(data, dict) else None
    points = data.get("points") if isinstance(data, dict) else None
    if not isinstance(metadata, dict) or not metadata.get("original_crs"):
        failures.append("metadata.original_crs is missing")
    if not isinstance(points, list) or not points:
        failures.append("points must be a non-empty array")
        points = []

    illuminations: list[float] = []
    for i, point in enumerate(points):
        try:
            lat, lon = float(point["lat"]), float(point["lon"])
            illumination = float(point["illumination_pct"])
            vector = point["three_pos"]
            x_m, y_m = float(point["proj_x_m"]), float(point["proj_y_m"])
        except (KeyError, TypeError, ValueError, OverflowError):
            failures.append(f"point {i} is missing numeric coordinates/value/vector")
            continue
        numbers = [lat, lon, illumination, x_m, y_m]
        if not all(math.isfinite(v) for v in numbers):
            failures.append(f"point {i} contains NaN or infinity")
        if not (-90.0 <= lat <= -65.0 and -180.0 <= lon <= 180.0):
            failures.append(f"point {i} is outside 65S–90S latitude/longitude bounds")
        if not (0.0 <= illumination <= 100.0):
            failures.append(f"point {i} has illumination outside [0, 100]")
        else:
            illuminations.append(illumination)
        if not isinstance(vector, list) or len(vector) != 3:
            failures.append(f"point {i} three_pos must contain 3 numbers")
        else:
            try:
                coords = [float(v) for v in vector]
                magnitude = math.sqrt(sum(v * v for v in coords))
                if not all(math.isfinite(v) for v in coords) or abs(magnitude - 1.0) > 0.001:
                    failures.append(f"point {i} has invalid unit vector magnitude ({magnitude})")
            except (TypeError, ValueError, OverflowError):
                failures.append(f"point {i} three_pos contains non-numeric values")
        if failures and len(failures) >= 30:
            break

    if illuminations and not any(v < 5.0 for v in illuminations):
        failures.append("no shadowed (<5%) points were sampled")
    if illuminations and not any(v > 50.0 for v in illuminations):
        failures.append("no sunlit (>50%) points were sampled")
    if failures:
        print("FAIL: sunlight JSON validation")
        for issue in failures:
            print(f"  - {issue}")
        return 1
    print("PASS: sunlight JSON validation")
    print(f"  CRS: {metadata['original_crs']}")
    print(f"  Points: {len(points):,}")
    print(f"  Illumination range: {min(illuminations):.3f}–{max(illuminations):.3f}%")
    print("  Coverage, finite values, shadow/sunlit classes, and Three.js unit vectors are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
