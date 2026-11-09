async function fetchWithAuth(url, options = {}) {
    options.credentials = "include";
    const res = await fetch(url, options);
    if (res.status === 401) window.location.href = 'login.html';
    return res;
}
let pollInterval;
let riskChart;
let currentTab = 'live';
let lastAlertTime = { "camera1": Date.now(), "camera2": Date.now() };
let lastAlertLevel = { "camera1": '', "camera2": '' };

const API_URL = '';

document.addEventListener('DOMContentLoaded', async () => {
    try {
        console.log("🚀 Initializing Vision Guard...");
        
        // Initialize chart & dropdowns
        initChart();
        fetchSamples();
        fetchConnectedCameras();
        toggleSourceInputs();
        
        // Initialize video feed overlays (waiting for user to click Start)
        ['camera1', 'camera2'].forEach(cid => {
            const v = document.getElementById(cid === 'camera1' ? 'cam1-video' : 'cam2-video');
            const el = document.getElementById(cid === 'camera1' ? 'cam1-overlay' : 'cam2-overlay');
            if (v) v.src = "";
            if (el) {
                el.innerHTML = `<div style="text-align: center;"><div style="font-size: 1.8rem; margin-bottom: 8px;">📹</div><div style="font-weight: 600; font-size: 1rem;">CAMERA OFFLINE</div><div style="font-size: 0.8rem; color: #a0abc0; margin-top: 4px;">Select source & click ▶ Start to begin</div></div>`;
                el.classList.remove('hidden');
                el.style.opacity = '1';
                el.style.display = 'flex';
            }
        });

        const res = await fetch(`${API_URL}/api/me`, {credentials: 'include'});
        if (res.ok) {
            const data = await res.json();
            console.log("👤 User role:", data.role);
            if (data.role !== 'admin') {
                document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
            }
        }
        // Start polling data
        startPolling();
        console.log("✅ Vision Guard initialized");
    } catch(e) { console.error('❌ Init error:', e); }
});

document.addEventListener('click', async (e) => {
    if (e.target && e.target.id === 'btnLogout') {
        await fetch(`${API_URL}/api/logout`, { method: 'POST', credentials: 'include' });
        window.location.href = 'login.html';
    }
});

function initChart() {
    const ctx = document.getElementById('riskChart').getContext('2d');
    Chart.defaults.color = '#A0ABC0';
    Chart.defaults.font.family = "'Outfit', sans-serif";
    
    let gradient1 = ctx.createLinearGradient(0, 0, 0, 400);
    gradient1.addColorStop(0, 'rgba(0, 240, 255, 0.5)');   
    gradient1.addColorStop(1, 'rgba(0, 240, 255, 0.0)');
    
    let gradient2 = ctx.createLinearGradient(0, 0, 0, 400);
    gradient2.addColorStop(0, 'rgba(157, 78, 221, 0.5)');   
    gradient2.addColorStop(1, 'rgba(157, 78, 221, 0.0)');

    riskChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Cam 1 Risk %',
                data: [],
                borderColor: '#00F0FF',
                backgroundColor: gradient1,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#00F0FF',
                pointHoverBorderColor: '#FFFFFF',
                pointHoverBorderWidth: 2
            },
            {
                label: 'Cam 2 Risk %',
                data: [],
                borderColor: '#9D4EDD',
                backgroundColor: gradient2,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#9D4EDD',
                pointHoverBorderColor: '#FFFFFF',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 500
            },
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true, max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#5B6A8A' }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#5B6A8A',
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

// ── Alert System Functions ──
function playAlertSound() {
    try {
        // Create a Web Audio API context for alert sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const now = audioContext.currentTime;
        
        // Create 3 beeps with 1000Hz tone
        for (let i = 0; i < 3; i++) {
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            
            osc.connect(gain);
            gain.connect(audioContext.destination);
            
            osc.frequency.value = 1000; // 1000 Hz beep
            gain.gain.setValueAtTime(0.3, now + i * 0.35);
            gain.gain.exponentialRampToValueAtTime(0.01, now + i * 0.35 + 0.25);
            
            osc.start(now + i * 0.35);
            osc.stop(now + i * 0.35 + 0.25);
        }
        
        // Long high-pitch blast at 1400Hz
        const osc2 = audioContext.createOscillator();
        const gain2 = audioContext.createGain();
        osc2.connect(gain2);
        gain2.connect(audioContext.destination);
        
        osc2.frequency.value = 1400;
        gain2.gain.setValueAtTime(0.3, now + 1.05);
        gain2.gain.exponentialRampToValueAtTime(0.01, now + 1.65);
        
        osc2.start(now + 1.05);
        osc2.stop(now + 1.65);
        
        console.log("🔊 Alert sound played");
    } catch (e) {
        console.error("Alert sound error:", e);
    }
}

