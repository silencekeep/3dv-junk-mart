import {
  Application,
  Asset,
  AssetListLoader,
  BLEND_NORMAL,
  Color,
  Entity,
  FILLMODE_FILL_WINDOW,
  Gizmo,
  Layer,
  Quat,
  RESOLUTION_AUTO,
  RotateGizmo,
  StandardMaterial,
  TranslateGizmo,
  Vec3,
} from 'playcanvas';
import { formatBytes, loadModelResponseWithCache } from './model-cache.js?v=20260408_43';

const params = new URLSearchParams(window.location.search);
const modelUrl = params.get('model');
const modelVersion = params.get('model_v') ?? 'unversioned';

const overlay = document.getElementById('overlay');
const statusLabel = document.getElementById('status-label');
const statusDetail = document.getElementById('status-detail');
const hintLabel = document.getElementById('viewer-hint');
const resetButton = document.getElementById('reset-view');
const calibrateButton = document.getElementById('calibrate-toggle');
const calibrationRotateButton = document.getElementById('calibration-rotate');
const calibrationTranslateButton = document.getElementById('calibration-translate');
const saveCalibrationButton = document.getElementById('save-calibration');
const cancelCalibrationButton = document.getElementById('cancel-calibration');
const setInitialViewButton = document.getElementById('set-initial-view');
const confirmInitialViewButton = document.getElementById('confirm-initial-view');
const cancelInitialViewButton = document.getElementById('cancel-initial-view');
const animationToggleButton = document.getElementById('animation-toggle');
const animationPanel = document.getElementById('animation-panel');
const animationPlayButton = document.getElementById('animation-play-toggle');
const animationProgressWrap = document.getElementById('animation-progress-wrap');
const animationProgressBar = document.getElementById('animation-progress-bar');
const minimalResetButton = document.getElementById('minimal-reset-view');
const taskId = params.get('task_id') ?? inferTaskIdFromModelUrl(modelUrl);
const readOnlyMode = params.get('readonly') === '1';
const embeddedMode = params.get('embed') === '1';
const autoPlayMode = params.get('autoplay') === '1';
const minimalMode = params.get('minimal') === '1';
const workflowMode = params.get('workflow');
const calibrationWorkflowMode =
  workflowMode === 'rotate' || workflowMode === 'translate' ? workflowMode : null;
const initialViewWorkflowMode = workflowMode === 'initial-view';

const AXIS_RIGHT = new Vec3(1, 0, 0);
const AXIS_UP = new Vec3(0, 1, 0);
const CAMERA_OFFSET = new Vec3(0, 0, 1);
const GRID_MINOR_COLOR = new Color(0.78, 0.8, 0.8, 0.38);
const GRID_MAJOR_COLOR = new Color(1, 1, 1, 0.9);
const AXIS_X_COLOR = new Color(1, 0.24, 0.18, 0.95);
const AXIS_Z_COLOR = new Color(0.26, 0.48, 1, 0.95);
const CALIBRATION_GRID_HALF_SIZE = 24.0;
const CALIBRATION_GRID_STEP = 0.35;
const CALIBRATION_GRID_MAJOR_EVERY = 10;
const CALIBRATION_GRID_MINOR_WIDTH = 0.006;
const CALIBRATION_GRID_MAJOR_WIDTH = 0.012;
const CALIBRATION_AXIS_WIDTH = 0.018;
const CALIBRATION_GRID_THICKNESS = 0.003;
const MAX_DEVICE_PIXEL_RATIO = 2;
const CALIBRATION_TOOL_ROTATE = 'rotate';
const CALIBRATION_TOOL_TRANSLATE = 'translate';
const MIN_ORBIT_ELEVATION = -89.9;
const MAX_ORBIT_ELEVATION = 89.9;
const WORLD_ORIGIN = new Vec3(0, 0, 0);
const DEFAULT_VIEW_HINT = readOnlyMode ? '拖动查看商品 · 双指缩放/平移/扭转' : '单指环绕旋转 · 双指平移/缩放/扭转';
const ANIMATION_TURN_DURATION_MS = 16000;
const ANIMATION_TURN_DEGREES = 360;

function createViewerLayers(appInstance) {
  const composition = appInstance.scene.layers;
  const referenceLayer = new Layer({ name: 'Calibration Reference' });
  const splatLayer = new Layer({ name: 'Product Splat' });
  composition.push(referenceLayer);
  composition.push(splatLayer);
  return {
    world: composition.getLayerByName('World'),
    reference: referenceLayer,
    splat: splatLayer,
    gizmo: null,
  };
}

function inferTaskIdFromModelUrl(url) {
  if (!url) {
    return null;
  }
  const match = url.match(/\/storage\/models\/([^/]+)\//);
  return match ? decodeURIComponent(match[1]) : null;
}

function setStatus(label, detail) {
  statusLabel.textContent = label;
  statusDetail.textContent = detail;
}

function hideOverlay() {
  overlay.classList.add('hidden');
}

function configureViewerMode() {
  const showCompactResetButton = minimalMode || workflowMode;
  if (embeddedMode) {
    document.body.classList.add('embedded-viewer');
  }
  if (minimalMode) {
    document.body.classList.add('minimal-viewer');
  }
  if (workflowMode) {
    document.body.classList.add('workflow-viewer');
  }
  minimalResetButton.hidden = !showCompactResetButton;

  if (!readOnlyMode) {
    if (workflowMode) {
      calibrateButton.hidden = true;
      calibrationRotateButton.hidden = true;
      calibrationTranslateButton.hidden = true;
      saveCalibrationButton.hidden = true;
      cancelCalibrationButton.hidden = true;
      setInitialViewButton.hidden = true;
      confirmInitialViewButton.hidden = true;
      cancelInitialViewButton.hidden = true;
      animationToggleButton.hidden = true;
      resetButton.hidden = true;
      hintLabel.hidden = true;
    }
    return;
  }

  calibrateButton.hidden = true;
  calibrationRotateButton.hidden = true;
  calibrationTranslateButton.hidden = true;
  saveCalibrationButton.hidden = true;
  cancelCalibrationButton.hidden = true;
  setInitialViewButton.hidden = true;
  confirmInitialViewButton.hidden = true;
  cancelInitialViewButton.hidden = true;
  if (minimalMode) {
    animationToggleButton.hidden = true;
    resetButton.hidden = true;
    hintLabel.hidden = true;
  }
}

function waitForPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => window.setTimeout(resolve, 0));
  });
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function normalizeAngleDelta(angle) {
  if (!Number.isFinite(angle)) {
    return 0;
  }
  while (angle > Math.PI) {
    angle -= Math.PI * 2;
  }
  while (angle < -Math.PI) {
    angle += Math.PI * 2;
  }
  return angle;
}

