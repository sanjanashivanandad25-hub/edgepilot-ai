import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  BufferAttribute,
  BufferGeometry,
  CatmullRomCurve3,
  Color,
  DoubleSide,
  MeshBasicMaterial,
  SphereGeometry,
  TorusGeometry,
  Vector3,
} from 'three';

const TIERS = [
  {
    name: 'On-device',
    caption: 'Private · immediate',
    detail: 'Closest to the data, with private, immediate execution.',
    context: 'Local execution avoids a network hop and keeps data close to its source.',
    color: '#72dfc1',
    place: 'device',
  },
  {
    name: 'Far Edge',
    caption: 'Nearby · resilient',
    detail: 'A nearby layer for low-latency, distributed workloads.',
    context: 'Nearby compute trades some locality for distributed capacity.',
    color: '#81cff7',
    place: 'far',
  },
  {
    name: 'Regional Edge',
    caption: 'Balanced · selected',
    detail: 'A regional fabric balancing latency, data locality, and scale.',
    context: 'Balances local responsiveness with broader shared capacity.',
    color: '#b397ff',
    place: 'regional',
  },
  {
    name: 'Cloud',
    caption: 'Elastic · centralized',
    detail: 'Central capacity with room to scale.',
    context: 'More distance can bring elastic, centralized capacity.',
    color: '#a9a2f7',
    place: 'cloud',
  },
];

const CORE = new Vector3(0, 0, 0);
const RING_GEOMETRY = new TorusGeometry(0.7, 0.009, 8, 96);
const NODE_GEOMETRY = new SphereGeometry(0.13, 24, 24);
const PARTICLE_GEOMETRY = new SphereGeometry(0.034, 10, 10);

function useSceneLayout() {
  const width = useThree((state) => state.viewport.width);
  const x = Math.min(3.25, width * (width < 7 ? 0.34 : 0.25));
  const y = Math.min(1.72, width * 0.18);

  return useMemo(
    () => [
      [-x, y, 0],
      [-x, -y, 0],
      [x, -y, 0],
      [x, y, 0],
    ],
    [x, y],
  );
}

function createRouteCurve(destination, index) {
  const [x, y, z] = destination;
  const bend = index < 2 ? -0.46 : 0.46;
  return new CatmullRomCurve3([
    CORE.clone(),
    new Vector3(x * 0.28, y * 0.22 + bend, z + 0.08),
    new Vector3(x * 0.7, y * 0.86 + bend, z - 0.06),
    new Vector3(x, y, z),
  ]);
}

function WorkloadNode({ reducedMotion }) {
  const group = useRef(null);
  const core = useRef(null);

  useFrame(({ clock }, delta) => {
    if (!group.current || !core.current || reducedMotion) return;
    group.current.rotation.y += delta * 0.12;
    group.current.rotation.x = Math.sin(clock.elapsedTime * 0.24) * 0.06;
    core.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 1.15) * 0.035);
  });

  return (
    <group ref={group}>
      <mesh ref={core}>
        <icosahedronGeometry args={[0.39, 2]} />
        <meshBasicMaterial color="#aa8cff" />
      </mesh>
      <mesh scale={1.22}>
        <icosahedronGeometry args={[0.39, 1]} />
        <meshBasicMaterial color="#d5c7ff" wireframe transparent opacity={0.46} />
      </mesh>
      <mesh scale={1.62}>
        <sphereGeometry args={[0.39, 24, 24]} />
        <meshBasicMaterial color="#9c7bff" transparent opacity={0.14} side={DoubleSide} />
      </mesh>
      <mesh scale={0.48}>
        <sphereGeometry args={[0.39, 24, 24]} />
        <meshBasicMaterial color="#e0d5ff" transparent opacity={0.86} />
      </mesh>
      {[0.78, 0.94, 1.13].map((scale, index) => (
        <mesh
          key={scale}
          geometry={RING_GEOMETRY}
          scale={scale}
          rotation={[
            Math.PI / 2 + index * 0.42,
            index * 0.35,
            index * 0.6,
          ]}
        >
          <meshBasicMaterial
            color={index === 1 ? '#9c84ff' : '#8c80c7'}
            transparent
            opacity={index === 1 ? 0.68 : 0.3}
          />
        </mesh>
      ))}
      <pointLight color="#9e80ff" intensity={8} distance={5} decay={2} />
    </group>
  );
}

