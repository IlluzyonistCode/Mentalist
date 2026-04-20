let updateInterval = null;
let trackerStarted = false;
let playersData = [];
let rotationData = [];
let threatsData = {};
let alliancesData = {};
let playerClaims = {};
let bayesData = {};
let nlpData = {};
let analyticsSidebarOpen = false;
let selectedAnalyticsName = null;
let activeAnalyticsTab = 'bayes';

document.addEventListener('DOMContentLoaded', async () => {
    console.log('%c Mentalist Tracker Initialized ', 'background: #8b0000; color: #fff; font-weight: bold;');

    if (typeof utils !== 'undefined') utils.initModule('tracker');

    setupCommandInput();
    setupEventListeners();

    await startTracker();

    if (trackerStarted) {
        updateData();

        updateInterval = setInterval(updateData, 2000);
    }
});

window.addEventListener('beforeunload', () => {
    if (updateInterval) clearInterval(updateInterval);

    try {
        if (typeof eel !== 'undefined' && eel.tracker_stop) eel.tracker_stop();
    } catch (error) {
        console.log('Cleanup on unload failed:', error);
    }
});

async function startTracker() {
    try {
        const result = await eel.tracker_start()();

        if (result.success) {
            trackerStarted = true;

            console.log('Tracker engine connected.');
        } else console.error('Start error:', result.error);
    } catch (error) {
        console.error('Bridge init error:', error);
    }
}

async function updateData() {
    if (!trackerStarted) return;

    try {
        const result = await eel.tracker_get_state()();

        if (result && result.success) {
            playersData = result.players || [];
            rotationData = result.rotation || [];
            threatsData = result.threat_levels || {};
            alliancesData = result.player_alliances || {};
            playerClaims = result.player_claims || {};
            bayesData = result.bayes || {};
            nlpData = result.nlp || {};

            if (playersData.length > 0) {
                renderPlayers();
                renderRemainingRoles();
                renderAnalytics();
            } else {
                const grid = document.getElementById('playersGrid');

                if (grid) grid.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding: 2rem; color: var(--text-muted);">Waiting for game start...</div>';
            }
        }
    } catch (error) {
        console.error('Polling error:', error);
    }
}

function renderRemainingRoles() {
    if (!rotationData || rotationData.length === 0) return;

    const remaining = {
        'GOOD': [],
        'EVIL': [],
        'UNKNOWN': []
    };

    const distinctRotation = [];
    const seen = new Set();

    rotationData.forEach(role => {
        if (!seen.has(role.id)) {
            seen.add(role.id);

            distinctRotation.push(role);
        }
    });

    distinctRotation.forEach(role => {
        const total = rotationData.filter(r => r.id === role.id).length;
        let found = 0;

        playersData.forEach(player => {
            if (player.role === role.id) found++;
        });

        const unfound = total - found;

        for (let i = 0; i < unfound; i++) {
            const aura = role.aura || 'UNKNOWN';

            remaining[aura].push(role.name);
        }
    });

    const goodEl = document.getElementById('remainingGood');
    const evilEl = document.getElementById('remainingEvil');
    const unknownEl = document.getElementById('remainingUnknown');

    if (goodEl) goodEl.textContent = remaining.GOOD.join(', ') || '---';
    if (evilEl) evilEl.textContent = remaining.EVIL.join(', ') || '---';
    if (unknownEl) unknownEl.textContent = remaining.UNKNOWN.join(', ') || '---';
}

function renderPlayers() {
    const grid = document.getElementById('playersGrid');

    if (!grid) return;

    const fragment = document.createDocumentFragment();

    playersData.forEach(player => {
        const card = createPlayerCard(player);

        fragment.appendChild(card);
    });

    grid.innerHTML = '';
    grid.appendChild(fragment);
}