function parseNumberParam(name, fallback) {
  const raw = params.get(name);
  if (raw == null || raw === '') {
    return fallback;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : fallback;
}

function buildDisplayConfig() {
  const modelRotationDeg = new Vec3(
    parseNumberParam('model_rx', 0),
    parseNumberParam('model_ry', 0),
    parseNumberParam('model_rz', 0)
  );
  const modelTranslation = new Vec3(
    parseNumberParam('model_tx', 0),
    parseNumberParam('model_ty', 0),
    parseNumberParam('model_tz', 0)
  );
  const modelScale = parseNumberParam('model_scale', 1);
  const cameraEulerDeg = new Vec3(
    parseNumberParam('cam_rx', -18),
    parseNumberParam('cam_ry', 26),
    parseNumberParam('cam_rz', 0)
  );
  const cameraDistance = parseNumberParam('cam_dist', NaN);

  return {
    modelRotationDeg,
    modelRotation: new Quat().setFromEulerAngles(modelRotationDeg.x, modelRotationDeg.y, modelRotationDeg.z),
    modelTranslation,
    modelScale,
    cameraEulerDeg,
    cameraDistance: Number.isFinite(cameraDistance) ? cameraDistance : null,
  };
}

class OrbitControls {
  constructor(cameraEntity, canvas) {
    this.cameraEntity = cameraEntity;
    this.canvas = canvas;
    this.target = new Vec3(0, 0, 0);
    this.defaultTarget = new Vec3(0, 0, 0);
    this.distance = 1.6;
    this.defaultDistance = 1.6;
    this.minDistance = 0.25;
    this.maxDistance = 10;
    this.rotation = new Quat();
    this.azim = 0;
    this.elevation = 0;
    this.roll = 0;
    this.defaultAzim = 0;
    this.defaultElevation = 0;
    this.defaultRoll = 0;
    this.rotateSpeed = 0.3;
    this.mouseRotateSpeed = 0.14;
    this.twistSpeed = 0.9;
    this.zoomSpeed = 0.0028;
    this.panSpeed = 1.1;
    this.enabled = true;
    this.onUserInteractionStart = null;
    this.onUserInteractionEnd = null;
    this.singlePointerOnly = false;
    this.singlePointerGestureBlocked = false;
    this.hasPanned = false;
    this.activePointers = new Map();
    this.lastSinglePointer = null;
    this.lastMultiGesture = null;

    this._offset = new Vec3();
    this._position = new Vec3();
    this._panRight = new Vec3();
    this._panUp = new Vec3();
    this._orbitRotation = new Quat();

    this.onPointerDown = this.onPointerDown.bind(this);
    this.onPointerMove = this.onPointerMove.bind(this);
    this.onPointerUp = this.onPointerUp.bind(this);
    this.onWheel = this.onWheel.bind(this);
    this.onContextMenu = this.onContextMenu.bind(this);
    this.onDoubleClick = this.onDoubleClick.bind(this);
    this.preventBrowserGesture = this.preventBrowserGesture.bind(this);

    canvas.addEventListener('pointerdown', this.onPointerDown, { passive: false });
    canvas.addEventListener('pointermove', this.onPointerMove, { passive: false });
    canvas.addEventListener('pointerup', this.onPointerUp, { passive: false });
    canvas.addEventListener('pointercancel', this.onPointerUp, { passive: false });
    canvas.addEventListener('wheel', this.onWheel, { passive: false });
    canvas.addEventListener('contextmenu', this.onContextMenu);
    canvas.addEventListener('dblclick', this.onDoubleClick);
    document.addEventListener('touchstart', this.preventBrowserGesture, { passive: false });
    document.addEventListener('touchmove', this.preventBrowserGesture, { passive: false });
    document.addEventListener('gesturestart', this.preventBrowserGesture, { passive: false });
    document.addEventListener('gesturechange', this.preventBrowserGesture, { passive: false });
    document.addEventListener('gestureend', this.preventBrowserGesture, { passive: false });

    this.updateCamera();
  }

  preventBrowserGesture(event) {
    if (event.target?.closest?.('button')) {
      return;
    }
    event.preventDefault();
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    if (!enabled) {
      this.activePointers.clear();
      this.lastSinglePointer = null;
      this.lastMultiGesture = null;
    }
  }

  setSinglePointerOnly(enabled) {
    this.singlePointerOnly = enabled;
    this.singlePointerGestureBlocked = false;
    this.activePointers.clear();
    this.lastSinglePointer = null;
    this.lastMultiGesture = null;
  }

  notifyUserInteractionStart() {
    this.onUserInteractionStart?.();
  }

  destroy() {
    this.canvas.removeEventListener('pointerdown', this.onPointerDown);
    this.canvas.removeEventListener('pointermove', this.onPointerMove);
    this.canvas.removeEventListener('pointerup', this.onPointerUp);
    this.canvas.removeEventListener('pointercancel', this.onPointerUp);
    this.canvas.removeEventListener('wheel', this.onWheel);
    this.canvas.removeEventListener('contextmenu', this.onContextMenu);
    this.canvas.removeEventListener('dblclick', this.onDoubleClick);
    document.removeEventListener('touchstart', this.preventBrowserGesture);
    document.removeEventListener('touchmove', this.preventBrowserGesture);
    document.removeEventListener('gesturestart', this.preventBrowserGesture);
    document.removeEventListener('gesturechange', this.preventBrowserGesture);
    document.removeEventListener('gestureend', this.preventBrowserGesture);
  }

  setDefaults({ target, distance, euler }) {
    this.defaultTarget.copy(target);
    this.target.copy(target);
    this.defaultDistance = distance;
    this.distance = distance;
    this.defaultAzim = euler?.y ?? 0;
    this.defaultElevation = clamp(euler?.x ?? 0, MIN_ORBIT_ELEVATION, MAX_ORBIT_ELEVATION);
    this.defaultRoll = euler?.z ?? 0;
    this.azim = this.defaultAzim;
    this.elevation = this.defaultElevation;
    this.roll = this.defaultRoll;
    this.hasPanned = false;
    this.updateCamera();
  }

  setDefaultTarget(target, syncCurrent) {
    this.defaultTarget.copy(target);
    if (syncCurrent && !this.hasPanned) {
      this.target.copy(target);
      this.updateCamera();
    }
  }

  setCurrentAsDefault() {
    this.defaultTarget.copy(this.target);
    this.defaultDistance = this.distance;
    this.defaultAzim = this.azim;
    this.defaultElevation = this.elevation;
    this.defaultRoll = this.roll;
    this.hasPanned = false;
  }

  getCameraConfig() {
    return {
      camera_rotation_deg: [
        roundCoordinate(this.elevation),
        normalizeDegrees(this.azim),
        normalizeDegrees(this.roll),
      ],
      camera_distance: roundCoordinate(this.distance),
    };
  }

  getViewState() {
    return {
      target: this.target.clone(),
      distance: this.distance,
      azim: this.azim,
      elevation: this.elevation,
      roll: this.roll,
      hasPanned: this.hasPanned,
    };
  }

  setViewState(state) {
    this.target.copy(state.target ?? this.defaultTarget);
    this.distance = state.distance ?? this.defaultDistance;
    this.azim = state.azim ?? this.defaultAzim;
    this.elevation = clamp(state.elevation ?? this.defaultElevation, MIN_ORBIT_ELEVATION, MAX_ORBIT_ELEVATION);
    this.roll = state.roll ?? this.defaultRoll;
    this.hasPanned = state.hasPanned ?? false;
    this.updateCamera();
  }

  setHorizontalOrbitProgress(baseState, progress) {
    this.setViewState({
      target: baseState.target,
      distance: baseState.distance,
      azim: baseState.azim + progress * ANIMATION_TURN_DEGREES,
      elevation: baseState.elevation,
      roll: baseState.roll,
      hasPanned: false,
    });
  }

  reset() {
    this.target.copy(this.defaultTarget);
    this.distance = this.defaultDistance;
    this.azim = this.defaultAzim;
    this.elevation = this.defaultElevation;
    this.roll = this.defaultRoll;
    this.hasPanned = false;
    this.updateCamera();
  }

  updateCamera() {
    this._orbitRotation.setFromEulerAngles(this.elevation, this.azim, 0);
    this._offset.copy(CAMERA_OFFSET).mulScalar(this.distance);
    this._orbitRotation.transformVector(this._offset, this._offset);
    this._position.copy(this.target).add(this._offset);
    this.cameraEntity.setPosition(this._position);
    this.cameraEntity.lookAt(this.target);
    if (this.roll !== 0) {
      this.cameraEntity.rotateLocal(0, 0, this.roll);
    }
    this.rotation.copy(this.cameraEntity.getLocalRotation());
  }

  rotate(dx, dy, pointerType) {
    const speed = pointerType === 'mouse' ? this.mouseRotateSpeed : this.rotateSpeed;

    this.azim -= dx * speed;
    this.elevation = clamp(this.elevation - dy * speed, MIN_ORBIT_ELEVATION, MAX_ORBIT_ELEVATION);
    this.updateCamera();
  }

  pan(dx, dy) {
    const rect = this.canvas.getBoundingClientRect();
    const camera = this.cameraEntity.camera;
    const distance = Math.max(this.distance, this.minDistance);
    const viewHeight = 2 * distance * Math.tan((camera.fov * Math.PI) / 360);
    const viewWidth = viewHeight * camera.aspectRatio;
    const worldX = (dx / rect.width) * viewWidth * this.panSpeed;
    const worldY = (dy / rect.height) * viewHeight * this.panSpeed;

    this.rotation.transformVector(AXIS_RIGHT, this._panRight);
    this.rotation.transformVector(AXIS_UP, this._panUp);

    this.target.add(this._panRight.mulScalar(-worldX)).add(this._panUp.mulScalar(worldY));
    this.hasPanned = true;
    this.updateCamera();
  }

  twist(angleDeltaRadians) {
    const normalized = normalizeAngleDelta(angleDeltaRadians);
    if (Math.abs(normalized) < 0.01) {
      return;
    }

    this.roll += (normalized * 180) / Math.PI * this.twistSpeed;
    this.updateCamera();
  }

  zoomByScale(scale) {
    if (!Number.isFinite(scale) || scale <= 0) {
      return;
    }
    this.distance = clamp(this.distance / scale, this.minDistance, this.maxDistance);
    this.updateCamera();
  }

  zoomByWheel(deltaY) {
    const scale = Math.exp(deltaY * this.zoomSpeed);
    this.distance = clamp(this.distance * scale, this.minDistance, this.maxDistance);
    this.updateCamera();
  }

  capturePointer(event) {
    if (this.canvas.setPointerCapture) {
      this.canvas.setPointerCapture(event.pointerId);
    }
  }

  releasePointer(event) {
    if (this.canvas.releasePointerCapture) {
      this.canvas.releasePointerCapture(event.pointerId);
    }
  }

  refreshGestureState() {
    const pointers = [...this.activePointers.values()];
    if (pointers.length === 1) {
      const pointer = pointers[0];
      this.lastSinglePointer = { x: pointer.x, y: pointer.y, pointerType: pointer.pointerType };
      this.lastMultiGesture = null;
      return;
    }

    if (pointers.length >= 2) {
      const [a, b] = pointers;
      this.lastSinglePointer = null;
      this.lastMultiGesture = {
        midX: (a.x + b.x) * 0.5,
        midY: (a.y + b.y) * 0.5,
        distance: Math.hypot(a.x - b.x, a.y - b.y),
        angle: Math.atan2(b.y - a.y, b.x - a.x),
      };
      return;
    }

    this.lastSinglePointer = null;
    this.lastMultiGesture = null;
  }

  onPointerDown(event) {
    if (!this.enabled) {
      return;
    }
    event.preventDefault();
    this.notifyUserInteractionStart();

    this.capturePointer(event);
    this.activePointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
      pointerType: event.pointerType,
      buttons: event.buttons,
    });

    if (this.singlePointerOnly && this.activePointers.size > 1) {
      this.singlePointerGestureBlocked = true;
      this.lastSinglePointer = null;
      this.lastMultiGesture = null;
      return;
    }

    this.refreshGestureState();
  }

  onPointerMove(event) {
    if (!this.enabled) {
      return;
    }
    if (!this.activePointers.has(event.pointerId)) {
      return;
    }

    event.preventDefault();
    this.activePointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
      pointerType: event.pointerType,
      buttons: event.buttons,
    });

    if (this.singlePointerOnly && this.singlePointerGestureBlocked) {
      return;
    }

    const pointers = [...this.activePointers.values()];
    if (pointers.length === 1 && this.lastSinglePointer) {
      const pointer = pointers[0];
      const dx = pointer.x - this.lastSinglePointer.x;
      const dy = pointer.y - this.lastSinglePointer.y;
      const wantsPan = !this.singlePointerOnly
        && pointer.pointerType === 'mouse'
        && ((pointer.buttons & 2) !== 0 || (pointer.buttons & 4) !== 0);

      if (wantsPan) {
        this.pan(dx, dy);
      } else {
        this.rotate(dx, dy, pointer.pointerType);
      }

      this.lastSinglePointer = { x: pointer.x, y: pointer.y, pointerType: pointer.pointerType };
      return;
    }

    if (this.singlePointerOnly) {
      this.refreshGestureState();
      return;
    }

    if (pointers.length >= 2 && this.lastMultiGesture) {
      const [a, b] = pointers;
      const midX = (a.x + b.x) * 0.5;
      const midY = (a.y + b.y) * 0.5;
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      const angle = Math.atan2(b.y - a.y, b.x - a.x);
      const dx = midX - this.lastMultiGesture.midX;
      const dy = midY - this.lastMultiGesture.midY;
      const scale = distance / Math.max(this.lastMultiGesture.distance, 1);
      const angleDelta = normalizeAngleDelta(angle - this.lastMultiGesture.angle);

      this.pan(dx, dy);
      this.zoomByScale(scale);
      this.twist(angleDelta);

      this.lastMultiGesture = { midX, midY, distance, angle };
    }
  }

  onPointerUp(event) {
    if (!this.enabled) {
      return;
    }
    if (this.activePointers.has(event.pointerId)) {
      event.preventDefault();
      this.activePointers.delete(event.pointerId);
      this.releasePointer(event);
      if (this.singlePointerOnly && this.activePointers.size === 0) {
        this.singlePointerGestureBlocked = false;
      }
      this.refreshGestureState();
      if (this.activePointers.size === 0) {
        this.onUserInteractionEnd?.();
      }
    }
  }

  onWheel(event) {
    if (!this.enabled) {
      return;
    }
    event.preventDefault();
    this.notifyUserInteractionStart();
    if (this.singlePointerOnly) {
      return;
    }
    this.zoomByWheel(event.deltaY);
  }

  onContextMenu(event) {
    event.preventDefault();
  }

  onDoubleClick(event) {
    if (!this.enabled) {
      return;
    }
    event.preventDefault();
    this.notifyUserInteractionStart();
    if (this.singlePointerOnly) {
      return;
    }
    this.reset();
  }
}