function DeploymentNode({ tier, position, selected, onSelect }) {
  const [hovered, setHovered] = useState(false);
  const color = useMemo(() => new Color(tier.color), [tier.color]);
  const material = useMemo(
    () =>
      new MeshBasicMaterial({
        color: selected || hovered ? color : '#27243a',
        transparent: true,
        opacity: selected || hovered ? 1 : 0.8,
      }),
    [color, hovered, selected],
  );
  const ringMaterial = useMemo(
    () =>
      new MeshBasicMaterial({
        color,
        transparent: true,
        opacity: selected || hovered ? 0.88 : 0.38,
      }),
    [color, hovered, selected],
  );

  useEffect(
    () => () => {
      material.dispose();
      ringMaterial.dispose();
    },
    [material, ringMaterial],
  );

  return (
    <group position={position}>
      <mesh
        geometry={NODE_GEOMETRY}
        material={material}
        scale={selected || hovered ? 1.32 : 1}
        onPointerOver={(event) => {
          event.stopPropagation();
          setHovered(true);
          onSelect(tier.name);
        }}
        onPointerOut={() => setHovered(false)}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(tier.name);
        }}
      />
      <mesh
        geometry={RING_GEOMETRY}
        material={ringMaterial}
        scale={selected || hovered ? 1.9 : 1.55}
        rotation={[Math.PI / 2, 0.3, 0]}
      />
      <mesh
        geometry={RING_GEOMETRY}
        material={ringMaterial}
        scale={selected || hovered ? 2.35 : 2}
        rotation={[0.6, Math.PI / 2, 0.35]}
      />
    </group>
  );
}

function DataFlowParticles({ curve, active, offset, reducedMotion }) {
  const particles = useRef([]);
  const progress = useMemo(() => [0, 0.44, 0.78][offset % 3], [offset]);

  useFrame(({ clock }) => {
    const time = reducedMotion ? 0 : clock.elapsedTime;
    particles.current.forEach((particle, index) => {
      if (!particle) return;
      const travel = reducedMotion ? progress : (time * 0.085 + progress + index * 0.28) % 1;
      curve.getPointAt(travel, particle.position);
    });
  });

  return (
    <>
      {[0, 1].map((index) => (
        <mesh
          key={index}
          ref={(node) => {
            particles.current[index] = node;
          }}
          geometry={PARTICLE_GEOMETRY}
        >
          <meshBasicMaterial
            color={active ? '#e5dbff' : '#7f77a1'}
            transparent
            opacity={active ? 0.96 : 0.18}
          />
        </mesh>
      ))}
    </>
  );
}

function RouteNetwork({ selectedTier, onSelect, reducedMotion }) {
  const positions = useSceneLayout();
  const root = useRef(null);
  const routes = useMemo(
    () => positions.map((position, index) => createRouteCurve(position, index)),
    [positions],
  );

  useFrame(({ clock }, delta) => {
    if (!root.current || reducedMotion) return;
    root.current.rotation.y = Math.sin(clock.elapsedTime * 0.15) * 0.04;
    root.current.rotation.x = Math.cos(clock.elapsedTime * 0.12) * 0.025;
    root.current.rotation.y += delta * 0.006;
  });

  return (
    <group ref={root}>
      <WorkloadNode reducedMotion={reducedMotion} />
      {TIERS.map((tier, index) => {
        const curve = routes[index];
        const selected = selectedTier === tier.name;
        return (
          <group key={tier.name}>
            <mesh>
              <tubeGeometry args={[curve, 72, selected ? 0.016 : 0.006, 7, false]} />
              <meshBasicMaterial
                color={tier.color}
                transparent
                opacity={selected ? 0.88 : 0.19}
              />
            </mesh>
            <DataFlowParticles
              curve={curve}
              active={selected}
              offset={index}
              reducedMotion={reducedMotion}
            />
            <DeploymentNode
              tier={tier}
              position={positions[index]}
              selected={selected}
              onSelect={onSelect}
            />
          </group>
        );
      })}
    </group>
  );
}

