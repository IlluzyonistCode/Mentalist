class MentalistUpdater {
    constructor() {
        this.updateAvailable = false;
        this.updateInfo = null;
        this.downloading = false;
        this.installing = false;
    }

    async initialize() {
        setTimeout(() => this.checkForUpdates(true), 3000);

        this.createUpdateButton();
    }

    createUpdateButton() {
        const header = document.querySelector('.main-header');

        if (!header) return;

        const updateButton = document.createElement('button');
        updateButton.className = 'update-button';
        updateButton.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <path d="M3 3v5h5" />
                <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
                <path d="M16 16h5v5" />
            </svg>
            <span>Check Updates</span>
        `;
        updateButton.style.display = 'none';
        updateButton.onclick = () => this.showUpdateDialog();

        const serverStatus = header.querySelector('.server-status');

        if (serverStatus) header.insertBefore(updateButton, serverStatus);
        
        else header.appendChild(updateButton);

        this.updateButton = updateButton;
    }

    async checkForUpdates(silent=false) {
        try {
            if (!silent) this.showLoading('Checking for updates...');

            const result = await eel.check_for_updates()();

            if (!result.success) {
                if (!silent) this.showError('Failed to check for updates: ' + result.error);

                return;
            }

            if (result.update_available) {
                this.updateAvailable = true;
                this.updateInfo = result.update_info;

                if (this.updateButton) {
                    this.updateButton.style.display = 'flex';
                    this.updateButton.classList.add('update-available');
                }

                if (!silent) this.showUpdateDialog();
                
                else this.showUpdateNotification();
            } else {
                if (!silent) this.showSuccess('You are running the latest version!');
            }
        } catch (error) {
            console.error('Update check error:', error);

            if (!silent) this.showError('Failed to check for updates');
        }
    }

    showUpdateNotification() {
        const notification = document.createElement('div');
        notification.className = 'update-notification';
        notification.innerHTML = `
            <div class="update-notification-content">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
                <div>
                    <strong>Update Available!</strong>
                    <span>Version ${this.updateInfo.version} is ready to install</span>
                </div>
                <button onclick="updater.showUpdateDialog()">Install</button>
                <button class="close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('fade-out');

            setTimeout(() => notification.remove(), 500);
        }, 10000);
    }

    showUpdateDialog() {
        if (!this.updateInfo) {
            this.checkForUpdates(false);

            return;
        }

        const modal = document.createElement('div');
        modal.className = 'update-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content update-modal-content">
                <div class="modal-header">
                    <h2>Update Available</h2>
                    <button class="modal-close" onclick="this.closest('.update-modal').remove()">×</button>
                </div>
                
                <div class="modal-body">
                    <div class="version-info">
                        <div class="version-current">
                            <span class="label">Current Version</span>
                            <span class="value">${this.getCurrentVersion()}</span>
                        </div>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M5 12h14M12 5l7 7-7 7"/>
                        </svg>
                        <div class="version-new">
                            <span class="label">New Version</span>
                            <span class="value highlight">${this.updateInfo.version}</span>
                        </div>
                    </div>

                    <div class="update-details">
                        <div class="detail-item">
                            <span class="detail-label">Size:</span>
                            <span class="detail-value">${this.formatSize(this.updateInfo.size)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Released:</span>
                            <span class="detail-value">${this.formatDate(this.updateInfo.release_date)}</span>
                        </div>
                    </div>

                    ${this.updateInfo.changelog ? `
                        <div class="changelog">
                            <h3>What's New:</h3>
                            <div class="changelog-content">
                                ${this.formatChangelog(this.updateInfo.changelog)}
                            </div>
                        </div>
                    ` : ''}

                    <div class="update-progress" style="display: none;">
                        <div class="progress-bar">
                            <div class="progress-fill"></div>
                        </div>
                        <div class="progress-text">Preparing...</div>
                    </div>
                </div>

                <div class="modal-footer">
                    <button class="btn-secondary" onclick="this.closest('.update-modal').remove()">
                        Later
                    </button>
                    <button class="btn-primary" onclick="updater.startUpdate(this)">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        Download & Install
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    }

    async startUpdate(button) {
        if (this.downloading || this.installing) return;

        const modal = button.closest('.update-modal-content');
        const progressContainer = modal.querySelector('.update-progress');
        const progressFill = modal.querySelector('.progress-fill');
        const progressText = modal.querySelector('.progress-text');
        const footer = modal.querySelector('.modal-footer');

        progressContainer.style.display = 'block';
        footer.style.display = 'none';

        this.downloading = true;

        try {
            const result = await eel.download_and_install_update(this.updateInfo)();

            if (!result.success) throw new Error(result.error || 'Update failed');

            progressText.textContent = 'Downloading...';
        } catch (error) {
            this.downloading = false;
            this.showError('Update failed: ' + error.message);

            modal.closest('.update-modal').remove();
        }
    }

    updateProgress(eventType, data) {
        const modal = document.querySelector('.update-modal-content');

        if (!modal) return;

        const progressFill = modal.querySelector('.progress-fill');
        const progressText = modal.querySelector('.progress-text');

        switch (eventType) {
            case 'download_started':
                progressText.textContent = 'Downloading...';

                break;

            case 'download_progress':
                const percent = data.percent || 0;
                
                progressFill.style.width = percent + '%';
                progressText.textContent = `Downloading... ${percent.toFixed(1)}%`;
                
                break;

            case 'download_complete':
                progressFill.style.width = '100%';
                progressText.textContent = 'Download complete!';

                this.downloading = false;
                this.installing = true;

                break;

            case 'install_started':
                progressText.textContent = 'Installing update...';

                break;

            case 'install_complete':
                progressText.textContent = 'Installation complete!';

                this.installing = false;

                setTimeout(() => this.showRestartDialog(), 1000);

                break;

            case 'download_failed':
            case 'install_failed':
                this.downloading = false;
                this.installing = false;
                this.showError('Update failed: ' + (data.error || 'Unknown error'));
                
                modal.closest('.update-modal').remove();
                
                break;
        }
    }

    showRestartDialog() {
        const modal = document.querySelector('.update-modal');

        if (modal) modal.remove();

        const restartModal = document.createElement('div');
        restartModal.className = 'update-modal';
        restartModal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content update-success-modal">
                <div class="success-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                </div>
                <h2>Update Installed Successfully!</h2>
                <p>Please restart the application to use the new version.</p>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="this.closest('.update-modal').remove()">
                        Restart Later
                    </button>
                    <button class="btn-primary" onclick="updater.restartNow()">
                        Restart Now
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(restartModal);
    }

    async restartNow() {
        try {
            await eel.restart_application()();
        } catch (error) {
            console.error('Restart error:', error);
        }
    }

    getCurrentVersion() {
        const versionEl = document.querySelector('.footer-value');

        return versionEl ? versionEl.textContent : '1.0.0';
    }

    formatSize(bytes) {
        const units = ['B', 'KB', 'MB', 'GB'];
        let size = bytes;
        let unitIndex = 0;

        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }

        return `${size.toFixed(2)} ${units[unitIndex]}`;
    }

    formatDate(dateString) {
        const date = new Date(dateString);

        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    formatChangelog(changelog) {
        return changelog
            .split('\n')
            .filter(line => line.trim())
            .map(line => `<div class="changelog-item">• ${line.trim()}</div>`)
            .join('');
    }

    showLoading(message) {
        console.log('Loading:', message);
    }

    showSuccess(message) {
        console.log('Success:', message);
    }

    showError(message) {
        console.error('Error:', message);
    }
}

window.update_progress = function(eventType, data) {
    if (window.updater) window.updater.updateProgress(eventType, data);
};

window.notify_update_available = function(updateInfo) {
    if (window.updater) {
        window.updater.updateAvailable = true;
        window.updater.updateInfo = updateInfo;
        window.updater.showUpdateNotification();
    }
};

window.show_update_success = function() {
    if (window.updater) window.updater.showRestartDialog();
};

window.show_update_error = function(error) {
    if (window.updater) window.updater.showError(error);
};

window.updater = new MentalistUpdater();

document.addEventListener('DOMContentLoaded', () => {
    window.updater.initialize();
});
