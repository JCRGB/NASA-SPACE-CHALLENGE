// Paint processed South Pole samples onto one sphere aligned to the Moon mesh.
import * as THREE from 'three';
import suitabilityMode from './suitability.js';
import sunlightMode from './sunlight.js';
import terrainMode from './terrain.js';
import solarMode from './solarEnergy.js';

const MODES = Object.fromEntries([suitabilityMode, sunlightMode, terrainMode, solarMode]
    .map(mode => [mode.key, mode]));
const MODE_COLORS = Object.fromEntries(Object.values(MODES).map(mode =>
    [mode.key, mode.stops.map(hex => new THREE.Color(hex))]));
const CANVAS_SIZE = 1024;
const OVERLAY_NAME = 'Lunar processed heatmap surface';
const SURFACE_SCALE = 1.003;
const BRUSH_RADIUS = 12;
const EDGE_FADE_START = 490;

let activeMode = document.querySelector('.control-btn.active')?.dataset.mode || 'sunlight';
let datasetsPromise;
let attachPromise;
let sceneRef;
let overlay;
let texture;
let canvasContext;
let legend;
let maxColatitudeRad;

async function loadDataset(mode) {
    const response = await fetch(mode.dataUrl);
    if (!response.ok) throw new Error(`${mode.key} dataset request failed (${response.status})`);
    const dataset = await response.json();
    if (!Array.isArray(dataset.locations) || dataset.locations.length === 0) {
        throw new Error(`${mode.key} dataset must contain a non-empty locations array`);
    }
    const points = dataset.locations.filter(point =>
        Number.isFinite(point.lat) && Number.isFinite(point.lon) && Number.isFinite(mode.value(point)));
    if (!points.length) throw new Error(`${mode.key} dataset has no valid map locations`);
    return points;
}

function loadDatasets() {
    if (!datasetsPromise) {
        datasetsPromise = Promise.all(Object.values(MODES).map(async mode =>
            [mode.key, await loadDataset(mode)]))
            .then(entries => Object.fromEntries(entries));
    }
    return datasetsPromise;
}

function hasUvMesh(object) {
    let found = false;
    object?.traverse?.(child => {
        if (child.isMesh && child.geometry?.attributes?.uv) found = true;
    });
    return found;
}

function isMoonGroup(object) {
    return Boolean(object?.isGroup && hasUvMesh(object));
}

function findMoonRoot(pivot) {
    // main.js wraps the loaded glTF in a pivot and adds pole markers to that pivot.
    // The direct child containing the UV meshes is the actual lunar model root.
    return pivot.children.find(child => child !== pivot && child.isGroup && hasUvMesh(child)) || pivot;
}

function measureWorldSphere(moonRoot) {
    moonRoot.updateWorldMatrix(true, true);
    const bounds = new THREE.Box3().setFromObject(moonRoot);
    if (bounds.isEmpty()) throw new Error('Could not measure the loaded Moon mesh bounds');

    const sphere = new THREE.Sphere();
    bounds.getBoundingSphere(sphere);
    // Box3.getBoundingSphere returns the sphere around the AABB corners, which
    // overestimates a globe's radius. Keep its exact world center, then measure
    // the farthest actual Moon vertex from that center for the surface radius.
    let radiusSquared = 0;
    const vertex = new THREE.Vector3();
    moonRoot.traverse(mesh => {
        const positions = mesh.isMesh ? mesh.geometry?.attributes?.position : null;
        if (!positions) return;
        for (let i = 0; i < positions.count; i++) {
            vertex.fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld);
            radiusSquared = Math.max(radiusSquared, vertex.distanceToSquared(sphere.center));
        }
    });
    sphere.radius = Math.sqrt(radiusSquared);
    if (!Number.isFinite(sphere.radius) || sphere.radius <= 0) {
        throw new Error('Could not determine the Moon mesh world radius');
    }
    return sphere;
}

