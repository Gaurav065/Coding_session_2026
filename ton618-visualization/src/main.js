import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { gsap } from 'gsap';

import starfieldVert from './shaders/starfield.vert?raw';
import starfieldFrag from './shaders/starfield.frag?raw';
import blackholeVert from './shaders/blackhole.vert?raw';
import blackholeFrag from './shaders/blackhole.frag?raw';

const TON618_MASS = 66e9;
const RS_SUN = 2953;
const TON618_RS = TON618_MASS * RS_SUN;
const AU = 1.496e11;
const LY = 9.461e15;

let renderer, scene, camera, composer, bloomPass;
let starfieldMesh, blackholeMesh;
let starfieldMaterial, blackholeMaterial;

let time = 0;
let timeScale = 1.0;
let isPaused = false;
let cameraDistance = 15;
let targetDistance = 15;
let exposure = 1.0;
let highQuality = true;
let showInfo = true;

let spherical = new THREE.Spherical(15, Math.PI * 0.5, 0);
let targetSpherical = new THREE.Spherical(15, Math.PI * 0.5, 0);
let autoRotate = true;
let autoRotateSpeed = 0.00008;

let fps = 0;
let frameCount = 0;
let lastFpsTime = performance.now();

const canvasContainer = document.getElementById('canvas-container');
const fpsEl = document.getElementById('fps');
const camDistEl = document.getElementById('cam-dist');
const timeScaleEl = document.getElementById('time-scale');
const timeScaleValEl = document.getElementById('time-scale-val');
const camDistValEl = document.getElementById('cam-dist-val');
const exposureValEl = document.getElementById('exposure-val');
const qualityBadge = document.getElementById('quality-badge');
const btnPause = document.getElementById('btn-pause');
const btnReset = document.getElementById('btn-reset');
const btnInfo = document.getElementById('btn-info');
const btnFullscreen = document.getElementById('btn-fullscreen');
const btnQuality = document.getElementById('btn-quality');
const timeSlider = document.getElementById('time-scale-slider');
const distSlider = document.getElementById('cam-dist-slider');
const expSlider = document.getElementById('exposure-slider');

function initRenderer() {
    renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'low-power', precision: 'mediump' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.0));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    canvasContainer.appendChild(renderer.domElement);
}

function initScene() {
    scene = new THREE.Scene();
    
    camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1e6);
    
    createStarfield();
    createBlackHole();
    
    updateCameraPosition();
    
    setupPostProcessing();
}

function createStarfield() {
    starfieldMaterial = new THREE.ShaderMaterial({
        vertexShader: starfieldVert,
        fragmentShader: starfieldFrag,
        uniforms: {
            uTime: { value: 0 },
            uExposure: { value: 1.0 },
            uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) }
        },
        side: THREE.BackSide,
        depthWrite: false
    });
    
    const geo = new THREE.SphereGeometry(5000, 64, 64);
    starfieldMesh = new THREE.Mesh(geo, starfieldMaterial);
    starfieldMesh.renderOrder = 0;
    scene.add(starfieldMesh);
}

function createBlackHole() {
    blackholeMaterial = new THREE.ShaderMaterial({
        vertexShader: blackholeVert,
        fragmentShader: blackholeFrag,
        uniforms: {
            uTime: { value: 0 },
            uExposure: { value: 1.0 },
            uCameraPos: { value: new THREE.Vector3() },
            uRs: { value: 1.0 },
            uSpin: { value: 0.9 },
            uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
            uHighQuality: { value: true }
        },
        transparent: true,
        depthWrite: true,
        side: THREE.BackSide
    });
    
    const geo = new THREE.SphereGeometry(200, 128, 128);
    blackholeMesh = new THREE.Mesh(geo, blackholeMaterial);
    blackholeMesh.renderOrder = 1;
    scene.add(blackholeMesh);
}

