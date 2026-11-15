// Sun / shadow solver for the south-polar heatmap.
// Pure maths (no three.js): given the terrain elevations and a Sun position,
// work out which map points are in sunlight and which are in shadow.
//
// Geometry: everything is done in 3D around the Moon's centre, with +Z toward
// the north pole and longitude measured from +X. The terrain grid is laid out
// in the same south-polar stereographic plane the data was exported in
// (x = rho * sin(lon), y = rho * cos(lon)), so a point's lat/lon from the JSON
// lands in the right cell.

export const MOON_RADIUS_KM = 1737.4;
const R = MOON_RADIUS_KM;
const D2R = Math.PI / 180;
const BIAS_KM = 0.004;   // 4 m of tolerance so sloped ground does not shadow itself

// Unit vector (z = north) -> south-polar stereographic plane, in km
function planeX(ux, uy, uz) { return (2 * R * uy) / (1 - uz); }
function planeY(ux, uy, uz) { return (2 * R * ux) / (1 - uz); }

function unitVector(latDeg, lonDeg) {
    const lat = latDeg * D2R;
    const lon = lonDeg * D2R;
    const c = Math.cos(lat);
    return [c * Math.cos(lon), c * Math.sin(lon), Math.sin(lat)];
}

/**
 * Build a regular height grid from points that carry lat, lon and elevation_m.
 * Returns null when there is not enough elevation data to cast shadows.
 */
export function buildTerrain(points) {
    const usable = points.filter(p =>
        Number.isFinite(p.lat) && Number.isFinite(p.lon) && Number.isFinite(p.elevation_m));
    if (usable.length < 400) return null;

    const xs = new Float64Array(usable.length);
    const ys = new Float64Array(usable.length);
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    usable.forEach((p, i) => {
        const [ux, uy, uz] = unitVector(p.lat, p.lon);
        xs[i] = planeX(ux, uy, uz);
        ys[i] = planeY(ux, uy, uz);
        minX = Math.min(minX, xs[i]); maxX = Math.max(maxX, xs[i]);
        minY = Math.min(minY, ys[i]); maxY = Math.max(maxY, ys[i]);
    });

    const G = Math.min(512, Math.max(32, Math.round(Math.sqrt(usable.length))));
    const cell = Math.max(maxX - minX, maxY - minY) / (G - 1);
    const sums = new Float64Array(G * G);
    const counts = new Uint16Array(G * G);
    usable.forEach((p, k) => {
        const i = Math.round((xs[k] - minX) / cell);
        const j = Math.round((ys[k] - minY) / cell);
        if (i < 0 || j < 0 || i >= G || j >= G) return;
        sums[j * G + i] += p.elevation_m / 1000;
        counts[j * G + i]++;
    });

    const heights = new Float32Array(G * G).fill(NaN);
    for (let n = 0; n < G * G; n++) if (counts[n]) heights[n] = sums[n] / counts[n];

    // Fill small holes from their neighbours (a few passes is plenty)
    for (let pass = 0; pass < 4; pass++) {
        const next = heights.slice();
        for (let j = 0; j < G; j++) {
            for (let i = 0; i < G; i++) {
                if (!Number.isNaN(heights[j * G + i])) continue;
                let sum = 0, n = 0;
                for (let dj = -1; dj <= 1; dj++) {
                    for (let di = -1; di <= 1; di++) {
                        const ii = i + di, jj = j + dj;
                        if (ii < 0 || jj < 0 || ii >= G || jj >= G) continue;
                        const v = heights[jj * G + ii];
                        if (!Number.isNaN(v)) { sum += v; n++; }
                    }
                }
                if (n) next[j * G + i] = sum / n;
            }
        }
        heights.set(next);
    }

    let hMax = -Infinity;
    for (let n = 0; n < G * G; n++) if (heights[n] > hMax) hMax = heights[n];
    return { G, cell, minX, minY, heights, hMax };
}

// Bilinear height lookup in km; NaN outside the surveyed square
function heightAt(t, x, y) {
    const fx = (x - t.minX) / t.cell;
    const fy = (y - t.minY) / t.cell;
    const max = t.G - 1;
    if (fx < 0 || fy < 0 || fx > max || fy > max) return NaN;
    const i = Math.min(Math.floor(fx), t.G - 2);
    const j = Math.min(Math.floor(fy), t.G - 2);
    const tx = fx - i, ty = fy - j, h = t.heights, G = t.G;
    const a = h[j * G + i], b = h[j * G + i + 1];
    const c = h[(j + 1) * G + i], d = h[(j + 1) * G + i + 1];
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
}

/**
 * For every point, 1 = in sunlight, 0 = in shadow.
 * sunLonDeg / sunLatDeg is the sub-solar point (where the Sun is straight overhead).
 * At the south pole the Sun's elevation is -sunLatDeg.
 */
export function computeLit(terrain, points, sunLonDeg, sunLatDeg) {
    const lit = new Uint8Array(points.length);
    const [sx, sy, sz] = unitVector(sunLatDeg, sunLonDeg);
    const step = terrain.cell;
    const maxDistance = terrain.cell * terrain.G * 2;

    for (let n = 0; n < points.length; n++) {
        const p = points[n];
        const [ux, uy, uz] = unitVector(p.lat, p.lon);

        // Sun below this point's own horizon
        if (ux * sx + uy * sy + uz * sz <= 0) continue;

        let h0 = Number.isFinite(p.elevation_m) ? p.elevation_m / 1000
            : heightAt(terrain, planeX(ux, uy, uz), planeY(ux, uy, uz));
        if (!Number.isFinite(h0)) h0 = 0;

        const r0 = R + h0;
        const px = ux * r0, py = uy * r0, pz = uz * r0;
        let blocked = false;

        for (let t = step; t <= maxDistance; t += step) {
            const qx = px + sx * t, qy = py + sy * t, qz = pz + sz * t;
            const qr = Math.sqrt(qx * qx + qy * qy + qz * qz);
            const rayHeight = qr - R;
            if (rayHeight > terrain.hMax) break;                  // above every peak
            const ground = heightAt(terrain,
                planeX(qx / qr, qy / qr, qz / qr),
                planeY(qx / qr, qy / qr, qz / qr));
            if (Number.isNaN(ground)) break;                      // left the surveyed square
            if (ground > rayHeight + BIAS_KM) { blocked = true; break; }
        }
        lit[n] = blocked ? 0 : 1;
    }
    return lit;
}