if (!modelUrl) {
  setStatus('缺少模型地址', '请通过 ?model=/storage/models/<task>/model.ply 或 model.sog 传入模型 URL。');
  throw new Error('Missing model URL.');
}

const canvas = document.createElement('canvas');
canvas.setAttribute('aria-label', '3D Gaussian Splat Viewer');
document.querySelector('.viewport').appendChild(canvas);

const app = new Application(canvas, {
  graphicsDeviceOptions: {
    antialias: true,
    alpha: false,
  },
});

app.graphicsDevice.maxPixelRatio = Math.min(window.devicePixelRatio || 1, MAX_DEVICE_PIXEL_RATIO);
app.setCanvasFillMode(FILLMODE_FILL_WINDOW);
app.setCanvasResolution(RESOLUTION_AUTO);
app.scene.ambientLight = new Color(0.82, 0.82, 0.82);
app.start();
const viewerLayers = createViewerLayers(app);

window.addEventListener('resize', () => {
  app.graphicsDevice.maxPixelRatio = Math.min(window.devicePixelRatio || 1, MAX_DEVICE_PIXEL_RATIO);
  app.resizeCanvas();
});

const assets = [
  new Asset('product-splat', 'gsplat', {
    url: modelUrl,
  }),
];

let modelLoadSource = 'network';
let lastModelProgressUpdateAt = 0;
assets[0].on('progress', (receivedBytes, totalBytes) => {
  const now = performance.now();
  if (now - lastModelProgressUpdateAt < 250) {
    return;
  }

  lastModelProgressUpdateAt = now;
  const totalLabel = totalBytes ? formatBytes(totalBytes) : '未知大小';
  const label = modelLoadSource === 'cache'
    ? '正在解析本地模型...'
    : '正在下载并解析模型...';
  setStatus(label, `${formatBytes(receivedBytes)} / ${totalLabel}`);
});
assets[0].on('load:data', () => {
  setStatus('正在创建渲染资源...', '模型数据已读取，正在排序并上传到 GPU。');
});