function setupPostProcessing() {
    const renderScene = new RenderPass(scene, camera);
    
    bloomPass = new UnrealBloomPass(
        new THREE.Vector2(window.innerWidth / 4, window.innerHeight / 4),
        1.5, 0.4, 0.1
    );
    bloomPass.threshold = 0.2;
    bloomPass.strength = 1.5;
    bloomPass.radius = 0.5;
    bloomPass.enabled = true;
    
    const toneMapShader = {
        uniforms: {
            tDiffuse: { value: null },
            uExposure: { value: 1.0 }
        },
        vertexShader: `
            varying vec2 vUv;
            void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
        `,
        fragmentShader: `
            uniform sampler2D tDiffuse;
            uniform float uExposure;
            varying vec2 vUv;
            void main() {
                vec3 color = texture2D(tDiffuse, vUv).rgb;
                color *= uExposure;
                color = color / (color + vec3(1.0));
                color = pow(color, vec3(1.0/2.2));
                gl_FragColor = vec4(color, 1.0);
            }
        `
    };
    
    const toneMapPass = new ShaderPass(toneMapShader);
    
    composer = new EffectComposer(renderer);
    composer.addPass(renderScene);
    composer.addPass(bloomPass);
    composer.addPass(toneMapPass);
    composer.addPass(new OutputPass());
}

function updateCameraPosition() {
    const radius = cameraDistance;
    camera.position.setFromSpherical(new THREE.Spherical(radius, spherical.phi, spherical.theta));
    camera.lookAt(0, 0, 0);
    
    blackholeMaterial.uniforms.uCameraPos.value.copy(camera.position);
    blackholeMaterial.uniforms.uResolution.value.set(window.innerWidth, window.innerHeight);
    starfieldMaterial.uniforms.uResolution.value.set(window.innerWidth, window.innerHeight);
    
    camDistEl.textContent = cameraDistance.toFixed(1) + ' Rs';
    camDistValEl.textContent = cameraDistance.toFixed(1) + ' Rs';
}

function animate(currentTime) {
    requestAnimationFrame(animate);
    
    if (!isPaused) {
        time += (currentTime - lastFpsTime) * 0.001 * timeScale;
    }
    lastFpsTime = currentTime;
    
    if (autoRotate && !isPaused) {
        targetSpherical.theta += autoRotateSpeed * timeScale * 60;
    }
    
    spherical.theta += (targetSpherical.theta - spherical.theta) * 0.05;
    spherical.phi += (targetSpherical.phi - spherical.phi) * 0.05;
    cameraDistance += (targetDistance - cameraDistance) * 0.05;
    
    updateCameraPosition();
    
    starfieldMaterial.uniforms.uTime.value = time;
    starfieldMaterial.uniforms.uExposure.value = exposure;
    blackholeMaterial.uniforms.uTime.value = time;
    blackholeMaterial.uniforms.uExposure.value = exposure;
    blackholeMaterial.uniforms.uHighQuality.value = highQuality;
    
    composer.render();
    
    frameCount++;
    if (currentTime - lastFpsTime > 1000) {
        fps = Math.round(frameCount * 1000 / (currentTime - lastFpsTime));
        frameCount = 0;
        lastFpsTime = currentTime;
        fpsEl.textContent = fps;
    }
    
    timeScaleEl.textContent = timeScale.toFixed(1) + '×';
}

function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, highQuality ? 2 : 1.5));
    composer.setSize(window.innerWidth, window.innerHeight);
    bloomPass.setSize(window.innerWidth, window.innerHeight);
    blackholeMaterial.uniforms.uResolution.value.set(window.innerWidth, window.innerHeight);
    starfieldMaterial.uniforms.uResolution.value.set(window.innerWidth, window.innerHeight);
}

function onMouseMove(e) {
    if (e.buttons === 1) {
        autoRotate = false;
        targetSpherical.theta -= e.movementX * 0.005;
        targetSpherical.phi = THREE.MathUtils.clamp(targetSpherical.phi - e.movementY * 0.005, 0.1, Math.PI - 0.1);
    }
}

function onWheel(e) {
    e.preventDefault();
    targetDistance = THREE.MathUtils.clamp(targetDistance + e.deltaY * 0.02, 3, 100);
}

function onKeyDown(e) {
    switch (e.code) {
        case 'Space':
            e.preventDefault();
            togglePause();
            break;
        case 'KeyR':
            resetView();
            break;
        case 'KeyI':
            toggleInfo();
            break;
        case 'KeyF':
            toggleFullscreen();
            break;
        case 'KeyQ':
            toggleQuality();
            break;
        case 'Digit1': setPreset(1); break;
        case 'Digit2': setPreset(2); break;
        case 'Digit3': setPreset(3); break;
        case 'Digit4': setPreset(4); break;
    }
}

function togglePause() {
    isPaused = !isPaused;
    btnPause.textContent = isPaused ? '▶ Play' : '⏸ Pause';
    btnPause.classList.toggle('active', isPaused);
}

