let isInitialized = false;

let boosterStartTime = null;
let boosterStats = {
    gamesPlayed: 0,
    villagerGames: 0,
    werewolfGames: 0,
    soloGames: 0
};

let currentState = {
    phase: 'Waiting for game...',
    role: 'None',
    action: 'Idle'
};

let guestMode = false;
let noPcgLocked = false;

let processingLogs = false;

document.addEventListener('DOMContentLoaded', async () => {
    console.log('%c Mentalist Booster Initialized ', 'background: #00ff88; color: #000; font-weight: bold;');
    addLog('info', 'Initializing Booster module...');

    try {
        const result = await eel.booster_start()();

        if (result.success) {
            addLog('success', 'Booster started successfully!');

            initGuestModeToggle();
            initHeadlessModeToggle();
            await initStats();

            boosterStartTime = performance.now();

            setInterval(updateUptime, 1000);
            setInterval(async () => {
                if (processingLogs) return;
                
                try {
                    processingLogs = true;

                    const data = await eel.get_booster_data()();
                    
                    if (!data) return;
                    
                    if (data.states && data.states.length > 0) {
                        data.states.forEach(state => {
                            if (state.initialized && !isInitialized) {
                                isInitialized = true;

                                setStatus('running', 'RUNNING');
                                addLog('success', '✓ Browser ready');
                            }

                            if (state.stats) {
                                Object.assign(boosterStats, state.stats);
                                updateStats();
                            }

                            if (state.phase) updateState('phase', state.phase);
                            if (state.role) updateState('role', state.role);
                            if (state.action) updateState('action', state.action);
                        });
                    }
                    
                    if (data.logs && data.logs.length > 0) addLogsBatch(data.logs);
                } catch (error) {
                    console.error('[BOOSTER] Polling error:', error);
                } finally {
                    processingLogs = false;
                }
            }, 1000);
        } else {
            addLog('error', `Failed to start Booster: ${result.error || 'Unknown error'}`);
            setStatus('error', 'ERROR');
        }
    } catch (error) {
        console.error('Booster initialization error:', error);
        addLog('error', 'Critical error during initialization');
        setStatus('error', 'FAILED');
    }
});

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

    if (msg.includes('premium custom games is active')) {
        updateState('action', 'PCG active');
    } else if (msg.includes('premium custom games not purchased')) {
        updateState('action', 'No PCG');
        applyNoPcgLock();
    } else if (msg.includes('creating custom room')) {
        updateState('phase', 'Creating room');
        updateState('action', 'Setting up');
    } else if (msg.includes('game created')) {
        updateState('phase', 'In lobby');
        updateState('action', 'Waiting for players');
    } else if (msg.includes('scanning rooms')) {
        updateState('phase', 'Searching lobby');
        updateState('action', 'Scanning rooms');
    } else if (msg.includes('joining room')) {
        updateState('phase', 'Joining lobby');
        updateState('action', 'Connecting');
    } else if (msg.includes('successfully joined room')) {
        updateState('phase', 'In lobby');
        updateState('action', 'Waiting for start');
    } else if (msg.includes('waiting for game start')) {
        updateState('phase', 'Lobby ready');
        updateState('action', 'Starting soon');
    } else if (msg.includes('host left the room')) {
        updateState('phase', 'Lobby closed');
        updateState('action', 'Finding new room');
    } else if (msg.includes('you are a') || msg.includes('you are an')) {
        const roleMatch = msg.match(/you are (?:a|an) (.+?)!/i);

        if (roleMatch) {
            const roleName = roleMatch[1];
            const roleCapitalized = roleName.split(' ').map(w =>
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');

            updateState('role', roleCapitalized);

            const isWolf = roleName.toLowerCase().includes('wolf');

            if (isWolf) {
                updateState('phase', 'Night');
            } else {
                updateState('phase', 'Day');
            }
        }
    } else if (msg.includes('finding players')) {
        updateState('action', 'Scanning players');
    } else if (msg.includes('sending message')) {
        updateState('action', 'Sending message');
    } else if (msg.includes('voting couple') || msg.includes('voting target')) {
        updateState('action', 'Voting');
    } else if (msg.includes('finding target')) {
        updateState('action', 'Finding target');
    } else if (msg.includes('target found')) {
        updateState('action', 'Target locked');
    } else if (msg.includes('analyzing day chat') || msg.includes('analyzing night chat')) {
        updateState('action', 'Analyzing chat');
    } else if (msg.includes('waiting for voting phase')) {
        updateState('action', 'Waiting for vote');
    } else if (msg.includes('voting phase started')) {
        updateState('phase', 'Voting phase');
        updateState('action', 'Ready to vote');
    } else if (msg.includes('waiting for game end')) {
        updateState('phase', 'Game ongoing');
        updateState('action', 'Waiting for end');
    } else if (msg.includes('end!')) {
        updateState('phase', 'Game ended');
        updateState('action', 'Processing');
    } else if (msg.includes('exiting')) {
        updateState('phase', 'Exiting');
        updateState('action', 'Leaving lobby');
    } else if (msg.includes('guest mode')) {
        const isGuest = msg.includes('enabled');

        guestMode = isGuest;

        applyGuestModeUI(isGuest);
    }
}

