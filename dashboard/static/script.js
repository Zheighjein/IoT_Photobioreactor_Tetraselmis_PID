// ==================== CONFIG ====================
const reactorConfig = {
    'ON/OFF': { name: 'Photobioreactor 2', phMin: 7.4, phMax: 7.6, tempMin: 27, tempMax: 29 },
    'PID':    { name: 'Photobioreactor 1', phMin: 7.4, phMax: 7.6, tempMin: 25, tempMax: 28 }
};

let currentAlgorithm = 'ON/OFF';
let phChart, tempChart, comparisonPhChart, comparisonTempChart, metricsChart;
let pollInterval = null;
let latestStatus = null;
let systemActive = false;

const MAX_POINTS_PH   = 4;
const MAX_POINTS_TEMP = 8;

// ==================== NOTIFICATION BADGE ====================
const notifQueue = [];
let notifCount = 0;
const notifState = {};

function pushNotif(algo, param, value, status) {
    const key = `${algo}-${param}`;
    if (notifState[key] === status) return; // no change, skip
    notifState[key] = status;

    const time  = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const color = status === 'ALERT' ? 'text-red-600' : status === 'STABLE' ? 'text-green-600' : 'text-amber-500';
    const icon  = status === 'ALERT' ? '⚠️' : status === 'STABLE' ? '✅' : '🔔';
    const algoLabel = algo === 'PID' ? 'Photobioreactor 1 (PID)' : 'Photobioreactor 2 (ON/OFF)';
    notifQueue.unshift({ algo: algoLabel, param, value, status, time, icon, color });
    if (notifQueue.length > 10) notifQueue.pop();
    notifCount++;

    const badge = document.getElementById('notif-badge');
    badge.textContent = notifCount > 9 ? '9+' : notifCount;
    badge.classList.remove('hidden');
    renderNotifList();
}

function renderNotifList() {
    const list = document.getElementById('notif-list');
    if (!list) return;
    if (!notifQueue.length) {
        list.innerHTML = '<li class="px-4 py-6 text-center text-xs text-gray-400">No new notifications</li>';
        return;
    }
    list.innerHTML = notifQueue.map(n => `
        <li class="px-4 py-3">
            <div class="flex justify-between items-start">
                <div>
                    <p class="text-xs font-bold ${n.color}">${n.icon} ${n.status === 'STABLE' ? 'SUCCESS' : n.status} — ${n.algo}</p>
                    <p class="text-xs text-gray-600 mt-0.5">${n.param}: ${n.value}</p>
                </div>
                <span class="text-[10px] text-gray-400 whitespace-nowrap ml-2">${n.time}</span>
            </div>
        </li>`).join('');
}

function clearNotifBadge() {
    notifCount = 0;
    document.getElementById('notif-badge').classList.add('hidden');
    notifQueue.length = 0;
    renderNotifList();
}

// ==================== API HELPERS ====================
async function fetchHistory() {
    const res = await fetch('/api/history');
    return res.json();
}

async function fetchStatus() {
    const res = await fetch('/api/status');
    return res.json();
}

async function fetchLogs() {
    const res = await fetch('/api/logs');
    return res.json();
}

