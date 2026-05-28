// 灵知系统 - 数据分析模块
const AnalyticsModule = {
    initialized: false,
    dashboardData: null,

    init() {
        if (this.initialized) return;
        this.initialized = true;
        this.bindEvents();
        this.loadDashboard();
    },

    bindEvents() {
        const refreshBtn = document.getElementById('analyticsRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadDashboard());
        }

        const periodSelect = document.getElementById('analyticsPeriod');
        if (periodSelect) {
            periodSelect.addEventListener('change', () => this.loadDashboard());
        }
    },

    async loadDashboard() {
        const container = document.getElementById('analyticsContent');
        if (!container) return;

        container.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载分析数据...</p></div>';

        try {
            const data = await API.analytics.dashboard();
            this.dashboardData = data.data;
            this.renderDashboard();
        } catch (error) {
            container.innerHTML = `
                <div class="results-placeholder">
                    <div class="placeholder-icon">📊</div>
                    <h3>加载失败</h3>
                    <p>${Utils.escapeHtml(error.message)}</p>
                    <button class="btn btn-primary mt-md" onclick="AnalyticsModule.loadDashboard()">重试</button>
                </div>
            `;
        }
    },

    renderDashboard() {
        const container = document.getElementById('analyticsContent');
        if (!container || !this.dashboardData) return;

        const d = this.dashboardData;
        const overview = d.overview || d.summary || d;
        const searchStats = d.search || d.search_stats || {};
        const feedbackStats = d.feedback || d.feedback_stats || {};
        const usageStats = d.usage || d.usage_stats || {};

        const totalSearches = overview.total_searches || searchStats.total || 0;
        const totalQueries = overview.total_queries || searchStats.queries || 0;
        const avgLatency = overview.avg_latency || searchStats.avg_latency || 0;
        const feedbackPositive = overview.positive_feedback || feedbackStats.positive || 0;
        const feedbackNegative = overview.negative_feedback || feedbackStats.negative || 0;
        const activeUsers = overview.active_users || usageStats.active_users || 0;
        const documentsServed = overview.documents_served || searchStats.documents_served || 0;

        const feedbackTotal = feedbackPositive + feedbackNegative;
        const satisfactionRate = feedbackTotal > 0 ? ((feedbackPositive / feedbackTotal) * 100).toFixed(1) : '--';

        container.innerHTML = `
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:24px;">
                ${this.createStatCard('🔍', '总搜索次数', Utils.formatNumber(totalSearches))}
                ${this.createStatCard('❓', '总查询数', Utils.formatNumber(totalQueries))}
                ${this.createStatCard('⏱️', '平均延迟', avgLatency ? avgLatency.toFixed(0) + 'ms' : '--')}
                ${this.createStatCard('📄', '文档服务数', Utils.formatNumber(documentsServed))}
                ${this.createStatCard('👍', '正面反馈', Utils.formatNumber(feedbackPositive))}
                ${this.createStatCard('👎', '负面反馈', Utils.formatNumber(feedbackNegative))}
                ${this.createStatCard('😊', '满意度', satisfactionRate + '%')}
                ${this.createStatCard('👥', '活跃用户', Utils.formatNumber(activeUsers))}
            </div>

            ${d.top_queries || d.popular_queries ? this.renderTopQueries(d.top_queries || d.popular_queries) : ''}
            ${d.domain_distribution || d.by_domain ? this.renderDomainDistribution(d.domain_distribution || d.by_domain) : ''}
            ${d.daily_trend || d.trends ? this.renderTrend(d.daily_trend || d.trends) : ''}
        `;
    },

    createStatCard(icon, label, value) {
        return `
            <div style="background:var(--bg-primary);border:1px solid var(--border-color);border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:28px;margin-bottom:8px;">${icon}</div>
                <div style="font-size:24px;font-weight:600;">${value}</div>
                <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;">${label}</div>
            </div>
        `;
    },

    renderTopQueries(queries) {
        if (!queries || !queries.length) return '';

        return `
            <div style="background:var(--bg-primary);border:1px solid var(--border-color);border-radius:12px;padding:16px;margin-bottom:16px;">
                <h3 style="font-size:16px;margin-bottom:12px;">🔥 热门查询</h3>
                <div style="display:grid;gap:6px;">
                    ${queries.slice(0, 15).map((q, i) => `
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border-radius:4px;${i % 2 === 0 ? 'background:var(--bg-secondary);' : ''}">
                            <span style="font-size:14px;">
                                <span style="color:var(--text-tertiary);margin-right:8px;">${i + 1}.</span>
                                ${Utils.escapeHtml(q.query || q.text || q.keyword || '')}
                            </span>
                            <span style="font-size:13px;color:var(--text-secondary);">${Utils.formatNumber(q.count || q.hits || 0)} 次</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    },

    renderDomainDistribution(domains) {
        if (!domains || !domains.length) return '';

        const maxCount = Math.max(...domains.map(d => d.count || 0), 1);

        return `
            <div style="background:var(--bg-primary);border:1px solid var(--border-color);border-radius:12px;padding:16px;margin-bottom:16px;">
                <h3 style="font-size:16px;margin-bottom:12px;">📚 领域分布</h3>
                <div style="display:grid;gap:8px;">
                    ${domains.slice(0, 10).map(d => {
                        const count = d.count || 0;
                        const pct = (count / maxCount * 100).toFixed(0);
                        return `
                            <div style="display:flex;align-items:center;gap:12px;">
                                <span style="min-width:80px;font-size:14px;text-align:right;">${Utils.escapeHtml(d.domain || d.name || d.key || '')}</span>
                                <div style="flex:1;height:20px;background:var(--bg-secondary);border-radius:4px;overflow:hidden;">
                                    <div style="height:100%;width:${pct}%;background:var(--primary);border-radius:4px;min-width:2px;"></div>
                                </div>
                                <span style="min-width:50px;font-size:13px;color:var(--text-secondary);">${Utils.formatNumber(count)}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    },

    renderTrend(trends) {
        if (!trends || !trends.length) return '';

        return `
            <div style="background:var(--bg-primary);border:1px solid var(--border-color);border-radius:12px;padding:16px;">
                <h3 style="font-size:16px;margin-bottom:12px;">📈 使用趋势</h3>
                <div style="display:flex;align-items:flex-end;gap:2px;height:120px;">
                    ${trends.slice(-30).map(t => {
                        const count = t.count || t.value || 0;
                        const maxVal = Math.max(...trends.slice(-30).map(x => x.count || x.value || 0), 1);
                        const height = Math.max((count / maxVal * 100).toFixed(0), 2);
                        return `
                            <div title="${t.date || t.label || ''}: ${count}" style="flex:1;height:${height}%;background:var(--primary);border-radius:2px 2px 0 0;opacity:0.7;cursor:pointer;min-width:4px;"></div>
                        `;
                    }).join('')}
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:4px;">
                    <span style="font-size:11px;color:var(--text-tertiary);">${trends[0]?.date || ''}</span>
                    <span style="font-size:11px;color:var(--text-tertiary);">${trends[trends.length - 1]?.date || ''}</span>
                </div>
            </div>
        `;
    }
};

window.initAnalytics = function() {
    AnalyticsModule.init();
};
