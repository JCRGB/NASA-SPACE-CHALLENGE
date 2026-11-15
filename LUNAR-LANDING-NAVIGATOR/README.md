# Lunar Landing Site Navigator backend

The pipeline creates a 100 × 100 sample grid for the Lunar South Pole / Shackleton Crater region and serves four JSON datasets through Flask. Synthetic inputs are generated automatically when either raw GeoTIFF is missing.

## Setup and run

```bash
cd lunar-navigator-backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python scripts/process_lunar_data.py
python app.py
```

The API runs at `http://127.0.0.1:5000`. Available routes are `/api/health`, `/api/sunlight`, `/api/slopes`, `/api/solar-potential`, and `/api/suitability`. Suitability accepts `min_score` and non-negative `slope_weight`, `solar_weight`, `ice_weight` query parameters.

Run the tests in a second terminal from this directory after processing:

```bash
source .venv/bin/activate
python -m unittest -v test_api.py
```

Replace `data/raw/lunar_dem.tif` and `data/raw/lunar_illumination.tif` with aligned, single-band GeoTIFFs to process real data. Values from the built-in generator are synthetic demonstration data, not flight-certified terrain products.