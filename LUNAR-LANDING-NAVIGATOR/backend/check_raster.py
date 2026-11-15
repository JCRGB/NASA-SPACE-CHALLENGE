import rasterio

path = "backend/data_storage/nasa_lunar_illumination_85s_60m.tif"

with rasterio.open(path) as src:
    print("dtype:", src.dtypes, "| nodata:", src.nodata)
    print("scales:", src.scales, "| offsets:", src.offsets)
    print("size:", src.width, "x", src.height)

    a = src.read(1, masked=True)
    print("min / max / mean:", a.min(), a.max(), a.mean())
    print("fraction exactly 0:", (a == 0).sum() / a.count())
    print("fraction masked (nodata):", a.mask.sum() / a.size)