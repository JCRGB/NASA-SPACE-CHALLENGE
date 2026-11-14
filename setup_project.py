
from pathlib import Path

# Main project folder
PROJECT_NAME = "LUNAR-LANDING-NAVIGATOR"

# Folder structure and files
structure = {
    "src/layers": [
        "sunlight.js",
        "terrain.js",
        "solarEnergy.js",
        "suitability.js"
    ],

    "assets": [
        "moon.glb",
        "moon_texture.jpg"
    ],

    "data": [
        "sunlight.json",
        "terrain.json",
        "solar_energy.json"
    ],

    "src": [
        "main.js",
        "moon.js",
        "controls.js",
        "interaction.js",
        "data.js"
    ],

    "": [
        "index.html",
        "style.css",
        "package.json",
        "README.md"
    ]
}

# Create main project folder beside this script
project_path = Path(__file__).parent / PROJECT_NAME

# Create folders and files
for folder, files in structure.items():

    folder_path = project_path / folder

    # Create folder
    folder_path.mkdir(parents=True, exist_ok=True)

    # Create files
    for filename in files:
        file_path = folder_path / filename

        if not file_path.exists():
            file_path.touch()

# Confirm completion
print("\nProject structure created successfully!")
print(f"Location: {project_path}")

print("\nYour project is ready!")