function showAlertToast(message, level) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${level === 'HIGH RISK' ? '#ef4444' : level === 'CRITICAL' ? '#991b1b' : '#f59e0b'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        z-index: 9999;
        font-weight: 600;
        font-size: 14px;
        max-width: 400px;
        animation: slideInRight 0.3s ease;
        font-family: 'Inter', sans-serif;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Auto-remove after 6 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 6000);
}

async function checkAlerts() {
    try {
        const res = await fetchWithAuth(`${API_URL}/api/alerts?n=1`);
        const data = await res.json();
        
        ['camera1', 'camera2'].forEach(camId => {
            if (data[camId] && data[camId].alerts && data[camId].alerts.length > 0) {
                const latestAlert = data[camId].alerts[0]; // Most recent alert
                
                // Only trigger if it's a new alert
                if (latestAlert.level === 'HIGH RISK' || latestAlert.level === 'CRITICAL') {
                    const rawTs = (latestAlert.timestamp || '').replace(' ', 'T');
                    const alertTime = Date.parse(rawTs) || Date.now();
                    const now = Date.now();
                    
                    if (alertTime > lastAlertTime[camId] || (now - lastAlertTime[camId]) > 10000) {
                        lastAlertTime[camId] = now;
                        lastAlertLevel[camId] = latestAlert.level;
                        
                        console.log(`🚨 HIGH RISK ALERT (${camId}):`, latestAlert.message);
                        playAlertSound();
                        showAlertToast(`🚨 ${latestAlert.message}`, latestAlert.level);
                    }
                }
            }
        });
    } catch (e) {
        console.error("Alert check error:", e);
    }
}

function switchTab(tabId) {
    currentTab = tabId;
    
    // Update Nav
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        const onclick = link.getAttribute('onclick');
        if (onclick && onclick.includes(tabId)) {
            link.classList.add('active');
        }
    });
    
    // Update Views
    document.querySelectorAll('.view-section').forEach(view => {
        view.classList.remove('active');
        view.classList.add('hidden');
    });
    const targetView = document.getElementById(`view-${tabId}`);
    if (targetView) {
        targetView.classList.remove('hidden');
        targetView.classList.add('active');
    }
    
    if (tabId === 'analytics') loadAnalytics();
    if (tabId === 'evidence') loadEvidence();
}

function toggleSourceInputs() {
    const srcType = document.getElementById('sourceType').value;
    document.getElementById('webcamInput').classList.toggle('hidden', srcType !== 'Webcam');
    document.getElementById('sampleInput').classList.toggle('hidden', srcType !== 'Sample' && srcType !== 'Upload');
    document.getElementById('rtspInput').classList.toggle('hidden', srcType !== 'RTSP');

    if (srcType === 'Webcam') {
        fetchConnectedCameras();
    }
    if (srcType === 'Upload') {
        const fileInput = document.getElementById('videoUploadInput');
        if (fileInput) fileInput.click();
    }
}

async function fetchSamples() {
    try {
        const res = await fetchWithAuth(`${API_URL}/api/samples`);
        const data = await res.json();
        const select = document.getElementById('sampleFile');
        if (!select) return;
        const currentVal = select.value;
        select.innerHTML = '';
        data.samples.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s;
            if (s === currentVal) opt.selected = true;
            select.appendChild(opt);
        });
    } catch(e) { console.error("Failed to load samples", e); }
}

async function fetchConnectedCameras() {
    try {
        const res = await fetchWithAuth(`${API_URL}/api/detect_cameras`);
        const data = await res.json();
        const select = document.getElementById('webcamSelect');
        const input = document.getElementById('webcamIndex');
        if (!select) return;
        const currentVal = input && input.value !== "" ? input.value : (select.value !== "" ? select.value : "0");
        select.innerHTML = '';
        
        // Build map of detected cameras
        const detectedMap = {};
        if (data && data.cameras) {
            data.cameras.forEach(c => {
                detectedMap[c.index] = c.label;
            });
        }
        
        // Always provide indices 0, 1, 2, 3, 4 so the user can select ANY camera number
        for (let idx = 0; idx <= 4; idx++) {
            const opt = document.createElement('option');
            opt.value = idx;
            if (detectedMap[idx]) {
                opt.textContent = `🟢 ${detectedMap[idx]}`;
            } else if (idx === 0) {
                opt.textContent = `Webcam #0 (Default / Built-in Camera)`;
            } else {
                opt.textContent = `Webcam #${idx} (USB / External Camera)`;
            }
            if (String(idx) === String(currentVal)) {
                opt.selected = true;
            }
            select.appendChild(opt);
        }
        
        if (input) {
            input.value = select.value;
        }
    } catch(e) { console.error("Failed to detect cameras", e); }
}

