let isInitialized = false;

let spinnerStartTime = null;
let spinnerStats = {
    totalSpins: 0,
    successfulSpins: 0,
    failedSpins: 0
};

let currentState = {
    phase: 'Waiting for initialization...',
    action: 'Idle',
    lastSpin: 'Never',
    successRate: 'N/A'
};

let updateInterval = null;
let isSpinning = false;
let processingLogs = false;

document.addEventListener('DOMContentLoaded', async () => {
    console.log('%c Mentalist Spinner Initialized ', 'background: #ffed4e; color: #000; font-weight: bold;');

    addLog('info', 'Initializing Spinner module...');

    try {
        const result = await eel.spinner_start()();

        if (result.success) {
            addLog('success', 'Spinner started successfully!');

            spinnerStartTime = Date.now();

            setInterval(updateUptime, 1000);

            updateInterval = setInterval(pollSpinnerState, 2000);
            
            setInterval(async () => {
                if (processingLogs) {
                    console.log('[SPINNER] Skipping poll - already processing');

                    return;
                }
                
                try {
                    processingLogs = true;

                    const data = await eel.get_spinner_data()();
                    
                    if (!data) return;

                    if (data.states && data.states.length > 0) {
                        const latestState = data.states[data.states.length - 1];
                        
                        if (latestState.initialized && !isInitialized) {
                            isInitialized = true;

                            setStatus('running', 'RUNNING');
                            addLog('success', '✓ Emulator initialized - ready to spin');
                        }
                        
                        if (latestState.phase) updateState('phase', latestState.phase);
                        if (latestState.action) updateState('action', latestState.action);
                        if (latestState.lastSpin) updateState('lastSpin', latestState.lastSpin);
                        if (latestState.stats) {
                            Object.assign(spinnerStats, latestState.stats);
                            
                            updateStats();
                        }
                    }

                    if (data.logs && data.logs.length > 0) addLogsBatch(data.logs);
                } catch (e) {
                    console.error('[SPINNER] Polling error:', e);
                } finally {
                    processingLogs = false;
                }
            }, 1000);
        } else {
            addLog('error', `Failed to start Spinner: ${result.error || 'Unknown error'}`);
            setStatus('error', 'ERROR');
        }
    } catch (error) {
        console.error('Spinner initialization error:', error);
        addLog('error', 'Critical error during initialization');
        setStatus('error', 'FAILED');
    }
});

window.addEventListener('beforeunload', () => {
    if (updateInterval) clearInterval(updateInterval);
});

async function pollSpinnerState() {
    try {
        updateStateDisplay();
    } catch (error) {
        console.error('State polling error:', error);
    }
}

function setStatus(level, text) {
    const indicator = document.getElementById('statusIndicator');
    const statusText = indicator.querySelector('.status-text');

    indicator.className = 'status-indicator ' + level;
    statusText.textContent = text;
}

function addLogsBatch(logs) {
    if (!logs || logs.length === 0) return;
    
    const logContent = document.getElementById('logContent');
    const fragment = document.createDocumentFragment();
    
    logs.forEach(log => {
        const entry = document.createElement('div');
        entry.className = `log-entry log-${log.type}`;
        
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });
        
        entry.innerHTML = `
            <span class="log-time">[${time}]</span>
            <span class="log-message">${log.message}</span>
        `;
        
        fragment.appendChild(entry);

        parseLogForState(log.message);
    });
    
    logContent.appendChild(fragment);
    logContent.scrollTop = logContent.scrollHeight;
}

