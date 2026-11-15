"""Landing-site suitability scoring for lunar South Pole raster cells."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt


def calculate_suitability(
    slope_degrees: np.ndarray,
    illumination_percent: np.ndarray,
    *,
    slope_weight: float = 0.5,
    solar_weight: float = 0.3,
    ice_weight: float = 0.2,
    pixel_size_m: float = 60.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (0-100 score, risk labels) arrays aligned to the input rasters.

    Low-illumination cells (<5%) represent possible permanently shadowed
    regions. Nearby cells receive a distance-decaying water-ice access bonus.
    Slopes over 15 degrees receive a strong safety penalty.
    """
    slope = np.asarray(slope_degrees, dtype=float)
    illumination = np.asarray(illumination_percent, dtype=float)
    if slope.shape != illumination.shape:
        raise ValueError("slope and illumination arrays must have identical shapes")
    weights = np.asarray([slope_weight, solar_weight, ice_weight], dtype=float)
    if np.any(weights < 0) or not np.isfinite(weights).all() or weights.sum() <= 0:
        raise ValueError("weights must be finite, non-negative, and have a positive sum")
    if pixel_size_m <= 0:
        raise ValueError("pixel_size_m must be positive")

    valid = np.isfinite(slope) & np.isfinite(illumination)
    illumination = np.clip(illumination, 0.0, 100.0)
    # Terrain component rewards gentle terrain, reaching zero at 30 degrees.
    terrain_score = np.clip(1.0 - np.maximum(slope, 0.0) / 30.0, 0.0, 1.0)
    # Solar yield at 20% efficiency: 1361 W/m² * 24 h / 1000 * 0.20.
    solar_score = illumination / 100.0
    shadow = (illumination < 5.0) & valid
    if shadow.any():
        # Proximity bonus fades over 10 km; shadow pixels themselves score 1.
        distance_m = distance_transform_edt(~shadow) * pixel_size_m
        ice_score = np.clip(1.0 - distance_m / 10_000.0, 0.0, 1.0)
    else:
        ice_score = np.zeros_like(illumination)

    normalized_weights = weights / weights.sum()
    score = 100.0 * (
        normalized_weights[0] * terrain_score
        + normalized_weights[1] * solar_score
        + normalized_weights[2] * ice_score
    )
    score = np.where(slope > 15.0, score * 0.35, score)
    score = np.where(valid, np.clip(score, 0.0, 100.0), np.nan)

    risk = np.full(score.shape, "Hazardous", dtype=object)
    risk[(score >= 40.0) & (slope <= 15.0)] = "Moderate"
    risk[(score >= 70.0) & (slope <= 15.0)] = "Optimal"
    risk[~valid] = "NoData"
    return score, risk
