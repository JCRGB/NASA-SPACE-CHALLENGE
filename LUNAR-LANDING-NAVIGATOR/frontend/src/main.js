
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ==========================================
// 1. CREATE SCENE
// ==========================================

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050510);

// ==========================================
// 2. CAMERA
// ==========================================

const camera = new THREE.PerspectiveCamera(
    45,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
);

camera.position.set(0, 0, 5);

// ==========================================
// 3. RENDERER
// ==========================================

const renderer = new THREE.WebGLRenderer({
    antialias: true
});

renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

document.body.appendChild(renderer.domElement);

// ==========================================
// 4. 360-DEGREE STARFIELD BACKGROUND
// ==========================================

const textureLoader = new THREE.TextureLoader();

textureLoader.load(
    '/assets/textures/space_panorama.jpg',

    function(texture) {

        texture.colorSpace = THREE.SRGBColorSpace;

        const skyGeometry = new THREE.SphereGeometry(
            100,
            64,
            64
        );

        const skyMaterial = new THREE.MeshBasicMaterial({
            map: texture,
            side: THREE.BackSide,
            depthWrite: false
        });

        const skybox = new THREE.Mesh(
            skyGeometry,
            skyMaterial
        );

        skybox.renderOrder = -1;
        scene.add(skybox);

        console.log('360-degree starfield loaded!');

    },

    undefined,

    function(error) {
        console.error('Skybox loading error:', error);
    }
);

// ==========================================
// 5. ADD EXTRA 3D STARS
// ==========================================

function createStarLayer(count, radius, starSize) {

    const positions = [];
    const colors = [];

    for (let i = 0; i < count; i++) {

        // Random direction around a sphere
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);

        const x = radius * Math.sin(phi) * Math.cos(theta);
        const y = radius * Math.sin(phi) * Math.sin(theta);
        const z = radius * Math.cos(phi);

        positions.push(x, y, z);

        // Slight variation in star colour
        const color = new THREE.Color();

        if (Math.random() > 0.85) {
            color.setHSL(0.58, 0.35, 0.85);
        } else {
            color.setHSL(0.12, 0.05, 0.9 + Math.random() * 0.1);
        }

        colors.push(color.r, color.g, color.b);
    }

    const geometry = new THREE.BufferGeometry();

    geometry.setAttribute(
        'position',
        new THREE.Float32BufferAttribute(positions, 3)
    );

    geometry.setAttribute(
        'color',
        new THREE.Float32BufferAttribute(colors, 3)
    );

    const material = new THREE.PointsMaterial({
        size: starSize,
        vertexColors: true,
        transparent: true,
        opacity: 0.9,
        sizeAttenuation: true,
        depthWrite: false
    });

    const stars = new THREE.Points(geometry, material);

    scene.add(stars);
}

// Three layers at different distances
createStarLayer(700, 18, 0.04);
createStarLayer(450, 35, 0.06);
createStarLayer(300, 60, 0.08);

console.log('Extra 3D star layers created!');

// ==========================================
// 6. REALISTIC MOON LIGHTING
// ==========================================

const ambientLight = new THREE.AmbientLight(
    0xffffff,
    0.15
);

scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(
    0xffffff,
    2.5
);

directionalLight.position.set(5, 2, 5);
scene.add(directionalLight);

// ==========================================
// 7. CAMERA CONTROLS
// ==========================================

const controls = new OrbitControls(
    camera,
    renderer.domElement
);

controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.enableZoom = true;
controls.enablePan = false;

// ==========================================
// 8. LOAD MOON MODEL
// ==========================================

const loader = new GLTFLoader();

loader.load(
    '/assets/models/moon.glb',

    function(gltf) {

        const moon = gltf.scene;

        const box = new THREE.Box3().setFromObject(moon);

        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());

        moon.position.sub(center);

        const maxDimension = Math.max(
            size.x,
            size.y,
            size.z
        );

        const scale = 2.5 / maxDimension;

        moon.scale.setScalar(scale);

        scene.add(moon);

        console.log('Moon loaded successfully!');
    },

    function(progress) {

        if (progress.total > 0) {

            const percentage = Math.round(
                (progress.loaded / progress.total) * 100
            );

            console.log(`Loading Moon: ${percentage}%`);
        }
    },

    function(error) {
        console.error('Moon loading error:', error);
    }
);

// ==========================================
// 9. WINDOW RESIZE
// ==========================================

window.addEventListener('resize', () => {

    camera.aspect = window.innerWidth / window.innerHeight;

    camera.updateProjectionMatrix();

    renderer.setSize(
        window.innerWidth,
        window.innerHeight
    );
});



 // ==========================================
 // 9.5 MISSION CONTROL BUTTONS
 // ==========================================

 const moduleDescriptions = {

    sunlight: {
        title: 'SUNLIGHT',
        description: 'Monitoring lunar illumination conditions.'
    },

    terrain: {
        title: 'TERRAIN',
        description: 'Inspecting lunar elevation and surface slopes.'
    },

    solar: {
        title: 'SOLAR ENERGY',
        description: 'Analysing potential solar energy generation.'
    },

    suitability: {
        title: 'SUITABILITY',
        description: 'Evaluating potential lunar landing locations.'
    }

};

const controlButtons = document.querySelectorAll('.control-btn');

controlButtons.forEach(button => {

    button.addEventListener('click', () => {

        // Remove active state from all buttons
        controlButtons.forEach(btn => {
            btn.classList.remove('active');
        });

        // Activate selected button
        button.classList.add('active');

        // Get selected module
        const mode = button.dataset.mode;
        const selectedModule = moduleDescriptions[mode];

        // Update information panel
        document.getElementById('active-module').textContent =
            selectedModule.title;

        document.getElementById('module-description').textContent =
            selectedModule.description;

        console.log('Active module:', selectedModule.title);

    });

});


// ==========================================
// 10. ANIMATION LOOP
// ==========================================

function animate() {

    requestAnimationFrame(animate);

    controls.update();

    renderer.render(scene, camera);
}

animate();
