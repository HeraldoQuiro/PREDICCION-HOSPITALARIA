/**
 * =============================================================================
 * SISTEMA DE PREDICCIÓN DE SATURACIÓN DE CAMAS UCI — PUNO 2026 (SatUCI-Puno)
 * JavaScript Principal: Chart.js, Interactividad de Dashboard y Registro en Vivo
 * =============================================================================
 */

document.addEventListener('DOMContentLoaded', function () {
    initClock();
    initFlashAlerts();
    initDashboardCharts();
    initRegistroLiveCalc();
    initMobileSidebar();
});

/**
 * 1. Reloj en tiempo real para el topbar (Hora Local Puno)
 */
function initClock() {
    const clockEl = document.getElementById('topbar-live-clock');
    if (!clockEl) return;

    function update() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        clockEl.textContent = `${hours}:${minutes}:${seconds}`;
    }

    update();
    setInterval(update, 1000);
}

/**
 * 2. Cierre automático de alertas Flash
 */
function initFlashAlerts() {
    const alerts = document.querySelectorAll('.flash-alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 400);
        }, 6000);
    });
}

/**
 * 3. Gráficas interactivas con Chart.js (Dashboard)
 */
let trendChartInstance = null;
let bedsChartInstance = null;

function initDashboardCharts() {
    const trendCanvas = document.getElementById('occupancyTrendChart');
    const bedsCanvas = document.getElementById('bedDistributionChart');

    if (trendCanvas) {
        loadTrendChart(30);
        
        // Manejadores de botones de filtro temporal
        const filterBtns = document.querySelectorAll('.btn-chart-filter[data-days]');
        filterBtns.forEach(btn => {
            btn.addEventListener('click', function () {
                filterBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const days = parseInt(this.getAttribute('data-days'), 10);
                loadTrendChart(days);
            });
        });
    }

    if (bedsCanvas) {
        loadBedsDistributionChart();
    }
}

/**
 * Carga la serie temporal de ocupación desde el endpoint /api/chart/trend
 */
function loadTrendChart(days) {
    const canvas = document.getElementById('occupancyTrendChart');
    if (!canvas) return;

    fetch(`/api/chart/trend?days=${days}`)
        .then(response => response.json())
        .then(data => {
            renderTrendChart(canvas, data);
        })
        .catch(err => {
            console.error('[SatUCI] Error cargando datos de tendencia:', err);
        });
}

function renderTrendChart(canvas, chartData) {
    const ctx = canvas.getContext('2d');

    if (trendChartInstance) {
        trendChartInstance.destroy();
    }

    // Configuración global de Chart.js para modo oscuro
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";

    // Dataset para la línea de umbral crítico de saturación (85%)
    const thresholdData = chartData.labels.map(() => 85.0);

    const datasets = [
        ...chartData.datasets,
        {
            label: 'Umbral Saturación (85%)',
            data: thresholdData,
            borderColor: '#ff4757',
            borderWidth: 2,
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
            tension: 0
        }
    ];

    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        boxHeight: 12,
                        padding: 16,
                        usePointStyle: true,
                        font: { size: 12, weight: '500' }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    borderWidth: 1,
                    padding: 12,
                    boxPadding: 6,
                    usePointStyle: true,
                    callbacks: {
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            if (context.parsed.y !== null) {
                                label += context.parsed.y.toFixed(1) + '%';
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.04)',
                        drawBorder: false
                    },
                    ticks: {
                        maxRotation: 45,
                        font: { size: 11 }
                    }
                },
                y: {
                    min: 0,
                    max: 105,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        stepSize: 20,
                        callback: val => val + '%'
                    }
                }
            }
        }
    });
}

/**
 * Carga la gráfica de barras de camas ocupadas vs disponibles
 */
function loadBedsDistributionChart() {
    const canvas = document.getElementById('bedDistributionChart');
    if (!canvas) return;

    fetch('/api/chart/beds')
        .then(res => res.json())
        .then(data => {
            renderBedsDistributionChart(canvas, data);
        })
        .catch(err => console.error('[SatUCI] Error cargando camas:', err));
}

