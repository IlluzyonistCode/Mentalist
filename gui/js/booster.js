let isInitialized = false;

let boosterStartTime = null;
let boosterStats = {
    gamesPlayed: 0,
    werewolfGames: 0,
    villagerGames: 0
};

let currentState = {
    phase: 'Waiting for game...',
    role: 'Unknown',
    action: 'Idle'
};

let updateInterval = null;
let processingLogs = false;

document.addEventListener('DOMContentLoaded', async () => {
    console.log('%c Mentalist Booster Initialized ', 'background: #00ff88; color: #000; font-weight: bold;');

    addLog('info', 'Initializing Booster module...');

    try {
        const result = await eel.booster_start()();

        if (result.success) {
            addLog('success', 'Booster started successfully!');

            boosterStartTime = Date.now();

            setInterval(updateUptime, 1000);
            updateInterval = setInterval(pollBoosterState, 2000);
            
            setInterval(async () => {
                if (processingLogs) return;
                
                try {
                    processingLogs = true;
                    const data = await eel.get_booster_data()();
                    
                    if (!data) return;
                    
                    if (data.states && data.states.length > 0) {
                        const latestState = data.states[data.states.length - 1];
                        
                        if (latestState.initialized && !isInitialized) {
                            isInitialized = true;
                            setStatus('running', 'RUNNING');
                            addLog('success', '✓ Browser ready');
                        }
                        
                        if (latestState.phase) updateState('phase', latestState.phase);
                        if (latestState.role) updateState('role', latestState.role);
                        if (latestState.action) updateState('action', latestState.action);
                    }
                    
                    if (data.logs && data.logs.length > 0) {
                        addLogsBatch(data.logs);
                    }
                } catch (e) {
                    console.error('[BOOSTER] Polling error:', e);
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

window.addEventListener('beforeunload', () => {
    if (updateInterval) clearInterval(updateInterval);
});

async function pollBoosterState() {
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

    if (msg.includes('checking for cancel modal') || msg.includes('cancel modal detected')) {
        updateState('phase', 'Modal window');
        updateState('action', 'Closing cancel dialog');
    } else if (msg.includes('cancel modal closed') || msg.includes('no cancel modal')) {
        updateState('action', 'Cancel dialog handled');
    } else if (msg.includes('checking for join new button') || msg.includes('join new button found')) {
        updateState('action', 'Clicking join new');
    } else if (msg.includes('join new clicked')) {
        updateState('action', 'Join new executed');
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
    } else if (msg.includes('game already started')) {
        updateState('phase', 'Room unavailable');
        updateState('action', 'Retrying');
    } else if (msg.includes('you are a') || msg.includes('you are an')) {
        const roleMatch = msg.match(/you are (?:a|an) (.+?)!/i);

        if (roleMatch) {
            const roleName = roleMatch[1];
            const roleCapitalized = roleName.split(' ').map(w =>
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');

            updateState('role', roleCapitalized);

            if (roleName.toLowerCase().includes('wolf')) {
                updateState('phase', 'Night');

                boosterStats.werewolfGames++;
            } else {
                updateState('phase', 'Day');

                boosterStats.villagerGames++;
            }

            updateStats();
        }
    } else if (msg.includes('finding players')) {
        updateState('action', 'Scanning players');
    } else if (msg.includes('players found')) {
        updateState('action', 'Players identified');
    } else if (msg.includes('sending message')) {
        updateState('action', 'Sending message');
    } else if (msg.includes('message sent')) {
        updateState('action', 'Message delivered');
    } else if (msg.includes('voting couple') || msg.includes('voting target')) {
        updateState('action', 'Voting');
    } else if (msg.includes('couple voted') || msg.includes('voted')) {
        updateState('action', 'Vote cast');
    } else if (msg.includes('finding target')) {
        updateState('action', 'Finding target');
    } else if (msg.includes('target found')) {
        updateState('action', 'Target locked');
    } else if (msg.includes('target not found')) {
        updateState('action', 'No target');
    } else if (msg.includes('selecting bullet')) {
        updateState('action', 'Loading bullet');
    } else if (msg.includes('bullet selected')) {
        updateState('action', 'Bullet ready');
    } else if (msg.includes('using holy water') || msg.includes('using bullet') ||
        msg.includes('using vigilante bullet')) {
        updateState('action', 'Using ability');
    } else if (msg.includes('holy water used') || msg.includes('bullet used') ||
        msg.includes('vigilante bullet used')) {
        updateState('action', 'Ability executed');
    } else if (msg.includes('tagging player')) {
        updateState('action', 'Tagging target');
    } else if (msg.includes('player tagged')) {
        updateState('action', 'Tag complete');
    } else if (msg.includes('analyzing day chat') || msg.includes('analyzing night chat')) {
        updateState('action', 'Analyzing chat');
    } else if (msg.includes('no suspicious target')) {
        updateState('action', 'No threats');
    } else if (msg.includes('waiting for voting phase')) {
        updateState('action', 'Waiting for voting phase');
    } else if (msg.includes('voting phase started')) {
        updateState('phase', 'Voting phase');
        updateState('action', 'Ready to vote');
    } else if (msg.includes('voting phase not detected')) {
        updateState('action', 'Voting unavailable');
    } else if (msg.includes('waiting for game end')) {
        updateState('phase', 'Game ongoing');
        updateState('action', 'Waiting for end');
    } else if (msg.includes('end!')) {
        updateState('phase', 'Game ended');
        updateState('action', 'Processing');

        boosterStats.gamesPlayed++;

        updateStats();
    } else if (msg.includes('exiting')) {
        updateState('phase', 'Exiting');
        updateState('action', 'Leaving lobby');
    }
}

function updateState(key, value) {
    if (currentState[key] === value) return;
    
    currentState[key] = value;

    updateStateDisplay();
}

function updateStateDisplay() {
    document.getElementById('currentPhase').textContent = currentState.phase;

    const roleEl = document.getElementById('currentRole');
    roleEl.textContent = currentState.role;
    roleEl.className = 'state-value';

    if (currentState.role.toLowerCase().includes('werewolf') ||
        currentState.role.toLowerCase().includes('wolf')) {
        roleEl.classList.add('werewolf');
    }

    else if (currentState.role !== 'Unknown') roleEl.classList.add('villager');

    const actionEl = document.getElementById('currentAction');
    actionEl.textContent = currentState.action;

    if (currentState.action !== 'Idle' && currentState.action !== 'Waiting') actionEl.classList.add('active');
    
    else actionEl.classList.remove('active');
}

function updateStats() {
    document.getElementById('gamesPlayed').textContent = boosterStats.gamesPlayed;
    document.getElementById('werewolfGames').textContent = boosterStats.werewolfGames;
    document.getElementById('villagerGames').textContent = boosterStats.villagerGames;
}

function updateUptime() {
    if (!boosterStartTime) return;

    const elapsed = Math.floor((Date.now() - boosterStartTime) / 1000);
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