function AmbientField({ reducedMotion }) {
  const points = useRef(null);
  const width = useThree((state) => state.viewport.width);
  const count = width < 6 ? 45 : 150;
  const geometry = useMemo(() => {
    const positions = new Float32Array(count * 3);
    for (let index = 0; index < count; index += 1) {
      const angle = index * 2.399;
      const radius = 1.5 + ((index * 37) % 100) / 28;
      positions[index * 3] = Math.cos(angle) * radius;
      positions[index * 3 + 1] = Math.sin(angle * 1.3) * radius * 0.58;
      positions[index * 3 + 2] = -1.4 - ((index * 17) % 50) / 20;
    }
    const result = new BufferGeometry();
    result.setAttribute('position', new BufferAttribute(positions, 3));
    return result;
  }, [count]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame(({ clock }, delta) => {
    if (points.current && !reducedMotion) {
      points.current.rotation.z += delta * 0.008;
      points.current.position.y = Math.sin(clock.elapsedTime * 0.11) * 0.04;
    }
  });

  return (
    <points ref={points} geometry={geometry}>
      <pointsMaterial
        color="#a99bdb"
        size={0.018}
        sizeAttenuation
        transparent
        opacity={0.5}
        depthWrite={false}
      />
    </points>
  );
}

function SceneContents({ selectedTier, onSelect, reducedMotion }) {
  const group = useRef(null);
  const pointerTarget = useRef({ x: 0, y: 0 });
  const { viewport } = useThree();

  useFrame(({ pointer }, delta) => {
    if (!group.current || reducedMotion) return;
    pointerTarget.current.x += (pointer.x * 0.12 - pointerTarget.current.x) * Math.min(delta * 2, 1);
    pointerTarget.current.y += (pointer.y * 0.08 - pointerTarget.current.y) * Math.min(delta * 2, 1);
    group.current.position.x = pointerTarget.current.x;
    group.current.position.y = pointerTarget.current.y;
  });

  return (
    <>
      <fog attach="fog" args={['#080812', viewport.width * 0.72, viewport.width * 1.8]} />
      <ambientLight intensity={0.58} />
      <pointLight position={[4, 3, 5]} color="#7063c5" intensity={22} distance={13} />
      <pointLight position={[-5, -2, 3]} color="#23667a" intensity={10} distance={11} />
      <group ref={group}>
        <AmbientField reducedMotion={reducedMotion} />
        <RouteNetwork
          selectedTier={selectedTier}
          onSelect={onSelect}
          reducedMotion={reducedMotion}
        />
      </group>
    </>
  );
}

export default function HeroScene() {
  const [selectedTier, setSelectedTier] = useState('On-device');
  const [reducedMotion, setReducedMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  const activeTier = TIERS.find((tier) => tier.name === selectedTier) ?? TIERS[2];
  const section = useRef(null);
  const [inView, setInView] = useState(true);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const onChange = () => setReducedMotion(media.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    if (!section.current) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => setInView(entry.isIntersecting),
      { rootMargin: '120px' },
    );
    observer.observe(section.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="hero-scene-wrap">
      <section className="hero-scene" ref={section} aria-label="Interactive deployment environment">
        <div className="scene-vignette" aria-hidden="true" />
        <Canvas
          className="deployment-canvas"
          camera={{ position: [0, 0, 10], fov: 39 }}
          dpr={[1, 1.5]}
          frameloop={reducedMotion || !inView ? 'demand' : 'always'}
          gl={{ alpha: true, antialias: true, powerPreference: 'low-power' }}
        >
          <Suspense fallback={null}>
            <SceneContents
              selectedTier={selectedTier}
              onSelect={setSelectedTier}
              reducedMotion={reducedMotion || !inView}
            />
          </Suspense>
        </Canvas>
        <div className="scene-label-layer" role="group" aria-label="Select a deployment tier">
          <span className="scene-core-label">AI / WORKLOAD</span>
          {TIERS.map((tier) => (
            <button
              className={`scene-tier-label scene-tier-${tier.place} ${selectedTier === tier.name ? 'is-selected' : ''}`}
              key={tier.name}
              type="button"
              style={{ '--tier-color': tier.color }}
              aria-pressed={selectedTier === tier.name}
              onFocus={() => setSelectedTier(tier.name)}
              onPointerEnter={() => setSelectedTier(tier.name)}
              onClick={() => setSelectedTier(tier.name)}
            >
              <strong>{tier.name}</strong>
              <span>{tier.caption}</span>
            </button>
          ))}
        </div>
        <span className="scene-coordinate scene-coordinate-a" aria-hidden="true">EDGE / 04</span>
      </section>
      <div className="scene-readout" aria-live="polite">
        <span className="scene-readout-kicker">PLACEMENT SIGNAL / ILLUSTRATIVE</span>
        <strong style={{ '--tier-color': activeTier.color }}>{activeTier.name}</strong>
        <p>{activeTier.detail}</p>
        <small>{activeTier.context}</small>
      </div>
    </div>
  );
}
