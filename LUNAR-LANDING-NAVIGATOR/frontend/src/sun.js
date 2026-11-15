// Sun position for the lunar viewer: a "mission day" slider, a play button,
// and a directional light placed where the Sun really is.
//
// The Moon spins once every ~29.53 days relative to the Sun, so the Sun's
// longitude sweeps all the way round in that time. Its height near the poles
// stays tiny (the Moon's axis is tilted only 1.54 degrees), which is why the
// poles sit on the day/night line and shadows there are so long.
//
// Other files learn about changes through:
//   window.lunarSun  = { live, day, lon, lat, elevation }
//   'sun-change' event on window (fired on every change)

import * as THREE from 'three';

// ---- Settings you can tweak ----------------------------------------------
const SYNODIC_DAYS = 29.530589;        // one lunar day (new moon to new moon)
const SUN_ELEVATION_AT_POLE_DEG = 1.0; // 0 to 1.54. Bigger = shorter shadows
const NEW_MOON_SUBSOLAR_LON = 180;     // at day 0 the Sun is over the far side
const PLAY_DAYS_PER_SECOND = 2.5;      // play speed (about 12 s per lunar day)
const LIGHT_DISTANCE = 20;
// ---------------------------------------------------------------------------

const PHASES = ['NEW MOON', 'WAXING CRESCENT', 'FIRST QUARTER', 'WAXING GIBBOUS',
    'FULL MOON', 'WANING GIBBOUS', 'LAST QUARTER', 'WANING CRESCENT'];

const STYLE = `
#sun-control {
  position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
  width: min(400px, 90vw); z-index: 30; box-sizing: border-box;
  padding: 12px 16px 14px; color: #cfeaf5;
  background: rgba(5, 12, 28, 0.86); border: 1px solid rgba(77, 232, 255, 0.35);
  border-radius: 10px; backdrop-filter: blur(6px);
  font-family: 'Share Tech Mono', monospace; user-select: none;
}
#sun-control .sc-head { display: flex; justify-content: space-between; align-items: baseline; }
#sun-control .sc-title { font-family: Orbitron, 'Share Tech Mono', monospace; font-size: 11px;
  letter-spacing: 0.22em; color: #4de8ff; }
#sun-control .sc-mode { font-size: 10px; letter-spacing: 0.12em; color: #7fa6b8; }
#sun-control .sc-mode.live { color: #ffd338; }
#sun-control .sc-readout { display: flex; justify-content: space-between; margin: 8px 0 2px;
  font-size: 13px; }
#sun-control .sc-day { font-family: Orbitron, 'Share Tech Mono', monospace; color: #fff; }
#sun-control .sc-sub { font-size: 11px; color: #7fa6b8; margin-bottom: 8px; }
#sun-control input[type=range] { width: 100%; margin: 6px 0; accent-color: #4de8ff; cursor: pointer; }
#sun-control .sc-buttons { display: flex; gap: 8px; }
#sun-control button { flex: 1; padding: 6px 0; cursor: pointer; font-size: 11px;
  letter-spacing: 0.14em; color: #cfeaf5; background: rgba(77, 232, 255, 0.08);
  border: 1px solid rgba(77, 232, 255, 0.35); border-radius: 6px;
  font-family: Orbitron, 'Share Tech Mono', monospace; }
#sun-control button:hover { background: rgba(77, 232, 255, 0.2); }
#sun-control button.on { background: rgba(77, 232, 255, 0.28); color: #fff; }
#sun-control .sc-note { font-size: 10px; color: #5f8294; margin-top: 8px; line-height: 1.4; }
`;

const wrap180 = deg => ((((deg + 180) % 360) + 360) % 360) - 180;

