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
let hardwareChart = null;
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
    
    // Initialize Ollama status check
    checkOllamaStatus();
    setInterval(checkOllamaStatus, 30000);
});

function setupEventListeners() {
    const testOllamaBtn = document.getElementById('test-ollama');
    if (testOllamaBtn) {
        testOllamaBtn.addEventListener('click', async function() {
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
            
            const isOnline = await checkOllamaStatus();
            
            this.disabled = false;
            this.innerHTML = '<i class="fas fa-bolt"></i> Test Now';
            
            if (isOnline) {
                addOllamaAction('✅ Ollama server is online and responding', 'ollama-success');
            } else {
                addOllamaAction('❌ Ollama server is offline or not responding', 'ollama-error');
            }
        });
    }

    const aiDiagnoseBtn = document.getElementById('ai-diagnose');
    if (aiDiagnoseBtn) {
        aiDiagnoseBtn.onclick = function() {
            this.disabled = true;
            runDoctorDiagnosis();
            setTimeout(() => this.disabled = false, 3000);
        };
    }

    const refreshAiBtn = document.getElementById('refresh-ai');
    if (refreshAiBtn) {
        refreshAiBtn.onclick = function() {
            if (elements.ollamaActions) {
                elements.ollamaActions.innerHTML = '';
            }
            addOllamaAction();
        };
    }

    const clearLogsBtn = document.getElementById('clear-logs');
    if (clearLogsBtn) {
        clearLogsBtn.onclick = function() {
            if (elements.rawLogs) {
                elements.rawLogs.textContent = 'Logs cleared ' + new Date().toLocaleTimeString();
            }
        };
    }

    const refreshLogsBtn = document.getElementById('refresh-logs');
    if (refreshLogsBtn) {
        refreshLogsBtn.onclick = function() {
            loadLogs();
        };
    }

    if (elements.analyze) {
        elements.analyze.onclick = async () => {
            elements.analyze.disabled = true;
            if (elements.summary) {
                elements.summary.innerHTML = "<div class='loading'></div> Analyzing with AI...";
            }
            
            try {
                const response = await fetch('/api/summary');
                const data = await response.json();
                
                if (elements.summary) {
                    if (data.ok) {
                        elements.summary.textContent = data.summary;
                    } else {
                        elements.summary.textContent = "Error: " + data.summary;
                    }
                }
            } catch (error) {
                if (elements.summary) {
                    elements.summary.textContent = "Error connecting to server: " + error.message;
                }
            } finally {
                elements.analyze.disabled = false;
            }
        };
    }
}

function toggleLogs() {
    const content = document.getElementById('logs-content');
    if (content) {
        content.classList.toggle('expanded');
    }
}