const loader = new AssetListLoader(assets, app.assets);
const displayConfig = buildDisplayConfig();
let controls = null;
let modelRoot = null;
let productSplat = null;
let rotateGizmo = null;
let translateGizmo = null;
let calibrationReferenceRoot = null;
let calibrationMode = false;
let calibrationTool = CALIBRATION_TOOL_ROTATE;
let calibrationDragging = false;
let initialViewMode = false;
let animationMode = false;
let animationPlaying = false;
let animationProgress = 0;
let animationBaseViewState = null;
let animationFrameId = null;
let animationLastFrameAt = 0;
let animationControlsVisible = true;
let animationControlsTapCandidate = null;
let calibrationAutoSaveTimer = null;
let calibrationSaveInFlight = false;
let calibrationSaveQueued = false;
let initialViewAutoSaveTimer = null;
let initialViewSaveInFlight = false;
let initialViewSaveQueued = false;
let savedModelRotation = null;
let savedModelTranslation = null;
let calibrationStartRotation = null;
let calibrationStartTranslation = null;
const eulerScratch = new Vec3();
const positionScratch = new Vec3();

function getGsplatAabbInfo(splatEntity) {
  modelRoot?.syncHierarchy?.();
  splatEntity?.syncHierarchy?.();

  const localAabb =
    splatEntity.gsplat?.customAabb ??
    splatEntity.gsplat?.asset?.resource?.aabb ??
    splatEntity.gsplat?.resource?.aabb ??
    splatEntity.gsplat?.instance?.resource?.aabb ??
    assets[0]?.resource?.aabb;
  if (localAabb?.center && localAabb?.halfExtents) {
    return { aabb: localAabb, space: 'local' };
  }

  const meshInstance =
    splatEntity.gsplat?.instance?.meshInstance ??
    splatEntity.gsplat?.meshInstance ??
    splatEntity.gsplat?.meshInstances?.[0];
  if (meshInstance?.aabb?.center && meshInstance?.aabb?.halfExtents) {
    return { aabb: meshInstance.aabb, space: 'world' };
  }

  return null;
}

function getGsplatFocalPoint(splatEntity) {
  const resource =
    splatEntity.gsplat?.asset?.resource ??
    splatEntity.gsplat?.resource ??
    splatEntity.gsplat?.instance?.resource ??
    assets[0]?.resource;

  if (typeof resource?.calcFocalPoint !== 'function') {
    return null;
  }

  const focalPoint = new Vec3();
  try {
    resource.calcFocalPoint(focalPoint);
  } catch (error) {
    console.warn('Failed to calculate gsplat focal point.', error);
    return null;
  }

  if (![focalPoint.x, focalPoint.y, focalPoint.z].every(Number.isFinite)) {
    return null;
  }

  splatEntity.getWorldTransform().transformPoint(focalPoint, focalPoint);
  return focalPoint;
}

function getModelWorldCenter(splatEntity) {
  const focalPoint = getGsplatFocalPoint(splatEntity);
  if (focalPoint) {
    return focalPoint;
  }

  const aabbInfo = getGsplatAabbInfo(splatEntity);
  if (aabbInfo?.space === 'world') {
    return new Vec3().copy(aabbInfo.aabb.center);
  }

  const target = modelRoot
    ? modelRoot.getLocalPosition().clone()
    : new Vec3().copy(displayConfig.modelTranslation);
  const aabb = aabbInfo?.aabb;

  if (!aabb?.center) {
    return target;
  }

  const localCenter = new Vec3().copy(aabb.center);
  splatEntity.getWorldTransform().transformPoint(localCenter, localCenter);
  return localCenter;
}

function buildHomeView(splatEntity) {
  const aabbInfo = getGsplatAabbInfo(splatEntity);
  const aabb = aabbInfo?.aabb;
  const target = WORLD_ORIGIN.clone();
  let radius = 0.12;

  if (aabb?.halfExtents) {
    radius = Math.max(aabb.halfExtents.x, aabb.halfExtents.y, aabb.halfExtents.z, 0.12);
    if (aabbInfo.space !== 'world') {
      radius *= displayConfig.modelScale;
    }
  }

  return {
    target,
    distance: clamp(displayConfig.cameraDistance ?? radius * 4.8, 0.8, 8),
    euler: displayConfig.cameraEulerDeg,
  };
}

function refreshOrbitTarget(syncCurrent) {
  if (!controls) {
    return;
  }
  controls.setDefaultTarget(WORLD_ORIGIN, syncCurrent);
}

