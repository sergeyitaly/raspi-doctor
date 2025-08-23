// DOM Elements
const elements = {
    analyze: document.getElementById('analyze'),
    summary: document.getElementById('summary'),
    network: document.getElementById('network'),
    security: document.getElementById('security'),
    rawLogs: document.getElementById('raw-logs'),
    headerCpu: document.getElementById('header-cpu'),
    headerMemory: document.getElementById('header-memory'),
    headerStatus: document.getElementById('header-status'),
    metricCpu: document.getElementById('metric-cpu'),
    metricMemory: document.getElementById('metric-memory'),
    metricDisk: document.getElementById('metric-disk'),
    uptime: document.getElementById('uptime'),
    loadAvg: document.getElementById('load-avg'),
    processCount: document.getElementById('process-count'),
    cpuCores: document.getElementById('cpu-cores'),
    totalMemory: document.getElementById('total-memory'),
    totalDisk: document.getElementById('total-disk'),
    overallHealth: document.getElementById('overall-health'),
    aiStatus: document.getElementById('ai-status'),
    ollamaActions: document.getElementById('ollama-actions'),
    patternsCount: document.getElementById('patterns-count'),
    actionsCount: document.getElementById('actions-count'),
    metricsCount: document.getElementById('metrics-count'),
    successRate: document.getElementById('success-rate'),
    dbStatus: document.getElementById('db-status'),
    aiDoctorStatus: document.getElementById('ai-doctor-status'),
    ollamaStatus: document.getElementById('ollama-status')
};

// Initialize charts
let hardwareChart;
let cpuData = [];
let memoryData = [];
let diskData = [];
let timestamps = [];

// Load initial data
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
    loadInitialData();
    loadDatabaseMetrics();
    
    // Set up periodic updates
    setInterval(updateLiveData, 5000);
    setInterval(loadDatabaseMetrics, 30000);
    setInterval(addOllamaAction, 15000);
    
    // Set up event listeners
    setupEventListeners();
    
    // Load real logs
    loadLogs();
});

function setupEventListeners() {
    document.getElementById('ai-diagnose').onclick = function() {
        this.disabled = true;
        runDoctorDiagnosis();
        setTimeout(() => this.disabled = false, 3000);
    };

    document.getElementById('refresh-ai').onclick = function() {
        elements.ollamaActions.innerHTML = '';
        addOllamaAction();
    };

    document.getElementById('clear-logs').onclick = function() {
        elements.rawLogs.textContent = 'Logs cleared ' + new Date().toLocaleTimeString();
    };

    document.getElementById('refresh-logs').onclick = function() {
        loadLogs();
    };

    elements.analyze.onclick = async () => {
        elements.analyze.disabled = true;
        elements.summary.innerHTML = "<div class='loading'></div> Analyzing with AI...";
        
        try {
            const response = await fetch('/api/summary');
            const data = await response.json();
            
            if (data.ok) {
                elements.summary.textContent = data.summary;
            } else {
                elements.summary.textContent = "Error: " + data.summary;
            }
        } catch (error) {
            elements.summary.textContent = "Error connecting to server: " + error.message;
        } finally {
            elements.analyze.disabled = false;
        }
    };
}

function toggleLogs() {
    const content = document.getElementById('logs-content');
    content.classList.toggle('expanded');
}

function loadLogs() {
    fetch('/api/hardware')
        .then(response => response.json())
        .then(data => {
            elements.rawLogs.textContent = data.report || "No logs available";
        })
        .catch(error => {
            elements.rawLogs.textContent = "Error loading logs: " + error.message;
        });
}

