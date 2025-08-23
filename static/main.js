// DOM Elements
const elements = {
    analyze: document.getElementById('analyze'),
    summary: document.getElementById('summary'),
    network: document.getElementById('network'),
    security: document.getElementById('security'),
    rawLogs: document.getElementById('raw-logs'),
    headerCpu: document.getElementById('header-cpu'),
    metricCpu: document.getElementById('metric-cpu'),
    metricMemory: document.getElementById('metric-memory'),
    uptime: document.getElementById('uptime'),
    loadAvg: document.getElementById('load-avg'),
    processCount: document.getElementById('process-count'),
    cpuCores: document.getElementById('cpu-cores'),
    totalMemory: document.getElementById('total-memory'),
    totalDisk: document.getElementById('total-disk'),
    overallHealth: document.getElementById('overall-health'),
    aiStatus: document.getElementById('ai-status'),
    ollamaActions: document.getElementById('ollama-actions')
};

// Initialize charts
let hardwareChart;
let cpuData = [];
let memoryData = [];

// Load initial data
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
    simulateLiveData();
    loadInitialData();
    
    // Set up periodic updates
    setInterval(updateLiveData, 2000);
    setInterval(addOllamaAction, 10000);
    
    // Set up event listeners
    setupEventListeners();
    
    // Load real logs
    loadLogs();
});

function setupEventListeners() {
    document.getElementById('ai-diagnose').onclick = function() {
        this.disabled = true;
        addOllamaAction();
        setTimeout(() => this.disabled = false, 3000);
    };

    document.getElementById('refresh-ai').onclick = function() {
        elements.ollamaActions.innerHTML = '';
        for (let i = 0; i < 3; i++) {
            addOllamaAction();
        }
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

function loadInitialData() {
    // Simulate initial data load
    elements.uptime.textContent = '3d 12h 45m';
    elements.loadAvg.textContent = '1.2, 1.5, 1.8';
    elements.processCount.textContent = '87';
    elements.cpuCores.textContent = '4 cores';
    elements.totalMemory.textContent = '4GB';
    elements.totalDisk.textContent = '32GB free';
    
    // Load network data
    fetch('/api/network')
        .then(response => response.json())
        .then(data => {
            elements.network.textContent = data.summary || 'No network data available';
        });
    
    // Load security data
    fetch('/api/security')
        .then(response => response.json())
        .then(data => {
            elements.security.textContent = data.report || 'No security data available';
        });
}

function simulateLiveData() {
    // Simulate live data updates
    setInterval(() => {
        const cpuTemp = (Math.random() * 15 + 50).toFixed(1);
        const memoryUsage = Math.floor(Math.random() * 20 + 60);
        
        elements.metricCpu.textContent = `${cpuTemp}°C`;
        elements.metricMemory.textContent = `${memoryUsage}%`;
        elements.headerCpu.textContent = `${cpuTemp}°C`;
        
        // Update chart data
        cpuData.push(parseFloat(cpuTemp));
        memoryData.push(memoryUsage);
        
        if (cpuData.length > 15) {
            cpuData.shift();
            memoryData.shift();
        }
        
        updateChart();
        
    }, 2000);
}

function updateLiveData() {
    // Simulate network status changes
    const networkStatus = Math.random() > 0.1 ? 'Stable' : 'Unstable';
    const statusElement = document.querySelector('.status-card:nth-child(3) .status-value');
    const indicator = document.querySelector('.status-card:nth-child(3) .status-indicator');
    
    if (networkStatus === 'Unstable') {
        statusElement.textContent = 'Unstable';
        indicator.className = 'status-indicator danger';
        document.querySelector('.status-card:nth-child(3)').className = 'status-card danger';
    } else {
        statusElement.textContent = 'Stable';
        indicator.className = 'status-indicator ok';
        document.querySelector('.status-card:nth-child(3)').className = 'status-card ok';
    }
}

function addOllamaAction() {
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
    
    const actionElement = document.createElement('div');
    actionElement.className = 'ollama-action';
    actionElement.innerHTML = `
        <div class="timestamp">${action.timestamp}</div>
        <div class="${action.class}">${action.message}</div>
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
                    min: 40,
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
        hardwareChart.update('none');
    }
}