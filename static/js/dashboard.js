/* ═══════════════════════════════ CrowdWatch AI V2 Dashboard JS ═════════ */

const API = {
    telemetry:     '/api/telemetry',
    alerts:        '/api/alerts?limit=20',
    analytics:     '/api/analytics',
    evidence:      '/api/evidence',
    config:        '/api/config',
    chatbot:       '/api/chatbot',
    alertHistory:  '/api/alert_history',
};

let trendChart = null;
let lastRiskLevel = 'LOW';
const alarmAudio = document.getElementById('alarm-audio');

// ── Helpers ────────────────────────────────────────────────────────────────

function setBar(id, pct, cap = 100) {
    const el = document.getElementById(id);
    if (el) el.style.width = Math.min(pct, cap) + '%';
}

function riskColor(level) {
    return { LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#f97316', CRITICAL: '#ef4444' }[level] || '#6366f1';
}

function riskBadge(level) {
    const map = { CRITICAL: 'rb-critical', HIGH: 'rb-high', MEDIUM: 'rb-medium', LOW: 'rb-low' };
    return `<span class="risk-badge ${map[level] || 'rb-low'}">${level}</span>`;
}

function monoClock() {
    const el = document.getElementById('live-clock');
    setInterval(() => { el.textContent = new Date().toLocaleTimeString(); }, 1000);
}

// ── Telemetry poll ─────────────────────────────────────────────────────────

async function pollTelemetry() {
    try {
        const t = await fetch(API.telemetry).then(r => r.json());

        // KPI cards
        document.getElementById('kpi-count').textContent   = t.count;
        document.getElementById('kpi-weapons').textContent = t.weapons_count;
        document.getElementById('kpi-panic').textContent   = t.panic_score.toFixed(0) + '%';
        document.getElementById('kpi-risk').textContent    = t.risk + '%';

        // Risk badge
        const riskBadgeEl   = document.getElementById('global-risk-badge');
        const riskLabelEl   = document.getElementById('risk-label');
        riskLabelEl.textContent = t.risk_level;
        riskBadgeEl.style.color  = riskColor(t.risk_level);
        riskBadgeEl.style.borderColor = riskColor(t.risk_level);
        riskBadgeEl.style.boxShadow = t.risk_level === 'CRITICAL'
            ? `0 0 14px ${riskColor(t.risk_level)}55` : 'none';

        // Risk display card
        const riskDisplay = document.getElementById('risk-display');
        riskDisplay.textContent = t.risk_level;
        riskDisplay.style.color  = riskColor(t.risk_level);
        riskDisplay.style.borderColor = riskColor(t.risk_level);
        riskDisplay.style.boxShadow   = `0 0 18px ${riskColor(t.risk_level)}30`;

        document.getElementById('risk-reason-text').textContent = t.risk_reason  || 'No threats.';
        document.getElementById('risk-action-text').textContent = t.risk_action  || 'Monitoring.';

        // HUD chip state
        const hudState = document.getElementById('hud-state');
        hudState.textContent = `RISK: ${t.risk_level} | People: ${t.count}`;
        hudState.style.color = riskColor(t.risk_level);

        // Gauges
        setBar('bar-density', t.density);
        document.getElementById('g-density-val').textContent = t.density.toFixed(0) + '%';

        setBar('bar-violence', t.violence_prob || 0);
        document.getElementById('g-violence-val').textContent = t.violence ? 'DETECTED ⚠' : 'NORMAL';

        setBar('bar-panic', t.panic_score || 0);
        document.getElementById('g-panic-val').textContent = t.panic ? 'PANIC ⚠' : 'NORMAL';

        const dbPct = Math.min(((t.decibels - 40) / 70) * 100, 100);
        setBar('bar-noise', dbPct);
        document.getElementById('g-noise-val').textContent = t.decibels + ' dB';

        // Sidebar dB bar
        document.getElementById('db-fill').style.width  = dbPct + '%';
        document.getElementById('db-label').textContent = t.decibels + ' dB';

        // Audio alarm
        if (['HIGH', 'CRITICAL'].includes(t.risk_level) && !['HIGH', 'CRITICAL'].includes(lastRiskLevel)) {
            alarmAudio.play().catch(() => {});
        } else if (!['HIGH', 'CRITICAL'].includes(t.risk_level)) {
            alarmAudio.pause();
            alarmAudio.currentTime = 0;
        }
        lastRiskLevel = t.risk_level;

    } catch (e) {}
}

// ── Alert table ────────────────────────────────────────────────────────────

async function loadAlerts() {
    try {
        const alerts = await fetch(API.alerts).then(r => r.json());
        const tbody  = document.getElementById('alert-table-body');
        const badge  = document.getElementById('alert-count-badge');
        badge.textContent = (alerts.length || 0) + ' Alerts';

        if (!alerts.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="placeholder">No alerts logged yet.</td></tr>';
            return;
        }

        tbody.innerHTML = alerts.map(a => {
            const snap = a.evidence_path
                ? `<button class="snap-btn" onclick="openLightbox('/outputs/evidence/${a.evidence_path}', '${a.evidence_path}')">View</button>`
                : '—';
            return `<tr>
                <td class="mono">${a.timestamp}</td>
                <td>${a.type}</td>
                <td>${riskBadge(a.risk_level)}</td>
                <td>${a.details || '—'}</td>
                <td>${snap}</td>
            </tr>`;
        }).join('');
    } catch (e) {}
}

// ── Evidence gallery ───────────────────────────────────────────────────────

async function loadEvidence() {
    try {
        const files  = await fetch(API.evidence).then(r => r.json());
        const grid   = document.getElementById('evidence-grid');

        if (!files.length) {
            grid.innerHTML = '<div class="evidence-placeholder">No evidence saved yet. Trigger a simulation to generate snapshots.</div>';
            return;
        }

        grid.innerHTML = files.map(f => `
            <div class="ev-thumb-wrap" onclick="openLightbox('/outputs/evidence/images/${f}', '${f}')">
                <img src="/outputs/evidence/images/${f}" alt="${f}" loading="lazy">
                <div class="ev-thumb-cap">${f}</div>
            </div>`).join('');
    } catch (e) {}
}

// ── Lightbox ───────────────────────────────────────────────────────────────

function openLightbox(src, cap) {
    document.getElementById('lb-img').src = src;
    document.getElementById('lb-cap').textContent = cap;
    const lb = document.getElementById('lightbox');
    lb.style.display = 'flex';
}

document.getElementById('lb-close').addEventListener('click', () => {
    document.getElementById('lightbox').style.display = 'none';
});

// ── Chart.js analytics ─────────────────────────────────────────────────────

let chartLabels = [], chartCrowd = [], chartRisk = [];

async function loadChart() {
    try {
        const data = await fetch(API.analytics).then(r => r.json());
        if (!data.history || !data.history.length) return;

        chartLabels = data.history.map(r => r.timestamp || r.ts || '');
        chartCrowd  = data.history.map(r => r.person_count  || 0);
        chartRisk   = data.history.map(r => r.risk_score || 0);

        if (trendChart) { trendChart.destroy(); }

        const ctx = document.getElementById('trend-chart').getContext('2d');
        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [
                    {
                        label: 'Crowd Count',
                        data: chartCrowd,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99,102,241,0.08)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true,
                        pointRadius: 3,
                    },
                    {
                        label: 'Risk Score %',
                        data: chartRisk,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239,68,68,0.08)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true,
                        pointRadius: 3,
                        yAxisID: 'y2',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#8b95a8', boxWidth: 12, font: { size: 11 } }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#8b95a8', maxTicksLimit: 8, font: { size: 10 } },
                        grid:  { color: 'rgba(255,255,255,0.04)' }
                    },
                    y: {
                        ticks: { color: '#8b95a8', font: { size: 10 } },
                        grid:  { color: 'rgba(255,255,255,0.04)' }
                    },
                    y2: {
                        position: 'right',
                        ticks: { color: '#ef4444', font: { size: 10 }, callback: v => v + '%' },
                        grid:  { drawOnChartArea: false }
                    }
                }
            }
        });
    } catch (e) {}
}

