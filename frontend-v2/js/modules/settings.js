// 灵知系统 - 系统设置模块
const SettingsModule = {
    initialized: false,
    settings: {
        searchMode: 'semantic',
        searchResultsPerPage: 20,
        theme: 'light',
        language: 'zh-CN',
        autoSaveInterval: 30,
        enableNotifications: true,
        enableAnalytics: true,
        defaultDomain: '',
        maxHistoryItems: 50
    },

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.loadSettings();
        this.bindEvents();
        this.render();
    },

    loadSettings() {
        try {
            const saved = localStorage.getItem('zhineng_settings');
            if (saved) {
                this.settings = { ...this.settings, ...JSON.parse(saved) };
            }
        } catch (error) {
            console.error('加载设置失败:', error);
        }

        if (this.settings.theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    },

    saveSettings() {
        try {
            localStorage.setItem('zhineng_settings', JSON.stringify(this.settings));
        } catch (error) {
            console.error('保存设置失败:', error);
        }
    },

    bindEvents() {
        const container = document.getElementById('settingsContent');
        if (!container) return;

        container.addEventListener('change', (e) => {
            const field = e.target.dataset.field;
            if (!field) return;

            let value;
            if (e.target.type === 'checkbox') {
                value = e.target.checked;
            } else if (e.target.type === 'number') {
                value = parseInt(e.target.value) || this.settings[field];
            } else {
                value = e.target.value;
            }

            this.settings[field] = value;
            this.saveSettings();
            this.applySetting(field, value);

            const statusEl = container.querySelector('.settings-save-status');
            if (statusEl) {
                statusEl.textContent = '✓ 已保存';
                statusEl.style.opacity = '1';
                setTimeout(() => { statusEl.style.opacity = '0.5'; }, 2000);
            }
        });

        const resetBtn = document.getElementById('settingsResetBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                if (confirm('确定恢复默认设置？')) {
                    localStorage.removeItem('zhineng_settings');
                    location.reload();
                }
            });
        }
    },

    applySetting(field, value) {
        switch (field) {
            case 'theme':
                if (value === 'dark') {
                    document.documentElement.setAttribute('data-theme', 'dark');
                } else {
                    document.documentElement.removeAttribute('data-theme');
                }
                const themeBtn = document.querySelector('.theme-toggle');
                if (themeBtn) themeBtn.textContent = value === 'dark' ? '☀️' : '🌙';
                break;
            case 'language':
                break;
        }
    },

    render() {
        const container = document.getElementById('settingsContent');
        if (!container) return;

        const s = this.settings;

        container.innerHTML = `
            <div style="max-width:640px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;">
                    <h2 style="font-size:20px;">系统设置</h2>
                    <span class="settings-save-status" style="font-size:13px;color:var(--success);opacity:0.5;">✓ 已保存</span>
                </div>

                <div class="settings-section">
                    <h3 style="font-size:16px;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border-light);">外观</h3>

                    <div style="margin-bottom:16px;">
                        <label style="display:block;margin-bottom:6px;font-size:14px;">主题</label>
                        <select data-field="theme" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);">
                            <option value="light" ${s.theme === 'light' ? 'selected' : ''}>☀️ 亮色模式</option>
                            <option value="dark" ${s.theme === 'dark' ? 'selected' : ''}>🌙 暗色模式</option>
                        </select>
                    </div>

                    <div style="margin-bottom:16px;">
                        <label style="display:block;margin-bottom:6px;font-size:14px;">语言</label>
                        <select data-field="language" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);">
                            <option value="zh-CN" ${s.language === 'zh-CN' ? 'selected' : ''}>简体中文</option>
                            <option value="zh-TW" ${s.language === 'zh-TW' ? 'selected' : ''}>繁體中文</option>
                            <option value="en" ${s.language === 'en' ? 'selected' : ''}>English</option>
                        </select>
                    </div>
                </div>

                <div class="settings-section" style="margin-top:24px;">
                    <h3 style="font-size:16px;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border-light);">搜索</h3>

                    <div style="margin-bottom:16px;">
                        <label style="display:block;margin-bottom:6px;font-size:14px;">默认搜索模式</label>
                        <select data-field="searchMode" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);">
                            <option value="semantic" ${s.searchMode === 'semantic' ? 'selected' : ''}>语义搜索</option>
                            <option value="keyword" ${s.searchMode === 'keyword' ? 'selected' : ''}>关键词搜索</option>
                            <option value="hybrid" ${s.searchMode === 'hybrid' ? 'selected' : ''}>混合搜索</option>
                        </select>
                    </div>

                    <div style="margin-bottom:16px;">
                        <label style="display:block;margin-bottom:6px;font-size:14px;">每页结果数</label>
                        <select data-field="searchResultsPerPage" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);">
                            <option value="10" ${s.searchResultsPerPage === 10 ? 'selected' : ''}>10</option>
                            <option value="20" ${s.searchResultsPerPage === 20 ? 'selected' : ''}>20</option>
                            <option value="30" ${s.searchResultsPerPage === 30 ? 'selected' : ''}>30</option>
                            <option value="50" ${s.searchResultsPerPage === 50 ? 'selected' : ''}>50</option>
                        </select>
                    </div>

                    <div style="margin-bottom:16px;">
                        <label style="display:block;margin-bottom:6px;font-size:14px;">默认领域</label>
                        <select data-field="defaultDomain" style="width:100%;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-primary);color:var(--text-primary);">
                            <option value="" ${!s.defaultDomain ? 'selected' : ''}>全部领域</option>
                            <option value="qigong" ${s.defaultDomain === 'qigong' ? 'selected' : ''}>气功</option>
                            <option value="tcm" ${s.defaultDomain === 'tcm' ? 'selected' : ''}>中医</option>
                            <option value="confucianism" ${s.defaultDomain === 'confucianism' ? 'selected' : ''}>儒家</option>
                            <option value="buddhism" ${s.defaultDomain === 'buddhism' ? 'selected' : ''}>佛学</option>
                            <option value="taoism" ${s.defaultDomain === 'taoism' ? 'selected' : ''}>道家</option>
                            <option value="martial_arts" ${s.defaultDomain === 'martial_arts' ? 'selected' : ''}>武术</option>
                        </select>
                    </div>
                </div>

                <div class="settings-section" style="margin-top:24px;">
                    <h3 style="font-size:16px;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border-light);">数据与隐私</h3>

                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                        <div>
                            <div style="font-size:14px;">启用使用分析</div>
                            <div style="font-size:12px;color:var(--text-secondary);">帮助我们改进系统体验</div>
                        </div>
                        <label style="position:relative;display:inline-block;width:44px;height:24px;">
                            <input type="checkbox" data-field="enableAnalytics" ${s.enableAnalytics ? 'checked' : ''} style="opacity:0;width:0;height:0;">
                            <span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:${s.enableAnalytics ? 'var(--primary)' : 'var(--border-color)'};border-radius:12px;transition:0.3s;">
                                <span style="position:absolute;content:'';height:18px;width:18px;left:${s.enableAnalytics ? '23px' : '3px'};bottom:3px;background:white;border-radius:50%;transition:0.3s;"></span>
                            </span>
                        </label>
                    </div>

                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                        <div>
                            <div style="font-size:14px;">启用通知</div>
                            <div style="font-size:12px;color:var(--text-secondary);">接收系统通知和更新提醒</div>
                        </div>
                        <label style="position:relative;display:inline-block;width:44px;height:24px;">
                            <input type="checkbox" data-field="enableNotifications" ${s.enableNotifications ? 'checked' : ''} style="opacity:0;width:0;height:0;">
                            <span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:${s.enableNotifications ? 'var(--primary)' : 'var(--border-color)'};border-radius:12px;transition:0.3s;">
                                <span style="position:absolute;content:'';height:18px;width:18px;left:${s.enableNotifications ? '23px' : '3px'};bottom:3px;background:white;border-radius:50%;transition:0.3s;"></span>
                            </span>
                        </label>
                    </div>

                    <div style="margin-bottom:16px;">
                        <label style="display:block;margin-bottom:6px;font-size:14px;">历史记录上限</label>
                        <input type="number" data-field="maxHistoryItems" value="${s.maxHistoryItems}" min="10" max="500" step="10" style="width:100px;padding:8px 12px;border:1px solid var(--border-color);border-radius:6px;">
                    </div>
                </div>

                <div style="margin-top:32px;padding-top:16px;border-top:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-size:13px;color:var(--text-tertiary);">灵知系统 v2.0</div>
                    <button class="btn btn-secondary" id="settingsResetBtn">恢复默认设置</button>
                </div>
            </div>
        `;
    }
};

window.initSettings = function() {
    SettingsModule.init();
};