function normalizeDegrees(value) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  let normalized = ((value + 180) % 360 + 360) % 360 - 180;
  if (Math.abs(normalized) < 0.0001) {
    normalized = 0;
  }
  return Number(normalized.toFixed(4));
}

function roundCoordinate(value) {
  return Number((Number.isFinite(value) ? value : 0).toFixed(4));
}

function getModelRotationDeg() {
  const euler = modelRoot.getLocalEulerAngles();
  eulerScratch.copy(euler);
  return [
    normalizeDegrees(eulerScratch.x),
    normalizeDegrees(eulerScratch.y),
    normalizeDegrees(eulerScratch.z),
  ];
}

function getModelTranslation() {
  const position = modelRoot.getLocalPosition();
  positionScratch.copy(position);
  return [
    roundCoordinate(positionScratch.x),
    roundCoordinate(positionScratch.y),
    roundCoordinate(positionScratch.z),
  ];
}

function createReferenceMaterial(name, color) {
  const material = new StandardMaterial();
  material.name = name;
  material.diffuse.copy(color);
  material.emissive.copy(color);
  material.opacity = color.a;
  material.blendType = BLEND_NORMAL;
  material.depthTest = true;
  material.depthWrite = true;
  material.useLighting = false;
  material.update();
  return material;
}

function createStrip(name, position, scale, material, parent) {
  const strip = new Entity(name);
  strip.addComponent('render', {
    type: 'box',
    material,
    layers: [viewerLayers.reference.id],
  });
  strip.setLocalPosition(position.x, position.y, position.z);
  strip.setLocalScale(scale.x, scale.y, scale.z);
  parent.addChild(strip);
  return strip;
}

function createGridSegment(name, position, scale, material, parent) {
  return createStrip(name, position, scale, material, parent);
}

function ensureCalibrationReference() {
  if (calibrationReferenceRoot) {
    return calibrationReferenceRoot;
  }

  calibrationReferenceRoot = new Entity('CalibrationReference');
  calibrationReferenceRoot.enabled = false;
  app.root.addChild(calibrationReferenceRoot);

  const minorGridMaterial = createReferenceMaterial('CalibrationGridMinor', GRID_MINOR_COLOR);
  const majorGridMaterial = createReferenceMaterial('CalibrationGridMajor', GRID_MAJOR_COLOR);
  const axisXMaterial = createReferenceMaterial('CalibrationAxisX', AXIS_X_COLOR);
  const axisZMaterial = createReferenceMaterial('CalibrationAxisZ', AXIS_Z_COLOR);
  const size = CALIBRATION_GRID_HALF_SIZE;
  const step = CALIBRATION_GRID_STEP;
  const steps = Math.round(size / step);
  const length = size * 2;

  for (let index = -steps; index <= steps; index += 1) {
    if (index === 0) {
      continue;
    }

    const value = index * step;
    const isMajor = index % CALIBRATION_GRID_MAJOR_EVERY === 0;
    const material = isMajor ? majorGridMaterial : minorGridMaterial;
    const width = isMajor ? CALIBRATION_GRID_MAJOR_WIDTH : CALIBRATION_GRID_MINOR_WIDTH;

    for (let segmentIndex = -steps; segmentIndex < steps; segmentIndex += 1) {
      const segmentCenter = (segmentIndex + 0.5) * step;
      createGridSegment(
        `GridZ_${index}_${segmentIndex}`,
        { x: value, y: 0, z: segmentCenter },
        { x: width, y: CALIBRATION_GRID_THICKNESS, z: step * 1.02 },
        material,
        calibrationReferenceRoot
      );
      createGridSegment(
        `GridX_${index}_${segmentIndex}`,
        { x: segmentCenter, y: 0, z: value },
        { x: step * 1.02, y: CALIBRATION_GRID_THICKNESS, z: width },
        material,
        calibrationReferenceRoot
      );
    }
  }

  createStrip(
    'AxisX',
    { x: 0, y: CALIBRATION_GRID_THICKNESS * 2, z: 0 },
    { x: length, y: CALIBRATION_AXIS_WIDTH, z: CALIBRATION_AXIS_WIDTH },
    axisXMaterial,
    calibrationReferenceRoot
  );
  createStrip(
    'AxisZ',
    { x: 0, y: CALIBRATION_GRID_THICKNESS * 2, z: 0 },
    { x: CALIBRATION_AXIS_WIDTH, y: CALIBRATION_AXIS_WIDTH, z: length },
    axisZMaterial,
    calibrationReferenceRoot
  );

  return calibrationReferenceRoot;
}

function getCalibrationHint(enabled) {
  if (!enabled) {
    return DEFAULT_VIEW_HINT;
  }
  return calibrationTool === CALIBRATION_TOOL_TRANSLATE
    ? '校准模式：拖动移动箭头平移模型，使商品对齐世界原点'
    : '校准模式：拖动旋转环调整模型朝向';
}

function isCalibrationWorkflowActive() {
  return calibrationWorkflowMode != null;
}

function isInitialViewWorkflowActive() {
  return initialViewWorkflowMode;
}

function setCalibrationButtonState(enabled) {
  if (readOnlyMode) {
    hintLabel.textContent = DEFAULT_VIEW_HINT;
    return;
  }

  if (isCalibrationWorkflowActive()) {
    calibrateButton.hidden = true;
    calibrationRotateButton.hidden = true;
    calibrationTranslateButton.hidden = true;
    saveCalibrationButton.hidden = true;
    cancelCalibrationButton.hidden = true;
    setInitialViewButton.disabled = true;
    animationToggleButton.disabled = true;
    return;
  }

  calibrateButton.textContent = enabled ? '退出校准' : '校准坐标';
  calibrateButton.classList.toggle('primary', enabled);
  calibrationRotateButton.hidden = !enabled;
  calibrationTranslateButton.hidden = !enabled;
  calibrationRotateButton.classList.toggle('primary', enabled && calibrationTool === CALIBRATION_TOOL_ROTATE);
  calibrationTranslateButton.classList.toggle('primary', enabled && calibrationTool === CALIBRATION_TOOL_TRANSLATE);
  calibrationRotateButton.setAttribute('aria-pressed', String(enabled && calibrationTool === CALIBRATION_TOOL_ROTATE));
  calibrationTranslateButton.setAttribute('aria-pressed', String(enabled && calibrationTool === CALIBRATION_TOOL_TRANSLATE));
  saveCalibrationButton.hidden = !enabled;
  cancelCalibrationButton.hidden = !enabled;
  setInitialViewButton.disabled = enabled || initialViewMode || animationMode;
  animationToggleButton.disabled = enabled || initialViewMode;
  hintLabel.textContent = getCalibrationHint(enabled);
}

function ensureCalibrationGizmoLayer(cameraEntity) {
  if (viewerLayers.gizmo) {
    return viewerLayers.gizmo;
  }
  const gizmoLayer = Gizmo.createLayer(app, 'Calibration Overlay');
  viewerLayers.gizmo = gizmoLayer;
  cameraEntity.camera.layers = [
    viewerLayers.world.id,
    viewerLayers.reference.id,
    viewerLayers.splat.id,
    viewerLayers.gizmo.id,
  ];
  return gizmoLayer;
}

