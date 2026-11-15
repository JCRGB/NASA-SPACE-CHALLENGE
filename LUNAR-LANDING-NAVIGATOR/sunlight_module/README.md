# Lunar South Pole sunlight module

This standalone module converts NASA's polar illumination GeoTIFF into a compact JSON point cloud for rendering on a Three.js lunar globe. All module code, data, and output are contained in this directory.

## Dataset

The input is `raw_data/AVGVISIB_65S_240M_201608.tiff`, the attached NASA LRO LOLA lunar polar illumination product. NASA's Planetary Geodesy Data Archive (PGDA) distributes the polar illumination products at [PGDA product 69](https://pgda.gsfc.nasa.gov/products/69); the corresponding 65°S–90°S, 240 m GeoTIFF is `AVGVISIB_65S_240M_201608.TIF`. Although the GeoTIFF grid is rectangular, exported point coordinates are clipped to latitudes at or south of 65°S.

**Recommended dataset reference:** Mazarico, E., et al. (2011), “Illumination conditions of the lunar polar regions using LOLA topography,” *Icarus*, 211(2), 1066–1081, [doi:10.1016/j.icarus.2010.10.030](https://doi.org/10.1016/j.icarus.2010.10.030). PGDA asks users of the LOLA illumination maps to cite this work. The current GeoTIFF download links are on the [NASA PGDA product page](https://pgda.gsfc.nasa.gov/products/69).

The illumination value is the average fraction of time a surface element receives direct solar illumination over the lunar 18.6-year nodal cycle, expressed here as percent of time illuminated (0–100%). This is a long-term average, not a real-time forecast. Raster CRS, transform, dimensions, resolution, nodata, scale, offset, and source value encoding are copied into the output metadata and printed during processing.

The processor uses the raster's own CRS and its geodetic CRS via `pyproj`; it does not assume an Earth ellipsoid. Pixel-center projected coordinates are kept in the native raster units and are labeled metres in the output as required for the NASA polar stereographic product. Latitude/longitude are converted to a unit sphere vector with Three.js axes `(x, y, z) = (cos(lat)cos(lon), sin(lat), cos(lat)sin(lon))`.

## Install and run

From the repository root:

```bash
python3 -m venv .venv-sunlight
source .venv-sunlight/bin/activate
python -m pip install -r sunlight_module/requirements.txt
python sunlight_module/process_sunlight.py
python sunlight_module/test_sunlight.py
```

The processor writes `sunlight_module/output/sunlight_data.json` and defaults to at most 20,000 points. You can change that limit or paths:

```bash
python sunlight_module/process_sunlight.py --max-points 15000
python sunlight_module/process_sunlight.py --input sunlight_module/raw_data/AVGVISIB_65S_240M_201608.tiff --output sunlight_module/output/sunlight_data.json
```

The sampler spreads points among shadowed (<5%), intermediate, and highly illuminated (>50%) pixels where those classes exist, retaining useful illumination extremes while keeping the JSON small enough for browser rendering.