function updateWebcamFromInput(val) {
    const num = parseInt(val);
    const select = document.getElementById('webcamSelect');
    if (select && !isNaN(num)) {
        let found = false;
        for (let i = 0; i < select.options.length; i++) {
            if (parseInt(select.options[i].value) === num) {
                select.selectedIndex = i;
                found = true;
                break;
            }
        }
        if (!found) {
            const opt = document.createElement('option');
            opt.value = num;
            opt.textContent = `Webcam #${num}`;
            opt.selected = true;
            select.appendChild(opt);
        }
    }
}
window.updateWebcamFromInput = updateWebcamFromInput;

async function refreshCameras() {
    const note = document.getElementById('webcamDetectedNote');
    if (note) note.textContent = "Scanning for USB cameras...";
    await fetchConnectedCameras();
    const count = document.getElementById('webcamSelect')?.options?.length || 0;
    if (note) {
        note.textContent = "Cameras synced! Indices 0, 1, 2, 3, 4 ready.";
        setTimeout(() => { if (note) note.textContent = ""; }, 4000);
    }
}
window.refreshCameras = refreshCameras;

function triggerVideoUpload() {
    const fileInput = document.getElementById('videoUploadInput');
    if (fileInput) fileInput.click();
}
window.triggerVideoUpload = triggerVideoUpload;

async function handleVideoUpload(event) {
    const file = event.target.files ? event.target.files[0] : null;
    if (!file) return;

    console.log("📁 Selected file for upload:", file.name, file.size, file.type);
    const progressDiv = document.getElementById('uploadProgress');
    if (progressDiv) {
        const szMb = (file.size / (1024 * 1024)).toFixed(1);
        progressDiv.textContent = `⏳ Uploading "${file.name}" (${szMb} MB)...`;
        progressDiv.classList.remove('hidden');
    }

    const formData = new FormData();
    formData.append('video', file);

    try {
        const response = await fetch(`${API_URL}/api/upload_video`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });

        const resText = await response.text();
        let data = {};
        try {
            data = JSON.parse(resText);
        } catch (parseErr) {
            console.error("Non-JSON response from server:", resText);
            throw new Error(`Server returned status ${response.status}. Please make sure server is running and file size is under 1GB.`);
        }
        console.log("Upload server response:", data);

        if (response.ok && data.success) {
            if (progressDiv) {
                progressDiv.textContent = `✅ Uploaded "${data.filename}"!`;
                setTimeout(() => progressDiv.classList.add('hidden'), 5000);
            }

            const select = document.getElementById('sampleFile');
            if (select && data.samples) {
                select.innerHTML = '';
                data.samples.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s;
                    opt.textContent = s;
                    if (s === data.filename) opt.selected = true;
                    select.appendChild(opt);
                });
            }

            const srcSelect = document.getElementById('sourceType');
            if (srcSelect) {
                srcSelect.value = 'Sample';
                toggleSourceInputs();
            }

            alert(`Crowd video file "${data.filename}" uploaded successfully!\n\nIt is now selected in your video sources. Click "▶ Cam 1" or "▶ Both Cameras" to start AI analysis.`);
        } else {
            const err = data.error || `Upload failed with HTTP code ${response.status}`;
            console.error("❌ Upload server error:", err);
            alert(`Upload Error: ${err}`);
            if (progressDiv) progressDiv.classList.add('hidden');
        }
    } catch (e) {
        console.error("❌ Video upload network/JS error:", e);
        alert(`Failed to upload video file: ${e.message || 'Connection error'}.`);
        if (progressDiv) progressDiv.classList.add('hidden');
    } finally {
        event.target.value = '';
    }
}
window.handleVideoUpload = handleVideoUpload;