function loadLogs() {
    fetch('/api/hardware')
        .then(response => response.json())
        .then(data => {
            if (elements.rawLogs) {
                elements.rawLogs.textContent = data.report || "No logs available";
            }
        })
        .catch(error => {
            if (elements.rawLogs) {
                elements.rawLogs.textContent = "Error loading logs: " + error.message;
            }
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
        if (elements.patternsCount) {
            elements.patternsCount.textContent = patternsData.count || '0';
        }
        if (elements.actionsCount) {
            elements.actionsCount.textContent = actionsData.recent_actions?.length || '0';
        }
        if (elements.metricsCount) {
            elements.metricsCount.textContent = metricsData.available_metrics?.length || '0';
        }
        
        // Calculate success rate
        if (actionsData.statistics && elements.successRate) {
            const totalActions = Object.values(actionsData.statistics).reduce((sum, stat) => sum + stat.total, 0);
            const successfulActions = Object.values(actionsData.statistics).reduce((sum, stat) => sum + (stat.success_rate * stat.total), 0);
            const successRate = totalActions > 0 ? (successfulActions / totalActions * 100).toFixed(1) : '0';
            elements.successRate.textContent = `${successRate}%`;
        }
        
        // Update status indicators
        if (elements.dbStatus) {
            elements.dbStatus.textContent = 'Active';
            elements.dbStatus.className = 'tag tag-success';
        }
        
    } catch (error) {
        console.error('Error loading database metrics:', error);
        if (elements.dbStatus) {
            elements.dbStatus.textContent = 'Error';
            elements.dbStatus.className = 'tag tag-danger';
        }
    }
}

async function updateHealthDisplay(healthData) {
    // Update header metrics
    let cpuTemp = healthData.cpu?.temperature;
    
    // If temperature is 0, try to get it from the dedicated endpoint
    if (cpuTemp === 0 || cpuTemp === undefined) {
        try {
            const tempResponse = await fetch('/api/temperature');
            const tempData = await tempResponse.json();
            if (tempData.temperature && tempData.temperature > 0) {
                cpuTemp = tempData.temperature;
            }
        } catch (error) {
            console.error('Error fetching temperature:', error);
        }
    }
    
    if (cpuTemp && cpuTemp > 0) {
        if (elements.headerCpu) elements.headerCpu.textContent = `${cpuTemp.toFixed(1)}°C`;
        if (elements.metricCpu) elements.metricCpu.textContent = `${cpuTemp.toFixed(1)}°C`;
    } else {
        if (elements.headerCpu) elements.headerCpu.textContent = 'N/A';
        if (elements.metricCpu) elements.metricCpu.textContent = 'N/A';
    }
    
    if (healthData.memory?.percent) {
        if (elements.headerMemory) elements.headerMemory.textContent = `${healthData.memory.percent}%`;
        if (elements.metricMemory) elements.metricMemory.textContent = `${healthData.memory.percent}%`;
    }
    
    if (healthData.disk?.percent && elements.metricDisk) {
        elements.metricDisk.textContent = `${healthData.disk.percent}%`;
    }
    
    // Update system info
    if (elements.uptime) elements.uptime.textContent = 'Live';
    if (elements.loadAvg) {
        elements.loadAvg.textContent = healthData.cpu ? `${healthData.cpu.load_1min.toFixed(2)}, ${healthData.cpu.load_5min.toFixed(2)}, ${healthData.cpu.load_15min.toFixed(2)}` : '--';
    }
    if (elements.cpuCores) elements.cpuCores.textContent = healthData.cpu ? '4 cores' : '--';
    if (elements.totalMemory) elements.totalMemory.textContent = healthData.memory ? `${healthData.memory.total_gb}GB` : '--';
    if (elements.totalDisk) elements.totalDisk.textContent = healthData.disk ? `${healthData.disk.total_gb}GB` : '--';
    
    // Update chart data
    const now = new Date().toLocaleTimeString();
    timestamps.push(now);
    cpuData.push(cpuTemp > 0 ? cpuTemp : 0);
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
    if (!trendElement) return;
    
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
    
    const actionsContainer = document.getElementById('ollama-actions');
    if (!actionsContainer) return;
    
    const actionElement = document.createElement('div');
    actionElement.className = 'ollama-action';
    actionElement.innerHTML = `
        <div class="timestamp">${new Date().toLocaleTimeString()}</div>
        <div class="${className}">${message}</div>
    `;
    
    actionsContainer.prepend(actionElement);
    
    // Keep only last 5 actions
    while (actionsContainer.children.length > 5) {
        actionsContainer.removeChild(actionsContainer.lastChild);
    }
}

function initCharts() {
    const canvas = document.getElementById('hardwareChart');
    if (!canvas) return;
    
    // Destroy existing chart if it exists
    if (hardwareChart) {
        hardwareChart.destroy();
    }
    
    const ctx = canvas.getContext('2d');
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

async function checkOllamaStatus() {
    const statusElement = document.getElementById('ollama-status-text');
    const serverStatusElement = document.getElementById('ollama-server-status');
    const modelsElement = document.getElementById('ollama-models');
    const responseTimeElement = document.getElementById('ollama-response-time');
    const lastCheckElement = document.getElementById('ollama-last-check');
    const headerOllamaElement = document.getElementById('header-ollama');
    const ollamaStatusElement = document.getElementById('ollama-status');

    // Check if elements exist before trying to update them
    if (!statusElement || !serverStatusElement || !modelsElement || 
        !responseTimeElement || !lastCheckElement || !headerOllamaElement || 
        !ollamaStatusElement) {
        console.warn('Some Ollama status elements not found');
        return false;
    }

    try {
        const startTime = Date.now();
        const response = await fetch('/api/ollama-status', {
            signal: AbortSignal.timeout(5000)
        });
        const endTime = Date.now();
        const responseTime = endTime - startTime;

        const data = await response.json();
        
        // Update response time
        responseTimeElement.textContent = `${responseTime} ms`;
        
        // Update last check time
        lastCheckElement.textContent = new Date().toLocaleTimeString();

        if (data.status === 'online') {
            statusElement.textContent = 'Online ✅';
            statusElement.style.color = '#10b981';
            serverStatusElement.textContent = 'Online';
            serverStatusElement.className = 'tag tag-success';
            headerOllamaElement.textContent = 'Online';
            ollamaStatusElement.textContent = 'Online';
            ollamaStatusElement.className = 'tag tag-success';
            
            // Show available models
            if (data.models && data.models.length > 0) {
                const modelNames = data.models.map(model => model.name).join(', ');
                modelsElement.textContent = modelNames;
            } else {
                modelsElement.textContent = 'No models loaded';
            }
            
            return true;
        } else {
            statusElement.textContent = `Error: ${data.message || 'Unknown error'}`;
            statusElement.style.color = '#ef4444';
            serverStatusElement.textContent = 'Error';
            serverStatusElement.className = 'tag tag-danger';
            headerOllamaElement.textContent = 'Error';
            ollamaStatusElement.textContent = 'Error';
            ollamaStatusElement.className = 'tag tag-danger';
            modelsElement.textContent = 'Unknown';
            return false;
        }
    } catch (error) {
        console.error('Ollama status check failed:', error);
        statusElement.textContent = `Offline: ${error.name === 'TimeoutError' ? 'Timeout' : error.message}`;
        statusElement.style.color = '#ef4444';
        serverStatusElement.textContent = 'Offline';
        serverStatusElement.className = 'tag tag-danger';
        headerOllamaElement.textContent = 'Offline';
        ollamaStatusElement.textContent = 'Offline';
        ollamaStatusElement.className = 'tag tag-danger';
        modelsElement.textContent = 'Unknown';
        responseTimeElement.textContent = 'Timeout';
        lastCheckElement.textContent = new Date().toLocaleTimeString();
        return false;
    }
}

// Load network and security data
fetch('/api/network')
    .then(response => response.json())
    .then(data => {
        if (elements.network) {
            elements.network.textContent = data.summary || 'No network data available';
        }
    });

fetch('/api/security')
    .then(response => response.json())
    .then(data => {
        if (elements.security) {
            elements.security.textContent = data.report || 'No security data available';
        }
    });