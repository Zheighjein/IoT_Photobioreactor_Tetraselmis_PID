// ==================== CONFIG ====================
const reactorConfig = {
    'ON/OFF': { name: 'Photobioreactor 2', phMin: 8.1, phMax: 8.7, tempMin: 27, tempMax: 29 },
    'PID':    { name: 'Photobioreactor 1', phMin: 7.5, phMax: 8.0, tempMin: 25, tempMax: 28 }
};

let currentAlgorithm = 'ON/OFF';
let phChart, tempChart, comparisonChart;
let pollInterval = null;

// Local ring-buffer for chart history (filled from /api/history on load,
// then updated with each /api/data poll so we never need to re-fetch all 20 rows).
const dataStore = {
    'ON/OFF': { ph: [], temp: [], timestamps_ph: [], timestamps_temp: [], timestamps: [] },
    'PID':    { ph: [], temp: [], timestamps_ph: [], timestamps_temp: [], timestamps: [] }
};

const MAX_POINTS_PH   = 4;
const MAX_POINTS_TEMP = 8;
const MAX_POINTS = 8;

// ==================== API HELPERS ====================
async function fetchCurrentData(algo) {
    const res = await fetch(`/api/data?algorithm=${encodeURIComponent(algo)}`);
    return res.json();   // caller checks .status
}

async function fetchHistory() {
    const res = await fetch('/api/history');
    return res.json();
}

async function fetchLogs() {
    const res = await fetch('/api/logs');
    return res.json();
}

async function fetchStatus() {
    const res = await fetch('/api/status');
    return res.json();
}

// ==================== RING-BUFFER HELPER ====================
function pushPoint(store, ph, temp, ts) {
    store.ph.push(ph);
    store.temp.push(temp);
    store.timestamps_ph.push(ts);
    store.timestamps_temp.push(ts);
    if (store.ph.length > MAX_POINTS_PH)            { store.ph.shift(); store.timestamps_ph.shift(); }
    if (store.temp.length > MAX_POINTS_TEMP)         { store.temp.shift(); store.timestamps_temp.shift(); }
}

// ==================== UI UPDATES ====================
function setIdle() {
    document.getElementById('val-ph').innerText   = '—';
    document.getElementById('val-temp').innerText = '—';
    setStatusBadge('ph',   'NOT RUNNING', 'status-idle');
    setStatusBadge('temp', 'NOT RUNNING', 'status-idle');
}

function setStatusBadge(param, text, cls) {
    const el = document.getElementById(`status-${param}`);
    el.classList.remove('status-stable', 'status-adjusting', 'status-alert', 'status-idle');
    el.innerText = text;
    el.classList.add(cls);
}

function updateStatus(param, val, min, max) {
    const mid = (min + max) / 2;
    if (val >= min && val <= max) {
        setStatusBadge(param, 'STABLE', 'status-stable');
    } else if (Math.abs(val - mid) < 0.5) {
        setStatusBadge(param, 'ADJUSTING', 'status-adjusting');
    } else {
        setStatusBadge(param, 'ALERT', 'status-alert');
    }
}

// ==================== MAIN POLL ====================
async function pollData() {
    try {
        const json = await fetchCurrentData(currentAlgorithm);

        if (json.status === 'idle' || json.status === 'error') {
            setIdle();
            return;
        }

        const { ph, temperature, config, timestamp } = json;
        const ts = timestamp;

        // Update ring-buffer for the active algo
        pushPoint(dataStore[currentAlgorithm], ph, temperature, ts);

        // Update displayed values
        document.getElementById('val-ph').innerText   = ph.toFixed(2);
        document.getElementById('val-temp').innerText = temperature.toFixed(1);

        // Update status badges using server-supplied config ranges
        updateStatus('ph',   ph,          config.phMin,   config.phMax);
        updateStatus('temp', temperature, config.tempMin, config.tempMax);

        // Refresh charts
        updateCharts();

        // Also silently fetch the other algo's latest point so comparison chart stays fresh
        const otherAlgo = currentAlgorithm === 'ON/OFF' ? 'PID' : 'ON/OFF';
        fetchCurrentData(otherAlgo).then(other => {
            if (other.status === 'success') {
                pushPoint(dataStore[otherAlgo], other.ph, other.temperature, ts);
                updateComparisonChart();
            }
        });

    } catch (err) {
        console.warn('Poll error (Flask may be starting):', err);
        setIdle();
    }
}