async function startMonitoring(camId) {
    console.log("🎬 Starting monitoring...", camId);
    
    let cameras = camId === 'both' ? ['camera1', 'camera2'] : [camId];
    
    for (let cid of cameras) {
        const overlay = document.getElementById(cid === 'camera1' ? 'cam1-overlay' : 'cam2-overlay');
        if (overlay) {
            overlay.innerHTML = '<div class="spinner"></div><div style="text-align: center;"><div style="font-size: 1.2rem; margin-top: 12px;">Starting Camera...</div></div>';
            overlay.classList.remove('hidden');
            overlay.style.opacity = '1';
            overlay.style.display = 'flex';
        }
    }
    
    const srcType = document.getElementById('sourceType').value;
    let param = 0;
    if (srcType === 'Webcam') {
        const sel = document.getElementById('webcamSelect');
        param = (sel && sel.value !== "" && !isNaN(parseInt(sel.value))) ? parseInt(sel.value) : (parseInt(document.getElementById('webcamIndex')?.value) || 0);
    } else if (srcType === 'Sample') {
        param = document.getElementById('sampleFile')?.value || "crowd_sample_1.mp4";
    } else if (srcType === 'RTSP') {
        param = document.getElementById('rtspUrl')?.value || "";
    }

    try {
        const response = await fetchWithAuth(`${API_URL}/api/start`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ src_type: srcType, param: param, camera_id: camId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('statusDot').className = 'dot active';
            document.getElementById('statusText').textContent = 'MONITORING ACTIVE';
            
            for (let cid of cameras) {
                const overlay = document.getElementById(cid === 'camera1' ? 'cam1-overlay' : 'cam2-overlay');
                if (camId === 'both' && !data[cid]) {
                    if (overlay) {
                        overlay.innerHTML = `<div style="text-align: center; color: #ff6b6b;"><div style="font-size: 1.5rem;">⚠️</div><div style="margin-top: 12px;">Camera Offline</div></div>`;
                        overlay.classList.remove('hidden');
                        overlay.style.opacity = '1';
                        overlay.style.display = 'flex';
                    }
                    continue;
                }
                const feedUrl = `${API_URL}/video_feed/${cid}?t=${new Date().getTime()}`;
                const videoFeed = document.getElementById(cid === 'camera1' ? 'cam1-video' : 'cam2-video');
                if (videoFeed) {
                    videoFeed.src = ""; // Unbind previous stream
                    setTimeout(() => { videoFeed.src = feedUrl; }, 50);
                }
                if (overlay) {
                    overlay.style.opacity = '0';
                    overlay.style.display = 'none';
                    overlay.classList.add('hidden');
                }
            }
            startPolling();
        } else {
            console.error("❌ Start failed:", data.error);
            const errMsg = data.error || "Failed to start camera.";
            alert(`⚠️ Camera Start Failed: ${errMsg}`);
            for (let cid of cameras) {
                const overlay = document.getElementById(cid === 'camera1' ? 'cam1-overlay' : 'cam2-overlay');
                if (overlay) {
                    overlay.innerHTML = `<div style="text-align: center; color: #ff6b6b;"><div style="font-size: 1.5rem;">⚠️</div><div style="margin-top: 8px; font-weight: 600;">Failed to Start</div><div style="font-size: 0.8rem; color: #ccc; margin-top: 4px;">${errMsg}</div></div>`;
                    overlay.classList.remove('hidden');
                    overlay.style.opacity = '1';
                    overlay.style.display = 'flex';
                }
            }
        }
    } catch (e) { 
        console.error("❌ Start error:", e);
        alert(`❌ Network or server error: ${e.message}`);
        for (let cid of cameras) {
            const overlay = document.getElementById(cid === 'camera1' ? 'cam1-overlay' : 'cam2-overlay');
            if (overlay) {
                overlay.innerHTML = `<div style="text-align: center; color: #ff6b6b;"><div style="font-size: 1.5rem;">⚠️</div><div style="margin-top: 8px;">Error Connecting to Server</div></div>`;
                overlay.classList.remove('hidden');
                overlay.style.opacity = '1';
                overlay.style.display = 'flex';
            }
        }
    }
}

async function stopMonitoring(camId) {
    try {
        await fetchWithAuth(`${API_URL}/api/stop`, { 
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ camera_id: camId })
        });
        
        let cameras = camId === 'both' ? ['camera1', 'camera2'] : [camId];
        for (let cid of cameras) {
            const videoFeed = document.getElementById(cid === 'camera1' ? 'cam1-video' : 'cam2-video');
            if (videoFeed) videoFeed.src = "";
            const overlay = document.getElementById(cid === 'camera1' ? 'cam1-overlay' : 'cam2-overlay');
            if (overlay) {
                overlay.classList.remove('hidden');
                overlay.style.display = 'flex';
                overlay.style.opacity = '1';
                overlay.innerHTML = `<div style="text-align: center;"><div style="font-size: 1.8rem; margin-bottom: 8px;">📹</div><div style="font-weight: 600; font-size: 1rem;">CAMERA OFFLINE</div><div style="font-size: 0.8rem; color: #a0abc0; margin-top: 4px;">Select source & click ▶ Start to begin</div></div>`;
            }
            
            ['kpiCount', 'kpiDensity', 'kpiMovement', 'kpiRisk', 'kpiStatus', 'subDensity', 'subMovement', 'subRisk', 'lblBehavior', 'lblViolence', 'lblWeapon', 'lblAudio', 'lblAction'].forEach(id => {
                const el = document.getElementById(`${id}-${cid}`);
                if (el) el.textContent = '—';
            });
            const rCard = document.getElementById(`riskCard-${cid}`);
            if (rCard) rCard.className = 'kpi-card glass-panel risk-card';
        }
    } catch(e) { console.error("Stop error", e); }
}