// ── Simulation toggles ─────────────────────────────────────────────────────

async function postConfig(patch) {
    await fetch(API.config, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch)
    });
}

['weapon', 'violence', 'panic', 'scream'].forEach(name => {
    const el = document.getElementById(`tog-${name}`);
    if (el) {
        el.addEventListener('change', () => {
            postConfig({ [`simulated_${name}`]: el.checked });
        });
    }
});

const capSlider = document.getElementById('cap-slider');
const capVal    = document.getElementById('cap-val');
capSlider.addEventListener('input', () => {
    capVal.textContent = capSlider.value;
    postConfig({ capacity: parseInt(capSlider.value) });
});

const densSlider = document.getElementById('dens-slider');
const densVal    = document.getElementById('dens-val');
densSlider.addEventListener('input', () => {
    densVal.textContent = densSlider.value + '%';
    postConfig({ density_threshold: parseInt(densSlider.value) });
});

// ── Source selector ────────────────────────────────────────────────────────

document.getElementById('btn-webcam').addEventListener('click', async () => {
    await fetch('/api/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ src_type: 'Webcam', param: 0 })
    });
    document.getElementById('kpi-source').textContent = 'Webcam #0';
    document.querySelectorAll('.src-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-webcam').classList.add('active');
});

document.getElementById('btn-webcam-2').addEventListener('click', async () => {
    await fetch('/api/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ src_type: 'Webcam', param: 1 })
    });
    document.getElementById('kpi-source').textContent = 'Webcam #1';
    document.querySelectorAll('.src-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-webcam-2').classList.add('active');
});