// ==================== ALGORITHM SWITCH ====================
function setAlgorithm(algo) {
    currentAlgorithm = algo;

    // Button styles
    const btnOnOff = document.getElementById('btn-onoff');
    const btnPid   = document.getElementById('btn-pid');
    if (algo === 'ON/OFF') {
        btnOnOff.classList.add('active');    btnOnOff.classList.remove('inactive');
        btnPid.classList.remove('active');   btnPid.classList.add('inactive');
    } else {
        btnPid.classList.add('active');      btnPid.classList.remove('inactive');
        btnOnOff.classList.remove('active'); btnOnOff.classList.add('inactive');
    }

    // Labels
    const config = reactorConfig[algo];
    document.getElementById('reactor-title').innerText = config.name;
    document.getElementById('ph-range').innerText      = `${config.phMin} - ${config.phMax}`;
    document.getElementById('temp-range').innerText    = `${config.tempMin} - ${config.tempMax}`;

    // Immediately pull the latest reading for the newly selected reactor
    pollData();
}

// ==================== CHART MANAGEMENT ====================
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
        y: { beginAtZero: false },
        x: { ticks: { maxRotation: 0, maxTicksLimit: 5 } }
    }
};

function initializeCharts() {
    // pH Chart
    const phCtx = document.getElementById('phChart').getContext('2d');
    phChart = new Chart(phCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'pH',
                data: [],
                borderColor: '#3A5F3C',
                backgroundColor: 'rgba(58, 95, 60, 0.1)',
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#3A5F3C'
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: { min: 6.5, max: 9, title: { display: true, text: 'pH' } },
                x: { ticks: { maxRotation: 0, autoSkip: false } }
            }
        }
    });

    // Temperature Chart
    const tempCtx = document.getElementById('tempChart').getContext('2d');
    tempChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temperature',
                data: [],
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#ef4444'
            }]
        },
        options: {
            ...chartDefaults,
            scales: {
                y: { min: 24, max: 30 },
                x: { ticks: { maxRotation: 0, autoSkip: false } }
            }
        }
    });

    // Comparison Chart
    const compCtx = document.getElementById('comparisonChart').getContext('2d');
    comparisonChart = new Chart(compCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'ON/OFF pH',
                    data: [],
                    borderColor: '#3A5F3C',
                    backgroundColor: 'rgba(58, 95, 60, 0.05)',
                    tension: 0.3,
                    borderWidth: 2
                },
                {
                    label: 'PID pH',
                    data: [],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.05)',
                    tension: 0.3,
                    borderWidth: 2
                }
            ]
        },
        options: {
            ...chartDefaults,
            plugins: { legend: { display: true, position: 'top' } },
            scales: { ...chartDefaults.scales, y: { min: 7, max: 8.5 } }
        }
    });
}

function updateCharts() {
    const store = dataStore[currentAlgorithm];

    if (phChart) {
        phChart.data.labels           = store.timestamps_ph;
        phChart.data.datasets[0].data = store.ph;
        phChart.update('none');
    }
    if (tempChart) {
        tempChart.data.labels           = store.timestamps_temp;
        tempChart.data.datasets[0].data = store.temp;
        tempChart.update('none');
    }
}

function updateComparisonChart() {
    const showPh   = document.getElementById('show-ph-trend').checked;
    const showTemp = document.getElementById('show-temp-trend').checked;

    if (!comparisonChart) return;

    // Use longer of the two timestamp arrays as labels
    const labels = dataStore['ON/OFF'].timestamps.length >= dataStore['PID'].timestamps.length
        ? dataStore['ON/OFF'].timestamps
        : dataStore['PID'].timestamps;

    comparisonChart.data.labels = labels;

    // Dataset 0 → ON/OFF pH or temp
    comparisonChart.data.datasets[0].data   = showPh ? dataStore['ON/OFF'].ph   : dataStore['ON/OFF'].temp;
    comparisonChart.data.datasets[0].label  = showPh ? 'ON/OFF pH' : 'ON/OFF Temp';
    comparisonChart.data.datasets[0].hidden = false;

    // Dataset 1 → PID pH or temp
    comparisonChart.data.datasets[1].data   = showPh ? dataStore['PID'].ph   : dataStore['PID'].temp;
    comparisonChart.data.datasets[1].label  = showPh ? 'PID pH' : 'PID Temp';
    comparisonChart.data.datasets[1].hidden = false;

    comparisonChart.update();
}