async function toggleSim(type, btn) {
    window.simState = window.simState || {};
    window.simState[type] = !window.simState[type];
    const active = window.simState[type];
    if (btn) {
        if (active) {
            btn.style.borderColor = '#ff0055';
            btn.style.background = 'rgba(255, 0, 85, 0.28)';
            btn.style.color = '#ff0055';
            btn.style.fontWeight = 'bold';
        } else {
            btn.style.borderColor = '';
            btn.style.background = '';
            btn.style.color = '';
            btn.style.fontWeight = '';
        }
    }
    console.log(`🔬 Triggering simulation: ${type} = ${active}`);
    await fetchWithAuth(`${API_URL}/api/simulate`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ type: type, active: active })
    });
}
window.toggleSim = toggleSim;
window.toggleSimulation = toggleSim;

async function sendTestTelegramAlert() {
    const btn = document.getElementById('btnTestTelegram');
    const oldText = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '⏳ Sending to Telegram...';
        btn.disabled = true;
    }
    try {
        const res = await fetchWithAuth(`${API_URL}/api/test_telegram`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            alert('✅ Telegram Alert Dispatched! Check your Telegram app.');
        } else {
            alert('⚠️ ' + (data.message || 'Telegram alert failed. Please verify credentials.'));
        }
    } catch (e) {
        alert('❌ Network error: ' + e.message);
    } finally {
        if (btn) {
            btn.innerHTML = oldText;
            btn.disabled = false;
        }
    }
}
window.sendTestTelegramAlert = sendTestTelegramAlert;

function updateAlertBanner(data) {
    const alertBanner = document.getElementById('alertBanner');
    if (!alertBanner) return;

    let highestCam = null;
    let highestStats = null;
    let highestLevel = 'SAFE';

    ['camera1', 'camera2'].forEach(cid => {
        if (data[cid] && data[cid].running && data[cid].stats) {
            const lvl = data[cid].stats.risk_level;
            if (lvl === 'CRITICAL') {
                highestLevel = 'CRITICAL';
                highestCam = cid;
                highestStats = data[cid].stats;
            } else if (lvl === 'HIGH RISK' && highestLevel !== 'CRITICAL') {
                highestLevel = 'HIGH RISK';
                highestCam = cid;
                highestStats = data[cid].stats;
            }
        }
    });

    if (highestStats) {
        alertBanner.className = 'alert-banner';
        const camLabel = highestCam === 'camera1' ? 'Camera 1' : 'Camera 2';
        let evBtnHtml = '';
        if (highestStats.evidence_file) {
            const isVid = highestStats.evidence_file.endsWith('.mp4');
            const urlPath = isVid ? `${API_URL}/api/evidence/vid/${highestStats.evidence_file}` : `${API_URL}/api/evidence/img/${highestStats.evidence_file}`;
            evBtnHtml = `<a href="${urlPath}" target="_blank" style="margin-left:10px; background:#00F0FF; color:#0f172a; padding:3px 10px; border-radius:6px; font-weight:700; text-decoration:none; display:inline-block;">📁 View Evidence</a>`;
        }
        
        const phone = "917892935942";
        const waText = encodeURIComponent(`🚨 VISION GUARD ALERT [${camLabel}]: ${highestStats.risk_level} (${Math.round(highestStats.risk_score)}%)\nCrowd: ${highestStats.person_count} persons\nAction: ${highestStats.recommended_action || 'Check camera'}`);
        const waBtnHtml = `<a href="https://web.whatsapp.com/send?phone=${phone}&text=${waText}" target="_blank" style="margin-left:8px; background:#25D366; color:#ffffff; padding:3px 10px; border-radius:6px; font-weight:700; text-decoration:none; display:inline-block;">💬 Send WhatsApp</a>`;

        alertBanner.querySelector('.alert-msg').innerHTML = `⚠️ <strong>[${camLabel}] ${highestStats.risk_level} (${Math.round(highestStats.risk_score)}%)</strong> — ${highestStats.recommended_action || 'Immediate attention required'}${evBtnHtml}${waBtnHtml}`;
        
        if ((highestStats.risk_level === 'HIGH RISK' || highestStats.risk_level === 'CRITICAL') && !window.alarmPlaying) {
            window.alarmPlaying = true;
            playAlertSound();
            setTimeout(() => { window.alarmPlaying = false; }, 4000);
        }
    } else {
        alertBanner.className = 'alert-banner hidden';
    }
}

