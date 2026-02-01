let moduleIsLaunching = false;
let availableModules = {
    tracker: false,
    stalker: false,
    booster: false,
    spinner: false
};

document.addEventListener('DOMContentLoaded', async () => {
    initParticles();
    await updateModulesStatus();
    checkServerStatus();
    setInterval(checkServerStatus, 30000);
    setInterval(updateModulesStatus, 60000);
});

async function updateModulesStatus() {
    try {
        const status = await eel.get_modules_status()();

        if (status) {
            if (status.modules) {
                availableModules = status.modules;

                updateModuleCards();
            }

            updateFooter(status);
        }
    } catch (error) {
        console.error('Failed to get modules status:', error);

        updateFooterError();
    }
}

function updateModuleCards() {
    Object.keys(availableModules).forEach(moduleName => {
        const card = document.querySelector(`[data-module="${moduleName}"]`);

        if (!card) return;

        const button = card.querySelector('.card-button span');
        const cardButton = card.querySelector('.card-button');

        if (!availableModules[moduleName]) {
            card.classList.add('module-disabled');
            button.textContent = 'LOCKED';
            cardButton.disabled = true;
        } else {
            card.classList.remove('module-disabled');
            button.textContent = 'LAUNCH';
            cardButton.disabled = false;
        }
    });
}

function updateFooter(status) {
    const versionElement = document.querySelector('.footer-info-grid .footer-item:nth-child(1) .footer-value');
    
    if (versionElement && status.version) versionElement.textContent = status.version;

    const modulesElement = document.querySelector('.footer-info-grid .footer-item:nth-child(2) .footer-value');
    
    if (modulesElement) {
        const activeCount = status.active_count ?? Object.values(availableModules).filter(v => v).length;
        
        modulesElement.textContent = `${activeCount} Available`;
    }

    const statusElement = document.querySelector('.footer-info-grid .footer-item:nth-child(3) .footer-value');
    
    if (statusElement) {
        const isReady = status.ready ?? false;

        statusElement.textContent = isReady ? 'Ready' : 'Not Ready';
        statusElement.classList.remove('ready', 'not-ready');
        statusElement.classList.add(isReady ? 'ready' : 'not-ready');
    }
}

function updateFooterError() {
    const versionElement = document.querySelector('.footer-info-grid .footer-item:nth-child(1) .footer-value');
    const modulesElement = document.querySelector('.footer-info-grid .footer-item:nth-child(2) .footer-value');
    const statusElement = document.querySelector('.footer-info-grid .footer-item:nth-child(3) .footer-value');

    if (versionElement) versionElement.textContent = 'Error';
    if (modulesElement) modulesElement.textContent = 'Unknown';
    if (statusElement) {
        statusElement.textContent = 'Error';
        statusElement.classList.remove('ready');
        statusElement.classList.add('not-ready');
    }
}

function initParticles() {
    const container = document.getElementById('blood-particles');

    for (let i = 0; i < 200; i++) createBloodParticle(container);

    setInterval(() => {
        if (container.children.length < 80) createBloodParticle(container);
    }, 3000);
}

function createBloodParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'blood-particle';

    const size = Math.random() * 8 + 5;
    const startX = Math.random() * 100;
    const startY = Math.random() * 100;
    const duration = Math.random() * 20 + 15;
    const delay = Math.random() * 5;
    const drift = (Math.random() - 0.5) * 30;

    particle.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        left: ${startX}%;
        top: ${startY}%;
        background: radial-gradient(circle, #8b0000, #4a0000);
        border-radius: 50%;
        opacity: ${Math.random() * 0.4 + 0.2};
        box-shadow: 0 0 ${size * 2}px rgba(139, 0, 0, 0.3);
        animation: bloodFloat ${duration}s infinite ease-in-out ${delay}s;
        pointer-events: none;
        z-index: 1;
        --drift: ${drift}px;
    `;

    container.appendChild(particle);

    setTimeout(() => {
        if (particle.parentNode === container) particle.remove();
    }, (duration + delay) * 1000);
}

async function checkServerStatus() {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    try {
        const result = await eel.check_server_connection()();

        if (result.connected) {
            statusDot.classList.add('online');
            statusDot.classList.remove('offline');

            const uptime = formatUptime(result.uptime);
            statusText.textContent = `Server Online • ${uptime} • ${result.syncs} syncs`;
        } else {
            statusDot.classList.add('offline');
            statusDot.classList.remove('online');

            let reason = 'Offline';

            if (result.reason === 'disabled') reason = 'Disabled';
            else if (result.reason === 'no_url') reason = 'Not Configured';
            else if (result.reason === 'auth_failed') reason = 'Auth Failed';

            statusText.textContent = `Server ${reason}`;
        }
    } catch (error) {
        statusDot.classList.add('offline');
        statusDot.classList.remove('online');
        statusText.textContent = 'Server Unreachable';
    }
}

function formatUptime(seconds) {
    if (!seconds) return '0s';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m`;
    return `${seconds}s`;
}

async function launchModule(moduleName) {
    if (!availableModules[moduleName]) {
        showNotification(`${moduleName.toUpperCase()} module is not available. Check your configuration.`, 'error');
        
        return;
    }

    if (moduleIsLaunching) {
        console.log('Another module is already launching');

        return;
    }

    console.log(`Launching module: ${moduleName}`);

    const card = document.querySelector(`[data-module="${moduleName}"]`);
    const button = card.querySelector('.card-button');
    const originalText = button.querySelector('span').textContent;

    moduleIsLaunching = true;

    const allButtons = document.querySelectorAll('.card-button');

    allButtons.forEach(btn => {
        btn.disabled = true;
        btn.style.opacity = '0.5';
        btn.style.cursor = 'not-allowed';
    });

    button.querySelector('span').textContent = 'LOADING...';

    try {
        let result;

        switch (moduleName) {
            case 'tracker':
                result = await eel.tracker_start()();
                
                if (result.success) window.location.href = 'modules/tracker.html';

                break;

            case 'stalker':
                result = await eel.stalker_start()();

                if (result.success) window.location.href = 'modules/stalker.html';

                break;

            case 'booster':
                window.location.href = 'modules/booster.html';

                break;

            case 'spinner':
                window.location.href = 'modules/spinner.html';

                break;

            default:
                throw new Error('Unknown module');
        }

        if (result && !result.success) throw new Error(result.error || 'Unknown error');
    } catch (error) {
        console.error('Module launch error:', error);

        showNotification(`Failed to launch ${moduleName}: ${error.message}`, 'error');

        moduleIsLaunching = false;
        const moduleNames = ['tracker', 'stalker', 'booster', 'spinner'];

        allButtons.forEach((btn, index) => {
            if (availableModules[moduleNames[index]]) {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
            }
        });

        button.querySelector('span').textContent = originalText;
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    const borderColor = type === 'error' ? 'var(--state-danger)' : 'var(--state-success)';
    const glowColor = type === 'error' ? '255, 68, 68' : '0, 255, 136';

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 2rem;
        background: var(--bg-panel);
        border: 2px solid ${borderColor};
        color: var(--text-bright);
        font-family: 'Cinzel', serif;
        font-size: 0.85rem;
        letter-spacing: 2px;
        z-index: 9999;
        animation: slideInRight 0.3s ease-out;
        box-shadow: var(--shadow-deep), 0 0 30px rgba(${glowColor}, 0.3);
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key >= '1' && e.key <= '4') {
        e.preventDefault();

        const modules = ['tracker', 'stalker', 'booster', 'spinner'];

        launchModule(modules[parseInt(e.key) - 1]);
    }
});