function uvDirectionFrame(moonRoot, center) {
    moonRoot.updateWorldMatrix(true, true);
    const meshes = [];
    let minV = Infinity;
    let maxV = -Infinity;
    moonRoot.traverse(mesh => {
        if (!mesh.isMesh || !mesh.geometry?.attributes?.uv || !mesh.geometry?.attributes?.position) return;
        const uv = mesh.geometry.attributes.uv;
        meshes.push({ uv, positions: mesh.geometry.attributes.position, matrixWorld: mesh.matrixWorld.clone() });
        for (let i = 0; i < uv.count; i++) {
            minV = Math.min(minV, uv.getY(i));
            maxV = Math.max(maxV, uv.getY(i));
        }
    });
    if (!meshes.length) throw new Error('Moon model has no UV coordinates for polar alignment');

    const worldVertex = (item, index) => new THREE.Vector3()
        .fromBufferAttribute(item.positions, index).applyMatrix4(item.matrixWorld);
    function poleAt(targetV) {
        const position = new THREE.Vector3();
        let count = 0;
        for (const item of meshes) {
            for (let i = 0; i < item.uv.count; i++) {
                if (Math.abs(item.uv.getY(i) - targetV) < 0.002) {
                    position.add(worldVertex(item, i));
                    count++;
                }
            }
        }
        return count ? position.divideScalar(count) : null;
    }
    function vertexAt(targetU, targetV) {
        let nearest = Infinity;
        let result = null;
        for (const item of meshes) {
            for (let i = 0; i < item.uv.count; i++) {
                let du = Math.abs(item.uv.getX(i) - targetU);
                du = Math.min(du, 1 - du);
                const dv = item.uv.getY(i) - targetV;
                const distance = du * du + dv * dv;
                if (distance < nearest) {
                    nearest = distance;
                    result = worldVertex(item, i);
                }
            }
        }
        return result;
    }

    const north = poleAt(minV);
    const south = poleAt(maxV);
    if (!north || !south) throw new Error('Could not find the Moon mesh north/south UV poles');
    const northAxis = new THREE.Vector3().subVectors(north, south).normalize();
    const equatorV = (minV + maxV) / 2;
    const flatten = point => {
        const direction = point.sub(center);
        return direction.addScaledVector(northAxis, -direction.dot(northAxis)).normalize();
    };
    const longitudeZero = flatten(vertexAt(0.5, equatorV));
    const longitudeQuarter = flatten(vertexAt(0.75, equatorV));
    let eastAxis = new THREE.Vector3().crossVectors(northAxis, longitudeZero).normalize();
    if (eastAxis.dot(longitudeQuarter) < 0) eastAxis.negate();

    // SphereGeometry's local u=0.5 meridian points along +X, north along +Y,
    // and u=0.75 points along -Z. Rotate that UV frame onto the real Moon mesh.
    // The polar cap geometry uses local +X for longitude zero, local +Z for
    // increasing longitude, and local -Y toward the South Pole.
    const basis = new THREE.Matrix4().makeBasis(longitudeZero, northAxis.clone().negate(), eastAxis);
    return new THREE.Quaternion().setFromRotationMatrix(basis);
}

function polarCapExtent(points) {
    const maxSampleColatitude = Math.max(...points.map(point =>
        (90 - Math.abs(point.lat)) * Math.PI / 180));
    // Leave a small margin around the outermost sample so the heatmap can fade
    // cleanly before the cap edge.
    return maxSampleColatitude + Math.PI / 180;
}

function createPolarCapGeometry(radius, colatitudeRad) {
    const geometry = new THREE.SphereGeometry(
        radius,
        256,
        64,
        0,
        Math.PI * 2,
        0,
        colatitudeRad,
    );
    const positions = geometry.getAttribute('position');
    const uvs = geometry.getAttribute('uv');
    const maxHorizontalR = radius * Math.sin(colatitudeRad);
    for (let i = 0; i < positions.count; i++) {
        const x = positions.getX(i);
        const z = positions.getZ(i);
        uvs.setXY(i,
            0.5 + x / (2 * maxHorizontalR),
            0.5 + z / (2 * maxHorizontalR));
    }
    uvs.needsUpdate = true;
    return geometry;
}

function colorAt(mode, value) {
    const t = THREE.MathUtils.clamp((value - mode.min) / (mode.max - mode.min), 0, 1);
    const stops = MODE_COLORS[mode.key];
    const scaled = t * (stops.length - 1);
    const lower = Math.min(Math.floor(scaled), stops.length - 2);
    return new THREE.Color().copy(stops[lower]).lerp(stops[lower + 1], scaled - lower).getStyle();
}

function fixed(value, digits = 1) {
    return Number(value).toFixed(digits);
}

function coordinate(point) {
    return `${fixed(point.lat, 3)}°, ${fixed(point.lon, 3)}°`;
}

