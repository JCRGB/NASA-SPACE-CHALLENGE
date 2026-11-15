"""Flask API for the processed lunar landing site layers."""

import json
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from scripts.process_lunar_data import PROCESSED_DIR, score_suitability


app = Flask(__name__)
CORS(app)
FILES = {
    "sunlight": "sunlight_data.json",
    "slopes": "slope_data.json",
    "solar-potential": "solar_potential.json",
    "suitability": "suitability_scores.json",
}


def load_dataset(name): 
    path = PROCESSED_DIR / FILES[name]
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    available = {key: (PROCESSED_DIR / filename).exists() for key, filename in FILES.items()}
    return jsonify({"status": "ok", "region": {"name": "Lunar South Pole / Shackleton Crater",
                    "latitude": [-89.9, -85.0], "longitude": [-180.0, 180.0]},
                    "grid_size": "100x100", "datasets": available})


@app.get("/api/<name>")
def dataset(name):
    if name not in FILES:
        return jsonify({"error": "Unknown dataset"}), 404
    data = load_dataset(name)
    if data is None:
        return jsonify({"error": "Dataset not generated; run python scripts/process_lunar_data.py"}), 503
    if name == "suitability":
        try:
            min_score = float(request.args.get("min_score", 0))
            slope_weight = float(request.args.get("slope_weight", 0.5))
            solar_weight = float(request.args.get("solar_weight", 0.3))
            ice_weight = float(request.args.get("ice_weight", 0.2))
            if not 0 <= min_score <= 100:
                raise ValueError("min_score must be between 0 and 100")
            for item in data:
                score = float(score_suitability(item["slope_degrees"], item["illumination"], item["ice_bonus"],
                                                slope_weight, solar_weight, ice_weight))
                item["value"] = round(score, 4)
                item["risk_rating"] = "Hazardous" if item["slope_degrees"] > 15 or score < 35 else (
                    "Optimal" if score >= 70 else "Moderate")
            data = [item for item in data if item["value"] >= min_score]
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