function updateUI(stats, cid) {
    document.getElementById(`kpiCount-${cid}`).textContent = stats.person_count;
    document.getElementById(`kpiDensity-${cid}`).textContent = Math.round(stats.density_score) + '%';
    document.getElementById(`subDensity-${cid}`).textContent = stats.density_level;
    document.getElementById(`kpiMovement-${cid}`).textContent = stats.movement_speed.toFixed(1) + ' px/f';
    document.getElementById(`subMovement-${cid}`).textContent = stats.movement_level;
    document.getElementById(`kpiRisk-${cid}`).textContent = Math.round(stats.risk_score) + '%';
    document.getElementById(`subRisk-${cid}`).textContent = stats.risk_trend;
    document.getElementById(`kpiStatus-${cid}`).textContent = stats.risk_level;
    
    document.getElementById(`lblBehavior-${cid}`).textContent = stats.behavior_status;
    const congEl = document.getElementById(`lblCongestion-${cid}`);
    if (congEl) congEl.textContent = `${Math.round(stats.congestion_score || 0)}% (${stats.congestion_frames || 0} frames)`;
    const threatEl = document.getElementById(`lblThreat-${cid}`);
    if (threatEl) {
        threatEl.textContent = stats.threat_status || 'CLEAR';
        threatEl.style.color = (stats.threat_status && stats.threat_status !== 'CLEAR') ? '#EF4444' : '#22C55E';
    }
    document.getElementById(`lblViolence-${cid}`).textContent = stats.violence_detected ? '⚠️ Detected' : '✅ Clear';
    document.getElementById(`lblWeapon-${cid}`).textContent = stats.weapon_detected ? '🔴 Detected' : '✅ Clear';
    document.getElementById(`lblAudio-${cid}`).textContent = stats.noise_db.toFixed(1);
    document.getElementById(`lblAction-${cid}`).textContent = stats.recommended_action;

    const riskCard = document.getElementById(`riskCard-${cid}`);
    if (stats.risk_level === 'HIGH RISK' || stats.risk_level === 'CRITICAL') {
        riskCard.className = 'kpi-card glass-panel risk-card high';
    } else {
        riskCard.className = 'kpi-card glass-panel risk-card';
    }
}

async function pollData() {
    try {
        const res = await fetchWithAuth(`${API_URL}/api/stats`);
        const data = await res.json();
        
        let running = false;
        if (data.camera1 && data.camera1.running) {
            updateUI(data.camera1.stats, 'camera1');
            running = true;
        }
        if (data.camera2 && data.camera2.running) {
            updateUI(data.camera2.stats, 'camera2');
            running = true;
        }
        
        updateAlertBanner(data);

        if (running) {
            document.getElementById('statusDot').className = 'dot active';
            document.getElementById('statusText').textContent = 'MONITORING ACTIVE';
            checkAlerts();
        } else {
            document.getElementById('statusDot').className = 'dot';
            document.getElementById('statusText').textContent = 'MONITORING STOPPED';
        }

        if (currentTab === 'live') {
            const histRes = await fetchWithAuth(`${API_URL}/api/history`);
            const histData = await histRes.json();
            
            if (histData.camera1 && histData.camera1.time.length > 0) {
                riskChart.data.labels = histData.camera1.time;
                riskChart.data.datasets[0].data = histData.camera1.risk;
            }
            if (histData.camera2 && histData.camera2.time.length > 0) {
                if (histData.camera1.time.length === 0) riskChart.data.labels = histData.camera2.time;
                riskChart.data.datasets[1].data = histData.camera2.risk;
            }
            riskChart.update();
        }
    } catch (e) { console.error("Poll error", e); }
}

function startPolling() {
    stopPolling();
    pollInterval = setInterval(pollData, 1000);
}



function stopPolling() {
    if (pollInterval) clearInterval(pollInterval);
}

/* ── Analytics Tab ── */
let selectedAnalyticsFilter = 'all';

