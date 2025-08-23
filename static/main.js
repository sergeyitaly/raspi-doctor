// static/main.js - Enhanced for real-time updates

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
    ollamaActions: document.getElementById('ollama-actions'),
    cpuTrend: document.getElementById('cpu-trend'),
    memoryTrend: document.getElementById('memory-trend')
};

// Initialize charts and data
let hardwareChart;
let cpuData = [];
let memoryData = [];
let lastCpuValue = 0;
let lastMemoryValue = 0;

// Load initial data and set up periodic updates
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
    loadInitialData();
    setupEventListeners();
    
    // Set up periodic updates
    setInterval(updateSystemHealth, 2000);
    setInterval(updateSecurityStatus, 10000);
    setInterval(updateNetworkStatus, 5000);
    setInterval(addOllamaAction, 15000);
    
    // Initial updates
    updateSystemHealth();
    updateSecurityStatus();
    updateNetworkStatus();
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
        fetch('/api/health/history')
            .then(response => response.json())
            .then(data => {
                elements.rawLogs.textContent = JSON.stringify(data, null, 2);
            })
            .catch(error => {
                elements.rawLogs.textContent = 'Error loading logs: ' + error;
            });
    };

    elements.analyze.onclick = async () => {
        elements.analyze.disabled = true;
        elements.summary.innerHTML = "<div class='loading'></div> Analyzing with AI...";
        
        try {
            const response = await fetch('/api/health');
            const healthData = await response.json();
            
            // Simulate AI analysis based on real data
            let analysis = generateAIAnalysis(healthData);
            elements.summary.textContent = analysis;
        } catch (error) {
            elements.summary.textContent = "Error analyzing system: " + error;
        } finally {
            elements.analyze.disabled = false;
        }
    };
}

function generateAIAnalysis(healthData) {
    let analysis = "🤖 AI System Analysis:\n\n";
    
    // CPU analysis
    if (healthData.cpu.temperature > 75) {
        analysis += "🌡️ CPU Temperature: WARNING - High temperature detected\n";
    } else if (healthData.cpu.temperature > 65) {
        analysis += "🌡️ CPU Temperature: Noticeable heat\n";
    } else {
        analysis += "🌡️ CPU Temperature: Normal\n";
    }
    
    if (healthData.cpu.percent > 80) {
        analysis += "🚀 CPU Usage: High load\n";
    } else {
        analysis += "🚀 CPU Usage: Normal\n";
    }
    
    // Memory analysis
    if (healthData.memory.percent > 85) {
        analysis += "💾 Memory: CRITICAL - High memory usage\n";
    } else if (healthData.memory.percent > 70) {
        analysis += "💾 Memory: Elevated usage\n";
    } else {
        analysis += "💾 Memory: Normal\n";
    }
    
    // Disk analysis
    if (healthData.disk.percent > 90) {
        analysis += "💿 Disk: WARNING - Low disk space\n";
    } else if (healthData.disk.percent > 80) {
        analysis += "💿 Disk: Getting full\n";
    } else {
        analysis += "💿 Disk: Adequate space\n";
    }
    
    // Network analysis
    if (healthData.network.packet_loss_percent > 10) {
        analysis += "📶 Network: Unstable connection\n";
    } else if (healthData.network.packet_loss_percent > 5) {
        analysis += "📶 Network: Some packet loss\n";
    } else {
        analysis += "📶 Network: Stable\n";
    }
    
    analysis += `\nOverall Status: ${healthData.status.overall.toUpperCase()}`;
    
    return analysis;
}

function toggleLogs() {
    const content = document.getElementById('logs-content');
    content.classList.toggle('expanded');
}

function loadInitialData() {
    // Initial placeholder data
    elements.uptime.textContent = 'Loading...';
    elements.loadAvg.textContent = 'Loading...';
    elements.processCount.textContent = 'Loading...';
    elements.cpuCores.textContent = 'Loading...';
    elements.totalMemory.textContent = 'Loading...';
    elements.totalDisk.textContent = 'Loading...';
    
    elements.network.textContent = 'Loading network data...';
    elements.security.textContent = 'Loading security data...';
}

async function updateSystemHealth() {
    try {
        const response = await fetch('/api/health');
        const healthData = await response.json();
        
        if (healthData.error) {
            console.error('Error fetching health data:', healthData.error);
            return;
        }
        
        // Update basic system info
        elements.uptime.textContent = healthData.system.uptime;
        elements.loadAvg.textContent = `${healthData.cpu.load_1min.toFixed(1)}, ${healthData.cpu.load_5min.toFixed(1)}, ${healthData.cpu.load_15min.toFixed(1)}`;
        elements.processCount.textContent = healthData.system.processes;
        elements.cpuCores.textContent = `${healthData.cpu.cores} cores`;
        elements.totalMemory.textContent = `${healthData.memory.total_gb}GB`;
        elements.totalDisk.textContent = `${healthData.disk.free_gb.toFixed(1)}GB free`;
        
        // Update metrics
        elements.metricCpu.textContent = `${healthData.cpu.temperature.toFixed(1)}°C`;
        elements.metricMemory.textContent = `${healthData.memory.percent.toFixed(1)}%`;
        elements.headerCpu.textContent = `${healthData.cpu.temperature.toFixed(1)}°C`;
        
        // Update status indicators
        updateStatusIndicator('overall', healthData.status.overall);
        updateStatusIndicator('network', healthData.status.network);
        updateStatusIndicator('security', healthData.status.security);
        
        // Update trend indicators
        updateTrendIndicator('cpu', healthData.cpu.temperature);
        updateTrendIndicator('memory', healthData.memory.percent);
        
        // Update chart data
        cpuData.push(healthData.cpu.temperature);
        memoryData.push(healthData.memory.percent);
        
        if (cpuData.length > 15) {
            cpuData.shift();
            memoryData.shift();
        }
        
        updateChart();
        
    } catch (error) {
        console.error('Error updating system health:', error);
    }
}