function bindCalibrationGizmoEvents(gizmo) {
  gizmo.on('transform:start', () => {
    calibrationDragging = true;
    controls?.setEnabled(false);
  });
  gizmo.on('transform:end', () => {
    calibrationDragging = false;
    refreshOrbitTarget(true);
    controls?.setEnabled(calibrationMode);
    scheduleCalibrationWorkflowSave();
  });
}

function ensureRotateGizmo(cameraEntity) {
  if (rotateGizmo) {
    return rotateGizmo;
  }

  const gizmoLayer = ensureCalibrationGizmoLayer(cameraEntity);
  rotateGizmo = new RotateGizmo(cameraEntity.camera, gizmoLayer);
  rotateGizmo.coordSpace = 'world';
  rotateGizmo.rotationMode = 'absolute';
  rotateGizmo.size = 1.05;
  bindCalibrationGizmoEvents(rotateGizmo);
  rotateGizmo.detach();
  return rotateGizmo;
}

function ensureTranslateGizmo(cameraEntity) {
  if (translateGizmo) {
    return translateGizmo;
  }

  const gizmoLayer = ensureCalibrationGizmoLayer(cameraEntity);
  translateGizmo = new TranslateGizmo(cameraEntity.camera, gizmoLayer);
  translateGizmo.coordSpace = 'world';
  translateGizmo.size = 1.05;
  translateGizmo.axisPlaneSize = 0;
  translateGizmo.axisCenterSize = 0;
  ['xy', 'xz', 'yz', 'xyz'].forEach((shapeAxis) => translateGizmo.enableShape(shapeAxis, false));
  bindCalibrationGizmoEvents(translateGizmo);
  translateGizmo.detach();
  return translateGizmo;
}

function getActiveCalibrationGizmo() {
  return calibrationTool === CALIBRATION_TOOL_TRANSLATE ? translateGizmo : rotateGizmo;
}

function detachCalibrationGizmos() {
  rotateGizmo?.detach();
  translateGizmo?.detach();
}

function attachActiveCalibrationGizmo() {
  if (!calibrationMode || !modelRoot) {
    return;
  }

  detachCalibrationGizmos();
  getActiveCalibrationGizmo()?.attach([modelRoot]);
}

function setCalibrationTool(tool) {
  if (calibrationDragging || calibrationTool === tool) {
    return;
  }

  calibrationTool = tool;
  setCalibrationButtonState(calibrationMode);
  attachActiveCalibrationGizmo();
}

function setCalibrationMode(enabled) {
  if (enabled && (initialViewMode || animationMode)) {
    return;
  }

  if (!rotateGizmo || !translateGizmo || !modelRoot) {
    return;
  }

  calibrationMode = enabled;
  calibrationDragging = false;
  controls?.setEnabled(true);
  ensureCalibrationReference().enabled = enabled;
  setCalibrationButtonState(enabled);

  if (enabled) {
    calibrationStartRotation = modelRoot.getLocalRotation().clone();
    calibrationStartTranslation = modelRoot.getLocalPosition().clone();
    attachActiveCalibrationGizmo();
    return;
  }

  detachCalibrationGizmos();
  calibrationStartRotation = null;
  calibrationStartTranslation = null;
}

function cancelCalibration() {
  if (modelRoot && calibrationStartRotation) {
    modelRoot.setLocalRotation(calibrationStartRotation);
  }
  if (modelRoot && calibrationStartTranslation) {
    modelRoot.setLocalPosition(calibrationStartTranslation);
  }
  refreshOrbitTarget(true);
  setCalibrationMode(false);
}

function setInitialViewButtonState(enabled) {
  if (readOnlyMode) {
    hintLabel.textContent = DEFAULT_VIEW_HINT;
    return;
  }

  if (isInitialViewWorkflowActive()) {
    setInitialViewButton.hidden = true;
    confirmInitialViewButton.hidden = true;
    cancelInitialViewButton.hidden = true;
    calibrateButton.disabled = true;
    animationToggleButton.disabled = true;
    resetButton.disabled = false;
    return;
  }

  setInitialViewButton.hidden = enabled;
  confirmInitialViewButton.hidden = !enabled;
  cancelInitialViewButton.hidden = !enabled;
  confirmInitialViewButton.classList.toggle('primary', enabled);
  calibrateButton.disabled = enabled || animationMode;
  animationToggleButton.disabled = enabled || calibrationMode;
  resetButton.disabled = enabled || animationMode;
  hintLabel.textContent = enabled
    ? '设置初始视角：仅支持单指环绕调整，完成后点击“确认”保存'
    : DEFAULT_VIEW_HINT;
}

function enterInitialViewMode() {
  if (!controls) {
    return;
  }

  if (calibrationMode) {
    hintLabel.textContent = '请先保存或撤销坐标校准，再设置初始视角';
    return;
  }
  if (animationMode) {
    hintLabel.textContent = '请先退出动画展示，再设置初始视角';
    return;
  }

  initialViewMode = true;
  controls.reset();
  controls.setSinglePointerOnly(true);
  setInitialViewButtonState(true);
}

function exitInitialViewMode({ resetView = false, hint = DEFAULT_VIEW_HINT } = {}) {
  if (!initialViewMode) {
    return;
  }

  if (resetView) {
    controls?.reset();
  }
  initialViewMode = false;
  controls?.setSinglePointerOnly(false);
  setInitialViewButtonState(false);
  hintLabel.textContent = hint;
}

function updateAnimationProgress() {
  animationProgressBar.style.transform = `scaleX(${clamp(animationProgress, 0, 1)})`;
}

function setAnimationProgressVisible(visible) {
  animationProgressWrap.hidden = !visible;
}

function setAnimationControlsVisible(visible) {
  animationControlsVisible = visible;
  animationPanel.classList.toggle('controls-hidden', !visible);
}

function revealAnimationControls() {
  if (!animationMode) {
    return;
  }
  setAnimationControlsVisible(true);
  setAnimationProgressVisible(true);
}

function beginAnimationControlsTapCandidate(event) {
  if (!animationMode || animationControlsVisible) {
    animationControlsTapCandidate = null;
    return;
  }
  animationControlsTapCandidate = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    moved: false,
  };
}

function updateAnimationControlsTapCandidate(event) {
  if (
    !animationControlsTapCandidate ||
    animationControlsTapCandidate.pointerId !== event.pointerId
  ) {
    return;
  }

  const distance = Math.hypot(
    event.clientX - animationControlsTapCandidate.x,
    event.clientY - animationControlsTapCandidate.y
  );
  if (distance > 8) {
    animationControlsTapCandidate.moved = true;
  }
}

function resolveAnimationControlsTapCandidate(event) {
  if (
    !animationControlsTapCandidate ||
    animationControlsTapCandidate.pointerId !== event.pointerId
  ) {
    return;
  }

  const shouldReveal = !animationControlsTapCandidate.moved;
  animationControlsTapCandidate = null;
  if (shouldReveal) {
    revealAnimationControls();
  }
}