function summaryRows(mode, points) {
    const values = points.map(point => mode.value(point));
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const peak = points[values.indexOf(maximum)];

    if (mode.key === 'suitability') {
        const optimalCount = points.filter(point => mode.value(point) >= 75 && point.risk_rating === 'Optimal').length;
        return [
            ['Optimal Zones', `${optimalCount.toLocaleString()} / ${points.length.toLocaleString()} (${fixed(optimalCount / points.length * 100)}%)`],
            ['Peak Site Score', `${fixed(maximum)} / 100 · ${coordinate(peak)}`],
        ];
    }
    if (mode.key === 'sunlight') {
        const shadowedCount = points.filter(point => mode.value(point) < 5).length;
        return [
            ['Mean Illumination', `${fixed(mean)}%`],
            ['Peak Sunlight Ridge', `${fixed(maximum)}% · ${coordinate(peak)}`],
            ['Permanently Shadowed (<5%)', `${shadowedCount.toLocaleString()} / ${points.length.toLocaleString()} (${fixed(shadowedCount / points.length * 100)}%)`],
        ];
    }
    if (mode.key === 'terrain') {
        const safeCount = points.filter(point => mode.value(point) < 15).length;
        const elevations = points.map(point => point.elevation_m).filter(Number.isFinite);
        const elevationRange = elevations.length
            ? `${fixed(Math.min(...elevations))}–${fixed(Math.max(...elevations))} m`
            : 'Elevation unavailable';
        return [
            ['Safe Flat Terrain (<15°)', `${fixed(safeCount / points.length * 100)}% of surveyed region`],
            ['Slope Range · Elevation Range', `${fixed(minimum)}–${fixed(maximum)}° · ${elevationRange}`],
        ];
    }
    return [
        ['Mean Solar Yield', `${fixed(mean, 2)} kWh/m²/day`],
        ['Peak Power Site', `${fixed(maximum, 2)} kWh/m²/day · ${coordinate(peak)}`],
    ];
}

function renderSummary(mode, points) {
    const panel = document.getElementById('mode-summary');
    if (!panel || !points.length) return;
    const rows = summaryRows(mode, points);
    panel.replaceChildren(...rows.map(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'row';
        const heading = document.createElement('span');
        heading.textContent = label;
        const result = document.createElement('b');
        result.textContent = value;
        row.append(heading, result);
        return row;
    }));
}

function cssRgb(colorStyle) {
    const match = colorStyle.match(/\d+(?:\.\d+)?/g);
    return match ? match.slice(0, 3).map(value => Math.round(Number(value))).join(',') : '255,255,255';
}

function drawSpot(x, y, rgb) {
    const gradient = canvasContext.createRadialGradient(x, y, 0, x, y, BRUSH_RADIUS);
    // Keep samples translucent so the Moon's own texture stays visible under
    // overlapping values and the heatmap reads as a surface overlay.
    gradient.addColorStop(0, `rgba(${rgb},0.68)`);
    gradient.addColorStop(0.62, `rgba(${rgb},0.36)`);
    gradient.addColorStop(1, `rgba(${rgb},0)`);
    canvasContext.fillStyle = gradient;
    canvasContext.beginPath();
    canvasContext.arc(x, y, BRUSH_RADIUS, 0, Math.PI * 2);
    canvasContext.fill();
}

function paintDataset(mode, points) {
    canvasContext.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    let observedMin = Infinity;
    let observedMax = -Infinity;
    const maxSinColatitude = Math.sin(maxColatitudeRad);

    for (const point of points) {
        const value = mode.value(point);
        observedMin = Math.min(observedMin, value);
        observedMax = Math.max(observedMax, value);
        const colatitudeRad = (90 - Math.abs(point.lat)) * Math.PI / 180;
        const lonRad = point.lon * Math.PI / 180;
        const px = CANVAS_SIZE / 2
            + (Math.sin(colatitudeRad) * Math.cos(lonRad) / maxSinColatitude) * (CANVAS_SIZE / 2);
        const py = CANVAS_SIZE / 2
            + (Math.sin(colatitudeRad) * Math.sin(lonRad) / maxSinColatitude) * (CANVAS_SIZE / 2);
        const rgb = cssRgb(colorAt(mode, value));
        drawSpot(px, py, rgb);
    }

    const edgeFade = canvasContext.createRadialGradient(
        CANVAS_SIZE / 2, CANVAS_SIZE / 2, 0,
        CANVAS_SIZE / 2, CANVAS_SIZE / 2, CANVAS_SIZE / 2,
    );
    edgeFade.addColorStop(EDGE_FADE_START / (CANVAS_SIZE / 2), 'rgba(0,0,0,1)');
    edgeFade.addColorStop(1, 'rgba(0,0,0,0)');
    canvasContext.globalCompositeOperation = 'destination-in';
    canvasContext.fillStyle = edgeFade;
    canvasContext.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    canvasContext.globalCompositeOperation = 'source-over';

    texture.needsUpdate = true;
    updateLegend(mode, observedMin, observedMax, points.length);
    console.info(`Heatmap ${mode.key}: painted ${points.length.toLocaleString()} JSON locations (${observedMin.toFixed(3)}–${observedMax.toFixed(3)} ${mode.unit}).`);
}

function createCanvasTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = CANVAS_SIZE;
    canvas.height = CANVAS_SIZE;
    canvasContext = canvas.getContext('2d', { alpha: true });
    if (!canvasContext) throw new Error('Could not create 2D canvas context for the lunar heatmap');
    texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    // Keep texture row zero aligned with the planar UVs written to the cap.
    texture.flipY = false;
    texture.generateMipmaps = true;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.needsUpdate = true;
}

function updateLegend(mode, observedMin, observedMax, pointCount) {
    if (!legend) {
        legend = document.createElement('aside');
        legend.className = 'heatmap-legend';
        legend.setAttribute('aria-live', 'polite');
        legend.innerHTML = '<strong class="title"></strong><div class="gradient"></div><div class="labels"><span></span><span></span></div><small></small>';
        document.body.appendChild(legend);
    }
    legend.querySelector('.title').textContent = mode.title;
    legend.querySelector('.gradient').style.background = `linear-gradient(90deg, ${mode.stops.join(', ')})`;
    const labels = legend.querySelectorAll('.labels span');
    labels[0].textContent = mode.labels[0];
    labels[1].textContent = mode.labels[1];
    legend.querySelector('small').textContent = `${mode.source} · ${pointCount.toLocaleString()} locations · observed ${observedMin.toFixed(2)}–${observedMax.toFixed(2)} ${mode.unit}`;
    legend.hidden = false;
}

function removeOldOverlay(scene) {
    for (const child of [...scene.children]) {
        if (child.name === OVERLAY_NAME) scene.remove(child);
    }
}

async function attachHeatmap(scene) {
    sceneRef = scene;
    if (overlay) return;
    if (attachPromise) return attachPromise;
    attachPromise = (async () => {
        const pivot = scene.children.find(isMoonGroup);
        if (!pivot) return;
        const moonRoot = findMoonRoot(pivot);
        const sphere = measureWorldSphere(moonRoot);
        const orientation = uvDirectionFrame(moonRoot, sphere.center);
        const datasets = await loadDatasets();

        maxColatitudeRad = polarCapExtent(datasets[activeMode]);
        createCanvasTexture();
        removeOldOverlay(scene);
        const surfaceRadius = sphere.radius * SURFACE_SCALE;
        const geometry = createPolarCapGeometry(surfaceRadius, maxColatitudeRad);
        // Draw the mapped data on a transparent shell with depth testing off.
        // This lets the South Pole remain visible through the globe as it
        // rotates onto the far hemisphere, while alphaTest preserves clear
        // canvas pixels so they do not tint the rest of the Moon.
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            opacity: 1,
            alphaTest: 0.015,
            depthTest: false,
            depthWrite: false,
            side: THREE.DoubleSide,
            toneMapped: false,
        });
        overlay = new THREE.Mesh(geometry, material);
        overlay.name = OVERLAY_NAME;
        overlay.position.copy(sphere.center);
        overlay.quaternion.copy(orientation);
        overlay.visible = true;
        overlay.renderOrder = 999;
        scene.add(overlay);
        paintDataset(MODES[activeMode], datasets[activeMode]);
        renderSummary(MODES[activeMode], datasets[activeMode]);
        console.info(`Moon world sphere radius: ${sphere.radius.toFixed(6)}; heatmap cap radius: ${surfaceRadius.toFixed(6)} (${SURFACE_SCALE.toFixed(3)}×); cap colatitude: ${(maxColatitudeRad * 180 / Math.PI).toFixed(3)}°.`);
    })().finally(() => { attachPromise = null; });
    return attachPromise;
}

function scheduleAttach(scene) {
    void attachHeatmap(scene).catch(error => console.error('Moon surface heatmap could not be loaded:', error));
}

const originalAdd = THREE.Object3D.prototype.add;
THREE.Object3D.prototype.add = function addWithSurfaceHeatmap(...objects) {
    const result = originalAdd.apply(this, objects);
    if (this.isScene && objects.some(isMoonGroup)) scheduleAttach(this);
    return result;
};

document.querySelectorAll('.control-btn').forEach(button => {
    button.addEventListener('click', () => {
        activeMode = button.dataset.mode;
        loadDatasets().then(datasets => renderSummary(MODES[activeMode], datasets[activeMode]))
            .catch(error => console.error('Could not calculate lunar dataset summary:', error));
        if (!overlay) {
            if (sceneRef) scheduleAttach(sceneRef);
            return;
        }
        loadDatasets().then(datasets => paintDataset(MODES[activeMode], datasets[activeMode]))
            .catch(error => console.error('Could not switch lunar heatmap dataset:', error));
    });
});