document.getElementById('file-upload-input').addEventListener('change', async function () {
    const file = this.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('video', file);
    const resp = await fetch('/api/upload', { method: 'POST', body: fd }).then(r => r.json());
    if (resp.status === 'ok') {
        document.getElementById('kpi-source').textContent = resp.filename;
        document.getElementById('btn-webcam').classList.remove('active');
    }
});

document.getElementById('btn-grid-toggle').addEventListener('click', async function () {
    const cfg = await fetch(API.config).then(r => r.json());
    await postConfig({ show_grid: !cfg.show_grid });
    this.classList.toggle('active');
});

// ── Chart refresh ──────────────────────────────────────────────────────────

document.getElementById('btn-refresh-chart').addEventListener('click', loadChart);
document.getElementById('btn-refresh-evidence').addEventListener('click', loadEvidence);

// ── Chatbot ────────────────────────────────────────────────────────────────

async function sendChat() {
    const input = document.getElementById('chat-input');
    const q = input.value.trim();
    if (!q) return;
    addMsg(q, 'user');
    input.value = '';
    try {
        const r = await fetch(API.chatbot, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q })
        }).then(r => r.json());
        addMsg(r.response || 'No response.', 'bot');
    } catch (e) {
        addMsg('Error connecting to AI assistant.', 'bot');
    }
}

function addMsg(text, role) {
    const body = document.getElementById('chatbot-messages');
    const div  = document.createElement('div');
    div.className = `msg ${role}`;
    div.innerHTML = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
}

document.getElementById('chat-send').addEventListener('click', sendChat);
document.getElementById('chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') sendChat();
});

// ── Nav smooth scroll ──────────────────────────────────────────────────────

document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', function(e) {
        const target = this.getAttribute('href');
        if (target && target.startsWith('#')) {
            e.preventDefault();
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            document.querySelector(target)?.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// ── Static evidence image serving ─────────────────────────────────────────

// Evidence served via outputs route — ensure Flask has a route for this
// (handled in app.py via send_from_directory)

// ── Initialise ─────────────────────────────────────────────────────────────

monoClock();

setInterval(pollTelemetry, 1500);
setInterval(loadAlerts,     5000);
setInterval(loadEvidence,  12000);
setInterval(loadChart,     30000);

// Initial loads
pollTelemetry();
loadAlerts();
loadEvidence();
loadChart();

console.log('CrowdWatch AI V2 Dashboard Initialised');