function updateState(key, value) {
    if (currentState[key] === value) return;
    
    currentState[key] = value;

    updateStateDisplay();
}

function updateStateDisplay() {
    const phaseEl = document.getElementById('currentPhase');
    phaseEl.textContent = currentState.phase;

    if (currentState.phase === 'Creating room') phaseEl.style.color = '#00bcd4';
    
    else phaseEl.style.color = '';

    const roleEl = document.getElementById('currentRole');

    roleEl.textContent = currentState.role;
    roleEl.className = 'state-value';

    if (currentState.role.toLowerCase().includes('werewolf') ||
        currentState.role.toLowerCase().includes('wolf'))
        roleEl.classList.add('werewolf');

    else if (currentState.role !== 'None') roleEl.classList.add('villager');

    const actionEl = document.getElementById('currentAction');
    actionEl.textContent = currentState.action;

    if (currentState.action !== 'Idle' && currentState.action !== 'Waiting')
        actionEl.classList.add('active');
    
    else actionEl.classList.remove('active');
}

function updateStats() {
    document.getElementById('gamesPlayed').textContent = boosterStats.gamesPlayed;
    document.getElementById('villagerGames').textContent = boosterStats.villagerGames;
    document.getElementById('werewolfGames').textContent = boosterStats.werewolfGames;
    document.getElementById('soloGames').textContent = boosterStats.soloGames;
}

function updateUptime() {
    if (!boosterStartTime) return;

    const elapsed = Math.floor((performance.now() - boosterStartTime) / 1000);
    const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
    const seconds = (elapsed % 60).toString().padStart(2, '0');

    document.getElementById('uptime').textContent = `${hours}:${minutes}:${seconds}`;
}

async function initStats() {
    try {
        const result = await eel.booster_get_stats()();

        if (result && result.success && result.stats) {
            Object.assign(boosterStats, result.stats);
            
            updateStats();
        }
    } catch (e) {
        console.warn('[BOOSTER] Could not load stats:', e);
    }
}

async function initGuestModeToggle() {
    try {
        const result = await eel.booster_get_guest_mode()();

        if (result && result.success) {
            guestMode = result.guest_mode;

            applyGuestModeUI(guestMode);
        }
    } catch (e) {
        console.warn('[BOOSTER] Could not read guest mode:', e);
    }
}

function applyNoPcgLock() {
    noPcgLocked = true;
    guestMode = true;

    applyGuestModeUI(true);

    const btn = document.getElementById('guestModeToggle');
    const desc = document.getElementById('guestModeDesc');

    if (btn) {
        btn.dataset.locked = '1';
        btn.style.opacity = '0.45';
        btn.style.cursor = 'not-allowed';
        btn.title = 'Host mode requires Premium Custom Games';
    }

    if (desc) desc.textContent = 'Joining existing rooms (no PCG)';

    addLog('warning', 'No PCG — Host mode locked, joining rooms only');
}

