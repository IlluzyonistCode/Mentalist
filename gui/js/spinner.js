let spinnerStartTime = null;
let isRunning = false;
let manualVisible = false;
let pollInterval = null;

let spinnerStats = {
    totalSpins: 0,
    successfulSpins: 0,
    failedSpins: 0
};

let currentState = {
    phase: 'Initializing...',
    action: 'Idle',
    lastSpin: 'Never',
    device: '—'
};

document.addEventListener('DOMContentLoaded', () => {
    addLog('info', 'Scanning for ADB devices...');
    setStatus('initializing', 'SCANNING');

    runAutoSetup();
});

async function runAutoSetup() {
    setScanStatus('loading', 'Starting ADB server and scanning...');

    try {
        const result = await eel.spinner_adb_scan()();

        if (result.serial) {
            setScanStatus('success', `Found device: ${result.serial}`);
            addLog('success', `Auto-connected: ${result.serial}`);

            startSpinner(result.serial);
        } else if (result.devices && result.devices.length > 0) {
            setScanStatus('success', `Found ${result.devices.length} device(s)`);
            showDeviceList(result.devices);
        } else {
            setScanStatus('error', 'No devices found');
            addLog('warning', 'No ADB devices found. Connect your phone or enter IP manually.');

            showManual();
        }
    } catch (error) {
        setScanStatus('error', 'Scan failed');
        addLog('error', `Scan error: ${error.message || error}`);
    }
}

async function rescanDevices() {
    document.getElementById('deviceList').style.display = 'none';

    addLog('info', 'Rescanning...');
    setScanStatus('loading', 'Rescanning...');

    runAutoSetup();
}

function toggleManual() {
    manualVisible = !manualVisible;

    document.getElementById('wizardManual').style.display = manualVisible ? 'block' : 'none';
}

function showManual() {
    manualVisible = true;

    document.getElementById('wizardManual').style.display = 'block';
}

async function connectManual() {
    const ip = document.getElementById('deviceIp').value.trim();
    const portRaw = document.getElementById('devicePort').value.trim();
    const port = portRaw || '5555';

    if (!ip) {
        addLog('error', 'Enter an IP address.');

        return;
    }

    addLog('info', `Connecting to ${ip}:${port}...`);

    try {
        const result = await eel.spinner_adb_connect(ip, port)();

        if (result.success) {
            addLog('success', `Connected: ${ip}:${port}`);

            startSpinner(`${ip}:${port}`);
        }

        else addLog('error', `Connection failed: ${result.error}`);
    } catch (error) {
        addLog('error', `Connection error: ${e.message || error}`);
    }
}

function showDeviceList(devices) {
    const list = document.getElementById('deviceList');
    const items = document.getElementById('deviceItems');

    items.innerHTML = '';

    devices.forEach(dev => {
        const item = document.createElement('div');
        item.className = 'device-item';
        item.onclick = () => selectDevice(dev.serial);

        const badge = dev.transport === 'wifi'
            ? '<span class="device-badge wifi">WiFi</span>'
            : '<span class="device-badge usb">USB</span>';

        item.innerHTML = `
            <div>
                <div class="device-serial">${dev.serial}</div>
                <div class="device-meta">${dev.model || dev.product || 'Unknown model'}</div>
            </div>
            ${badge}
        `;

        items.appendChild(item);
    });

    list.style.display = 'block';
}

function selectDevice(serial) {
    addLog('info', `Selected device: ${serial}`);

    startSpinner(serial);
}

async function startSpinner(serial) {
    addLog('info', `Starting Spinner on ${serial}...`);
    setStatus('initializing', 'CONNECTING');

    try {
        const result = await eel.spinner_start_mobile(serial)();

        if (result.success) {
            currentState.device = serial;

            transitionToRunning(serial);
        } else {
            addLog('error', `Failed to start: ${result.error}`);
            setStatus('error', 'ERROR');
        }
    } catch (error) {
        addLog('error', `Start error: ${error.message || error}`);
        setStatus('error', 'ERROR');
    }
}

function transitionToRunning(serial) {
    document.getElementById('wizardView').style.display = 'none';
    document.getElementById('runningView').style.display = 'grid';
    document.getElementById('currentDevice').textContent = serial;

    isRunning = true;
    spinnerStartTime = performance.now();

    setInterval(updateUptime, 1000);

    setStatus('running', 'RUNNING');
    addLogRunning('success', `Spinner started on ${serial}`);

    pollInterval = setInterval(pollLogs, 1500);
}

async function pollLogs() {
    try {
        const data = await eel.get_spinner_data()();

        if (!data) return;

        if (data.logs && data.logs.length > 0)
            data.logs.forEach(log => {
                addLogRunning(log.type, log.message);
                parseLogForState(log.message);
            });
    } catch (error) {
        console.error('Poll error:', error);
    }
}