function createPlayerCard(player) {
    const card = document.createElement('div');
    const isSelected = player.name && player.name === selectedAnalyticsName;

    card.className = `player-card ${player.dead ? 'dead' : ''} ${isSelected ? 'analytics-selected' : ''}`;
    card.onclick = () => showPlayerDetails(player);

    const threat = threatsData[player.name];
    let threatHTML = '';

    if (threat !== undefined && threat !== null) {
        const level = threat < 30 ? 'low' : threat < 70 ? 'medium' : 'high';

        threatHTML = `<div class="threat-badge threat-${level}">${threat}%</div>`;
    } else threatHTML = `<div class="threat-badge" style="border: 1px dashed var(--text-muted); color: var(--text-muted);">?</div>`;

    const heroIcon = player.hero ? '<span style="color: var(--neon-yellow); margin-right: 5px;">👑</span>' : '';
    const levelDisplay = player.level !== -1 ?
        `<span class="player-level">⭐${player.level}</span>` :
        (player.min_level !== -1 ? `<span class="player-level">⭐${player.min_level}+</span>` : '');

    let claimHTML = '';

    if (!player.role) {
        if (player.claim) claimHTML += `<span style="color: var(--neon-blue); font-size: 0.85rem; margin-right: 8px;">C: ${player.claim}</span>`;

        if (player.contradiction) claimHTML += `<span style="color: #ff4444; font-weight: bold; font-size: 0.85rem;">CC: ${player.contradiction}</span>`;
    }

    let protectionHTML = '';

    for (const [protector, targets] of Object.entries(alliancesData))
        if (targets[player.name]) protectionHTML += `<span title="Protected by ${protector}" style="color: #5d5dff; margin-left: 5px;">🛡️<small>x${targets[player.name]}</small></span>`;

    const teamHTML = player.team ? `<span class="player-team team-${player.team.toLowerCase()}">${player.team}</span>` : '';
    const auraHTML = player.aura ? `<span class="player-aura aura-${player.aura.toLowerCase()}">${player.aura}</span>` : '';

    let possibleHTML = '';

    if (!player.role && player.possible_roles && player.possible_roles.length > 0) {
        const roleItems = player.possible_roles.map(p => {
            let icons = '';

            if (!p.has_card && !p.has_icon) icons = ' <small>❌⭕</small>';
            else if (!p.has_card) icons = ' <small>❌</small>';
            else if (!p.has_icon) icons = ' <small>⭕</small>';

            return `<span>${p.role}${icons}</span>`;
        });

        possibleHTML = `<div class="possible-roles"><span class="possible-roles-label">POSSIBLE:</span> ${roleItems.join(' / ')}</div>`;
    }

    card.innerHTML = `
        ${threatHTML}
        <div class="player-identity">
            <span class="player-number">${player.index}</span>
            <span class="player-name">${heroIcon}${player.name || '---'} ${levelDisplay}</span>
        </div>
        <div class="player-role-info">
            <div class="${player.role ? 'player-role' : 'player-role-unknown'}">
                ${player.role_name ? player.role_name : (claimHTML || '---')} ${protectionHTML}
            </div>
            <div class="status-badges">${teamHTML}${auraHTML}</div>
        </div>
        ${possibleHTML}
        <div class="player-stats">
            <span>💬 ${player.messages_count || 0}</span>
            <span>👁️ ${player.mentions_count || 0}</span>
        </div>
    `;

    return card;
}

function toggleAnalytics() {
    analyticsSidebarOpen = !analyticsSidebarOpen;

    const sidebar = document.getElementById('analyticsSidebar');
    const btn = document.getElementById('analyticsToggleBtn');

    if (analyticsSidebarOpen) {
        sidebar.classList.remove('collapsed');
        btn.classList.add('analytics-toggle-active');

        renderAnalytics();
    } else {
        sidebar.classList.add('collapsed');
        btn.classList.remove('analytics-toggle-active');
    }
}

function switchAnalyticsTab(tab, el) {
    activeAnalyticsTab = tab;

    document.querySelectorAll('.analytics-tab').forEach(t => t.classList.remove('active'));

    el.classList.add('active');

    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

    const pane = document.getElementById(`tab-${tab}`);

    if (pane) pane.classList.add('active');

    if (tab === 'graph') renderMentionGraph();
}

function renderAnalytics() {
    if (!analyticsSidebarOpen) return;

    renderBayesTab();
    renderNlpTab();

    if (activeAnalyticsTab === 'graph') renderMentionGraph();

    if (selectedAnalyticsName) renderAnalyticsDetail(selectedAnalyticsName);
}

