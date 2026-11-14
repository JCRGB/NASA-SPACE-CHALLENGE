
from pathlib import Path

# ==========================================
# LUNAR LANDING SITE NAVIGATOR
# AUTOMATIC PROJECT SETUP
# ==========================================

PROJECT_NAME = "LUNAR-LANDING-NAVIGATOR"

# Create project beside this Python script
BASE = Path(__file__).parent / PROJECT_NAME

# ==========================================
# PROJECT FILES
# ==========================================

files = {

    # FRONTEND
    "frontend/index.html": "",
    "frontend/style.css": "",
    "frontend/package.json": """{
  "name": "lunar-landing-navigator",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite"
  },
  "dependencies": {
    "three": "^0.180.0"
  },
  "devDependencies": {
    "vite": "^7.0.0"
  }
}""",

    "frontend/src/main.js": "// Main frontend entry point\n",
    "frontend/src/moon.js": "// 3D Moon creation and rendering\n",
    "frontend/src/controls.js": "// Visualisation mode controls\n",
    "frontend/src/interaction.js": "// Mouse interaction and coordinates\n",
    "frontend/src/data.js": "// Backend API communication\n",

    # VISUALISATION LAYERS
    "frontend/src/layers/sunlight.js": "// Sunlight visualisation\n",
    "frontend/src/layers/terrain.js": "// Terrain visualisation\n",
    "frontend/src/layers/solarEnergy.js": "// Solar energy visualisation\n",
    "frontend/src/layers/suitability.js": "// Overall suitability visualisation\n",

    # BACKEND
    "backend/app.py": """from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return jsonify({"message": "Lunar Navigator API is running"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
""",

    "backend/requirements.txt": """flask
flask-cors
numpy
pandas
rasterio
Pillow
""",

    # PYTHON CALCULATIONS
    "backend/calculations/__init__.py": "",
    "backend/calculations/sunlight.py": "# Sunlight calculations\n",
    "backend/calculations/terrain.py": "# Terrain calculations\n",
    "backend/calculations/solar_energy.py": "# Solar energy calculations\n",
    "backend/calculations/suitability.py": "# Landing suitability calculations\n",

    # DATA PROCESSING
    "backend/processing/__init__.py": "",
    "backend/processing/data_loader.py": "# Load NASA datasets\n",
    "backend/processing/coordinate_converter.py": "# Convert lunar coordinates\n",

    # DATA FILES
    "data/processed/sunlight.json": '{"locations": []}',
    "data/processed/terrain.json": '{"locations": []}',
    "data/processed/solar_energy.json": '{"locations": []}',
    "data/processed/suitability.json": '{"locations": []}',

    # DOCUMENTATION
    "README.md": """# Lunar Landing Site Navigator

Interactive 3D lunar exploration and landing-site suitability analysis.

## Technologies
- Three.js
- JavaScript
- Python
- Flask
- NASA scientific datasets

## Features
- Sunlight visualisation
- Terrain visualisation
- Solar energy potential
- Overall landing suitability
""",

    ".gitignore": """node_modules/
__pycache__/
*.pyc
.venv/
.env
.DS_Store
"""
}

# ==========================================
# CREATE DIRECTORIES AND FILES
# ==========================================

for relative_path, content in files.items():

    file_path = BASE / relative_path

    # Automatically create parent folders
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Do not overwrite existing files
    if not file_path.exists():
        file_path.write_text(content, encoding="utf-8")

# Create asset and raw data folders
folders = [
    "frontend/assets/models",
    "frontend/assets/textures",
    "data/raw/sunlight",
    "data/raw/elevation"
]

for folder in folders:
    (BASE / folder).mkdir(parents=True, exist_ok=True)

# ==========================================
# COMPLETION MESSAGE
# ==========================================

print("\n================================")
print("LUNAR PROJECT CREATED!")
print("================================")
print(f"\nProject location:\n{BASE}")

print(f"\nFiles created: {len(files)}")
print("Folders created successfully!")

print("\nNext steps:")
print("1. Open LUNAR-LANDING-NAVIGATOR in VS Code.")
print("2. Install frontend dependencies.")
print("3. Install backend dependencies.")
print("4. Start developing!")