async function fetchMetrics() {
    const res = await fetch('/api/metrics');
    return res.json();
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

function checkFreshness(statusJson) {
    if (!statusJson || statusJson.status !== 'success') return false;
    const serverTime = statusJson.server_time;
    for (const [algo, data] of Object.entries(statusJson.reactors)) {
        if (data.online && data.timestamp) {
            const age = (serverTime - data.timestamp) * 1000;
            if (age < 10000) return true;
        }
    }
    return false;
}

function renderLiveParameters(statusJson) {
    if (!statusJson || statusJson.status !== 'success') {
        setIdle();
        return;
    }

    const reactorData = statusJson.reactors[currentAlgorithm];
    const config = reactorData?.config || reactorConfig[currentAlgorithm];
    const serverTime = statusJson.server_time;
    const isFresh = reactorData?.online && reactorData?.timestamp &&
                    ((serverTime - reactorData.timestamp) * 1000) < 10000;

    if (!reactorData || !isFresh) {
        setIdle();
        return;
    }

    const ph = reactorData.ph;
    const temperature = reactorData.temperature;
    const isAdjusting = reactorData.co2 === 1;

    document.getElementById('val-ph').innerText   = ph.toFixed(2);
    document.getElementById('val-temp').innerText = temperature.toFixed(1);
    setStatusBadge('ph',   isAdjusting ? 'ADJUSTING' : 'STABLE', isAdjusting ? 'status-adjusting' : 'status-stable');
    updateStatus('temp', temperature, config.tempMin, config.tempMax);
}

function renderSystemStatus(statusJson) {
    if (!statusJson || statusJson.status !== 'success') return;

    const serverTime = statusJson.server_time;
    for (const [algo, data] of Object.entries(statusJson.reactors)) {
        const suffix = algo === 'ON/OFF' ? 'onoff' : 'pid';

        const onlineEl = document.getElementById(`status-online-${suffix}`);
        const phEl     = document.getElementById(`status-ph-val-${suffix}`);
        const tempEl   = document.getElementById(`status-temp-val-${suffix}`);

        const isFresh = data.online && data.timestamp && ((serverTime - data.timestamp) * 1000) < 10000;
        const onlineText = isFresh ? 'Online' : 'Offline';

        if (onlineEl) onlineEl.innerText = onlineText;
        if (phEl)     phEl.innerText     = isFresh ? data.ph.toFixed(2)                  : '—';
        if (tempEl)   tempEl.innerText   = isFresh ? `${data.temperature.toFixed(1)} °C` : '—';

        if (algo === 'PID' && data.algorithm_params) {
            const kpEl = document.getElementById('status-kp');
            const kiEl = document.getElementById('status-ki');
            const kdEl = document.getElementById('status-kd');
            if (kpEl) kpEl.innerText = typeof data.algorithm_params.kp === 'number' ? data.algorithm_params.kp.toFixed(4) : data.algorithm_params.kp;
            if (kiEl) kiEl.innerText = typeof data.algorithm_params.ki === 'number' ? data.algorithm_params.ki.toFixed(4) : data.algorithm_params.ki;
            if (kdEl) kdEl.innerText = typeof data.algorithm_params.kd === 'number' ? data.algorithm_params.kd.toFixed(4) : data.algorithm_params.kd;
        }
    }
}

// ==================== AUTOTUNE ====================
let countdownInterval = null;

function formatCountdown(seconds) {
    if (seconds <= 0) return '00:00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

async function pollAutotune() {
    try {
        const res = await fetch('/api/autotune');
        const json = await res.json();
        if (json.status !== 'success') return;

        const banner     = document.getElementById('autotune-banner');
        const selector   = document.getElementById('algorithm-selector');
        const isAutotune = json.mode === 'AUTOTUNE';

        banner.classList.remove('hidden');

        if (json.ph !== null && json.ph !== undefined)
            document.getElementById('autotune-ph').innerText = json.ph.toFixed(3);

        if (isAutotune) {
            selector.style.display = 'none';
            document.getElementById('autotune-dot').className = 'w-3 h-3 bg-amber-400 rounded-full animate-pulse';
            document.getElementById('autotune-title').innerText = 'Autotune In Progress';
            document.getElementById('autotune-title').className = 'font-bold text-amber-800 uppercase tracking-widest text-sm';

            if (countdownInterval) clearInterval(countdownInterval);
            if (json.autotune_start) {
                const endTime = json.autotune_start + json.autotune_duration;
                countdownInterval = setInterval(() => {
                    const remaining = endTime - (Date.now() / 1000);
                    document.getElementById('autotune-countdown').innerText = formatCountdown(remaining);
                }, 1000);
            }
        } else {
            selector.style.display = '';
            if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
            document.getElementById('autotune-dot').className = 'w-3 h-3 bg-green-500 rounded-full';
            document.getElementById('autotune-title').innerText = 'Autotune Complete';
            document.getElementById('autotune-title').className = 'font-bold text-green-700 uppercase tracking-widest text-sm';
            document.getElementById('autotune-countdown').innerText = 'Done';
            document.getElementById('autotune-transition').classList.remove('hidden');
            if (json.pid) {
                document.getElementById('autotune-pid-result').classList.remove('hidden');
                document.getElementById('autotune-kp').innerText = json.pid.kp;
                document.getElementById('autotune-ki').innerText = json.pid.ki;
                document.getElementById('autotune-kd').innerText = json.pid.kd;
            }
        }
    } catch (e) {
        console.warn('Autotune poll error:', e);
    }
}

// ==================== MAIN POLL ====================
// Each poll fetches /api/history for all chart data (real DB values + real timestamps)
// and /api/status for the live display and system status.
async function pollData() {
    try {
        const statusJson = await fetchStatus();
        latestStatus = statusJson;
        systemActive = checkFreshness(statusJson);

        // Update inactive overlay
        const overlay = document.getElementById('inactive-overlay');
        if (overlay) {
            overlay.classList.toggle('hidden', systemActive);
        }

        if (statusJson.status !== 'success') {
            setIdle();
        } else {
            renderLiveParameters(statusJson);
            renderSystemStatus(statusJson);

            // Check both reactors for notification badge
            const serverTime = statusJson.server_time;
            for (const [algo, data] of Object.entries(statusJson.reactors)) {
                if (!data.online || !data.timestamp) continue;
                if ((serverTime - data.timestamp) * 1000 >= 10000) continue;
                const cfg = reactorConfig[algo];
                const phStatus   = data.co2 === 1 ? 'ADJUSTING' : 'STABLE';
                const tempStatus = data.temperature < cfg.tempMin || data.temperature > cfg.tempMax ? 'ALERT' : 'STABLE';
                pushNotif(algo, 'pH',  data.ph.toFixed(2),              phStatus);
                pushNotif(algo, 'Temp', data.temperature.toFixed(1) + '°C', tempStatus);
            }
        }

        const hist = await fetchHistory();
        if (hist.status === 'success') {
            updateChartsFromHistory(hist.data);
        }

    } catch (err) {
        console.warn('Poll error (Flask may be starting):', err);
        setIdle();
    }
}

// ==================== CHART DATA FROM HISTORY ====================
function updateChartsFromHistory(data) {
    if (!systemActive) return;

    const store = data[currentAlgorithm];
    if (!store) return;

    const phData   = store.ph.slice(-MAX_POINTS_PH);
    const tempData = store.temperature.slice(-MAX_POINTS_TEMP);
    const phTs     = store.timestamps.slice(-MAX_POINTS_PH);
    const tempTs   = store.timestamps.slice(-MAX_POINTS_TEMP);

    if (phChart) {
        phChart.data.labels           = phTs;
        phChart.data.datasets[0].data = phData;
        phChart.update('none');
    }
    if (tempChart) {
        tempChart.data.labels           = tempTs;
        tempChart.data.datasets[0].data = tempData;
        tempChart.update('none');
    }

    updateComparisonChartFromHistory(data);
}

// ==================== ALGORITHM SWITCH ====================
function setAlgorithm(algo) {
    currentAlgorithm = algo;

    const btnOnOff = document.getElementById('btn-onoff');
    const btnPid   = document.getElementById('btn-pid');
    if (algo === 'ON/OFF') {
        btnOnOff.classList.add('active');    btnOnOff.classList.remove('inactive');
        btnPid.classList.remove('active');   btnPid.classList.add('inactive');
    } else {
        btnPid.classList.add('active');      btnPid.classList.remove('inactive');
        btnOnOff.classList.remove('active'); btnOnOff.classList.add('inactive');
    }

    const config = reactorConfig[algo];
    document.getElementById('reactor-title').innerText = config.name;
    document.getElementById('ph-range').innerText      = `${config.phMin} - ${config.phMax}`;
    document.getElementById('temp-range').innerText    = `${config.tempMin} - ${config.tempMax}`;

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
                y: { min: 20, max: 30 },
                x: { ticks: { maxRotation: 0, autoSkip: false } }
            }
        }
    });

    const metricsCtx = document.getElementById('metricsChart').getContext('2d');
    metricsChart = new Chart(metricsCtx, {
        type: 'bar',
        data: {
            labels: ['IAE', 'ISE', 'ITAE'],
            datasets: [
                { label: 'PID (R1)',    data: [null, null, null], backgroundColor: 'rgba(99,102,241,0.7)',  borderColor: '#6366f1', borderWidth: 1 },
                { label: 'ON/OFF (R2)', data: [null, null, null], backgroundColor: 'rgba(58,95,60,0.7)',   borderColor: '#3A5F3C', borderWidth: 1 }
            ]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: { x: { beginAtZero: true } }
        }
    });

    const compPhCtx = document.getElementById('comparisonPhChart').getContext('2d');
    comparisonPhChart = new Chart(compPhCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'PID (R1)',   data: [], borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.05)', tension: 0.3, borderWidth: 2, pointRadius: 3 },
                { label: 'ON/OFF (R2)', data: [], borderColor: '#3A5F3C', backgroundColor: 'rgba(58,95,60,0.05)',  tension: 0.3, borderWidth: 2, pointRadius: 3 }
            ]
        },
        options: {
            ...chartDefaults,
            plugins: { legend: { display: false } },
            scales: {
                y: { min: 6.5, max: 9, title: { display: true, text: 'pH' } },
                x: { ticks: { maxRotation: 0, maxTicksLimit: 6 } }
            }
        }
    });

    const compTempCtx = document.getElementById('comparisonTempChart').getContext('2d');
    comparisonTempChart = new Chart(compTempCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'PID (R1)',   data: [], borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.05)', tension: 0.3, borderWidth: 2, pointRadius: 3 },
                { label: 'ON/OFF (R2)', data: [], borderColor: '#3A5F3C', backgroundColor: 'rgba(58,95,60,0.05)',  tension: 0.3, borderWidth: 2, pointRadius: 3 }
            ]
        },
        options: {
            ...chartDefaults,
            plugins: { legend: { display: false } },
            scales: {
                y: { min: 20, max: 30, title: { display: true, text: '°C' } },
                x: { ticks: { maxRotation: 0, maxTicksLimit: 6 } }
            }
        }
    });
}

