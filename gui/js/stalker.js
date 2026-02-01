let stalkerData = {
    targets: [],
    currentPage: 1,
    totalPages: 1
};

let updateInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
    console.log('Stalker module initialized');

    try {
        const initResult = await eel.stalker_start()();
        console.log('Engine status:', initResult);
    } catch (e) {
        console.error('Failed to ensure engine start:', e);
    }

    await loadTargets(1);

    updateInterval = setInterval(async () => {
        await loadTargets(stalkerData.currentPage);
    }, 60000);
});

window.addEventListener('beforeunload', () => {
    if (updateInterval) clearInterval(updateInterval);
});

async function loadTargets(page = 1) {
    const container = document.getElementById('targetsList');

    if (typeof utils !== 'undefined' && utils.showLoading) utils.showLoading('targetsList', 'ACCESSING DATABASE...');
    
    else container.innerHTML = '<div class="loading-state">SYNCHRONIZING...</div>';

    try {
        const result = await eel.stalker_get_targets(page)();

        if (result.success) {
            stalkerData.targets = result.targets;
            stalkerData.currentPage = result.current_page;
            stalkerData.totalPages = result.total_pages;

            renderTargets();
            updatePagination();
        }

        else container.innerHTML = `<div class="error-state"><p>CRITICAL ERROR: ${result.error}</p></div>`;
    } catch (error) {
        console.error('Bridge error:', error);

        container.innerHTML = `<div class="error-state"><p>CONNECTION LOST TO CORE</p></div>`;
    }
}

async function updateTargets() {
    if (typeof utils !== 'undefined' && utils.showNotification) utils.showNotification('Recalibrating all targets...', 'info');

    try {
        const result = await eel.stalker_update_targets()();

        if (result.success) setTimeout(() => loadTargets(stalkerData.currentPage), 3000);
    } catch (e) {
        console.error(e);
    }
}

function renderTargets() {
    const container = document.getElementById('targetsList');
    container.innerHTML = '';

    if (!stalkerData.targets || stalkerData.targets.length === 0) {
        container.innerHTML = '<div class="empty-state"><h3>DATABASE EMPTY</h3><p>Start tracking by adding a username.</p></div>';
        
        return;
    }

    stalkerData.targets.forEach((target) => {
        const card = createTargetCard(target);
        container.appendChild(card);
    });
}

function createTargetCard(target) {
    const card = document.createElement('div');
    card.className = 'target-card fade-in';

    const total = (target.win_count || 0) + (target.lose_count || 0) + (target.tie_count || 0);
    const wr = total > 0 ? Math.round((target.win_count / total) * 100) : 0;

    const statusClass = (target.status && target.status.toLowerCase().includes('online')) ? 'online' : 'offline';

    card.innerHTML = `
        <div class="target-header">
            <div class="target-identity">
                <div class="target-number">${target.index || '?'}</div>
                <div class="target-main-info">
                    <div class="target-name-row">
                        <span class="target-name">${target.name || 'Unknown'}</span>
                        <span class="target-level">★${target.level !== -1 ? target.level : '??'}</span>
                        <span class="status-dot ${statusClass}"></span>
                    </div>
                    <div class="target-id-sub">${target.id || 'N/A'}</div>
                </div>
            </div>
            <div class="target-quick-stats">
                <div class="q-stat" title="Win Rate">
                    <span class="q-label">WR</span>
                    <span class="q-value ${wr > 50 ? 'high' : ''}">${wr}%</span>
                </div>
                <div class="q-stat" title="Play Time">
                    <span class="q-label">TIME</span>
                    <span class="q-value">${target.play_time || 'N/A'}</span>
                </div>
                <div class="target-actions-cell">
                    <button class="icon-btn" onclick="event.stopPropagation(); showTargetDetails('${target.id}')" title="Full Dossier">👁️</button>
                    <button class="icon-btn danger" onclick="event.stopPropagation(); deleteTarget('${target.id}')" title="Delete">✖</button>
                </div>
            </div>
        </div>
        
        <div class="target-compact-grid">
            <div class="mini-stat"><span>👤 Friends:</span> <strong>${target.friends_count || 0}</strong></div>
            <div class="mini-stat"><span>🌹 Roses:</span> <strong>${target.received_roses || 0} / ${target.sent_roses || 0}</strong></div>
            <div class="mini-stat"><span>⌛ Created:</span> <strong>${target.created || '???'}</strong></div>
            <div class="mini-stat"><span>📅 Last:</span> <strong>${target.last_online || 'Never'}</strong></div>

            <div class="mini-stat" title="Village Wins/Losses"><span>🏠 Vill:</span> <strong class="green">${target.village_win_count || 0}</strong>/<strong class="red">${target.village_lose_count || 0}</strong></div>
            <div class="mini-stat" title="Werewolf Wins/Losses"><span>🐺 Wolf:</span> <strong class="green">${target.werewolf_win_count || 0}</strong>/<strong class="red">${target.werewolf_lose_count || 0}</strong></div>
            <div class="mini-stat" title="Solo Wins/Losses"><span>🔪 Solo:</span> <strong class="green">${target.solo_win_count || 0}</strong>/<strong class="red">${target.solo_lose_count || 0}</strong></div>
            <div class="mini-stat" title="Wins/Losses/Ties"><span>🥇 Tot:</span> <strong>${target.win_count || 0}</strong>/<strong>${target.lose_count || 0}</strong></div>
        </div>

        ${target.clan && target.clan.name ? `
        <div class="compact-clan">
            <span class="clan-tag-mini">${target.clan.tag || 'CLAN'}</span>
            <span class="clan-name-mini">${target.clan.name}</span>
            <span class="clan-xp-mini">${target.clan.player_xp || '0xp'}</span>
            <span class="clan-members-mini">👥${target.clan.member_count || '?'}/50</span>
        </div>
        ` : ''}
        
        <div class="win-rate-bar-mini">
            <div class="win-rate-fill" style="width: ${wr}%"></div>
        </div>
    `;

    card.onclick = () => showTargetDetails(target.id);

    return card;
}

