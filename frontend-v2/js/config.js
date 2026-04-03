// 灵知系统 - 配置文件
const Config = {
    // API 配置
    api: {
        baseURL: '/api/v1',
        apiV2: '/api/v2',
        timeout: 30000,
        retryAttempts: 3,
        retryDelay: 1000
    },

    // 分页配置
    pagination: {
        defaultPageSize: 20,
        pageSizeOptions: [10, 20, 50, 100]
    },

    // 路由配置
    routes: {
        default: 'search',
        modules: [
            'search',
            'library',
            'ai-assistant',
            'reasoning',
            'guoxue',
            'guji',
            'sysbooks',
            'annotation',
            'audio',
            'import',
            'analytics',
            'settings'
        ]
    },

    // 主题配置
    theme: {
        default: 'light',
        storageKey: 'lingzhi-theme'
    },

    // 状态配置
    status: {
        checkInterval: 60000,
        apiHealthCheck: '/api/v1/health'
    },

    // 键盘快捷键
    shortcuts: {
        'globalSearch': 'Ctrl+K',
        'toggleSidebar': 'Ctrl+B',
        'toggleTheme': 'Ctrl+D',
        'focusSearch': '/'
    },

    // 本地存储键
    storage: {
        sessionId: 'lingzhi-session-id',
        recentSearches: 'lingzhi-recent-searches',
        favorites: 'lingzhi-favorites'
    }
};

// 导出配置
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Config;
}