function addLog(type, message) {
    const logContent = document.getElementById('logContent');

    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;

    const time = new Date().toLocaleTimeString('en-US', { hour12: false });

    entry.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="log-message">${message}</span>
    `;

    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
}

function parseLogForState(message) {
    const msg = message.toLowerCase();
    const wheel = document.getElementById('wheelAnimation');
    const spinStatus = document.getElementById('spinStatus');

    if (msg.includes('waiting for bluestacks')) {
        updateState('phase', 'Waiting for BlueStacks');
        updateState('action', 'Launching emulator');
    } else if (msg.includes('opening bluestacks') || msg.includes('bluestacks ready')) {
        updateState('phase', 'BlueStacks active');
        updateState('action', 'Loading game');
    } else if (msg.includes('waiting for the game')) {
        updateState('phase', 'Loading game');
        updateState('action', 'Waiting for profile');
    } else if (msg.includes('game loaded')) {
        updateState('phase', 'Game ready');
        updateState('action', 'Navigating to wheel');
    } else if (msg.includes('checking ad button')) {
        updateState('phase', 'Checking rewards');
        updateState('action', 'Scanning for ad button');
    } else if (msg.includes('done!')) {
        updateState('phase', 'All spins complete');
        updateState('action', 'Session finished');
        setStatus('complete', 'COMPLETE');
        if (spinStatus) {
            spinStatus.textContent = 'COMPLETE!';
            spinStatus.className = 'spin-status success';
        }

        if (wheel) wheel.classList.remove('spinning');
    } else if (msg.includes('watching ad')) {
        updateState('phase', 'Watching advertisement');
        updateState('action', 'Ad in progress (120s)');

        let countdown = 120;

        const countdownInterval = setInterval(() => {
            countdown--;

            updateState('action', `Ad in progress (${countdown}s)`);

            if (countdown <= 0) clearInterval(countdownInterval);
        }, 1000);
    } else if (msg.includes('checking spin button')) {
        updateState('phase', 'Ready to spin');
        updateState('action', 'Locating spin button');
    } else if (msg.includes('spinned')) {
        updateState('phase', 'Spinning wheel');
        updateState('action', 'Processing spin');

        if (wheel) wheel.classList.add('spinning');

        if (spinStatus) {
            spinStatus.textContent = 'SPINNING!';
            spinStatus.className = 'spin-status spinning';
        }

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

        spinnerStats.totalSpins++;
        spinnerStats.successfulSpins++;

        updateStats();
        updateState('lastSpin', new Date().toLocaleTimeString());
    } else if (msg.includes('loading takes too long') || msg.includes('failed')) {
        updateState('phase', 'Error detected');
        updateState('action', 'Retrying...');

        spinnerStats.failedSpins++;
        updateStats();
    } else if (msg.includes('restarting')) {
        updateState('phase', 'Restarting');
        updateState('action', 'Closing game');
    }
}

function updateState(key, value) {
    if (currentState[key] === value) return;
    
    currentState[key] = value;

    updateStateDisplay();
}

function updateStateDisplay() {
    document.getElementById('currentPhase').textContent = currentState.phase;

    const actionEl = document.getElementById('currentAction');
    actionEl.textContent = currentState.action;

    if (currentState.action !== 'Idle' && currentState.action !== 'Waiting') actionEl.classList.add('active');
    else actionEl.classList.remove('active');

    document.getElementById('lastSpin').textContent = currentState.lastSpin;

    if (spinnerStats.totalSpins > 0) {
        const rate = Math.round((spinnerStats.successfulSpins / spinnerStats.totalSpins) * 100);
        document.getElementById('successRate').textContent = `${rate}%`;
        currentState.successRate = `${rate}%`;
    }
}

function updateStats() {
    document.getElementById('totalSpins').textContent = spinnerStats.totalSpins;
    document.getElementById('successfulSpins').textContent = spinnerStats.successfulSpins;
    document.getElementById('failedSpins').textContent = spinnerStats.failedSpins;
}

function updateUptime() {
    if (!spinnerStartTime) return;

    const elapsed = Math.floor((Date.now() - spinnerStartTime) / 1000);
    const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
    const seconds = (elapsed % 60).toString().padStart(2, '0');

    document.getElementById('uptime').textContent = `${hours}:${minutes}:${seconds}`;
}

function clearLog() {
    const logContent = document.getElementById('logContent');
    logContent.innerHTML = '';

    addLog('info', 'Log cleared');
}

eel.expose(spinner_log_update);

function spinner_log_update(type, message) {
    addLog(type, message);
}

eel.expose(spinner_state_update);

function spinner_state_update(stateData) {
    if (stateData.initialized && !isInitialized) {
        isInitialized = true;

        setStatus('running', 'RUNNING');
        addLog('success', '✓ Emulator initialized - ready to spin');
    }

    if (stateData.phase) updateState('phase', stateData.phase);
    if (stateData.action) updateState('action', stateData.action);
    if (stateData.lastSpin) updateState('lastSpin', stateData.lastSpin);
    if (stateData.stats) {
        Object.assign(spinnerStats, stateData.stats);

        updateStats();
    }
}
