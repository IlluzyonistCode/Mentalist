const utils = {
    async safeModuleExit(moduleName, options = {}) {
        const {
            backButtonId = 'backButton',
                statusIndicatorId = 'statusIndicator',
                stopDelay = 500,
                redirectUrl = '../index.html'
        } = options;

        const backButton = document.querySelector('.back-button') || document.getElementById(backButtonId);

        if (backButton && backButton.classList.contains('disabled')) {
            console.log(`${moduleName}: Already stopping, navigation blocked`);

            return;
        }

        if (backButton) {
            backButton.classList.add('disabled');
            backButton.textContent = '← STOPPING...';
            backButton.style.cursor = 'not-allowed';
            backButton.style.opacity = '0.6';
        }

        const statusIndicator = document.getElementById(statusIndicatorId);

        if (statusIndicator) {
            const statusText = statusIndicator.querySelector('.status-text');

            if (statusText) statusText.textContent = 'STOPPING...';

            statusIndicator.className = 'status-indicator warning';
        }

        try {
            console.log(`${moduleName}: Initiating safe shutdown...`);

            const stopFunctionName = `${moduleName}_stop`;

            if (typeof eel !== 'undefined' && eel[stopFunctionName]) {
                console.log(`${moduleName}: Calling ${stopFunctionName}()...`);

                const result = await eel[stopFunctionName]();

                console.log(`${moduleName}: Stop result:`, result);
            }

            else console.warn(`${moduleName}: Stop function not found`);

            await new Promise(resolve => setTimeout(resolve, stopDelay));

            console.log(`${moduleName}: Redirecting to main menu...`);

            window.location.href = redirectUrl;
        } catch (error) {
            console.error(`${moduleName}: Error during shutdown:`, error);

            utils.showNotification(`Error stopping ${moduleName}, forcing exit...`, 'warning', 2000);

            setTimeout(() => window.location.href = redirectUrl, 1000);
        }
    },


    formatTime(timestamp) {
        if (!timestamp) return 'N/A';

        const date = new Date(timestamp);

        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },

    formatDate(timestamp) {
        if (!timestamp) return 'N/A';

        const date = new Date(timestamp);

        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },

    formatDateTime(timestamp) {
        if (!timestamp) return 'N/A';

        return `${this.formatDate(timestamp)} ${this.formatTime(timestamp)}`;
    },

    formatUptime(seconds) {
        if (!seconds) return '0s';

        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (days > 0) return `${days}d ${hours}h`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        if (minutes > 0) return `${minutes}m ${secs}s`;

        return `${secs}s`;
    },

    formatDuration(seconds) {
        if (!seconds) return '0s';

        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
        if (minutes > 0) return `${minutes}m ${secs}s`;

        return `${secs}s`;
    },

    getTeamColor(team) {
        const colors = {
            'VILLAGER': '#00ff88',
            'WEREWOLF': '#ff0055',
            'SOLO': '#b537f2'
        };

        return colors[team] || '#a0a0b8';
    },

    getAuraColor(aura) {
        const colors = {
            'GOOD': '#00ff88',
            'EVIL': '#ff0055',
            'UNKNOWN': '#00d9ff'
        };

        return colors[aura] || '#a0a0b8';
    },

    getThreatColor(threat) {
        if (threat < 30) return '#00ff88';
        if (threat < 70) return '#ffed4e';

        return '#ff0055';
    },

    getThreatLevel(threat) {
        if (threat < 30) return 'low';
        if (threat < 70) return 'medium';

        return 'high';
    },

    showLoading(containerId, message = 'LOADING...') {
        const container = document.getElementById(containerId);

        if (container)
            container.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>${message}</p>
                </div>
            `;
    },

    hideLoading(containerId) {
        const container = document.getElementById(containerId);

        if (container) {
            const loadingState = container.querySelector('.loading-state');

            if (loadingState) loadingState.remove();
        }
    },

    showError(containerId, message = 'An error occurred') {
        const container = document.getElementById(containerId);

        if (container)
            container.innerHTML = `
                <div class="error-state">
                    <p>❌ ${message}</p>
                </div>
            `;
    },

    notificationQueue: [],

    showNotification(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} fade-in`;

        const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };

        notification.innerHTML = `
            <div class="notification-icon">${icons[type] || icons.info}</div>
            <div class="notification-message">${message}</div>
        `;

        notification.style.cssText = `
            position: fixed;
            top: ${20 + (this.notificationQueue.length * 80)}px;
            right: 20px;
            min-width: 300px;
            max-width: 500px;
            padding: 1rem 1.5rem;
            background: var(--bg-secondary);
            border: 1px solid;
            border-radius: 10px;
            color: var(--text-primary);
            font-family: 'Roboto', sans-serif;
            z-index: 10000;
            display: flex;
            align-items: center;
            gap: 1rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            animation: slideIn 0.3s ease-out;
        `;

        const typeColors = {
            success: '#00ff88',
            error: '#ff4444',
            warning: '#ffed4e',
            info: '#00d9ff'
        };

        const color = typeColors[type] || typeColors.info;

        notification.style.borderColor = color;
        notification.style.boxShadow = `0 0 20px ${color}4D`;

        document.body.appendChild(notification);

        this.notificationQueue.push(notification);

        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease-out';

            setTimeout(() => {
                notification.remove();

                this.notificationQueue = this.notificationQueue.filter(n => n !== notification);
                this.notificationQueue.forEach((n, i) => {
                    n.style.top = `${20 + (i * 80)}px`;
                });
            }, 300);
        }, duration);
    },

    openModal(modalId) {
        const modal = document.getElementById(modalId);

        if (modal) {
            modal.classList.add('active');

            document.body.style.overflow = 'hidden';
        }
    },

    closeModal(modalId) {
        const modal = document.getElementById(modalId);

        if (modal) {
            modal.classList.remove('active');

            document.body.style.overflow = '';
        }
    },

    async safeNavigate(targetUrl, currentModule = null) {
        try {
            if (currentModule && typeof eel !== 'undefined') {
                const stopFuncName = `${currentModule}_stop`;

                if (eel[stopFuncName]) {
                    console.log(`Stopping ${currentModule} module...`);

                    await eel[stopFuncName]();
                }
            }

            await new Promise(resolve => setTimeout(resolve, 250));

            window.location.href = targetUrl;
        } catch (error) {
            console.error('Navigation error:', error);
            
            window.location.href = targetUrl;
        }
    },

    setupBackButton(moduleName) {
        const backButton = document.querySelector('.back-button');

        if (backButton) {
            backButton.addEventListener('click', async (event) => {
                event.preventDefault();

                await this.safeNavigate('../index.html', moduleName);
            });
        }
    },

    setupCleanup(moduleName) {
        window.addEventListener('beforeunload', async () => {
            try {
                if (typeof eel !== 'undefined') {
                    const stopFuncName = `${moduleName}_stop`;

                    if (eel[stopFuncName]) await eel[stopFuncName]();
                }
            } catch (error) {
                console.log('Cleanup error:', error);
            }
        });
    },

    initModule(moduleName) {
        this.setupBackButton(moduleName);
        this.setupCleanup(moduleName);
        console.log(`%c ${moduleName.toUpperCase()} Module Initialized `,
            'background: #8b0000; color: #fff; font-weight: bold;');
    },



    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);

            this.showNotification('Copied to clipboard!', 'success', 2000);

            return true;
        } catch (err) {
            this.showNotification('Failed to copy', 'error', 2000);

            return false;
        }
    },

    debounce(func, wait) {
        let timeout;

        return function(...args) {
            clearTimeout(timeout);

            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    },

    throttle(func, limit) {
        let inThrottle;

        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);

                inThrottle = true;

                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    formatNumber: (num) => (num === -1 || num == null) ? 'N/A' : num.toLocaleString(),

    formatPercentage: (value, total) => (!total) ? '0%' : `${Math.round((value / total) * 100)}%`,

    formatWinRate(wins, losses) {
        const total = wins + losses;

        return total === 0 ? 'N/A' : `${Math.round((wins / total) * 100)}%`;
    }
};

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) utils.closeModal(e.target.id);
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape')
        document.querySelectorAll('.modal.active').forEach(m => utils.closeModal(m.id));
});

window.utils = utils;