function renderBayesTab() {
    const container = document.getElementById('bayesPlayerList');

    if (!container) return;

    const players = bayesData.players || [];

    if (players.length === 0) {
        container.innerHTML = '<div class="graph-empty">Waiting for game data...</div>';

        return;
    }

    container.innerHTML = '';

    players
        .slice()
        .sort((a, b) => a.slot - b.slot)
        .forEach(p => {
            const nlp = (nlpData.anomalies || {})[p.name] || {};
            const score = nlp.anomaly_score || 0;
            const tp = p.team_probs || {};

            const vPct = ((tp.VILLAGER || 0) * 100).toFixed(1);
            const wPct = ((tp.WEREWOLF || 0) * 100).toFixed(1);
            const sPct = ((tp.SOLO || 0) * 100).toFixed(1);

            const anomClass = score >= 60 ? 'bayes-anom-high' : score >= 30 ? 'bayes-anom-mid' : 'bayes-anom-low';
            const isSelected = p.name === selectedAnalyticsName;

            const row = document.createElement('div');

            row.className = `bayes-player-row ${isSelected ? 'selected' : ''}`;
            row.innerHTML = `
                <div class="bayes-row-header">
                    <span class="bayes-slot">${p.slot}</span>
                    <span class="bayes-name">${p.name || '---'}</span>
                    <span class="bayes-anom ${anomClass}">${score}</span>
                </div>
                <div class="team-prob-bar">
                    <div class="seg-v" style="width:${vPct}%" title="Villager ${vPct}%"></div>
                    <div class="seg-w" style="width:${wPct}%" title="Werewolf ${wPct}%"></div>
                    <div class="seg-s" style="width:${sPct}%" title="Solo ${sPct}%"></div>
                </div>
            `;
            row.onclick = () => selectAnalyticsPlayer(p.name);

            container.appendChild(row);
        });
}

function renderNlpTab() {
    const container = document.getElementById('nlpPlayerList');

    if (!container) return;

    const anomalies = nlpData.anomalies || {};

    if (Object.keys(anomalies).length === 0) {
        container.innerHTML = '<div class="graph-empty">No chat data yet</div>';

        return;
    }

    const sorted = Object.entries(anomalies).sort((a, b) => b[1].anomaly_score - a[1].anomaly_score);

    container.innerHTML = '';

    sorted.forEach(([name, anom]) => {
        const score = anom.anomaly_score || 0;
        const anomClass = score >= 60 ? 'bayes-anom-high' : score >= 30 ? 'bayes-anom-mid' : 'bayes-anom-low';
        const isSelected = name === selectedAnalyticsName;

        const drift = (anom.style_drift * 100).toFixed(0);
        const lenZ = anom.length_z > 0 ? '+' + anom.length_z.toFixed(1) : anom.length_z.toFixed(1);
        const msgs = anom.message_count || 0;

        const row = document.createElement('div');

        row.className = `bayes-player-row ${isSelected ? 'selected' : ''}`;
        row.innerHTML = `
            <div class="bayes-row-header">
                <span class="bayes-name">${name}</span>
                <span class="bayes-anom ${anomClass}">${score}</span>
            </div>
            <div style="font-family:'Cinzel',serif;font-size:0.6rem;color:var(--text-dirt);display:flex;gap:0.8rem;padding:2px 0;">
                <span title="Style drift">DRIFT ${drift}%</span>
                <span title="Length z-score">LEN ${lenZ}σ</span>
                <span title="Message count">MSG ${msgs}</span>
            </div>
        `;
        row.onclick = () => selectAnalyticsPlayer(name);

        container.appendChild(row);
    });
}