export function initSun({ light, lonA, lonB, northAxis, lonSign = 1, centerLon = 0 }) {
    // Share the Moon's real axes with heatmap.js so the overlay is placed with
    // exactly the same north/south flip and longitude convention as the
    // landmarks and the Sun light.
    window.lunarFrame = {
        northAxis: northAxis.clone(), lonA: lonA.clone(), lonB: lonB.clone(), lonSign, centerLon,
    };

    if (document.getElementById('sun-control')) return;

    const style = document.createElement('style');
    style.textContent = STYLE;
    document.head.appendChild(style);

    const state = window.lunarSun = {
        live: false,
        day: 0,
        lon: wrap180(NEW_MOON_SUBSOLAR_LON),
        lat: -SUN_ELEVATION_AT_POLE_DEG,       // Sun's elevation at the south pole = -lat
        elevation: SUN_ELEVATION_AT_POLE_DEG,
    };

    // ---- 3D light: same lat/lon -> direction maths the landmarks use ------
    const lightDir = new THREE.Vector3();
    function applyLight() {
        const lat = THREE.MathUtils.degToRad(state.lat);
        const lon = THREE.MathUtils.degToRad((state.lon - centerLon) * lonSign);
        lightDir.set(0, 0, 0)
            .addScaledVector(lonA, Math.cos(lat) * Math.cos(lon))
            .addScaledVector(lonB, Math.cos(lat) * Math.sin(lon))
            .addScaledVector(northAxis, Math.sin(lat))
            .normalize();
        light.position.copy(lightDir).multiplyScalar(LIGHT_DISTANCE);
    }

    // ---- UI ----------------------------------------------------------------
    const panel = document.createElement('div');
    panel.id = 'sun-control';
    panel.innerHTML = `
      <div class="sc-head"><span class="sc-title">SOLAR POSITION</span><span class="sc-mode"></span></div>
      <div class="sc-readout"><span class="sc-day"></span><span class="sc-phase"></span></div>
      <div class="sc-sub"></div>
      <input type="range" min="0" max="${SYNODIC_DAYS}" step="0.01" value="0" aria-label="Mission day">
      <div class="sc-buttons"><button class="sc-play">PLAY</button><button class="sc-avg">AVERAGE</button></div>
      <div class="sc-note">Drag to move the Sun. Sunlight and Solar Energy show live shadows for that day. AVERAGE returns to NASA's long-term data.</div>`;
    document.body.appendChild(panel);

    const slider = panel.querySelector('input');
    const playBtn = panel.querySelector('.sc-play');
    const avgBtn = panel.querySelector('.sc-avg');
    const modeEl = panel.querySelector('.sc-mode');

    function updateUi() {
        const lon = state.lon;
        panel.querySelector('.sc-day').textContent =
            `DAY ${state.day.toFixed(1)} / ${SYNODIC_DAYS.toFixed(1)}`;
        const phaseIndex = Math.floor((state.day / SYNODIC_DAYS) * 8 + 0.5) % 8;
        panel.querySelector('.sc-phase').textContent = PHASES[phaseIndex];
        panel.querySelector('.sc-sub').textContent =
            `Sun over ${Math.abs(lon).toFixed(1)}°${lon >= 0 ? 'E' : 'W'} · ${state.elevation.toFixed(1)}° above the pole's horizon`;
        modeEl.textContent = state.live ? 'LIVE SHADOWS' : 'LONG-TERM AVERAGE';
        modeEl.classList.toggle('live', state.live);
        avgBtn.classList.toggle('on', !state.live);
        playBtn.classList.toggle('on', playing);
        playBtn.textContent = playing ? 'PAUSE' : 'PLAY';
        if (document.activeElement !== slider) slider.value = state.day;
    }

    function broadcast() {
        window.dispatchEvent(new CustomEvent('sun-change', { detail: { ...state } }));
    }

    function setDay(day, live) {
        state.day = ((day % SYNODIC_DAYS) + SYNODIC_DAYS) % SYNODIC_DAYS;
        state.lon = wrap180(NEW_MOON_SUBSOLAR_LON - 360 * state.day / SYNODIC_DAYS);
        if (live !== undefined) state.live = live;
        applyLight();
        updateUi();
        broadcast();
    }

    // ---- Play loop -----------------------------------------------------------
    let playing = false;
    let last = 0;
    function tick(now) {
        if (!playing) return;
        const dt = Math.min((now - last) / 1000, 0.1);
        last = now;
        setDay(state.day + dt * PLAY_DAYS_PER_SECOND, true);
        requestAnimationFrame(tick);
    }

    slider.addEventListener('input', () => setDay(parseFloat(slider.value), true));
    playBtn.addEventListener('click', () => {
        playing = !playing;
        if (playing) {
            state.live = true;
            last = performance.now();
            requestAnimationFrame(tick);
        }
        setDay(state.day, state.live);
    });
    avgBtn.addEventListener('click', () => {
        playing = false;
        setDay(state.day, false);
    });

    setDay(0, false);   // lights the Moon and shows the panel; heatmap stays on the average
}