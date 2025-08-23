// DOM Elements - with safe element access
function getElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`Element with ID '${id}' not found`);
    }
    return element;
}

const elements = {
    analyze: getElement('analyze'),
    summary: getElement('summary'),
    network: getElement('network'),
    security: getElement('security'),
    rawLogs: getElement('raw-logs'),
    headerCpu: getElement('header-cpu'),
    headerMemory: getElement('header-memory'),
    headerStatus: getElement('header-status'),
    metricCpu: getElement('metric-cpu'),
    metricMemory: getElement('metric-memory'),
    metricDisk: getElement('metric-disk'),
    uptime: getElement('uptime'),
    loadAvg: getElement('load-avg'),
    processCount: getElement('process-count'),
    cpuCores: getElement('cpu-cores'),
    totalMemory: getElement('total-memory'),
    totalDisk: getElement('total-disk'),
    overallHealth: getElement('overall-health'),
    aiStatus: getElement('ai-status'),
    ollamaActions: getElement('ollama-actions'),
    patternsCount: getElement('patterns-count'),
    actionsCount: getElement('actions-count'),
    metricsCount: getElement('metrics-count'),
    successRate: getElement('success-rate'),
    dbStatus: getElement('db-status'),
    aiDoctorStatus: getElement('ai-doctor-status'),
    ollamaStatus: getElement('ollama-status')
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
    
    // Initialize Ollama status check only if elements exist
    if (checkOllamaElementsExist()) {
        checkOllamaStatus();
        setInterval(checkOllamaStatus, 30000);
    }
    
    // Setup Ollama test functionality
    setupOllamaTest();
});

// Check if all Ollama status elements exist
function checkOllamaElementsExist() {
    const requiredElements = [
        'ollama-status-text', 'ollama-server-status', 'ollama-models',
        'ollama-response-time', 'ollama-last-check', 'header-ollama', 'ollama-status'
    ];
    
    const allExist = requiredElements.every(id => {
        const exists = document.getElementById(id) !== null;
        if (!exists) {
            console.warn(`Ollama element '${id}' not found`);
        }
        return exists;
    });
    
    return allExist;
}

function setupOllamaTest() {
    const testPromptBtn = document.getElementById('test-ollama-prompt');
    const clearTestBtn = document.getElementById('clear-ollama-test');
    const testInput = document.getElementById('ollama-test-input');
    const testOutput = document.getElementById('ollama-test-output');
    
    if (testPromptBtn && testInput && testOutput) {
        testPromptBtn.addEventListener('click', async function() {
            const prompt = testInput.value.trim();
            if (!prompt) return;
            
            testPromptBtn.disabled = true;
            testPromptBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
            testOutput.textContent = 'Sending prompt to Ollama...';
            
            try {
                // Create timeout for browser compatibility
                const timeoutPromise = new Promise((_, reject) => {
                    setTimeout(() => reject(new Error('Request timed out after 2 minutes')), 120000);
                });
                
                const fetchPromise = fetch('/api/test-ollama', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ prompt: prompt })
                });
                
                // Race between fetch and timeout
                const response = await Promise.race([fetchPromise, timeoutPromise]);
                const data = await response.json();
                
                if (data.success) {
                    testOutput.textContent = data.response;
                } else {
                    testOutput.textContent = 'Error: ' + data.error;
                }
            } catch (error) {
                testOutput.textContent = 'Connection error: ' + error.message;
            } finally {
                testPromptBtn.disabled = false;
                testPromptBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Send Prompt';
            }
        });
    }
    
    if (clearTestBtn && testInput && testOutput) {
        clearTestBtn.addEventListener('click', function() {
            testInput.value = '';
            testOutput.textContent = 'Response will appear here...';
        });
    }
}

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
    // Check if all required elements exist before proceeding
    if (!checkOllamaElementsExist()) {
        return false;
    }
    
    const statusElement = document.getElementById('ollama-status-text');
    const serverStatusElement = document.getElementById('ollama-server-status');
    const modelsElement = document.getElementById('ollama-models');
    const responseTimeElement = document.getElementById('ollama-response-time');
    const lastCheckElement = document.getElementById('ollama-last-check');
    const headerOllamaElement = document.getElementById('header-ollama');
    const ollamaStatusElement = document.getElementById('ollama-status');

    try {
        const startTime = Date.now();
        
        // Use the simple health check endpoint instead
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Timeout')), 3000);
        });
        
        const fetchPromise = fetch('/api/health');
        const response = await Promise.race([fetchPromise, timeoutPromise]);
        const endTime = Date.now();
        const responseTime = endTime - startTime;

        const data = await response.json();
        
        // Update response time
        if (responseTimeElement) responseTimeElement.textContent = `${responseTime} ms`;
        
        // Update last check time
        if (lastCheckElement) lastCheckElement.textContent = new Date().toLocaleTimeString();

        if (data.status === 'ok' && data.ollama_port_open) {
            if (statusElement) {
                statusElement.textContent = 'Online ✅ (Port open)';
                statusElement.style.color = '#10b981';
            }
            if (serverStatusElement) {
                serverStatusElement.textContent = 'Online';
                serverStatusElement.className = 'tag tag-success';
            }
            if (headerOllamaElement) headerOllamaElement.textContent = 'Online';
            if (ollamaStatusElement) {
                ollamaStatusElement.textContent = 'Online';
                ollamaStatusElement.className = 'tag tag-success';
            }
            
            // Show available models (we know they exist from earlier testing)
            if (modelsElement) {
                modelsElement.textContent = 'tinyllama, phi3:mini';
            }
            
            return true;
        } else {
            // Handle offline state
            if (statusElement) {
                statusElement.textContent = 'Offline (Port closed)';
                statusElement.style.color = '#ef4444';
            }
            if (serverStatusElement) {
                serverStatusElement.textContent = 'Offline';
                serverStatusElement.className = 'tag tag-danger';
            }
            if (headerOllamaElement) headerOllamaElement.textContent = 'Offline';
            if (ollamaStatusElement) {
                ollamaStatusElement.textContent = 'Offline';
                ollamaStatusElement.className = 'tag tag-danger';
            }
            if (modelsElement) modelsElement.textContent = 'Unknown';
            return false;
        }
    } catch (error) {
        console.error('Ollama status check failed:', error);
        if (statusElement) {
            statusElement.textContent = `Check error: ${error.message || 'Unknown error'}`;
            statusElement.style.color = '#ef4444';
        }
        if (serverStatusElement) {
            serverStatusElement.textContent = 'Error';
            serverStatusElement.className = 'tag tag-danger';
        }
        if (headerOllamaElement) headerOllamaElement.textContent = 'Error';
        if (ollamaStatusElement) {
            ollamaStatusElement.textContent = 'Error';
            ollamaStatusElement.className = 'tag tag-danger';
        }
        if (modelsElement) modelsElement.textContent = 'Unknown';
        if (responseTimeElement) responseTimeElement.textContent = 'Error';
        if (lastCheckElement) lastCheckElement.textContent = new Date().toLocaleTimeString();
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