function clearAnimationControlsTapCandidate(event) {
  if (
    animationControlsTapCandidate &&
    animationControlsTapCandidate.pointerId === event.pointerId
  ) {
    animationControlsTapCandidate = null;
  }
}

function resetViewerView() {
  if (!controls) {
    return;
  }

  if (animationMode && animationBaseViewState) {
    pauseAnimationPlayback({
      hideProgress: false,
      hint: '已重置到默认展示视角，点击 Play 继续动画',
    });
    animationProgress = 0;
    updateAnimationProgress();
    controls.setViewState(animationBaseViewState);
    revealAnimationControls();
    return;
  }

  controls.reset();
}

function setAnimationButtonState() {
  animationToggleButton.textContent = animationMode ? '退出动画' : '动画展示';
  animationToggleButton.classList.toggle('primary', animationMode);
  animationPanel.hidden = !animationMode;
  animationPlayButton.textContent = animationPlaying ? 'Pause' : 'Play';
  animationPlayButton.classList.toggle('primary', animationPlaying);
  if (!readOnlyMode) {
    calibrateButton.disabled = animationMode || initialViewMode;
    setInitialViewButton.disabled = animationMode || calibrationMode || initialViewMode;
  }
  resetButton.disabled = animationMode || initialViewMode;

  if (!animationMode) {
    setAnimationControlsVisible(true);
    setAnimationProgressVisible(false);
  }
}

function stopAnimationFrame() {
  if (animationFrameId != null) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
}

function pauseAnimationPlayback({ hideProgress = true, hint = '动画已暂停，点击 Play 从断点继续' } = {}) {
  if (animationPlaying) {
    stopAnimationFrame();
    animationPlaying = false;
  }
  if (hideProgress) {
    setAnimationProgressVisible(false);
  }
  setAnimationButtonState();
  hintLabel.textContent = hint;
}

function handleAnimationUserInteraction() {
  if (!animationMode) {
    return;
  }
  pauseAnimationPlayback({
    hideProgress: false,
    hint: '检测到手势操作，动画已暂停；点击 Play 回到断点继续',
  });
  setAnimationControlsVisible(false);
}

function stepAnimationPlayback(timestamp) {
  if (!animationPlaying || !animationBaseViewState) {
    return;
  }

  const elapsed = Math.max(0, timestamp - animationLastFrameAt);
  animationLastFrameAt = timestamp;
  animationProgress = (animationProgress + elapsed / ANIMATION_TURN_DURATION_MS) % 1;
  controls?.setHorizontalOrbitProgress(animationBaseViewState, animationProgress);
  updateAnimationProgress();
  animationFrameId = requestAnimationFrame(stepAnimationPlayback);
}

function startAnimationPlayback() {
  if (!controls || !animationMode) {
    return;
  }

  if (!animationBaseViewState) {
    controls.reset();
    animationBaseViewState = controls.getViewState();
    animationProgress = 0;
  }

  stopAnimationFrame();
  controls.setHorizontalOrbitProgress(animationBaseViewState, animationProgress);
  updateAnimationProgress();
  setAnimationControlsVisible(true);
  setAnimationProgressVisible(true);
  animationPlaying = true;
  animationLastFrameAt = performance.now();
  setAnimationButtonState();
  hintLabel.textContent = '动画展示：正在自动环绕，触摸画面会暂停动画';
  animationFrameId = requestAnimationFrame(stepAnimationPlayback);
}

function toggleAnimationPlayback() {
  if (animationPlaying) {
    pauseAnimationPlayback();
    return;
  }
  startAnimationPlayback();
}

function enterAnimationMode() {
  if (!controls) {
    return;
  }
  if (calibrationMode) {
    hintLabel.textContent = '请先保存或撤销坐标校准，再进入动画展示';
    return;
  }
  if (initialViewMode) {
    hintLabel.textContent = '请先确认或取消初始视角设置，再进入动画展示';
    return;
  }

  animationMode = true;
  animationPlaying = false;
  animationProgress = 0;
  controls.reset();
  animationBaseViewState = controls.getViewState();
  controls.onUserInteractionStart = handleAnimationUserInteraction;
  updateAnimationProgress();
  setAnimationControlsVisible(true);
  setAnimationProgressVisible(true);
  setAnimationButtonState();
  hintLabel.textContent = '动画展示：点击 Play 开始 360° 水平环绕';
}

function exitAnimationMode() {
  if (!animationMode) {
    return;
  }

  pauseAnimationPlayback({ hideProgress: true, hint: DEFAULT_VIEW_HINT });
  animationMode = false;
  animationPlaying = false;
  animationProgress = 0;
  animationBaseViewState = null;
  controls.onUserInteractionStart = null;
  setAnimationControlsVisible(true);
  setAnimationButtonState();
  hintLabel.textContent = DEFAULT_VIEW_HINT;
}

function toggleAnimationMode() {
  if (animationMode) {
    exitAnimationMode();
    return;
  }
  enterAnimationMode();
}

function queueCalibrationWorkflowSave() {
  if (!isCalibrationWorkflowActive() || !calibrationMode) {
    return;
  }
  if (calibrationSaveInFlight) {
    calibrationSaveQueued = true;
    return;
  }
  calibrationSaveInFlight = true;
  saveCalibration({ fromWorkflow: true })
    .catch((error) => {
      console.error(error);
    })
    .finally(() => {
      calibrationSaveInFlight = false;
      if (calibrationSaveQueued) {
        calibrationSaveQueued = false;
        queueCalibrationWorkflowSave();
      }
    });
}

function scheduleCalibrationWorkflowSave() {
  if (!isCalibrationWorkflowActive() || calibrationDragging) {
    return;
  }
  window.clearTimeout(calibrationAutoSaveTimer);
  calibrationAutoSaveTimer = window.setTimeout(() => {
    queueCalibrationWorkflowSave();
  }, 180);
}

function queueInitialViewWorkflowSave() {
  if (!isInitialViewWorkflowActive() || !initialViewMode) {
    return;
  }
  if (initialViewSaveInFlight) {
    initialViewSaveQueued = true;
    return;
  }
  initialViewSaveInFlight = true;
  saveInitialView({ fromWorkflow: true })
    .catch((error) => {
      console.error(error);
    })
    .finally(() => {
      initialViewSaveInFlight = false;
      if (initialViewSaveQueued) {
        initialViewSaveQueued = false;
        queueInitialViewWorkflowSave();
      }
    });
}

function scheduleInitialViewWorkflowSave() {
  if (!isInitialViewWorkflowActive() || !initialViewMode) {
    return;
  }
  window.clearTimeout(initialViewAutoSaveTimer);
  initialViewAutoSaveTimer = window.setTimeout(() => {
    queueInitialViewWorkflowSave();
  }, 180);
}

function activateWorkflowMode() {
  if (calibrationWorkflowMode === 'rotate') {
    setCalibrationTool(CALIBRATION_TOOL_ROTATE);
    setCalibrationMode(true);
    return;
  }
  if (calibrationWorkflowMode === 'translate') {
    setCalibrationTool(CALIBRATION_TOOL_TRANSLATE);
    setCalibrationMode(true);
    return;
  }
  if (initialViewWorkflowMode) {
    enterInitialViewMode();
  }
}

