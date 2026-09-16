const $ = (id) => document.getElementById(id);
const app = { snapshot: { devices: [], events: [], demo_running: false }, selectedEventId: null, stream: null, streamConnected: false, apiHealthy: false, lastMessage: null };
const labels = {
  normal: ['Normal activity', '正常活动'],
  suspected: ['Fall suspected', '疑似跌倒'],
  confirmed: ['Fall confirmed', '已确认跌倒'],
  cleared: ['Alert cleared', '告警已解除']
};
const eventLabels = {
  suspected: ['Fall suspected', '疑似跌倒'],
  confirmed: ['Fall confirmed', '已确认跌倒'],
  cleared: ['Alert cleared', '告警已解除']
};
const connections = [[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16],[0,5],[0,6]];

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function percent(value) { return Number.isFinite(Number(value)) ? Math.round(Number(value) * 100) : null; }
function metric(value, digits = 1) { return Number.isFinite(Number(value)) ? Number(value).toFixed(digits).replace(/\.0$/, '') : '—'; }
function timeLabel(value, long = false) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('en-GB', {month: long ? 'short' : undefined, day: long ? 'numeric' : undefined, hour:'2-digit',minute:'2-digit',second:long ? undefined : '2-digit',hour12:false}).format(date);
}
function relativeTime(value) {
  if (!value) return '—';
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago / ${seconds}秒前`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago / ${Math.floor(seconds / 60)}分钟前`;
  return timeLabel(value, true);
}
async function api(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type':'application/json'}, ...options});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function route() {
  const requested = location.hash.slice(1) || 'overview';
  const page = document.getElementById(requested) || $('overview');
  document.querySelectorAll('.page').forEach(el => el.classList.toggle('active', el === page));
  document.querySelectorAll('.nav-link').forEach(el => {el.classList.toggle('active', el.dataset.page === page.id);if(el.dataset.page === page.id) el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  $('crumb').innerHTML = `Workspace <span>/</span> ${escapeHTML(page.dataset.title)} <small>${escapeHTML(page.dataset.zh)}</small>`;
  if (page.id === 'live') drawPose(activeDevice()?.online ? activeDevice().keypoints : []);
  window.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
}
function navigate(pageId) {
  if (!document.getElementById(pageId)?.classList.contains('page')) return;
  if (location.hash !== `#${pageId}`) history.pushState({page:pageId}, '', `#${pageId}`);
  route();
}
function activeDevice() { return app.snapshot.devices.find(d => d.online) || app.snapshot.devices[0] || null; }
function setSnapshot(snapshot, mergeEvents = false) {
  if (!snapshot || !Array.isArray(snapshot.devices) || !Array.isArray(snapshot.events)) return;
  if (mergeEvents) {
    const events = new Map(app.snapshot.events.map(event => [event.id, event]));
    snapshot.events.forEach(event => events.set(event.id, event));
    app.snapshot = {...snapshot, events: [...events.values()].sort((a,b) => b.id - a.id).slice(0,100)};
  } else {
    app.snapshot = snapshot;
  }
  app.lastMessage = Date.now();
  render();
}
function render() {
  const device = activeDevice();
  const state = device?.alert_state || null;
  const isDemo = device?.source === 'demo';
  const online = Boolean(device?.online);
  const liveDevice = online ? device : null;
  const confirmedUnacked = app.snapshot.events.filter(e => e.state === 'confirmed' && !e.acknowledged_at).length;
  $('navAlertCount').hidden = confirmedUnacked === 0;
  $('navAlertCount').textContent = confirmedUnacked;
  const badge = $('sourceBadge');
  badge.className = `source-badge ${online ? isDemo ? 'demo' : 'live' : ''}`;
  badge.innerHTML = online ? isDemo ? '<i></i> SYNTHETIC DEMO <small>合成演示</small>' : '<i></i> LIVE DATA <small>实时数据</small>' : '<i></i> WAITING FOR DATA <small>等待数据</small>';
  $('lastUpdate').textContent = device ? relativeTime(device.received_at) : '—';
  $('heroDevice').textContent = device?.device_id || '—';
  $('heroTime').textContent = device ? timeLabel(device.received_at) : '—';
  $('metricDevice').textContent = `Selected device / 当前设备：${device?.device_id || '—'}`;
  $('edgeFps').innerHTML = `${liveDevice ? metric(liveDevice.edge_fps) : '—'}<small>fps</small>`;
  $('poseQuality').innerHTML = `${liveDevice ? percent(liveDevice.pose_quality) : '—'}<small>%</small>`;
  $('qualityBar').style.width = `${liveDevice ? percent(liveDevice.pose_quality) : 0}%`;
  $('networkRtt').innerHTML = `${liveDevice ? metric(liveDevice.network_rtt_ms) : '—'}<small>ms</small>`;
  $('fallProbability').innerHTML = `${liveDevice ? percent(liveDevice.fall_probability) : '—'}<small>%</small>`;
  $('pipeEdge').textContent = online ? 'Online / 在线' : 'Awaiting input / 等待输入';
  $('pipeCloud').textContent = app.apiHealthy ? 'Healthy / 正常' : 'Checking / 检查中';
  $('pipeView').textContent = app.streamConnected ? 'Streaming / 推送中' : 'Ready / 已就绪';
  const hero = $('statusHero');
  hero.className = `status-hero ${online && state === 'confirmed' ? 'alert' : online && state === 'suspected' ? 'suspected' : ''}`;
  $('heroMode').textContent = online ? isDemo ? 'SYNTHETIC DEMO / 合成演示' : 'LIVE MONITORING / 实时监测' : 'NO SIGNAL / 暂无信号';
  $('heroKicker').textContent = online ? state === 'confirmed' ? 'ACTION REQUIRED · 需要关注' : state === 'suspected' ? 'REVIEWING SIGNAL · 正在复核' : 'SYSTEM ACTIVE · 系统运行中' : 'AWAITING DEVICE DATA · 等待设备数据';
  $('heroTitle').textContent = online ? (labels[state] || labels.normal)[0] : 'Monitoring is ready';
  $('heroSubtitle').textContent = online ? (labels[state] || labels.normal)[1] + (isDemo ? ' · 合成演示数据' : '') : '监测服务已就绪，等待边缘设备或演示数据。';
  $('heroSymbol').textContent = online && state === 'confirmed' ? '!' : online && state === 'suspected' ? '?' : '○';
  $('overviewEvents').innerHTML = eventRows(app.snapshot.events.slice(0,3), false);
  $('eventTotal').textContent = `${app.snapshot.events.length} EVENTS`;
  const filter = $('eventFilter').value;
  $('allEvents').innerHTML = eventRows(app.snapshot.events.filter(e => filter === 'all' || e.state === filter), true);
  renderDetail();
  renderLive(liveDevice, online);
  renderSystem();
}
function eventRows(events, selectable) {
  if (!events.length) return `<div class="empty-state">No events recorded yet.<br>尚无事件记录。${selectable ? '<br>Start a demo or connect a model sender. / 启动演示或连接模型。' : ''}</div>`;
  return events.map(e => `<button type="button" class="event-row ${selectable && app.selectedEventId === e.id ? 'selected' : ''}" data-event-id="${e.id}" aria-label="Open event ${e.id}"><span class="event-state-icon ${escapeHTML(e.state)}">${e.state === 'confirmed' ? '!' : e.state === 'suspected' ? '?' : '✓'}</span><span class="event-row-main"><strong>${escapeHTML((eventLabels[e.state] || ['Alert','告警'])[0])} <span style="font-weight:500;color:#9baab2">/ ${escapeHTML((eventLabels[e.state] || ['Alert','告警'])[1])}</span></strong><small>${escapeHTML(e.device_id)} · ${e.source === 'demo' ? 'Synthetic demo / 合成演示' : 'Live reading / 实时读数'}${e.acknowledged_at ? ' · Acknowledged / 已处理' : ''}</small></span><span class="event-row-time">${escapeHTML(timeLabel(e.timestamp, true))}</span><span class="event-row-arrow">›</span></button>`).join('');
}
function renderDetail() {
  const e = app.snapshot.events.find(item => item.id === app.selectedEventId);
  if (!e) {
    $('eventDetail').innerHTML = '<div class="eyebrow">EVENT DETAILS <span>事件详情</span></div><h3>Select an event <span>选择事件</span></h3><p class="detail-empty">Choose a row to inspect its model score, device and acknowledgment.<br>选择一条记录查看模型分数、设备及处理状态。</p>';
    return;
  }
  const title = eventLabels[e.state] || ['Alert','告警'];
  $('eventDetail').innerHTML = `<div class="eyebrow">EVENT #${e.id} <span>事件详情</span></div><div class="detail-state ${escapeHTML(e.state)}">${escapeHTML(title[0])}</div><div class="detail-zh">${escapeHTML(title[1])}</div><div class="detail-score">Fall probability / 跌倒概率 <strong>${percent(e.fall_probability)}%</strong></div><div class="detail-line"><span>Device / 设备</span><strong>${escapeHTML(e.device_id)}</strong></div><div class="detail-line"><span>Recorded / 记录时间</span><strong>${escapeHTML(timeLabel(e.timestamp, true))}</strong></div><div class="detail-line"><span>Pose quality / 姿态质量</span><strong>${percent(e.pose_quality)}%</strong></div><div class="detail-line"><span>Model / 模型</span><strong>${escapeHTML(e.model)}</strong></div><div class="detail-line"><span>Source / 来源</span><strong>${e.source === 'demo' ? 'Synthetic demo / 合成演示' : 'Live reading / 实时读数'}</strong></div>${e.acknowledged_at ? `<div class="ack-label">Acknowledged / 已处理 · ${escapeHTML(timeLabel(e.acknowledged_at, true))}${e.note ? `<br>${escapeHTML(e.note)}` : ''}</div>` : e.state === 'confirmed' ? `<form class="ack-form" data-event-id="${e.id}"><label for="ackNote">Response note / 处理备注（可选）</label><input id="ackNote" name="note" maxlength="200" placeholder="Reviewed by team / 团队已复核"><button type="submit" class="button button-dark">Acknowledge event <span>确认事件</span></button></form>` : ''}`;
}
function renderLive(device, online) {
  $('liveConnection').textContent = app.streamConnected ? 'STREAMING' : app.apiHealthy ? 'CONNECTED' : 'WAITING';
  $('poseStatus').textContent = device?.keypoints?.length === 17 ? device.source === 'demo' ? 'SYNTHETIC POSE' : 'POSE RECEIVED' : 'NO POSE DATA';
  $('frameSeq').textContent = `FRAME ${device?.frame_seq ?? '—'}`;
  $('decisionState').textContent = online ? (labels[device.alert_state] || labels.normal)[0] : 'No reading';
  $('decisionStateZh').textContent = online ? (labels[device.alert_state] || labels.normal)[1] : '暂无读数';
  $('modelName').textContent = device?.model || '—';
  $('decisionQuality').textContent = device ? `${percent(device.pose_quality)}%` : '—';
  $('decisionTime').textContent = device ? timeLabel(device.received_at) : '—';
  $('ringValue').textContent = device ? `${percent(device.fall_probability)}%` : '—';
  $('probRing').style.background = `conic-gradient(${device?.alert_state === 'confirmed' ? '#d97973' : device?.alert_state === 'suspected' ? '#dfae70' : '#76bfae'} ${(device ? device.fall_probability : 0) * 360}deg, #eaf0ee 0deg)`;
  const scores = device?.branch_scores || {};
  $('optionalScores').hidden = !Object.keys(scores).length;
  $('optionalScores').innerHTML = Object.entries(scores).map(([key,value]) => `<div><span>${key === 'pose' ? 'Pose branch / 姿态分支' : 'Geometry branch / 几何分支'}</span><strong>${percent(value)}%</strong></div>`).join('');
  document.querySelectorAll('.state-step').forEach(el => el.classList.toggle('active', online && el.dataset.state === device.alert_state));
  drawPose(device?.keypoints || []);
}
function drawPose(points) {
  const canvas = $('poseCanvas');
  const context = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  context.clearRect(0,0,w,h);
  context.strokeStyle = 'rgba(157,207,205,.08)';
  context.lineWidth = 1;
  for (let x=0;x<w;x+=44) {context.beginPath();context.moveTo(x,0);context.lineTo(x,h);context.stroke();}
  for (let y=0;y<h;y+=44) {context.beginPath();context.moveTo(0,y);context.lineTo(w,y);context.stroke();}
  context.strokeStyle = 'rgba(145,220,209,.10)'; context.lineWidth = 2;
  context.beginPath();context.ellipse(w/2,h/2,144,172,0,0,Math.PI*2);context.stroke();
  if (points.length !== 17) {
    context.textAlign = 'center';context.fillStyle = '#7b9ca5';context.font = '700 14px DM Sans, sans-serif';context.fillText('AWAITING ANONYMOUS POSE',w/2,h/2-4);
    context.font = '12px DM Sans, sans-serif';context.fillText('等待匿名骨架数据',w/2,h/2+21);
    return;
  }
  const locate = p => [w*.2 + p[0]*w*.6, h*.04 + p[1]*h*.91];
  context.lineCap='round';context.lineJoin='round';context.strokeStyle='#76d7bf';context.lineWidth=5;context.shadowBlur=14;context.shadowColor='rgba(108,221,185,.30)';
  connections.forEach(([a,b]) => {if(points[a][2]<.2||points[b][2]<.2)return;const [x1,y1]=locate(points[a]),[x2,y2]=locate(points[b]);context.beginPath();context.moveTo(x1,y1);context.lineTo(x2,y2);context.stroke();});
  context.shadowBlur=0;
  points.forEach(p => {if(p[2]<.2)return;const [x,y]=locate(p);context.beginPath();context.arc(x,y,5,0,Math.PI*2);context.fillStyle='#cef8df';context.fill();context.strokeStyle='#3a9d92';context.lineWidth=2;context.stroke();});
}
function renderSystem() {
  $('apiUrl').textContent = `${location.origin}/api/health`;
  $('apiHealth').textContent = app.apiHealthy ? 'HEALTHY' : 'UNAVAILABLE';
  $('apiHealth').className = `health-status ${app.apiHealthy ? 'ok' : 'bad'}`;
  $('dbHealth').textContent = app.apiHealthy ? 'PERSISTING' : 'UNKNOWN';
  $('dbHealth').className = `health-status ${app.apiHealthy ? 'ok' : ''}`;
  $('streamHealth').textContent = app.streamConnected ? 'STREAMING' : 'RECONNECTING';
  $('streamHealth').className = `health-status ${app.streamConnected ? 'ok' : ''}`;
  $('deviceList').innerHTML = app.snapshot.devices.length ? app.snapshot.devices.map(d => `<div class="device-entry"><strong>${escapeHTML(d.device_id)}</strong><span class="${d.online ? 'online' : 'offline'}">${d.online ? 'ONLINE / 在线' : 'STALE / 数据过期'}</span><p>${d.source === 'demo' ? 'Synthetic demo / 合成演示' : 'Live reading / 实时读数'} · ${escapeHTML(relativeTime(d.received_at))}<br>Model / 模型：${escapeHTML(d.model)} · FPS：${metric(d.edge_fps)}</p></div>`).join('') : '<div class="empty-state">No device readings yet.<br>尚无设备读数。</div>';
  $('contractExample').textContent = `POST /api/pose\nX-Device-Token: <configured token>\n\n{\n  "device_id": "edge-device-01",\n  "timestamp": "2026-09-15T08:00:00Z",\n  "frame_seq": 1001,\n  "pose_quality": 0.91,\n  "edge_fps": 5.4,\n  "keypoints": [[0.50, 0.12, 0.94], ...]\n}\n\nResearch model / 研究模型 → POST /api/ingest`;
}
async function refresh() {
  try {
    const [health, snapshot] = await Promise.all([api('/api/health'), api('/api/snapshot')]);
    app.apiHealthy = health.status === 'ok';
    setSnapshot(snapshot);
  } catch (error) {
    app.apiHealthy = false;
    renderSystem();
    console.warn('Dashboard refresh failed:', error);
  }
}
function connectStream() {
  if (app.stream) app.stream.close();
  const stream = new EventSource('/api/stream');
  app.stream = stream;
  stream.onopen = () => {app.streamConnected = true; render();};
  stream.onmessage = event => {try {const message = JSON.parse(event.data);if(message.type === 'snapshot') setSnapshot(message.data, true);}catch(error){console.warn('Invalid stream event', error);}};
  stream.onerror = () => {app.streamConnected = false;render();};
}
function demoMessage(text, kind = '') {$('demoMessage').textContent = text;$('demoMessage').className = `demo-message ${kind}`;}
async function demoAction(path, success) {
  try {await api(path, {method:'POST'});demoMessage(success,'success');await refresh();}
  catch (error) {demoMessage(`Error / 错误：${error.message}`,'error');}
}
let localCameraStream = null;
let localPoseModelPromise = null;
let localPoseFrame = 0;
let localCameraGeneration = 0;
let lastLocalPoseTime = 0;
let lastLocalVideoTime = -1;
let lastCloudPoseTime = 0;
let localCloudPending = false;
let localCloudFrameSeq = 0;
let localCloudSession = null;
let cloudModelCatalog = [];
let selectedCloudModelId = 'punpayut_transformer_tflite';
const localPoseConnections = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[25,27],[27,29],[29,31],[24,26],[26,28],[28,30],[30,32]];

function updateModelDetails() {
  const model = cloudModelCatalog.find(item => item.id === selectedCloudModelId);
  if (!model) return;
  $('modelInfoName').textContent = `${model.name_en} / ${model.name_zh}`;
  $('modelInfoPurpose').textContent = `${model.purpose_en} / ${model.purpose_zh}`;
  $('modelInfoSource').textContent = model.source || '—';
  $('modelInfoRuntime').textContent = `${model.runtime || '—'} · ${model.live_available ? 'LIVE / 可实时运行' : 'RESEARCH CHECKPOINT · NOT RUNNABLE / 研究检查点 · 暂不可实时运行'}`;
  $('modelInfoInput').textContent = `${(model.input_shape || []).join(' × ')} · threshold ${model.fall_threshold ?? '—'}`;
  $('modelInfoMetric').textContent = model.validation_f1 == null ? 'Upstream model / 上游模型' : `F1 ${Number(model.validation_f1).toFixed(4)} · fold ${model.fold}, seed ${model.seed}`;
}
async function loadCloudModels() {
  try {
    const info = await api('/api/model/browser/info');
    cloudModelCatalog = info.models || [];
    const activeModel = info.active_model_id || info.default_model_id;
    selectedCloudModelId = cloudModelCatalog.some(item => item.id === activeModel && item.live_available) ? activeModel : info.default_model_id;
    const select = $('cloudModelSelect');
    select.innerHTML = cloudModelCatalog.map(item => `<option value="${escapeHTML(item.id)}" ${item.id === selectedCloudModelId ? 'selected' : ''} ${item.live_available ? '' : 'disabled'}>${escapeHTML(item.name_en)} / ${escapeHTML(item.name_zh)}${item.live_available ? '' : ' · RESEARCH CHECKPOINT / 研究检查点 · 暂不可运行'}</option>`).join('');
  } catch (error) {
    $('cloudModelSelect').innerHTML = `<option>Model catalog unavailable / 模型目录不可用 · ${escapeHTML(error.message || error.name)}</option>`;
  }
}
async function changeCloudModel() {
  const previousSession = localCloudSession;
  selectedCloudModelId = $('cloudModelSelect').value;
  try {
    await api('/api/model/select',{method:'POST',body:JSON.stringify({model_id:selectedCloudModelId})});
    updateModelDetails();
    $('modelDetails').hidden = false;
  } catch (error) {
    $('modelSelectionHint').textContent = `Model selection failed / 模型选择失败：${error.message}`;
    await loadCloudModels();
    return;
  }
  if (!previousSession) return;
  fetch('/api/model/browser/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:previousSession})}).catch(()=>{});
  localCloudSession = (crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`).replaceAll('-','');
  localCloudFrameSeq = 0;lastCloudPoseTime = 0;localCloudPending = false;
  setLocalCloudResult('CLOUD COLLECTING 0/30 / 云端采集中');
}

async function getLocalPoseModel() {
  if (!localPoseModelPromise) {
    localPoseModelPromise = (async () => {
      const {FilesetResolver, PoseLandmarker} = await import('/vendor/mediapipe/vision_bundle.mjs');
      const vision = await FilesetResolver.forVisionTasks('/vendor/mediapipe/wasm');
      return PoseLandmarker.createFromOptions(vision, {
        baseOptions: {modelAssetPath:'/vendor/mediapipe/pose_landmarker_lite.task',delegate:'CPU'},
        runningMode:'VIDEO',numPoses:1,
        minPoseDetectionConfidence:0.5,minPosePresenceConfidence:0.5,minTrackingConfidence:0.5
      });
    })().catch(error => {localPoseModelPromise = null;throw error;});
  }
  return localPoseModelPromise;
}
function drawLocalPose(landmarks = []) {
  const canvas = $('localPoseOverlay');
  const video = $('localCameraVideo');
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width || !height) return;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const pixelWidth = Math.round(width * ratio), pixelHeight = Math.round(height * ratio);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;canvas.height = pixelHeight;
  }
  const context = canvas.getContext('2d');
  context.setTransform(ratio,0,0,ratio,0,0);
  context.clearRect(0,0,width,height);
  if (!landmarks.length || !video.videoWidth || !video.videoHeight) return;
  const scale = Math.min(width / video.videoWidth, height / video.videoHeight);
  const imageWidth = video.videoWidth * scale, imageHeight = video.videoHeight * scale;
  const offsetX = (width - imageWidth) / 2, offsetY = (height - imageHeight) / 2;
  const point = index => {
    const landmark = landmarks[index];
    if (!landmark || (landmark.visibility ?? 1) < 0.45 || (landmark.presence ?? 1) < 0.45) return null;
    if (!Number.isFinite(landmark.x) || !Number.isFinite(landmark.y)) return null;
    return [offsetX + landmark.x * imageWidth,offsetY + landmark.y * imageHeight];
  };
  context.strokeStyle = '#75e8bc';context.lineWidth = 2.5;context.lineCap = 'round';
  context.shadowColor = '#102f29';context.shadowBlur = 5;
  for (const [a,b] of localPoseConnections) {
    const first = point(a), second = point(b);
    if (!first || !second) continue;
    context.beginPath();context.moveTo(...first);context.lineTo(...second);context.stroke();
  }
  context.fillStyle = '#f2ffb4';
  for (const index of [0,11,12,13,14,15,16,23,24,25,26,27,28,29,30,31,32]) {
    const current = point(index);
    if (!current) continue;
    context.beginPath();context.arc(...current,3.5,0,Math.PI * 2);context.fill();
  }
  context.shadowBlur = 0;
}
function setLocalCloudResult(text, state = '') {
  const badge = $('localCloudResult');
  badge.textContent = text;
  badge.className = `cloud-result-badge ${state}`;
}
async function sendPoseToCloud(landmarks, generation) {
  if (localCloudPending || !localCloudSession || generation !== localCameraGeneration) return;
  localCloudPending = true;
  const points = landmarks.map(point => [
    Math.max(-0.5, Math.min(1.5, Number(point.x) || 0)),
    Math.max(-0.5, Math.min(1.5, Number(point.y) || 0)),
    Math.max(0, Math.min(1, Number(point.visibility ?? point.presence) || 0))
  ]);
  try {
    const result = await api('/api/model/browser/frame', {method:'POST',body:JSON.stringify({session_id:localCloudSession,frame_seq:++localCloudFrameSeq,landmarks:points,model_id:selectedCloudModelId})});
    if (generation !== localCameraGeneration) return;
    if (!result.ready) {
      setLocalCloudResult(`CLOUD COLLECTING ${result.frames_collected}/${result.frames_required} / 云端采集中`);
    } else {
      const probability = Math.round(result.fall_probability * 100);
      const fall = result.label === 'fall';
      setLocalCloudResult(`${fall ? 'FALL' : 'NO FALL'} ${probability}% · CLOUD ${result.inference_ms} ms / 云端`,fall ? 'fall' : 'ready');
    }
  } catch (error) {
    if (generation === localCameraGeneration) setLocalCloudResult(`CLOUD ERROR / 云端模型错误`, 'error');
  } finally {
    localCloudPending = false;
  }
}
function localPoseLoop(model, generation) {
  if (generation !== localCameraGeneration || !localCameraStream) return;
  const video = $('localCameraVideo');
  const now = performance.now();
  if (video.readyState >= 2 && now - lastLocalPoseTime >= 180 && video.currentTime !== lastLocalVideoTime) {
    lastLocalPoseTime = now;lastLocalVideoTime = video.currentTime;
    try {
      const result = model.detectForVideo(video, now);
      const landmarks = result.landmarks?.[0] || [];
      drawLocalPose(landmarks);
      $('localCameraStatus').textContent = landmarks.length ? 'Pose extracted locally · fall inference running on cloud / 本机已提取骨架 · 云端正在进行跌倒检测' : 'Camera running · cloud receives empty pose frames until a person is visible / 摄像头运行中 · 人体入镜前云端接收空骨架帧';
      $('localCameraStatus').classList.remove('error');
      if (now - lastCloudPoseTime >= 250) {
        lastCloudPoseTime = now;
        sendPoseToCloud(landmarks,generation);
      }
    } catch (error) {
      $('localCameraStatus').textContent = `Pose inference unavailable / 姿态识别不可用：${error.message || error.name}`;
      $('localCameraStatus').classList.add('error');
      return;
    }
  }
  localPoseFrame = requestAnimationFrame(() => localPoseLoop(model, generation));
}
async function openLocalCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    $('localCameraStatus').textContent = 'Camera access requires HTTPS or localhost / 摄像头需要 HTTPS 或 localhost';
    $('localCameraStatus').classList.add('error');
    return;
  }
  const generation = ++localCameraGeneration;
  $('openLocalCamera').disabled = true;
  $('localCameraStatus').classList.remove('error');
  $('localCameraStatus').textContent = 'Waiting for camera permission / 等待摄像头授权';
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video:true,audio:false});
    if (generation !== localCameraGeneration) {stream.getTracks().forEach(track => track.stop());return;}
    localCameraStream = stream;
    const video = $('localCameraVideo');
    video.srcObject = stream;
    await video.play();
    if (generation !== localCameraGeneration) return;
    video.parentElement.style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
    video.parentElement.classList.add('on');
    $('stopLocalCamera').disabled = false;
    $('localCameraStatus').textContent = 'Camera running · loading local pose model / 摄像头运行中 · 正在加载本机姿态模型';
    try {
      const model = await getLocalPoseModel();
      if (generation !== localCameraGeneration) return;
      const cloudInfo = await api('/api/model/browser/info');
      if (!cloudInfo.available || cloudInfo.inference_location !== 'cloud') throw new Error('cloud fall model is unavailable');
      if (!cloudModelCatalog.length) {cloudModelCatalog = cloudInfo.models || [];selectedCloudModelId = cloudInfo.default_model_id;updateModelDetails();}
      video.parentElement.classList.add('pose-ready');
      localCloudSession = (crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`).replaceAll('-','');
      localCloudFrameSeq = 0;lastCloudPoseTime = 0;localCloudPending = false;
      setLocalCloudResult('CLOUD COLLECTING 0/30 / 云端采集中');
      lastLocalPoseTime = 0;lastLocalVideoTime = -1;
      localPoseLoop(model,generation);
    } catch (error) {
      if (generation !== localCameraGeneration) return;
      $('localCameraStatus').textContent = `Camera running · pose model unavailable / 摄像头运行中 · 姿态模型无法加载：${error.message || error.name}`;
      $('localCameraStatus').classList.add('error');
    }
  } catch (error) {
    if (generation !== localCameraGeneration) return;
    stopLocalCamera();
    $('localCameraStatus').textContent = error.name === 'NotAllowedError' ? 'Camera permission denied / 摄像头权限被拒绝' : `Camera unavailable / 摄像头不可用：${error.message || error.name}`;
    $('localCameraStatus').classList.add('error');
  }
}
function stopLocalCamera() {
  const cloudSession = localCloudSession;
  localCameraGeneration++;
  cancelAnimationFrame(localPoseFrame);localPoseFrame = 0;
  localCameraStream?.getTracks().forEach(track => track.stop());
  localCameraStream = null;
  const video = $('localCameraVideo');
  video.srcObject = null;
  video.parentElement.classList.remove('on','pose-ready');
  video.parentElement.style.aspectRatio = '';
  const canvas = $('localPoseOverlay');
  canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
  localCloudSession = null;localCloudPending = false;localCloudFrameSeq = 0;
  setLocalCloudResult('CLOUD MODEL WAITING / 云端模型等待中');
  if (cloudSession) fetch('/api/model/browser/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:cloudSession}),keepalive:true}).catch(()=>{});
  $('openLocalCamera').disabled = false;
  $('stopLocalCamera').disabled = true;
  $('localCameraStatus').textContent = 'Camera preview stopped / 摄像头预览已关闭';
  $('localCameraStatus').classList.remove('error');
}
let piStatusPending = false;
let piControlBusy = false;
let piFrameUrl = null;
let piFrameLoading = false;
let selectedCameraSource = 'pi';
const piCameraClientId = (() => {
  try {
    let value = sessionStorage.getItem('fallguardPiCameraClient');
    if (!value) {
      value = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}_${Math.random().toString(36).slice(2)}`).replaceAll('-','_');
      sessionStorage.setItem('fallguardPiCameraClient', value);
    }
    return value;
  } catch (error) {
    return `${Date.now()}_${Math.random().toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`;
  }
})();
function clearPiFrame(message = 'Pi camera is off / 树莓派摄像头未开启') {
  if (piFrameUrl) URL.revokeObjectURL(piFrameUrl);
  piFrameUrl = null;
  $('piCameraFrame').removeAttribute('src');
  $('piCameraFrame').parentElement.classList.remove('on');
  $('piCameraPlaceholder').textContent = message;
}
async function refreshPiFrame() {
  if (piFrameLoading || selectedCameraSource !== 'pi' || !$('live').classList.contains('active') || $('stopPiCamera').disabled) return;
  piFrameLoading = true;
  try {
    const response = await fetch('/api/camera/pi/frame', {cache:'no-store'});
    if (response.status === 204) {clearPiFrame('Waiting for Pi camera frame / 等待树莓派摄像头画面');return;}
    if (!response.ok) {clearPiFrame('Pi preview unavailable / 树莓派预览不可用');return;}
    const blob = await response.blob();
    if (blob.type !== 'image/jpeg' || !blob.size) {clearPiFrame('Invalid Pi camera frame / 树莓派画面无效');return;}
    const nextUrl = URL.createObjectURL(blob);
    $('piCameraFrame').src = nextUrl;
    $('piCameraFrame').parentElement.classList.add('on');
    if (piFrameUrl) URL.revokeObjectURL(piFrameUrl);
    piFrameUrl = nextUrl;
  } catch (error) {
    clearPiFrame('Pi preview unavailable / 树莓派预览不可用');
  } finally {
    piFrameLoading = false;
  }
}
function changeCameraSource() {
  selectedCameraSource = $('cameraSourceSelect').value === 'local' ? 'local' : 'pi';
  $('localCameraPanel').hidden = selectedCameraSource !== 'local';
  $('piCameraPanel').hidden = selectedCameraSource !== 'pi';
  if (selectedCameraSource === 'pi' && localCameraStream) stopLocalCamera();
  if (selectedCameraSource === 'pi') refreshPiFrame();
}
function renderPiStatus(status) {
  const connected = Boolean(status.connected);
  const availability = connected ? status.availability || (status.running ? 'busy' : 'available') : 'unknown';
  $('piConnectionDot').classList.toggle('connected', connected);
  $('piConnectionDot').closest('.pi-link-chip').classList.toggle('connected', connected);
  $('piConnectionState').textContent = connected ? 'Raspberry Pi connected / 树莓派已连接' : status.state === 'unconfigured' ? 'Pi not configured / 未配置树莓派' : 'Raspberry Pi offline / 树莓派离线';
  $('piCameraState').textContent = connected ? `Camera / 摄像头：${status.running ? 'RUNNING / 运行中' : 'STOPPED / 已停止'}` : 'Edge link offline / 边缘连接离线';
  $('piUsageState').textContent = availability === 'available' ? 'AVAILABLE / 空闲' : availability === 'owned' ? 'RUNNING / 运行中' : availability === 'busy' ? 'IN USE / 正在使用' : 'STATUS UNKNOWN / 状态未知';
  $('startPiCamera').disabled = piControlBusy || !connected || availability !== 'available';
  $('stopPiCamera').disabled = piControlBusy || !connected || !status.running || !status.owned_by_requester;
  $('piCameraMessage').textContent = connected ? 'Direct camera control ready / 可直接控制树莓派摄像头' : status.error || 'Unable to reach Raspberry Pi / 无法连接树莓派';
  $('piCameraMessage').classList.toggle('error', !connected);
  if (!connected || !status.running) clearPiFrame();
}
async function refreshPiStatus() {
  if (piStatusPending) return;
  piStatusPending = true;
  try {
    const response = await fetch(`/api/camera/pi/status?client_id=${encodeURIComponent(piCameraClientId)}`, {cache:'no-store'});
    const status = await response.json();
    renderPiStatus(status);
  } catch (error) {
    renderPiStatus({connected:false,state:'offline'});
  } finally {
    piStatusPending = false;
  }
}
async function controlPiCamera(action) {
  piControlBusy = true;
  $('startPiCamera').disabled = true;
  $('stopPiCamera').disabled = true;
  $('piCameraMessage').textContent = action === 'start' ? 'Starting Pi camera / 正在启动树莓派摄像头' : 'Stopping Pi camera / 正在停止树莓派摄像头';
  try {
    const response = await fetch(`/api/camera/pi/${action}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:piCameraClientId})});
    const status = await response.json();
    piControlBusy = false;
    renderPiStatus(status);
    if (!response.ok) $('piCameraMessage').textContent = status.error || 'Pi camera control failed / 树莓派摄像头控制失败';
  } catch (error) {
    piControlBusy = false;
    renderPiStatus({connected:false,state:'offline'});
  }
}
document.addEventListener('click', event => {
  const internalLink = event.target.closest('a[href^="#"]');
  if (internalLink) {event.preventDefault();navigate(internalLink.hash.slice(1));return;}
  const row = event.target.closest('[data-event-id]');
  if (row && row.classList.contains('event-row')) {app.selectedEventId = Number(row.dataset.eventId);navigate('alerts');render();}
});
document.addEventListener('submit', async event => {
  const form = event.target.closest('.ack-form');if(!form)return;event.preventDefault();
  const button = form.querySelector('button');button.disabled=true;
  try {await api(`/api/events/${form.dataset.eventId}/ack`,{method:'POST',body:JSON.stringify({note:form.elements.note.value})});await refresh();}
  catch(error){alert(`Could not acknowledge / 无法确认：${error.message}`);button.disabled=false;}
});
$('eventFilter').addEventListener('change', render);
$('refreshButton').addEventListener('click', refresh);
$('startDemo').addEventListener('click', () => demoAction('/api/demo/start','Synthetic stream started / 合成数据流已启动'));
$('triggerFall').addEventListener('click', () => demoAction('/api/demo/fall','Fall sequence triggered / 跌倒场景已触发'));
$('stopDemo').addEventListener('click', () => demoAction('/api/demo/stop','Demo stopped / 演示已停止'));
 $('openLocalCamera').addEventListener('click', openLocalCamera);
 $('stopLocalCamera').addEventListener('click', stopLocalCamera);
$('startPiCamera').addEventListener('click', () => controlPiCamera('start'));
$('stopPiCamera').addEventListener('click', () => controlPiCamera('stop'));
$('refreshPiCamera').addEventListener('click', refreshPiStatus);
$('cloudModelSelect').addEventListener('change', changeCloudModel);
$('cameraSourceSelect').addEventListener('change', changeCameraSource);
window.addEventListener('pagehide', () => {stopLocalCamera();clearPiFrame();});
window.addEventListener('popstate', route);
window.addEventListener('hashchange', route);
changeCameraSource();route();refresh();connectStream();refreshPiStatus();loadCloudModels();
setInterval(() => { $('topClock').textContent = new Intl.DateTimeFormat('en-GB',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Shanghai'}).format(new Date()) + ' CST'; },1000);
setInterval(refresh,15000);
setInterval(refreshPiStatus,15000);
setInterval(refreshPiFrame,1000);