async function loadAnalytics() {
    try {
        const res = await fetchWithAuth(`${API_URL}/api/analytics`);
        const data = await res.json();
        
        // Camera 1 Stats
        if (data.camera1_stats) {
            document.getElementById('statMaxPeople-cam1').textContent = data.camera1_stats.max_people || 0;
            document.getElementById('statAvgPeople-cam1').textContent = data.camera1_stats.avg_people || 0;
            document.getElementById('statMaxRisk-cam1').textContent = data.camera1_stats.max_risk ? data.camera1_stats.max_risk + '%' : '0%';
            document.getElementById('statIncidents-cam1').textContent = data.camera1_stats.total_incidents || 0;
        }

        // Camera 2 Stats
        if (data.camera2_stats) {
            document.getElementById('statMaxPeople-cam2').textContent = data.camera2_stats.max_people || 0;
            document.getElementById('statAvgPeople-cam2').textContent = data.camera2_stats.avg_people || 0;
            document.getElementById('statMaxRisk-cam2').textContent = data.camera2_stats.max_risk ? data.camera2_stats.max_risk + '%' : '0%';
            document.getElementById('statIncidents-cam2').textContent = data.camera2_stats.total_incidents || 0;
        }

        // Combined Stats
        if (data.stats) {
            document.getElementById('statMaxPeople-comb').textContent = data.stats.max_people || 0;
            document.getElementById('statAvgPeople-comb').textContent = data.stats.avg_people || 0;
            document.getElementById('statMaxRisk-comb').textContent = data.stats.max_risk ? data.stats.max_risk + '%' : '0%';
            document.getElementById('statIncidents-comb').textContent = data.stats.total_incidents || 0;
        }
        
        // Incident Log Table
        const tbody = document.getElementById('incidentTableBody');
        tbody.innerHTML = '';
        data.incidents.forEach(inc => {
            const camSource = inc.video_source || 'Camera 1';
            const tr = document.createElement('tr');
            tr.setAttribute('data-camera', camSource);
            tr.innerHTML = `
                <td>${inc.timestamp.substring(11, 19)}</td>
                <td><span style="background:rgba(255,255,255,0.1); padding:3px 8px; border-radius:4px; font-weight:600;">${camSource}</span></td>
                <td style="color:${inc.risk_level.includes('CRITICAL') ? '#EF4444' : '#F59E0B'}; font-weight:700;">${inc.risk_level}</td>
                <td>${Math.round(inc.risk_score)}%</td>
                <td>${inc.people_count}</td>
                <td>${inc.alert_message || '-'}</td>
            `;
            tbody.appendChild(tr);
        });

        filterAnalytics(selectedAnalyticsFilter);
    } catch(e) { console.error("Load analytics error:", e); }
}

function filterAnalytics(camFilter) {
    selectedAnalyticsFilter = camFilter;

    // Update Filter Buttons
    document.getElementById('btnFilterAll').className = camFilter === 'all' ? 'btn btn-sm btn-secondary active' : 'btn btn-sm btn-secondary';
    document.getElementById('btnFilterCam1').className = camFilter === 'Camera 1' ? 'btn btn-sm btn-secondary active' : 'btn btn-sm btn-secondary';
    document.getElementById('btnFilterCam2').className = camFilter === 'Camera 2' ? 'btn btn-sm btn-secondary active' : 'btn btn-sm btn-secondary';

    const boxCam1 = document.getElementById('analytics-box-cam1');
    const boxCam2 = document.getElementById('analytics-box-cam2');
    const boxComb = document.getElementById('analytics-box-comb');

    if (camFilter === 'Camera 1') {
        if (boxCam1) boxCam1.style.display = 'block';
        if (boxCam2) boxCam2.style.display = 'none';
        if (boxComb) boxComb.style.display = 'none';
    } else if (camFilter === 'Camera 2') {
        if (boxCam1) boxCam1.style.display = 'none';
        if (boxCam2) boxCam2.style.display = 'block';
        if (boxComb) boxComb.style.display = 'none';
    } else {
        if (boxCam1) boxCam1.style.display = 'block';
        if (boxCam2) boxCam2.style.display = 'block';
        if (boxComb) boxComb.style.display = 'block';
    }

    // Filter Incidents Table Rows
    document.querySelectorAll('#incidentTableBody tr').forEach(tr => {
        const rowCam = tr.getAttribute('data-camera') || 'Camera 1';
        if (camFilter === 'all' || rowCam.includes(camFilter)) {
            tr.style.display = '';
        } else {
            tr.style.display = 'none';
        }
    });
}