function applyGuestModeUI(isGuest) {
    const btn = document.getElementById('guestModeToggle');
    const label = document.getElementById('guestModeLabel');
    const desc = document.getElementById('guestModeDesc');

    if (!btn) return;

    if (isGuest) {
        btn.classList.add('is-guest');
        label.textContent = 'GUEST';
        desc.textContent = 'Joining existing rooms';
    } else {
        btn.classList.remove('is-guest');
        label.textContent = 'HOST';
        desc.textContent = 'Creating own rooms';
    }
}

async function toggleGuestMode() {
    if (noPcgLocked) return;

    const btn = document.getElementById('guestModeToggle');

    if (btn && btn.dataset.locked) return;

    if (btn) btn.dataset.locked = '1';

    guestMode = !guestMode;

    applyGuestModeUI(guestMode);

    try {
        const result = await eel.booster_set_guest_mode(guestMode)();

        if (!result || !result.success) {
            guestMode = !guestMode;

            applyGuestModeUI(guestMode);
            addLog('error', 'Failed to switch guest mode');
        } else {
            const state = guestMode ? 'GUEST (joining rooms only)' : 'HOST (creating rooms)';

            addLog('info', `Mode switched → ${state}`);
        }
    } catch (e) {
        guestMode = !guestMode;

        applyGuestModeUI(guestMode);
        addLog('error', `Guest mode error: ${e}`);
    } finally {
        if (btn) delete btn.dataset.locked;
    }
}

let headlessMode = false;

async function initHeadlessModeToggle() {
    try {
        const result = await eel.booster_get_headless_mode()();

        if (result && result.success) {
            headlessMode = result.headless_mode;

            applyHeadlessModeUI(headlessMode);
        }
    } catch (e) {
        console.warn('[BOOSTER] Could not read headless mode:', e);
    }
}

function applyHeadlessModeUI(isHeadless) {
    const btn = document.getElementById('headlessModeToggle');
    const label = document.getElementById('headlessModeLabel');

    if (!btn) return;

    if (isHeadless) {
        btn.classList.add('is-guest');
        label.textContent = 'HIDDEN';
    } else {
        btn.classList.remove('is-guest');
        label.textContent = 'VISIBLE';
    }
}

async function toggleHeadlessMode() {
    const btn = document.getElementById('headlessModeToggle');

    if (btn && btn.dataset.locked) return;

    if (btn) btn.dataset.locked = '1';

    headlessMode = !headlessMode;

    applyHeadlessModeUI(headlessMode);

    try {
        const result = await eel.booster_set_headless_mode(headlessMode)();

        if (!result || !result.success) {
            headlessMode = !headlessMode;

            applyHeadlessModeUI(headlessMode);
            addLog('error', 'Failed to switch browser mode');
        } else {
            const state = headlessMode ? 'HIDDEN (headless)' : 'VISIBLE';

            addLog('info', `Browser mode → ${state}`);
            addLog('warning', 'Browser will restart on next cycle');
        }
    } catch (e) {
        headlessMode = !headlessMode;

        applyHeadlessModeUI(headlessMode);
        addLog('error', `Browser mode error: ${e}`);
    } finally {
        if (btn) delete btn.dataset.locked;
    }
}

function clearLog() {
    const logContent = document.getElementById('logContent');
    logContent.innerHTML = '';

    addLog('info', 'Log cleared');
}

eel.expose(booster_log_update);

function booster_log_update(type, message) {
    addLog(type, message);
}

eel.expose(booster_state_update);

function booster_state_update(stateData) {
    if (stateData.initialized && !isInitialized) {
        isInitialized = true;

        setStatus('running', 'RUNNING');
        addLog('success', '✓ Browser ready');
    }

    if (stateData.phase) updateState('phase', stateData.phase);
    if (stateData.role) updateState('role', stateData.role);
    if (stateData.action) updateState('action', stateData.action);
    if (stateData.stats) {
        Object.assign(boosterStats, stateData.stats);

        updateStats();
    }
}