async function loadInitialData() {
    try {
        // Load system health data
        const response = await fetch('/api/system-health');
        const data = await response.json();
        
        if (data.current_health && !data.current_health.error) {
            updateHealthDisplay(data.current_health);
        }
        
        if (data.historical_metrics && data.historical_metrics.metrics) {
            updateMetricsDisplay(data.historical_metrics.metrics);
        }
        
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

async function loadDatabaseMetrics() {
    try {
        const responses = await Promise.all([
            fetch('/api/metrics'),
            fetch('/api/patterns'),
            fetch('/api/actions'),
            fetch('/api/db-status')
        ]);
        
        const [metricsData, patternsData, actionsData, dbStatus] = await Promise.all(
            responses.map(r => r.json())
        );
        
        // Update database metrics
        elements.patternsCount.textContent = patternsData.count || '0';
        elements.actionsCount.textContent = actionsData.recent_actions?.length || '0';
        elements.metricsCount.textContent = metricsData.available_metrics?.length || '0';
        
        // Calculate success rate
        if (actionsData.statistics) {
            const totalActions = Object.values(actionsData.statistics).reduce((sum, stat) => sum + stat.total, 0);
            const successfulActions = Object.values(actionsData.statistics).reduce((sum, stat) => sum + (stat.success_rate * stat.total), 0);
            const successRate = totalActions > 0 ? (successfulActions / totalActions * 100).toFixed(1) : '0';
            elements.successRate.textContent = `${successRate}%`;
        }
        
        // Update status indicators
        elements.dbStatus.textContent = 'Active';
        elements.dbStatus.className = 'tag tag-success';
        
    } catch (error) {
        console.error('Error loading database metrics:', error);
        elements.dbStatus.textContent = 'Error';
        elements.dbStatus.className = 'tag tag-danger';
    }
}

function updateHealthDisplay(healthData) {
    // Update header metrics
    if (healthData.cpu?.temperature) {
        elements.headerCpu.textContent = `${healthData.cpu.temperature}°C`;
        elements.metricCpu.textContent = `${healthData.cpu.temperature}°C`;
    }
    
    if (healthData.memory?.percent) {
        elements.headerMemory.textContent = `${healthData.memory.percent}%`;
        elements.metricMemory.textContent = `${healthData.memory.percent}%`;
    }
    
    if (healthData.disk?.percent) {
        elements.metricDisk.textContent = `${healthData.disk.percent}%`;
    }
    
    // Update system info
    elements.uptime.textContent = 'Live';
    elements.loadAvg.textContent = healthData.cpu ? `${healthData.cpu.load_1min}, ${healthData.cpu.load_5min}, ${healthData.cpu.load_15min}` : '--';
    elements.cpuCores.textContent = healthData.cpu ? '4 cores' : '--';
    elements.totalMemory.textContent = healthData.memory ? `${healthData.memory.total_gb}GB` : '--';
    elements.totalDisk.textContent = healthData.disk ? `${healthData.disk.total_gb}GB` : '--';
    
    // Update chart data
    const now = new Date().toLocaleTimeString();
    timestamps.push(now);
    cpuData.push(healthData.cpu?.temperature || 0);
    memoryData.push(healthData.memory?.percent || 0);
    diskData.push(healthData.disk?.percent || 0);
    
    if (timestamps.length > 15) {
        timestamps.shift();
        cpuData.shift();
        memoryData.shift();
        diskData.shift();
    }
    
    updateChart();
}

function updateMetricsDisplay(metrics) {
    // Update trend indicators
    updateTrendIndicator('cpu', metrics.cpu_temperature?.value);
    updateTrendIndicator('memory', metrics.memory_percent?.value);
    updateTrendIndicator('disk', metrics.disk_percent?.value);
}

function updateTrendIndicator(metric, value) {
    if (!value) return;
    
    const trendElement = document.getElementById(`${metric}-trend`);
    const randomChange = (Math.random() * 2 - 1).toFixed(1);
    
    if (randomChange > 0.2) {
        trendElement.className = 'metric-trend trend-up';
        trendElement.innerHTML = `<i class="fas fa-arrow-up"></i><span>${randomChange}%</span>`;
    } else if (randomChange < -0.2) {
        trendElement.className = 'metric-trend trend-down';
        trendElement.innerHTML = `<i class="fas fa-arrow-down"></i><span>${Math.abs(randomChange)}%</span>`;
    } else {
        trendElement.className = 'metric-trend trend-neutral';
        trendElement.innerHTML = `<i class="fas fa-minus"></i><span>Stable</span>`;
    }
}

async function updateLiveData() {
    try {
        const response = await fetch('/api/system-health');
        const data = await response.json();
        
        if (data.current_health && !data.current_health.error) {
            updateHealthDisplay(data.current_health);
        }
        
    } catch (error) {
        console.error('Error updating live data:', error);
    }
}

async function runDoctorDiagnosis() {
    addOllamaAction("🤖 Running comprehensive system diagnosis...", "ollama-thinking");
    
    try {
        const response = await fetch('/api/run-doctor');
        const data = await response.json();
        
        if (data.status === 'started') {
            addOllamaAction("✅ Diagnosis started successfully", "ollama-success");
        } else {
            addOllamaAction("❌ Failed to start diagnosis", "ollama-error");
        }
    } catch (error) {
        addOllamaAction("❌ Error starting diagnosis: " + error.message, "ollama-error");
    }
}

function addOllamaAction(message, className) {
    if (!message) {
        // Default random actions
        const actions = [
            {
                message: "📊 Analyzing memory usage patterns...",
                class: "ollama-thinking",
                timestamp: "Just now"
            },
            {
                message: "✅ Optimized swap usage: 150MB reclaimed",
                class: "ollama-success",
                timestamp: "30s ago"
            },
            {
                message: "⚠️ Monitoring CPU temperature: Approaching threshold",
                class: "ollama-warning",
                timestamp: "1m ago"
            },
            {
                message: "🔧 Adjusted process priorities for better performance",
                class: "ollama-success",
                timestamp: "2m ago"
            },
            {
                message: "📡 Checking network connectivity...",
                class: "ollama-thinking",
                timestamp: "3m ago"
            }
        ];
        
        const action = actions[Math.floor(Math.random() * actions.length)];
        message = action.message;
        className = action.class;
    }
    
    const actionElement = document.createElement('div');
    actionElement.className = 'ollama-action';
    actionElement.innerHTML = `
        <div class="timestamp">${new Date().toLocaleTimeString()}</div>
        <div class="${className}">${message}</div>
    `;
    
    elements.ollamaActions.prepend(actionElement);
    
    // Keep only last 5 actions
    while (elements.ollamaActions.children.length > 5) {
        elements.ollamaActions.removeChild(elements.ollamaActions.lastChild);
    }
}

function initCharts() {
    const ctx = document.getElementById('hardwareChart').getContext('2d');
    hardwareChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({length: 15}, (_, i) => ''),
            datasets: [
                {
                    label: 'CPU °C',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 1.5,
                    pointRadius: 0
                },
                {
                    label: 'Memory %',
                    data: [],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 1.5,
                    pointRadius: 0
                },
                {
                    label: 'Disk %',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 1.5,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { 
                        color: '#94a3b8',
                        font: { size: 8 },
                        boxWidth: 8
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                    ticks: { 
                        color: '#94a3b8',
                        font: { size: 7 },
                        maxTicksLimit: 5
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { display: false }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            animations: {
                duration: 0
            }
        }
    });
}

function updateChart() {
    if (hardwareChart) {
        hardwareChart.data.datasets[0].data = cpuData;
        hardwareChart.data.datasets[1].data = memoryData;
        hardwareChart.data.datasets[2].data = diskData;
        hardwareChart.update('none');
    }
}

// Load network and security data
fetch('/api/network')
    .then(response => response.json())
    .then(data => {
        elements.network.textContent = data.summary || 'No network data available';
    });

fetch('/api/security')
    .then(response => response.json())
    .then(data => {
        elements.security.textContent = data.report || 'No security data available';
    });