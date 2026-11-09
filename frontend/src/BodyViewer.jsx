import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

/**
 * BodyViewer
 *
 * Loads a patient session's 3D body mesh and renders it with lighting
 * tuned for soft-tissue contours (soft key light, cool fill, rim light
 * to preserve silhouette — see the reasoning in the original design doc).
 *
 * Props:
 *   sessionId: string | null — an existing session's id. If null, shows
 *              a status message instead of trying to load anything.
 *   apiBase:   string — base URL of the Flask API, e.g. http://localhost:5000
 */
export default function BodyViewer({ sessionId, apiBase }) {
  const containerRef = useRef(null);
  const [status, setStatus] = useState(sessionId ? 'polling' : 'no-session');
  const [error, setError] = useState(null);

  // --- Poll session status until a mesh is ready ---
  const [meshUrl, setMeshUrl] = useState(null);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;
    let timeoutId;

    async function poll() {
      try {
        const res = await fetch(`${apiBase}/api/sessions/${sessionId}`);
        if (!res.ok) throw new Error(`status check failed: ${res.status}`);
        const doc = await res.json();

        if (cancelled) return;

        if (doc.status === 'ready') {
          setMeshUrl(`${apiBase}${doc.mesh_url}`);
          setStatus('ready');
        } else if (doc.status === 'failed') {
          setError(doc.error || 'mesh generation failed');
          setStatus('failed');
        } else {
          setStatus(doc.status); // 'uploaded' | 'processing'
          timeoutId = setTimeout(poll, 1000);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e.message);
          setStatus('failed');
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [sessionId, apiBase]);

  // --- Three.js scene setup + mesh loading, once meshUrl is known ---
  useEffect(() => {
    if (!meshUrl || !containerRef.current) return;

    const container = containerRef.current;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1e);

    const camera = new THREE.PerspectiveCamera(
      35, container.clientWidth / container.clientHeight, 0.1, 100
    );
    camera.position.set(0, 1.2, 3.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    // Key light — soft, slightly warm
    const key = new THREE.DirectionalLight(0xfff1e0, 1.8);
    key.position.set(2, 3, 2);
    key.castShadow = true;
    scene.add(key);

    // Fill light — cool, opposite side, no shadows
    const fill = new THREE.DirectionalLight(0xcfe0ff, 0.6);
    fill.position.set(-3, 1, 1);
    scene.add(fill);

    // Rim light — separates silhouette from background
    const rim = new THREE.DirectionalLight(0xffffff, 1.0);
    rim.position.set(0, 2, -3);
    scene.add(rim);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 0.3));
    scene.add(new THREE.AmbientLight(0xffffff, 0.15));

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 1, 0);
    controls.minDistance = 1.0;
    controls.maxDistance = 6;

    const loader = new GLTFLoader();
    let mounted = true;

    loader.load(
      meshUrl,
      (gltf) => {
        if (!mounted) return;
        gltf.scene.traverse((child) => {
          if (child.isMesh) {
            child.material = new THREE.MeshPhysicalMaterial({
              color: 0xe8b89c,
              roughness: 0.55,
              clearcoat: 0.08,
              clearcoatRoughness: 0.4,
              sheen: 0.15,
              sheenColor: new THREE.Color(0xffddcc),
            });
            child.castShadow = true;
            child.receiveShadow = true;
            child.geometry.computeVertexNormals();
          }
        });
        scene.add(gltf.scene);

        // Auto-frame the camera on whatever mesh actually loaded, instead
        // of assuming fixed dimensions — robust across placeholder meshes
        // now and real SMPL meshes (different proportions) later.
        const box = new THREE.Box3().setFromObject(gltf.scene);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);

        controls.target.copy(center);
        const fitDistance = maxDim / (2 * Math.tan((camera.fov * Math.PI) / 360));
        camera.position.set(center.x, center.y, center.z + fitDistance * 1.6);
        camera.near = fitDistance / 100;
        camera.far = fitDistance * 100;
        camera.updateProjectionMatrix();
        controls.minDistance = fitDistance * 0.3;
        controls.maxDistance = fitDistance * 4;
        controls.update();
      },
      undefined,
      (err) => {
        console.error('GLTF load error:', err);
        setError('failed to load mesh geometry');
      }
    );

    let frameId;
    function animate() {
      frameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();

    function handleResize() {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    }
    window.addEventListener('resize', handleResize);

    return () => {
      mounted = false;
      cancelAnimationFrame(frameId);
      window.removeEventListener('resize', handleResize);
      controls.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, [meshUrl]);

  if (!sessionId) {
    return (
      <StatusOverlay>
        No session_id set yet. Create one via POST /api/sessions, then set
        TEST_SESSION_ID in App.jsx.
      </StatusOverlay>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {status !== 'ready' && (
        <StatusOverlay>
          {error ? `Error: ${error}` : `Status: ${status}...`}
        </StatusOverlay>
      )}
    </div>
  );
}

function StatusOverlay({ children }) {
  return (
    <div
      style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#ddd', fontFamily: 'monospace', fontSize: '14px',
        background: '#1a1a1e', padding: '2rem', textAlign: 'center',
      }}
    >
      {children}
    </div>
  );
}