import json

d = json.load(open("../data/processed/solar_energy.json"))
print("top-level type: {}".format(type(d).__name__))
if isinstance(d, dict):
    print("keys: {}".format(list(d.keys())[:15]))
    pts = next(v for v in d.values() if isinstance(v, list))
else:
    pts = d

print("points: {}".format(len(pts)))
print("first point: {}".format(pts[0]))

vals = [p.get("value") if isinstance(p, dict) else p for p in pts]
good = [v for v in vals if isinstance(v, (int, float)) and v == v]
print("missing/NaN: {}".format(len(vals) - len(good)))
print("exact zeros: {} ({:.1f}%)".format(good.count(0), 100.0 * good.count(0) / len(good)))
print("min/max: {} / {}".format(min(good), max(good)))
print("values above 3.5: {}".format(len([v for v in good if v > 3.5])))
