// 灵知系统 - 应用主入口
let appState = {
    theme: localStorage.getItem(Config.theme.storageKey) || Config.theme.default,
    sessionId: localStorage.getItem(Config.storage.sessionId) || null,
    sidebarCollapsed: false
};

// 应用初始化
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initSidebar();
    initRouter();
    initGlobalSearch();
    initKeyboardShortcuts();
    initMobileMenu();
    initNotifications();
    loadSystemStats();
});

// 主题管理
function initTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const icon = themeToggle.querySelector('.icon');

    // 应用保存的主题
    applyTheme(appState.theme);

    themeToggle.addEventListener('click', () => {
        appState.theme = appState.theme === 'light' ? 'dark' : 'light';
        applyTheme(appState.theme);
        localStorage.setItem(Config.theme.storageKey, appState.theme);
    });

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        icon.textContent = theme === 'light' ? '🌙' : '☀️';
    }
}

// 侧边栏管理
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const toggleIcon = sidebarToggle.querySelector('.icon');

    sidebarToggle.addEventListener('click', () => {
        appState.sidebarCollapsed = !appState.sidebarCollapsed;
        sidebar.classList.toggle('collapsed', appState.sidebarCollapsed);
        toggleIcon.textContent = appState.sidebarCollapsed ? '»' : '«';
    });
}

// 路由初始化
function initRouter() {
    Router.init();
}

// 全局搜索
function initGlobalSearch() {
    const input = document.getElementById('globalSearchInput');
    const btn = document.querySelector('.global-search .search-btn');

    const doSearch = () => {
        const query = input.value.trim();
        if (query) {
            Router.navigate('search');
            setTimeout(() => {
                const mainInput = document.getElementById('mainSearchInput');
                if (mainInput) {
                    mainInput.value = query;
                    mainInput.dispatchEvent(new Event('input'));
                    document.getElementById('mainSearchBtn').click();
                }
            }, 100);
        }
    };

    btn.addEventListener('click', doSearch);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });
}

// 键盘快捷键
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl+K - 全局搜索
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            document.getElementById('globalSearchInput').focus();
        }

        // Ctrl+B - 切换侧边栏
        if (e.ctrlKey && e.key === 'b') {
            e.preventDefault();
            document.getElementById('sidebarToggle').click();
        }

        // Ctrl+D - 切换主题
        if (e.ctrlKey && e.key === 'd') {
            e.preventDefault();
            document.getElementById('themeToggle').click();
        }

        // Escape - 关闭模态框
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });
}

// 移动端菜单
function initMobileMenu() {
    const toggle = document.getElementById('mobileMenuToggle');
    const sidebar = document.getElementById('sidebar');

    toggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    // 点击外部关闭侧边栏
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 &&
            sidebar.classList.contains('open') &&
            !sidebar.contains(e.target) &&
            !toggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
}

// 通知系统
function initNotifications() {
    const btn = document.getElementById('notificationBtn');
    let unreadCount = 3;

    btn.addEventListener('click', () => {
        showNotificationPanel();
    });
}

function showNotificationPanel() {
    const modal = document.getElementById('modalContainer');
    const content = document.getElementById('modalContent');

    content.innerHTML = `
        <div class="notification-panel">
            <button class="modal-close" onclick="closeAllModals()">×</button>
            <h3>通知</h3>
            <div class="notification-list">
                <div class="notification-item unread">
                    <span class="notification-icon">📚</span>
                    <div class="notification-content">
                        <h4>数据更新</h4>
                        <p>古籍数据已更新，新增 100 条记录</p>
                        <span class="notification-time">5分钟前</span>
                    </div>
                </div>
                <div class="notification-item unread">
                    <span class="notification-icon">🔧</span>
                    <div class="notification-content">
                        <h4>系统维护</h4>
                        <p>系统将于今晚进行维护升级</p>
                        <span class="notification-time">1小时前</span>
                    </div>
                </div>
                <div class="notification-item">
                    <span class="notification-icon">✅</span>
                    <div class="notification-content">
                        <h4>导入完成</h4>
                        <p>音频转写任务已完成</p>
                        <span class="notification-time">昨天</span>
                    </div>
                </div>
            </div>
        </div>
    `;

    modal.classList.add('active');
}

// 关闭所有模态框
function closeAllModals() {
    document.getElementById('modalContainer').classList.remove('active');
}

// 加载系统统计
async function loadSystemStats() {
    try {
        const stats = await API.system.getStats();
        console.log('系统统计:', stats);
    } catch (error) {
        console.error('加载系统统计失败:', error);
    }
}

// 通用工具函数
const Utils = {
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    formatDate(date) {
        return new Date(date).toLocaleString('zh-CN');
    },

    formatNumber(num) {
        return new Intl.NumberFormat('zh-CN').format(num);
    },

    truncate(text, length = 100) {
        return text.length > length ? text.substring(0, length) + '...' : text;
    },

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
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
    }
};

// 全局可访问
window.closeAllModals = closeAllModals;
window.Utils = Utils;