function updateComparisonChartFromHistory(data) {
    if (!comparisonPhChart || !comparisonTempChart) return;

    const pid   = data['PID']    || { ph: [], temperature: [], timestamps: [] };
    const onoff = data['ON/OFF'] || { ph: [], temperature: [], timestamps: [] };

    const labels = pid.timestamps.length >= onoff.timestamps.length
        ? pid.timestamps
        : onoff.timestamps;

    comparisonPhChart.data.labels            = labels;
    comparisonPhChart.data.datasets[0].data  = pid.ph;
    comparisonPhChart.data.datasets[1].data  = onoff.ph;
    comparisonPhChart.update('none');

    comparisonTempChart.data.labels            = labels;
    comparisonTempChart.data.datasets[0].data  = pid.temperature;
    comparisonTempChart.data.datasets[1].data  = onoff.temperature;
    comparisonTempChart.update('none');
}

// ==================== METRICS ====================
async function refreshMetrics() {
    try {
        const json = await fetchMetrics();
        if (json.status !== 'success') return;

        const pid   = json.metrics['PID']    || {};
        const onoff = json.metrics['ON/OFF'] || {};

        document.getElementById('pid-iae').innerText    = pid.iae   ?? '—';
        document.getElementById('pid-ise').innerText    = pid.ise   ?? '—';
        document.getElementById('pid-itae').innerText   = pid.itae  ?? '—';
        document.getElementById('onoff-iae').innerText  = onoff.iae  ?? '—';
        document.getElementById('onoff-ise').innerText  = onoff.ise  ?? '—';
        document.getElementById('onoff-itae').innerText = onoff.itae ?? '—';

        if (metricsChart) {
            metricsChart.data.datasets[0].data = [pid.iae ?? 0,   pid.ise ?? 0,   pid.itae ?? 0];
            metricsChart.data.datasets[1].data = [onoff.iae ?? 0, onoff.ise ?? 0, onoff.itae ?? 0];
            metricsChart.update();
        }
    } catch (e) {
        console.warn('Metrics refresh error:', e);
    }
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
        if (latestStatus && latestStatus.status === 'success') {
            renderSystemStatus(latestStatus);
            return;
        }

        const json = await fetchStatus();
        if (json.status !== 'success') return;

        latestStatus = json;
        renderSystemStatus(json);
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

    const selector = document.getElementById('algorithm-selector');
    selector.style.display = tabId === 'parameters' ? 'flex' : 'none';

    if (tabId === 'visualization') {
        setTimeout(() => {
            if (comparisonPhChart)   comparisonPhChart.resize();
            if (comparisonTempChart) comparisonTempChart.resize();
            if (metricsChart)        metricsChart.resize();
        }, 100);
        pollData();
        refreshLogs();
        refreshMetrics();
    }
    if (tabId === 'status') {
        setTimeout(() => {}, 100);
        refreshStatus();
    }
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', async () => {
    initializeCharts();

    document.getElementById('bell-btn').addEventListener('click', e => {
        e.preventDefault();
        document.getElementById('notif-dropdown').classList.toggle('hidden');
    });
    document.addEventListener('click', e => {
        if (!document.getElementById('bell-btn').contains(e.target)) {
            document.getElementById('notif-dropdown').classList.add('hidden');
        }
    });
    renderNotifList();

    await pollAutotune();
    await pollData();
    pollInterval = setInterval(async () => { await pollAutotune(); await pollData(); }, 5000);
});