function updateViewerCameraQuery(cameraConfig) {
  const url = new URL(window.location.href);
  const [cameraRx, cameraRy, cameraRz] = cameraConfig.camera_rotation_deg;
  url.searchParams.set('cam_rx', String(cameraRx));
  url.searchParams.set('cam_ry', String(cameraRy));
  url.searchParams.set('cam_rz', String(cameraRz));
  url.searchParams.set('cam_dist', String(cameraConfig.camera_distance));
  window.history.replaceState(null, '', url);
}

async function saveInitialView({ fromWorkflow = false } = {}) {
  if (!taskId) {
    hintLabel.textContent = '当前 viewer URL 缺少 task_id，无法保存初始视角';
    return;
  }
  if (!controls) {
    return;
  }

  const cameraConfig = controls.getCameraConfig();
  if (!fromWorkflow) {
    confirmInitialViewButton.disabled = true;
    confirmInitialViewButton.textContent = '保存中...';
  }

  try {
    const response = await fetch(`/api/v1/reconstructions/${encodeURIComponent(taskId)}/viewer`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(cameraConfig),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }

    controls.setCurrentAsDefault();
    updateViewerCameraQuery(cameraConfig);
    if (fromWorkflow) {
      hintLabel.textContent = `初始视角已自动保存：旋转 ${cameraConfig.camera_rotation_deg.join(', ')}°，距离 ${cameraConfig.camera_distance}`;
    } else {
      exitInitialViewMode({
        hint: `初始视角已保存：旋转 ${cameraConfig.camera_rotation_deg.join(', ')}°，距离 ${cameraConfig.camera_distance}`,
      });
    }
  } catch (error) {
    console.error(error);
    hintLabel.textContent = '初始视角保存失败，请查看后端日志';
  } finally {
    if (!fromWorkflow) {
      confirmInitialViewButton.disabled = false;
      confirmInitialViewButton.textContent = '确认';
    }
  }
}

async function saveCalibration({ fromWorkflow = false } = {}) {
  if (!taskId) {
    hintLabel.textContent = '当前 viewer URL 缺少 task_id，无法保存校准';
    return;
  }

  if (!fromWorkflow) {
    saveCalibrationButton.disabled = true;
    saveCalibrationButton.textContent = '保存中...';
  }

  try {
    const response = await fetch(`/api/v1/reconstructions/${encodeURIComponent(taskId)}/viewer`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model_rotation_deg: getModelRotationDeg(),
        model_translation: getModelTranslation(),
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }

    savedModelRotation = modelRoot.getLocalRotation().clone();
    savedModelTranslation = modelRoot.getLocalPosition().clone();
    calibrationStartRotation = savedModelRotation.clone();
    calibrationStartTranslation = savedModelTranslation.clone();
    refreshOrbitTarget(true);
    hintLabel.textContent = fromWorkflow
      ? `校准已自动保存：旋转 ${getModelRotationDeg().join(', ')}°，平移 ${getModelTranslation().join(', ')}`
      : `校准已保存：旋转 ${getModelRotationDeg().join(', ')}°，平移 ${getModelTranslation().join(', ')}`;
  } catch (error) {
    console.error(error);
    hintLabel.textContent = '校准保存失败，请查看后端日志';
  } finally {
    if (!fromWorkflow) {
      saveCalibrationButton.disabled = false;
      saveCalibrationButton.textContent = '保存校准';
    }
  }
}

async function boot() {
  try {
    configureViewerMode();
    setStatus('正在检查本地模型缓存...', modelUrl);
    assets[0].file.contents = loadModelResponseWithCache(modelUrl, {
      version: modelVersion,
      onSource: (source) => {
        modelLoadSource = source;
      },
      onStatus: setStatus,
    });
    await waitForPaint();
    await new Promise((resolve, reject) => {
      loader.load((err) => (err ? reject(err) : resolve()));
    });

    const camera = new Entity('Camera');
    camera.addComponent('camera', {
      clearColor: new Color(0.04, 0.06, 0.08),
    });
    app.root.addChild(camera);

    modelRoot = new Entity('ModelRoot');
    modelRoot.setLocalPosition(displayConfig.modelTranslation);
    modelRoot.setLocalRotation(displayConfig.modelRotation);
    modelRoot.setLocalScale(displayConfig.modelScale, displayConfig.modelScale, displayConfig.modelScale);
    app.root.addChild(modelRoot);
    savedModelRotation = modelRoot.getLocalRotation().clone();
    savedModelTranslation = modelRoot.getLocalPosition().clone();

    productSplat = new Entity('Product');
    productSplat.addComponent('gsplat', {
      asset: assets[0],
    });
    productSplat.gsplat.layers = [viewerLayers.splat.id];
    modelRoot.addChild(productSplat);

    controls = new OrbitControls(camera, canvas);
    controls.setDefaults(buildHomeView(productSplat));
    controls.onUserInteractionEnd = () => {
      scheduleInitialViewWorkflowSave();
    };
    ensureRotateGizmo(camera);
    ensureTranslateGizmo(camera);

    resetButton.addEventListener('click', () => resetViewerView());
    minimalResetButton.addEventListener('click', () => resetViewerView());
    canvas.addEventListener('pointerdown', (event) => beginAnimationControlsTapCandidate(event));
    canvas.addEventListener('pointermove', (event) => updateAnimationControlsTapCandidate(event));
    canvas.addEventListener('pointerup', (event) => resolveAnimationControlsTapCandidate(event));
    canvas.addEventListener('pointercancel', (event) => clearAnimationControlsTapCandidate(event));
    if (!readOnlyMode) {
      calibrateButton.addEventListener('click', () => setCalibrationMode(!calibrationMode));
      calibrationRotateButton.addEventListener('click', () => setCalibrationTool(CALIBRATION_TOOL_ROTATE));
      calibrationTranslateButton.addEventListener('click', () => setCalibrationTool(CALIBRATION_TOOL_TRANSLATE));
      saveCalibrationButton.addEventListener('click', () => saveCalibration());
      cancelCalibrationButton.addEventListener('click', () => cancelCalibration());
      setInitialViewButton.addEventListener('click', () => enterInitialViewMode());
      confirmInitialViewButton.addEventListener('click', () => saveInitialView());
      cancelInitialViewButton.addEventListener('click', () => exitInitialViewMode({ resetView: true }));
    }
    animationToggleButton.addEventListener('click', () => toggleAnimationMode());
    animationPlayButton.addEventListener('click', () => toggleAnimationPlayback());
    setAnimationButtonState();
    activateWorkflowMode();

    hideOverlay();
    if (autoPlayMode) {
      enterAnimationMode();
      startAnimationPlayback();
    }
  } catch (error) {
    console.error(error);
    setStatus(
      '模型加载失败',
      '请确认模型文件可访问，并且产物是 PlayCanvas 支持的 PLY 或 SOG 格式。'
    );
  }
}

boot();
