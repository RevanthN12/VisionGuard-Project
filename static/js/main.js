/* VisionGuard Medical AI — Frontend Interactivity Script */

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initLanguageSwitcher();
    initDropzone();
    initCharts();
});

// Theme Management
function initTheme() {
    const savedTheme = localStorage.getItem('vg_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    const themeToggle = document.getElementById('themeToggleBtn');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('vg_theme', next);
            updateThemeIcon(next);
        });
    }
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
    }
}

// Multi-Language Support (i18n)
function initLanguageSwitcher() {
    const langSelect = document.getElementById('langSelect');
    if (langSelect) {
        langSelect.addEventListener('change', async (e) => {
            const lang = e.target.value;
            try {
                const res = await fetch(`/api/i18n/${lang}`);
                const data = await res.json();
                if (data.success) {
                    applyTranslations(data.translations);
                }
            } catch (err) {
                console.error("i18n fetch failed:", err);
            }
        });
    }
}

function applyTranslations(t) {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) {
            el.textContent = t[key];
        }
    });
}

// Drag & Drop Image Upload
function initDropzone() {
    const dropzone = document.getElementById('retinalDropzone');
    const fileInput = document.getElementById('retinalFileInput');
    const previewContainer = document.getElementById('imagePreviewBox');
    const previewImg = document.getElementById('previewImg');

    if (!dropzone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            fileInput.files = files;
            showPreview(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (fileInput.files.length > 0) {
            showPreview(fileInput.files[0]);
        }
    });

    function showPreview(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            if (previewImg) previewImg.src = e.target.result;
            if (previewContainer) previewContainer.classList.remove('d-none');
        };
        reader.readAsDataURL(file);
    }
}

// Chart.js Aggregations
function initCharts() {
    const ctxSeverity = document.getElementById('chartSeverity');
    if (ctxSeverity && window.severityData) {
        new Chart(ctxSeverity, {
            type: 'doughnut',
            data: {
                labels: Object.keys(window.severityData),
                datasets: [{
                    data: Object.values(window.severityData),
                    backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#881337'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8' } }
                }
            }
        });
    }
}