function renderBedsDistributionChart(canvas, bedData) {
    const ctx = canvas.getContext('2d');

    if (bedsChartInstance) {
        bedsChartInstance.destroy();
    }

    bedsChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: bedData.labels,
            datasets: [
                {
                    label: 'Camas Ocupadas',
                    data: bedData.occupied,
                    backgroundColor: 'rgba(255, 71, 87, 0.8)',
                    borderColor: '#ff4757',
                    borderWidth: 1,
                    borderRadius: 6
                },
                {
                    label: 'Camas Disponibles',
                    data: bedData.available,
                    backgroundColor: 'rgba(0, 212, 255, 0.8)',
                    borderColor: '#00d4ff',
                    borderWidth: 1,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        padding: 14,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    padding: 12
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { stepSize: 2 }
                }
            }
        }
    });
}

/**
 * 4. Calculador en vivo para el formulario de Registro Diario
 */
function initRegistroLiveCalc() {
    const selectHosp = document.getElementById('form-hospital-select');
    const inputTotal = document.getElementById('form-camas-total');
    const inputOcup = document.getElementById('form-camas-ocupadas');
    const displayDisp = document.getElementById('live-camas-disp');
    const displayPct = document.getElementById('live-porcentaje');
    const displayStatus = document.getElementById('live-status-badge');
    const progressBar = document.getElementById('live-progress-fill');

    if (!inputTotal || !inputOcup || !displayPct) return;

    // Cuando el usuario cambia de hospital, consultar su capacidad nominal
    if (selectHosp) {
        selectHosp.addEventListener('change', function () {
            const codigo = this.value;
            if (!codigo) return;
            fetch(`/api/hospital/${codigo}/latest`)
                .then(res => res.json())
                .then(data => {
                    if (data && data.camas_uci_tot) {
                        inputTotal.value = data.camas_uci_tot;
                        recalculate();
                    }
                })
                .catch(err => console.log('Error obteniendo hospital:', err));
        });
    }

    function recalculate() {
        const total = parseInt(inputTotal.value, 10) || 0;
        const ocup = parseInt(inputOcup.value, 10) || 0;

        if (total <= 0) {
            displayDisp.textContent = '0';
            displayPct.textContent = '0.0%';
            if (progressBar) progressBar.style.width = '0%';
            return;
        }

        const disp = Math.max(0, total - ocup);
        const pct = Math.min(100.0, Math.max(0.0, (ocup / total) * 100.0));

        displayDisp.textContent = disp;
        displayPct.textContent = `${pct.toFixed(1)}%`;

        if (progressBar) {
            progressBar.style.width = `${pct}%`;
            progressBar.className = 'progress-bar-fill';
            if (pct >= 85.0) {
                progressBar.classList.add('danger');
            } else if (pct >= 75.0) {
                progressBar.classList.add('warning');
            } else {
                progressBar.classList.add('success');
            }
        }

        if (displayStatus) {
            if (pct >= 85.0) {
                displayStatus.className = 'badge badge-danger animated-pulse';
                displayStatus.innerHTML = '<i class="fas fa-exclamation-triangle"></i> SATURADO (≥85%)';
            } else if (pct >= 75.0) {
                displayStatus.className = 'badge badge-warning';
                displayStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> EN ALERTA (≥75%)';
            } else {
                displayStatus.className = 'badge badge-success';
                displayStatus.innerHTML = '<i class="fas fa-check-circle"></i> NORMAL';
            }
        }
    }

    inputTotal.addEventListener('input', recalculate);
    inputOcup.addEventListener('input', recalculate);

    // Cálculo inicial
    recalculate();
}

/**
 * 5. Menú lateral responsive para móviles y tablets
 */
function initMobileSidebar() {
    const toggleBtn = document.getElementById('mobile-sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    if (!toggleBtn || !sidebar) return;

    toggleBtn.addEventListener('click', function () {
        sidebar.classList.toggle('mobile-open');
    });
}