function resetView() {
    gsap.to(targetSpherical, { theta: 0, phi: Math.PI * 0.5, duration: 1.5, ease: 'power2.inOut' });
    gsap.to({ val: targetDistance }, { val: 15, duration: 1.5, ease: 'power2.inOut', onUpdate: function() { targetDistance = this.targets()[0].val; }});
    gsap.to({ val: timeScale }, { val: 1.0, duration: 1.0, ease: 'power2.inOut', onUpdate: function() { timeScale = this.targets()[0].val; timeSlider.value = timeScale; timeScaleValEl.textContent = timeScale.toFixed(1) + '×'; }});
    autoRotate = true;
}

function toggleInfo() {
    showInfo = !showInfo;
    document.querySelectorAll('.ui-panel').forEach(el => el.style.display = showInfo ? 'block' : 'none');
    btnInfo.classList.toggle('active', !showInfo);
}

function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

function toggleQuality() {
    highQuality = !highQuality;
    qualityBadge.textContent = highQuality ? '4K Rendering' : 'HD Rendering';
    qualityBadge.style.background = highQuality ? 'var(--accent-dim)' : 'var(--border)';
    qualityBadge.style.color = highQuality ? 'var(--accent)' : 'var(--muted)';
    btnQuality.classList.toggle('active', !highQuality);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, highQuality ? 2 : 1.5));
    onResize();
}

function setPreset(n) {
    const presets = [
        { dist: 15, phi: Math.PI * 0.5, theta: 0, timeScale: 1.0, exp: 1.0 },
        { dist: 5, phi: Math.PI * 0.3, theta: 0.5, timeScale: 0.5, exp: 1.5 },
        { dist: 30, phi: Math.PI * 0.5, theta: 0, timeScale: 2.0, exp: 0.8 },
        { dist: 8, phi: Math.PI * 0.15, theta: 0, timeScale: 0.2, exp: 2.0 }
    ];
    const p = presets[n - 1];
    gsap.to(targetSpherical, { phi: p.phi, theta: p.theta, duration: 1.5, ease: 'power2.inOut' });
    gsap.to({ val: targetDistance }, { val: p.dist, duration: 1.5, ease: 'power2.inOut', onUpdate: function() { targetDistance = this.targets()[0].val; }});
    gsap.to({ val: timeScale }, { val: p.timeScale, duration: 1.0, ease: 'power2.inOut', onUpdate: function() { timeScale = this.targets()[0].val; timeSlider.value = timeScale; timeScaleValEl.textContent = timeScale.toFixed(1) + '×'; }});
    gsap.to({ val: exposure }, { val: p.exp, duration: 1.0, ease: 'power2.inOut', onUpdate: function() { exposure = this.targets()[0].val; expSlider.value = exposure; exposureValEl.textContent = exposure.toFixed(2); }});
}

function setupEventListeners() {
    window.addEventListener('resize', onResize);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', onKeyDown);
    
    btnPause.addEventListener('click', togglePause);
    btnReset.addEventListener('click', resetView);
    btnInfo.addEventListener('click', toggleInfo);
    btnFullscreen.addEventListener('click', toggleFullscreen);
    btnQuality.addEventListener('click', toggleQuality);
    
    timeSlider.addEventListener('input', (e) => {
        timeScale = parseFloat(e.target.value);
        timeScaleValEl.textContent = timeScale.toFixed(1) + '×';
    });
    
    distSlider.addEventListener('input', (e) => {
        targetDistance = parseFloat(e.target.value);
        camDistValEl.textContent = targetDistance.toFixed(1) + ' Rs';
    });
    
    expSlider.addEventListener('input', (e) => {
        exposure = parseFloat(e.target.value);
        exposureValEl.textContent = exposure.toFixed(2);
    });
    
    let touchStart = null;
    renderer.domElement.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }, { passive: true });
    
    renderer.domElement.addEventListener('touchmove', (e) => {
        if (touchStart && e.touches.length === 1) {
            autoRotate = false;
            targetSpherical.theta -= (e.touches[0].clientX - touchStart.x) * 0.01;
            targetSpherical.phi = THREE.MathUtils.clamp(targetSpherical.phi - (e.touches[0].clientY - touchStart.y) * 0.01, 0.1, Math.PI - 0.1);
            touchStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        }
    }, { passive: true });
    
    renderer.domElement.addEventListener('touchend', () => { touchStart = null; });
}

function init() {
    initRenderer();
    initScene();
    setupEventListeners();
    animate(performance.now());
}

init();