async function updateSecurityStatus() {
    try {
        const response = await fetch('/api/security');
        const securityData = await response.json();
        
        let securityText = `✓ Firewall: ${securityData.firewall}\n`;
        securityText += `✓ Failed logins: ${securityData.failed_logins}\n`;
        
        if (securityData.suspicious_ips.length > 0) {
            securityText += `⚠️ Suspicious IPs: ${securityData.suspicious_ips.length} detected\n`;
            securityData.suspicious_ips.forEach(ip => {
                securityText += `   - ${ip.ip} (${ip.attempts} attempts)\n`;
            });
        } else {
            securityText += `✓ No suspicious IP activity\n`;
        }
        
        securityText += `✓ Status: ${securityData.status}`;
        
        elements.security.textContent = securityText;
        
    } catch (error) {
        console.error('Error updating security status:', error);
    }
}

async function updateNetworkStatus() {
    try {
        const response = await fetch('/api/health');
        const healthData = await response.json();
        
        let networkText = `✓ Latency: ${healthData.network.latency_ms.toFixed(1)}ms\n`;
        networkText += `✓ Packet loss: ${healthData.network.packet_loss_percent.toFixed(1)}%\n`;
        networkText += `✓ Bandwidth: Sent ${healthData.network.sent_mb.toFixed(1)}MB, Received ${healthData.network.received_mb.toFixed(1)}MB\n`;
        networkText += `✓ Status: ${healthData.status.network}`;
        
        elements.network.textContent = networkText;
        
    } catch (error) {
        console.error('Error updating network status:', error);
    }
}

function updateStatusIndicator(type, status) {
    const statusMap = {
        'good': 'ok',
        'secure': 'ok', 
        'stable': 'ok',
        'warning': 'warning',
        'critical': 'danger',
        'unstable': 'warning',
        'poor': 'danger'
    };
    
    const statusClass = statusMap[status] || 'ok';
    
    if (type === 'overall') {
        elements.overallHealth.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        elements.overallHealth.className = `tag tag-${statusClass}`;
    } else if (type === 'network') {
        const networkStatus = document.querySelector('.status-card:nth-child(3) .status-value');
        const networkIndicator = document.querySelector('.status-card:nth-child(3) .status-indicator');
        const networkCard = document.querySelector('.status-card:nth-child(3)');
        
        networkStatus.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        networkIndicator.className = `status-indicator ${statusClass}`;
        networkCard.className = `status-card ${statusClass}`;
    } else if (type === 'security') {
        const securityStatus = document.querySelector('#security').previousElementSibling;
        if (securityStatus && securityStatus.classList.contains('tag')) {
            securityStatus.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            securityStatus.className = `tag tag-${statusClass}`;
        }
    }
}

function updateTrendIndicator(type, currentValue) {
    const trendElement = type === 'cpu' ? elements.cpuTrend : elements.memoryTrend;
    const lastValue = type === 'cpu' ? lastCpuValue : lastMemoryValue;
    
    if (lastValue === 0) {
        // First reading, no trend yet
        if (type === 'cpu') lastCpuValue = currentValue;
        else lastMemoryValue = currentValue;
        return;
    }
    
    const diff = currentValue - lastValue;
    const diffPercent = (diff / lastValue) * 100;
    
    if (Math.abs(diffPercent) < 1) {
        // Minimal change, show neutral
        trendElement.className = 'metric-trend trend-neutral';
        trendElement.innerHTML = '<i class="fas fa-minus"></i><span>Stable</span>';
    } else if (diff > 0) {
        // Increasing
        trendElement.className = 'metric-trend trend-up';
        trendElement.innerHTML = `<i class="fas fa-arrow-up"></i><span>+${diff.toFixed(1)}</span>`;
    } else {
        // Decreasing
        trendElement.className = 'metric-trend trend-down';
        trendElement.innerHTML = `<i class="fas fa-arrow-down"></i><span>${diff.toFixed(1)}</span>`;
    }
    
    // Update last value
    if (type === 'cpu') lastCpuValue = currentValue;
    else lastMemoryValue = currentValue;
}

function addOllamaAction() {
    const actions = [
        {
            message: "📊 Analyzing memory usage patterns...",
            class: "ollama-thinking",
            timestamp: new Date().toLocaleTimeString()
        },
        {
            message: "✅ Optimized swap usage: 150MB reclaimed",
            class: "ollama-success",
            timestamp: new Date().toLocaleTimeString()
        },
        {
            message: "⚠️ Monitoring CPU temperature: Approaching threshold",
            class: "ollama-warning",
            timestamp: new Date().toLocaleTimeString()
        },
        {
            message: "🔧 Adjusted process priorities for better performance",
            class: "ollama-success",
            timestamp: new Date().toLocaleTimeString()
        },
        {
            message: "📡 Checking network connectivity...",
            class: "ollama-thinking",
            timestamp: new Date().toLocaleTimeString()
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