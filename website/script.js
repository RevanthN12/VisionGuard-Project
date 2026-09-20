// Particle Background Effect
const canvas = document.getElementById('particleCanvas');
const ctx = canvas.getContext('2d');

let width, height, particles;

function initCanvas() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    particles = [];
    
    for(let i = 0; i < 80; i++) {
        particles.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            size: Math.random() * 2 + 1
        });
    }
}

function drawParticles() {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = 'rgba(56, 189, 248, 0.5)';
    
    particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        
        if(p.x < 0 || p.x > width) p.vx *= -1;
        if(p.y < 0 || p.y > height) p.vy *= -1;
        
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
    });
    
    requestAnimationFrame(drawParticles);
}

window.addEventListener('resize', initCanvas);
initCanvas();
drawParticles();

// Counter Animation
const counters = document.querySelectorAll('.counter');
const speed = 200;

counters.forEach(counter => {
    const updateCount = () => {
        const target = +counter.getAttribute('data-target');
        const count = +counter.innerText;
        const inc = target / speed;

        if (count < target) {
            counter.innerText = Math.ceil(count + inc);
            setTimeout(updateCount, 20);
        } else {
            counter.innerText = target;
        }
    };
    
    // Only animate when visible
    const observer = new IntersectionObserver(entries => {
        if(entries[0].isIntersecting) {
            updateCount();
            observer.disconnect();
        }
    });
    observer.observe(counter);
});


// Mock Live Dashboard Data
const kpiPeople = document.getElementById('kpi-people');
const kpiDensity = document.getElementById('kpi-density');
const kpiSpeed = document.getElementById('kpi-speed');

// Dashboard Mockup Simulation
setInterval(() => {
    // Generate slight variations
    const people = 120 + Math.floor(Math.random() * 15);
    const density = 40 + Math.floor(Math.random() * 10);
    const speed = (1.0 + Math.random() * 0.4).toFixed(1);
    
    document.getElementById('kpi-people').innerText = people;
    document.getElementById('kpi-density').innerText = density + '%';
    document.getElementById('kpi-speed').innerText = speed + ' px/f';
}, 2000);

// --- LOGIN MODAL LOGIC ---
function openLoginModal(e) {
    if(e) e.preventDefault();
    document.getElementById('loginModal').classList.add('active');
    document.getElementById('username').focus();
}

function closeLoginModal() {
    document.getElementById('loginModal').classList.remove('active');
    document.getElementById('loginError').style.display = 'none';
    document.getElementById('loginForm').reset();
}

function handleLogin(e) {
    e.preventDefault();
    const user = document.getElementById('username').value.trim();
    const pass = document.getElementById('password').value;

    const validUsers = {
        'admin': 'visionguard123',
        'operator': 'crowd@456',
        'demo': 'demo2026'
    };

    if (validUsers[user] && validUsers[user] === pass) {
        // Success: Redirect to the actual dashboard (Streamlit)
        window.location.href = "http://localhost:8501";
    } else {
        // Fail: Show error
        document.getElementById('loginError').style.display = 'block';
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('loginModal');
    if (event.target === modal) {
        closeLoginModal();
    }
}

const kpiRisk = document.getElementById('kpi-risk');
const logFeed = document.getElementById('log-feed');

let simPeople = 124;
let simDensity = 45;
let simSpeed = 1.2;

const logs = [
    "> [YOLOv8] Detected 3 new individuals in sector 4.",
    "> [FLOW] Calculating Farneback optical flow vectors.",
    "> [ANALYSIS] Crowd density stable at LOW threshold.",
    "> [SYS] Database log entry recorded successfully.",
    "> [YOLOv8] Tracking IDs updated for current frame.",
    "> [FLOW] Average movement speed calculated: 1.1 px/f"
];

function updateDashboard() {
    // Random walk simulation
    simPeople = Math.max(10, simPeople + Math.floor((Math.random() - 0.5) * 5));
    simDensity = Math.max(5, Math.min(95, simDensity + (Math.random() - 0.5) * 3));
    simSpeed = Math.max(0.2, simSpeed + (Math.random() - 0.5) * 0.2);
    
    kpiPeople.innerText = simPeople;
    kpiDensity.innerText = simDensity.toFixed(1) + '%';
    kpiSpeed.innerText = simSpeed.toFixed(1) + ' px/f';
    
    let riskLevel = "SAFE";
    let riskColor = "#22C55E";
    let riskClass = "";
    
    if (simDensity > 70) {
        riskLevel = "HIGH RISK";
        riskColor = "#EF4444";
        riskClass = "log-crit";
    } else if (simDensity > 55) {
        riskLevel = "WARNING";
        riskColor = "#F59E0B";
        riskClass = "log-warn";
    }
    
    kpiRisk.innerText = riskLevel;
    kpiRisk.style.color = riskColor;
    
    // Add log
    if (Math.random() > 0.6) {
        let newLog = logs[Math.floor(Math.random() * logs.length)];
        
        if (riskLevel !== "SAFE") {
            newLog = `> [ALERT] Risk level escalated to ${riskLevel}.`;
        }
        
        const p = document.createElement('p');
        p.innerText = newLog;
        if (riskClass) p.className = riskClass;
        
        logFeed.appendChild(p);
        logFeed.scrollTop = logFeed.scrollHeight;
        
        // Keep max 10 logs
        if (logFeed.children.length > 10) {
            logFeed.removeChild(logFeed.firstChild);
        }
    }
}

// Start simulation after delay
setTimeout(() => {
    setInterval(updateDashboard, 1500);
}, 2000);