// ==================== EVENT LOG ====================
async function refreshLogs() {
    try {
        const json = await fetchLogs();
        if (json.status !== 'success') return;

        const container = document.getElementById('event-log');
        if (!container) return;

        container.innerHTML = '';
        json.logs.forEach(log => {
            const statusClass = log.status === 'Success'   ? 'status-stable'
                              : log.status === 'Adjusting' ? 'status-adjusting'
                              : 'status-alert';

            container.innerHTML += `
                <div class="bg-white/10 p-3 rounded-lg border border-white/20">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="font-semibold">${log.parameter} – ${log.description}</p>
                            <p class="text-xs opacity-80">Reactor: ${log.reactor}</p>
                        </div>
                        <span class="status-badge ${statusClass}">${log.status}</span>
                    </div>
                    <p class="text-xs opacity-70 mt-2">${log.timestamp}</p>
                </div>`;
        });
    } catch (e) {
        console.warn('Log refresh error:', e);
    }
}

// ==================== SYSTEM STATUS TAB ====================
async function refreshStatus() {
    try {
        const json = await fetchStatus();
        if (json.status !== 'success') return;

        for (const [algo, data] of Object.entries(json.reactors)) {
            const suffix = algo === 'ON/OFF' ? 'onoff' : 'pid';

            const onlineEl = document.getElementById(`status-online-${suffix}`);
            const phEl     = document.getElementById(`status-ph-val-${suffix}`);
            const tempEl   = document.getElementById(`status-temp-val-${suffix}`);

            if (onlineEl) onlineEl.innerText = data.online ? 'Online' : 'Offline';
            if (phEl)     phEl.innerText     = data.online ? data.ph.toFixed(2)          : '—';
            if (tempEl)   tempEl.innerText   = data.online ? `${data.temperature.toFixed(1)} °C` : '—';

            // PID params
            if (algo === 'PID' && data.algorithm_params) {
                const kpEl = document.getElementById('status-kp');
                const kiEl = document.getElementById('status-ki');
                const kdEl = document.getElementById('status-kd');
                if (kpEl) kpEl.innerText = data.algorithm_params.kp;
                if (kiEl) kiEl.innerText = data.algorithm_params.ki;
                if (kdEl) kdEl.innerText = data.algorithm_params.kd;
            }
        }
    } catch (e) {
        console.warn('Status refresh error:', e);
    }
}

// ==================== TAB NAVIGATION ====================
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.getElementById(`content-${tabId}`).classList.remove('hidden');

    document.querySelectorAll('.nav-tab').forEach(el => {
        el.classList.remove('border-lime-400');
        el.classList.add('border-transparent');
    });
    document.getElementById(`tab-${tabId}`).classList.add('border-lime-400');

    if (tabId === 'visualization') {
        setTimeout(() => { if (comparisonChart) comparisonChart.resize(); }, 100);
        updateComparisonChart();
        refreshLogs();
    }
    if (tabId === 'status') {
        setTimeout(() => { if (comparisonChart) comparisonChart.resize(); }, 100);
        refreshStatus();
    }
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', async () => {
    initializeCharts();

    // Pre-fill ring-buffers from history endpoint
    try {
        const hist = await fetchHistory();
        if (hist.status === 'success') {
            for (const algo of ['ON/OFF', 'PID']) {
                const d = hist.data[algo];
                if (!d) continue;
                d.ph.forEach((ph, i) => {
                    pushPoint(dataStore[algo], ph, d.temperature[i], d.timestamps[i]);
                });
            }
            updateCharts();
            updateComparisonChart();
        }
    } catch (e) {
        console.warn('History pre-fill failed (simulation may not have started yet):', e);
    }

    // First poll immediately, then every 5 seconds (matches DT=5 in .env)
    await pollData();
    pollInterval = setInterval(pollData, 5000);
});