function parseLogForState(message) {
    const msg = message.toLowerCase();
    const wheel = document.getElementById('wheelAnimation');
    const spinStatus = document.getElementById('spinStatus');

    if (msg.includes('launching game')) {
        updateState('phase', 'Starting game');
        updateState('action', 'Launching app');
    } else if (msg.includes('waiting for main menu')) {
        updateState('phase', 'Loading game');
        updateState('action', 'Waiting for menu');
    } else if (msg.includes('opening gold wheel')) {
        updateState('phase', 'Navigating');
        updateState('action', 'Opening reward wheel');
    } else if (msg.includes('checking ad button')) {
        updateState('phase', 'Checking rewards');
        updateState('action', 'Scanning screen');
    } else if (msg.includes('clicking ad button')) {
        updateState('phase', 'Starting ad');
        updateState('action', 'Clicking watch button');
    } else if (msg.includes('watching ad')) {
        updateState('phase', 'Watching advertisement');
        updateState('action', 'Ad in progress');
    } else if (msg.includes('closing ad')) {
        updateState('phase', 'Closing ad');
        updateState('action', 'Pressing back');
    } else if (msg.includes('checking spin button')) {
        updateState('phase', 'Ready to spin');
        updateState('action', 'Locating spin button');
    } else if (msg.includes('spinned')) {
        updateState('phase', 'Spinning wheel');
        updateState('action', 'Processing spin');

        if (wheel) wheel.classList.add('spinning');

        if (spinStatus) {
            spinStatus.textContent = 'SPINNING!'
            spinStatus.className = 'spin-status spinning';
        }

        spinnerStats.totalSpins++;
        spinnerStats.successfulSpins++;

        updateStats();
        updateState('lastSpin', new Date().toLocaleTimeString());

        setTimeout(() => {
            if (wheel) wheel.classList.remove('spinning');

            if (spinStatus) {
                spinStatus.textContent = 'SUCCESS';
                spinStatus.className = 'spin-status success';
            }

            setTimeout(() => {
                if (spinStatus) {
                    spinStatus.textContent = 'READY';
                    spinStatus.className = 'spin-status';
                }
            }, 2000);
        }, 3000);
    } else if (msg.includes('done!')) {
        updateState('phase', 'All spins complete');
        updateState('action', 'Session finished');
        setStatus('complete', 'COMPLETE');

        if (spinStatus) {
            spinStatus.textContent = 'COMPLETE!';
            spinStatus.className = 'spin-status success';
        }

        if (wheel) wheel.classList.remove('spinning');

        if (pollInterval) clearInterval(pollInterval);
    } else if (msg.includes('loading takes too long') || msg.includes('could not close ad') || msg.includes('spin button not found')) {
        updateState('phase', 'Error');
        updateState('action', 'Retrying...');

        spinnerStats.failedSpins++;

        updateStats();
    } else if (msg.includes('restarting game')) {
        updateState('phase', 'Restarting');
        updateState('action', 'Force-stopping app');
    } else if (msg.includes('rejoin popup')) {
        updateState('action', 'Dismissing popup');
    }

    updateStateDisplay();
}

function setScanStatus(state, text) {
    const dot = document.querySelector('#step-scan .step-dot');
    const span = document.querySelector('#step-scan .step-status span:last-child');

    if (dot) { dot.className = `step-dot ${state}`; }

    if (span) span.textContent = text;
}

function setStatus(level, text) {
    const indicator = document.getElementById('statusIndicator');
    indicator.className = 'status-indicator ' + level;
    indicator.querySelector('.status-text').textContent = text;
}

function updateState(key, value) {
    if (currentState[key] === value) return;

    currentState[key] = value;
}

function updateStateDisplay() {
    const phase  = document.getElementById('currentPhase');
    const action = document.getElementById('currentAction');

    if (phase)  phase.textContent  = currentState.phase;

    if (action) {
        action.textContent = currentState.action;
        action.classList.toggle('active', currentState.action !== 'Idle');
    }

    const lastSpin = document.getElementById('lastSpin');

    if (lastSpin) lastSpin.textContent = currentState.lastSpin;

    if (spinnerStats.totalSpins > 0) {
        const rate = Math.round((spinnerStats.successfulSpins / spinnerStats.totalSpins) * 100);
        const el = document.getElementById('successRate');

        if (el) el.textContent = `${rate}%`;
    }
}

function updateStats() {
    const t = document.getElementById('totalSpins');
    const s = document.getElementById('successfulSpins');
    const f = document.getElementById('failedSpins');

    if (t) t.textContent = spinnerStats.totalSpins;

    if (s) s.textContent = spinnerStats.successfulSpins;

    if (f) f.textContent = spinnerStats.failedSpins;
}

function updateUptime() {
    if (!spinnerStartTime) return;

    const elapsed = Math.floor((performance.now() - spinnerStartTime) / 1000);
    const h = Math.floor(elapsed / 3600).toString().padStart(2, '0');
    const m = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
    const s = (elapsed % 60).toString().padStart(2, '0');
    const el = document.getElementById('uptime');

    if (el) el.textContent = `${h}:${m}:${s}`;
}

function addLog(type, message) {
    _appendLog('logContent', type, message);
}

function addLogRunning(type, message) {
    _appendLog('logContentRunning', type, message);
}

function _appendLog(containerId, type, message) {
    const container = document.getElementById(containerId);

    if (!container) return;

    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;

    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    entry.innerHTML = `<span class="log-time">[${time}]</span><span class="log-message">${message}</span>`;

    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function clearLog() {
    const running = document.getElementById('logContentRunning');
    const wizard  = document.getElementById('logContent');

    if (running && running.closest('#runningView').style.display !== 'none') {
        running.innerHTML = '';

        addLogRunning('info', 'Log cleared');
    } else {
        if (wizard) wizard.innerHTML = '';

        addLog('info', 'Log cleared');
    }
}

eel.expose(spinner_log_update);

function spinner_log_update(type, message) {
    if (isRunning) addLogRunning(type, message);

    else addLog(type, message);
    
    parseLogForState(message);
}