function updatePagination() {
    const pageInfo = document.getElementById('pageInfo');
    
    if (pageInfo)
        pageInfo.textContent = `PAGE ${stalkerData.currentPage} / ${stalkerData.totalPages}`;

    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');

    if (prevBtn) prevBtn.disabled = stalkerData.currentPage === 1;
    if (nextBtn) nextBtn.disabled = stalkerData.currentPage === stalkerData.totalPages;
}

async function previousPage() {
    if (stalkerData.currentPage > 1) await loadTargets(stalkerData.currentPage - 1);
}

async function nextPage() {
    if (stalkerData.currentPage < stalkerData.totalPages) await loadTargets(stalkerData.currentPage + 1);
}

function showAddTarget() {
    const input = document.getElementById('targetUsername');

    if (input) input.value = '';

    if (typeof utils !== 'undefined' && utils.openModal) utils.openModal('addTargetModal');
    
    else {
        const modal = document.getElementById('addTargetModal');

        if (modal) modal.classList.add('active');
    }
}

function closeAddTarget() {
    if (typeof utils !== 'undefined' && utils.closeModal) utils.closeModal('addTargetModal');
    
    else {
        const modal = document.getElementById('addTargetModal');

        if (modal) modal.classList.remove('active');
    }
}

async function addTarget() {
    const username = document.getElementById('targetUsername').value.trim();
    
    if (!username) return;

    try {
        const result = await eel.stalker_add_target(username)();

        if (result.success) {
            closeAddTarget();

            if (typeof utils !== 'undefined' && utils.showNotification) utils.showNotification('Target acquired!', 'success');

            await loadTargets(1);
        } else alert(result.error || 'Failed to add target');
    } catch (e) {
        console.error(e);
    }
}

async function deleteTarget(id) {
    if (!confirm(`Are you sure you want to stop tracking ${id}?`)) return;

    try {
        const result = await eel.stalker_delete_target(id)();

        if (result.success) await loadTargets(stalkerData.currentPage);
    } catch (e) {
        console.error(e);
    }
}

async function showTargetDetails(targetId) {
    const id = typeof targetId === 'object' ? targetId.id : targetId;
    const target = stalkerData.targets.find(t => t.id === id);

    if (!target) return;

    const modal = document.getElementById('targetModal');
    const title = document.getElementById('targetModalTitle');
    const body = document.getElementById('targetModalBody');

    title.textContent = target.name || 'Unknown';

    const villageWinRate = calculateWR(target.village_win_count, target.village_lose_count);
    const wolfWinRate = calculateWR(target.werewolf_win_count, target.werewolf_lose_count);
    const soloWinRate = calculateWR(target.solo_win_count, target.solo_lose_count);

    body.innerHTML = `
        <div class="dossier-layout">
            <div class="dossier-section">
                <h4>IDENTITY</h4>
                <p><strong>ID:</strong> ${target.id}</p>
                <p><strong>Created:</strong> ${target.created || 'Unknown'}</p>
                <p><strong>Bio:</strong> ${target.bio || 'No data'}</p>
            </div>
            
            <div class="dossier-grid">
                <div class="dossier-box">
                    <h5>DYNAMICS</h5>
                    <p>WR: <span class="highlight">${calculateWR(target.win_count, target.lose_count)}%</span></p>
                    <p>Games: ${(target.win_count || 0) + (target.lose_count || 0)}</p>
                    <p>Playtime: ${target.play_time || 'N/A'}</p>
                </div>
                <div class="dossier-box">
                    <h5>SOCIAL</h5>
                    <p>Friends: ${target.friends_count || 0}</p>
                    <p>Roses Recv: ${target.received_roses || 0}</p>
                    <p>Roses Sent: ${target.sent_roses || 0}</p>
                </div>
            </div>

            <div class="dossier-roles">
                <div class="role-stat">
                    <span>VILLAGE</span>
                    <div class="progress-bg"><div class="progress-fill green" style="width:${villageWinRate}%"></div></div>
                    <small>${target.village_win_count}W / ${target.village_lose_count}L</small>
                </div>
                <div class="role-stat">
                    <span>WEREWOLF</span>
                    <div class="progress-bg"><div class="progress-fill red" style="width:${wolfWinRate}%"></div></div>
                    <small>${target.werewolf_win_count}W / ${target.werewolf_lose_count}L</small>
                </div>
                <div class="role-stat">
                    <span>SOLO</span>
                    <div class="progress-bg"><div class="progress-fill purple" style="width:${soloWinRate}%"></div></div>
                    <small>${target.solo_win_count}W / ${target.solo_lose_count}L</small>
                </div>
            </div>
        </div>
    `;

    if (typeof utils !== 'undefined' && utils.openModal) utils.openModal('targetModal');
    
    else modal.classList.add('active');
}

function closeTargetDetails() {
    if (typeof utils !== 'undefined' && utils.closeModal) utils.closeModal('targetModal');
    
    else {
        const modal = document.getElementById('targetModal');

        if (modal) modal.classList.remove('active');
    }
}

function calculateWR(w, l) {
    const total = (w || 0) + (l || 0);

    return total > 0 ? Math.round((w / total) * 100) : 0;
}