function renderMentionGraph() {
    const svg = document.getElementById('mentionGraphSvg');
    const emptyMsg = document.getElementById('graphEmpty');

    if (!svg) return;

    const graph = nlpData.mention_graph || {};

    if (Object.keys(graph).length === 0) {
        svg.setAttribute('height', '0');

        if (emptyMsg) emptyMsg.style.display = 'block';

        return;
    }

    if (emptyMsg) emptyMsg.style.display = 'none';

    const nodes = playersData
        .filter(p => p.name)
        .map(p => ({ slot: p.index, name: p.name, dead: p.dead }));

    const W = svg.parentElement.clientWidth || 280;
    const cols = 3;
    const cellW = W / cols;
    const cellH = 56;

    const rows = Math.ceil(nodes.length / cols);
    const H = rows * cellH + 20;

    svg.setAttribute('height', H);

    const posMap = {};

    nodes.forEach((n, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);

        posMap[n.name] = {
            x: cellW * col + cellW / 2,
            y: cellH * row + cellH / 2 + 10
        };
    });

    const edges = [];

    for (const [fromName, targets] of Object.entries(graph)) {
        for (const [slotStr, count] of Object.entries(targets)) {
            const slot = parseInt(slotStr);
            const toNode = nodes.find(n => n.slot === slot);

            if (toNode && toNode.name !== fromName && posMap[fromName] && posMap[toNode.name])
                edges.push({ from: fromName, to: toNode.name, count });
        }
    }

    const maxEdge = edges.reduce((m, e) => Math.max(m, e.count), 1);

    let markup = '';

    edges.forEach(e => {
        const a = posMap[e.from];
        const b = posMap[e.to];
        const opacity = 0.2 + (e.count / maxEdge) * 0.6;
        const w = 1 + (e.count / maxEdge) * 3;

        markup += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="var(--blood-arterial)" stroke-width="${w.toFixed(1)}" opacity="${opacity.toFixed(2)}"/>`;
    });

    nodes.forEach(n => {
        const pos = posMap[n.name];
        const anom = ((nlpData.anomalies || {})[n.name] || {}).anomaly_score || 0;
        const color = anom >= 60 ? 'var(--cli-red)' : anom >= 30 ? 'var(--cli-yellow)' : 'var(--blood-arterial)';
        const ring = anom >= 30 ? `<circle cx="${pos.x}" cy="${pos.y}" r="14" fill="none" stroke="${color}" stroke-width="1" stroke-dasharray="3 2" opacity="0.6"/>` : '';
        const label = n.name.slice(0, 7);
        const opac = n.dead ? '0.35' : '0.9';

        markup += `
            <g opacity="${opac}" style="cursor:pointer" onclick="selectAnalyticsPlayer('${n.name.replace(/'/g, '')}')">
                <circle cx="${pos.x}" cy="${pos.y}" r="11" fill="var(--bg-plate)" stroke="${color}" stroke-width="1.5"/>
                ${ring}
                <text x="${pos.x}" y="${pos.y}" fill="var(--blood-arterial)" text-anchor="middle" dominant-baseline="central" font-family="Cinzel,serif" font-size="9" font-weight="700">${n.slot}</text>
                <text x="${pos.x}" y="${pos.y + 20}" fill="var(--text-dirt)" text-anchor="middle" font-family="Cinzel,serif" font-size="7">${label}</text>
            </g>`;
    });

    svg.innerHTML = markup;
}

function selectAnalyticsPlayer(name) {
    selectedAnalyticsName = selectedAnalyticsName === name ? null : name;

    document.querySelectorAll('.player-card').forEach(card => {
        card.classList.remove('analytics-selected');
    });

    if (selectedAnalyticsName) {
        const p = playersData.find(pl => pl.name === selectedAnalyticsName);

        if (p) {
            const cards = document.querySelectorAll('.player-card');

            if (cards[p.index - 1]) cards[p.index - 1].classList.add('analytics-selected');
        }

        renderAnalyticsDetail(selectedAnalyticsName);
    } else {
        const detail = document.getElementById('analyticsDetail');

        if (detail) detail.style.display = 'none';
    }

    renderBayesTab();
    renderNlpTab();
}

function renderAnalyticsDetail(name) {
    const detail = document.getElementById('analyticsDetail');
    const title = document.getElementById('analyticsDetailTitle');
    const content = document.getElementById('analyticsDetailContent');

    if (!detail || !title || !content) return;

    const bPlayer = (bayesData.players || []).find(p => p.name === name);
    const anom = (nlpData.anomalies || {})[name] || {};

    if (!bPlayer && !Object.keys(anom).length) return;

    detail.style.display = 'block';
    title.textContent = name;

    let html = '';

    if (bPlayer) {
        const tp = bPlayer.team_probs || {};
        const vPct = ((tp.VILLAGER || 0) * 100).toFixed(0);
        const wPct = ((tp.WEREWOLF || 0) * 100).toFixed(0);
        const sPct = ((tp.SOLO || 0) * 100).toFixed(0);

        html += `
            <div style="font-family:'Cinzel',serif;font-size:0.6rem;color:var(--text-dirt);display:flex;gap:0.8rem;margin-bottom:6px;">
                <span style="color:var(--cli-green)">V ${vPct}%</span>
                <span style="color:var(--cli-red)">W ${wPct}%</span>
                <span style="color:var(--cli-purple)">S ${sPct}%</span>
            </div>`;

        const topRoles = bPlayer.top_roles || [];
        const maxProb = topRoles.length ? topRoles[0].prob : 1;

        topRoles.forEach(r => {
            const barW = maxProb > 0 ? (r.prob / maxProb * 100).toFixed(1) : 0;
            const pct = (r.prob * 100).toFixed(1);

            html += `
                <div class="role-prob-row">
                    <span class="role-prob-name">${r.role_name}</span>
                    <div class="role-prob-bar-wrap">
                        <div class="role-prob-bar-fill" style="width:${barW}%"></div>
                    </div>
                    <span class="role-prob-val">${pct}%</span>
                </div>`;
        });
    }

    const flags = anom.flags || [];

    if (flags.length) {
        html += '<div class="bayes-flags">';

        flags.forEach(f => { html += `<div class="bayes-flag-item">${f}</div>`; });

        html += '</div>';
    }

    content.innerHTML = html;
}

function showPlayerDetails(player) {
    const modal = document.getElementById('playerModal');

    if (!modal) return;

    document.getElementById('playerModalTitle').textContent = `PLAYER #${player.index}: ${player.name || '---'}`;

    const bPlayer = (bayesData.players || []).find(p => p.name === player.name);
    const anom = (nlpData.anomalies || {})[player.name] || {};

    let bayesHTML = '';

    if (bPlayer) {
        const tp = bPlayer.team_probs || {};
        const vPct = ((tp.VILLAGER || 0) * 100).toFixed(0);
        const wPct = ((tp.WEREWOLF || 0) * 100).toFixed(0);
        const sPct = ((tp.SOLO || 0) * 100).toFixed(0);

        const topRolesHTML = (bPlayer.top_roles || []).map(r => {
            const barW = bPlayer.top_roles[0] ? (r.prob / bPlayer.top_roles[0].prob * 100).toFixed(1) : 0;

            return `
                <div class="role-prob-row" style="margin-bottom:4px;">
                    <span class="role-prob-name">${r.role_name}</span>
                    <div class="role-prob-bar-wrap">
                        <div class="role-prob-bar-fill" style="width:${barW}%"></div>
                    </div>
                    <span class="role-prob-val">${(r.prob * 100).toFixed(1)}%</span>
                </div>`;
        }).join('');

        bayesHTML = `
            <div style="margin-top:1.5rem;border-top:1px solid var(--blood-dried);padding-top:1.2rem;">
                <div style="font-family:'Cinzel',serif;font-size:0.7rem;letter-spacing:2px;color:var(--tal-gold);margin-bottom:0.8rem;">BAYESIAN ANALYSIS</div>
                <div style="font-family:'Cinzel',serif;font-size:0.65rem;color:var(--text-dirt);display:flex;gap:1rem;margin-bottom:0.8rem;">
                    <span style="color:var(--cli-green)">VILLAGER ${vPct}%</span>
                    <span style="color:var(--cli-red)">WEREWOLF ${wPct}%</span>
                    <span style="color:var(--cli-purple)">SOLO ${sPct}%</span>
                </div>
                ${topRolesHTML}
            </div>`;
    }

    let nlpHTML = '';

    if (Object.keys(anom).length) {
        const score = anom.anomaly_score || 0;
        const anomClass = score >= 60 ? 'bayes-anom-high' : score >= 30 ? 'bayes-anom-mid' : 'bayes-anom-low';
        const flags = (anom.flags || []).map(f => `<div class="bayes-flag-item">${f}</div>`).join('');

        nlpHTML = `
            <div style="margin-top:1.2rem;border-top:1px solid var(--blood-dried);padding-top:1.2rem;">
                <div style="font-family:'Cinzel',serif;font-size:0.7rem;letter-spacing:2px;color:var(--tal-gold);margin-bottom:0.8rem;">
                    STYLE ANALYSIS &nbsp;<span class="bayes-anom ${anomClass}">${score}</span>
                </div>
                <div style="font-family:'Cinzel',serif;font-size:0.65rem;color:var(--text-dirt);display:flex;gap:1rem;margin-bottom:0.6rem;">
                    <span>DRIFT ${(anom.style_drift * 100 || 0).toFixed(0)}%</span>
                    <span>LEN σ ${anom.length_z > 0 ? '+' : ''}${(anom.length_z || 0).toFixed(1)}</span>
                    <span>MSGS ${anom.message_count || 0}</span>
                </div>
                <div class="bayes-flags">${flags}</div>
            </div>`;
    }

    document.getElementById('playerModalBody').innerHTML = `
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <p><strong>Role:</strong> ${player.role_name || '---'}</p>
            <p><strong>Team:</strong> ${player.team || '---'}</p>
            <p><strong>Aura:</strong> ${player.aura || '---'}</p>
            <p><strong>Messages:</strong> ${player.messages_count || 0}</p>
            <p><strong>Mentions:</strong> ${player.mentions_count || 0}</p>
            <p><strong>Hero:</strong> ${player.hero ? 'Yes' : 'No'}</p>
        </div>
        <div style="margin-top: 1rem; border-top: 1px solid var(--wine-red); padding-top: 1rem;">
            <strong>Excluded:</strong> ${player.teams_exclude?.join(', ') || 'No'}
        </div>
        ${bayesHTML}
        ${nlpHTML}
    `;

    modal.classList.add('active');
}

function closePlayerModal() {
    const modal = document.getElementById('playerModal');

    if (modal) modal.classList.remove('active');
}

function showMastermind() {
    const modal = document.getElementById('mastermindModal');

    if (modal) {
        modal.classList.add('active');

        updateFocusPlayerDropdown();
    }
}

function closeMastermind() {
    const modal = document.getElementById('mastermindModal');

    if (modal) modal.classList.remove('active');
}

function showHelp() {
    const modal = document.getElementById('helpModal');

    if (modal) modal.classList.add('active');
}

function closeHelp() {
    const modal = document.getElementById('helpModal');

    if (modal) modal.classList.remove('active');
}

function updateFocusPlayerDropdown() {
    const select = document.getElementById('focusPlayer');

    if (!select) return;

    select.innerHTML = '<option value="">All players</option>';

    playersData.filter(p => !p.dead && p.name).forEach(p => {
        const opt = document.createElement('option');

        opt.value = p.name;
        opt.textContent = `${p.index}. ${p.name}`;
        select.appendChild(opt);
    });
}

async function runPrediction() {
    const focus = document.getElementById('focusPlayer').value;
    const list = document.getElementById('scenariosList');

    if (!list) return;

    list.innerHTML = '<div style="text-align:center; padding:2rem; color:var(--pale-red);">Analyzing probabilities...</div>';

    try {
        const result = await eel.tracker_predict(focus || null)();

        if (result.success) renderScenarios(result.scenarios);

        else list.innerHTML = `<div style="color:var(--blood-red); padding:1rem;">Error: ${result.error}</div>`;
    } catch (error) {
        list.innerHTML = '<div style="color:var(--blood-red); padding:1rem;">AI error</div>';
    }
}

function renderScenarios(scenarios) {
    const list = document.getElementById('scenariosList');

    if (!list) return;

    if (!scenarios || scenarios.length === 0) {
        list.innerHTML = '<div style="text-align:center; padding:1rem;">Scenarios not found</div>';

        return;
    }

    list.innerHTML = '';

    scenarios.forEach((s, i) => {
        const card = document.createElement('div');

        card.className = 'scenario-card';

        const pathHTML = s.path.map(step => `
            <div class="action-step">
                <span class="action-actor">${step.actor}</span>
                <span class="action-ability"> ${step.ability}</span>
                ${step.target ? `<span class="action-target"> → ${step.target}</span>` : ''}
            </div>
        `).join('');

        card.innerHTML = `
            <div class="scenario-header">
                <span class="scenario-number">SCENARIO #${i + 1}</span>
                <span class="scenario-probability">${(s.probability * 100).toFixed(1)}%</span>
            </div>
            ${pathHTML}
        `;

        list.appendChild(card);
    });
}

function generateCommandSuggestions(input) {
    const suggestions = [];
    const lower = input.toLowerCase().trim();

    const baseCommands = ['storm', 'update', 'cursed turned', 'undo', 'redo'];
    const playerNumbers = playersData.map(p => p.index);
    const playerNames = playersData.filter(p => p.name).map(p => p.name);

    const allRoles = new Set();

    rotationData.forEach(role => {
        allRoles.add(role.name);

        if (role.random_roles) role.random_roles.forEach(r => allRoles.add(r));
    });

    const roles = Array.from(allRoles);
    const tokens = lower.split(/\s+/);

    if (lower.startsWith('predict')) {
        suggestions.push('predict');

        playerNumbers.forEach(num => suggestions.push(`predict ${num}`));
        playerNames.forEach(name => suggestions.push(`predict ${name}`));
    } else if (/^\d+\s+is\s*/.test(lower)) {
        const num = tokens[0];
        const partial = tokens.slice(2).join(' ');

        const statuses = ['dead', 'alive', 'good', 'evil', 'unknown', 'villager', 'werewolf', 'solo', 'cursed'];
        const negations = ['not villager', 'not werewolf', 'not solo'];

        [...statuses, ...negations].forEach(status => {
            if (status.startsWith(partial)) suggestions.push(`${num} is ${status}`);
        });

        roles.forEach(role => {
            if (role.toLowerCase().includes(partial)) suggestions.push(`${num} is ${role}`);
        });
    } else if (/^\d+\s*[!=]=?\s*/.test(lower)) {
        const num = tokens[0];
        const op = lower.includes('!=') ? '!=' : '=';

        playerNumbers.forEach(num2 => {
            if (num !== num2.toString()) suggestions.push(`${num} ${op} ${num2}`);
        });
    } else if (lower.startsWith('name of')) {
        playerNumbers.forEach(num => suggestions.push(`name of ${num} is`));
    } else if (lower.startsWith('change')) {
        const partial = tokens.slice(1).join(' ');

        roles.forEach(role1 => {
            if (role1.toLowerCase().includes(partial)) {
                suggestions.push(`change ${role1} to`);

                roles.forEach(role2 => {
                    if (role1 !== role2) suggestions.push(`change ${role1} to ${role2}`);
                });
            }
        });
    } else if (lower.startsWith('remove')) {
        const partial = tokens.slice(1).join(' ');

        roles.forEach(role => {
            if (role.toLowerCase().includes(partial)) {
                suggestions.push(`remove ${role} from`);

                playerNumbers.forEach(num => suggestions.push(`remove ${role} from ${num}`));
            }
        });
    } else if (lower.startsWith('clear')) {
        playerNumbers.forEach(num => suggestions.push(`clear ${num}`));
    } else if (/^\d+$/.test(lower)) {
        playerNumbers.forEach(num => {
            if (num.toString().startsWith(lower)) {
                suggestions.push(`${num} is`);
                suggestions.push(`${num} =`);
                suggestions.push(`${num} !=`);
            }
        });
    } else {
        baseCommands.forEach(cmd => {
            if (cmd.startsWith(lower)) suggestions.push(cmd);
        });

        if ('predict'.startsWith(lower)) suggestions.push('predict');
        if ('name'.startsWith(lower)) suggestions.push('name of');
        if ('change'.startsWith(lower)) suggestions.push('change');
        if ('remove'.startsWith(lower)) suggestions.push('remove');
        if ('clear'.startsWith(lower)) suggestions.push('clear');

        playerNumbers.forEach(num => {
            if (num.toString().startsWith(lower)) suggestions.push(`${num} is`);
        });
    }

    return [...new Set(suggestions)];
}

function setupCommandInput() {
    const input = document.getElementById('commandInput');
    const dropdown = document.getElementById('autocompleteDropdown');

    if (!input || !dropdown) return;

    input.addEventListener('input', (e) => {
        const value = e.target.value.toLowerCase();

        if (!value) {
            dropdown.classList.remove('active');

            return;
        }

        const matches = generateCommandSuggestions(value);

        if (matches.length === 0) {
            dropdown.classList.remove('active');

            return;
        }

        dropdown.innerHTML = '';

        matches.slice(0, 5).forEach(cmd => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.textContent = cmd;
            item.onclick = () => {
                input.value = cmd;
                dropdown.classList.remove('active');
                executeCommand(cmd);
                input.value = '';
            };

            dropdown.appendChild(item);
        });

        dropdown.classList.add('active');
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            executeCommand(input.value);

            input.value = '';

            dropdown.classList.remove('active');
        } else if (e.key === 'Escape') dropdown.classList.remove('active');
    });
}

async function executeCommand(command) {
    if (!command.trim()) return;

    try {
        console.log('Sending command:', command);

        const result = await eel.tracker_send_command(command)();

        if (result && result.success) await updateData();
    } catch (error) {
        console.error('Command execution failed:', error);
    }
}

async function updatePlayers() {
    try {
        await executeCommand('update');
    } catch (error) {
        console.error('Update failed:', error);
    }
}

function setupEventListeners() {
    window.onclick = (e) => {
        if (e.target.classList.contains('modal')) e.target.classList.remove('active');
    };

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeMastermind();
            closePlayerModal();
            closeHelp();
        }
    });
}