/* ── Evidence Tab ── */
async function loadEvidence() {
    try {
        const res = await fetchWithAuth(`${API_URL}/api/evidence`);
        const data = await res.json();
        
        const grid1 = document.getElementById('evidenceGridCam1');
        const grid2 = document.getElementById('evidenceGridCam2');
        grid1.innerHTML = '';
        grid2.innerHTML = '';
        
        data.files.forEach(file => {
            const card = document.createElement('div');
            card.className = 'evidence-card';
            
            const mediaTag = file.type === "video" 
                ? `<video src="${API_URL}/api/evidence/vid/${file.name}" controls preload="metadata"></video>`
                : `<img src="${API_URL}/api/evidence/img/${file.name}" alt="Evidence">`;
            
            const downloadUrl = file.type === "video"
                ? `${API_URL}/api/evidence/vid/${file.name}`
                : `${API_URL}/api/evidence/img/${file.name}`;

            const badgeColor = file.camera === "Camera 2" ? "#9D4EDD" : "#00F0FF";
            const typeBadge = file.type === "video" ? "🎥 VIDEO CLIP" : "📸 SNAPSHOT";

            card.innerHTML = `
                ${mediaTag}
                <div class="details" style="text-align: left; padding: 12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="background:rgba(255,255,255,0.08); color:${badgeColor}; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.75rem;">📹 ${file.camera}</span>
                        <span style="color:#F97316; font-size:0.72rem; font-weight:600;">${typeBadge}</span>
                    </div>
                    <div style="font-size:0.8rem; color:#E2E8F0; margin-bottom:4px;">
                        📅 ${file.date || '—'} &nbsp; ⏰ ${file.time || '—'}
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <span style="font-size:0.7rem; color:#64748B; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:140px;" title="${file.name}">${file.name}</span>
                        <a href="${downloadUrl}" download="${file.name}" style="background:#00F0FF; color:#0b0f19; font-size:0.75rem; font-weight:700; padding:2px 8px; border-radius:4px; text-decoration:none;">⬇ Save</a>
                    </div>
                </div>
            `;
            
            if (file.camera === "Camera 2") {
                grid2.appendChild(card);
            } else {
                grid1.appendChild(card);
            }
        });
    } catch(e) { console.error(e); }
}

/* ── Reports Tab ── */
async function downloadReport(type, videoSource = null) {
    try {
        const res = await fetchWithAuth(`${API_URL}/api/reports/generate_${type}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ camera: videoSource })
        });
        const data = await res.json();
        if (data.success) {
            window.location.href = `${API_URL}/api/reports/download/${data.filename}`;
        } else {
            alert(data.error || "Failed to generate report.");
        }
    } catch(e) { console.error("Report generation error:", e); }
}

/* ── Chatbot Tab ── */
function handleChatKeyPress(e) {
    if (e.key === 'Enter') sendChatMessage();
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;
    
    // Add user message
    const hist = document.getElementById('chatHistory');
    hist.innerHTML += `<div class="chat-msg user-msg"><div class="msg-bubble">${msg}</div></div>`;
    input.value = '';
    hist.scrollTop = hist.scrollHeight;
    
    try {
        const res = await fetchWithAuth(`${API_URL}/api/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ query: msg })
        });
        const data = await res.json();
        
        hist.innerHTML += `<div class="chat-msg bot-msg"><div class="msg-bubble">${data.response}</div></div>`;
        hist.scrollTop = hist.scrollHeight;
    } catch(e) {
        console.error(e);
        hist.innerHTML += `<div class="chat-msg bot-msg"><div class="msg-bubble">Error connecting to Assistant API.</div></div>`;
    }
}

/* ── Settings Tab ── */
async function clearDatabase() {
    if (!confirm("Are you sure? This will permanently delete all logs and evidence files.")) {
        return;
    }
    try {
        const res = await fetchWithAuth(`${API_URL}/api/settings/clear_db`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            alert("Database and Evidence files cleared successfully.");
            // Reset charts
            riskChart.data.labels = [];
            riskChart.data.datasets[0].data = [];
            riskChart.update();
        } else {
            alert("Failed to clear database.");
        }
    } catch(e) { console.error(e); }
}


function updateAdminParam(key, value) {
    if (key === 'yolo_conf') document.getElementById('valYoloConf').innerText = value + '%';
    if (key === 'tripwire_y') document.getElementById('valTripwire').innerText = value + '%';
    if (key === 'density_low') document.getElementById('valDensity').innerText = value + '%';

    fetch('/api/config/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: key, value: parseInt(value) })
    })
    .catch(err => console.error('Admin API Error:', err));
}

// Randomize Diagnostics Mock
setInterval(() => {
    if (document.getElementById('view-settings').classList.contains('hidden')) return;
    document.getElementById('diagCpu').innerText = (Math.random() * 20 + 5).toFixed(1) + '%';
    document.getElementById('diagMem').innerText = Math.floor(Math.random() * 50 + 400) + ' MB';
}, 2000);
