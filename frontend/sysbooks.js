import { API_BASE, escapeHtml } from './core.js';

let sysbooksStatsCache = null;

function initSysbooks() {
    const searchInput = document.getElementById('sysbooks-search-input');
    const searchBtn = document.getElementById('sysbooks-search-btn');
    const domainFilter = document.getElementById('sysbooks-domain-filter');
    const extFilter = document.getElementById('sysbooks-extension-filter');

    const doSearch = () => {
        searchSysbooks(searchInput.value.trim(), domainFilter.value, extFilter.value);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });
    domainFilter.addEventListener('change', doSearch);
    extFilter.addEventListener('change', doSearch);

    loadSysbooksStats();
}

async function loadSysbooksStats() {
    const statsDiv = document.getElementById('sysbooks-stats');
    try {
        const resp = await fetch(`${API_BASE}/sysbooks/stats`);
        const json = await resp.json();
        sysbooksStatsCache = json.data;
        const d = json.data;

        const total = d.total >= 1e4
            ? (d.total / 1e4).toFixed(0) + '万'
            : d.total;
        statsDiv.innerHTML = `<span class="stat-badge">📖 ${total} 条书目</span>`;

        const domainFilter = document.getElementById('sysbooks-domain-filter');
        domainFilter.innerHTML = '<option value="">全部领域</option>' +
            d.by_domain.slice(0, 30).map(r =>
                `<option value="${escapeHtml(r.domain || '')}">${escapeHtml(r.domain || '未知')} (${r.count.toLocaleString()})</option>`
            ).join('');

        const extFilter = document.getElementById('sysbooks-extension-filter');
        extFilter.innerHTML = '<option value="">全部格式</option>' +
            d.by_extension.slice(0, 15).map(r =>
                `<option value="${escapeHtml(r.extension || '')}">.${escapeHtml(r.extension || '?')} (${r.count.toLocaleString()})</option>`
            ).join('');
    } catch (e) {
        statsDiv.innerHTML = '<span class="stat-badge error">统计加载失败</span>';
    }
}

async function searchSysbooks(query = '', domain = '', extension = '', page = 1) {
    const resultsDiv = document.getElementById('sysbooks-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';
    try {
        const params = new URLSearchParams({ page, size: 30 });
        if (query) params.set('q', query);
        if (domain) params.set('domain', domain);
        if (extension) params.set('extension', extension);

        const resp = await fetch(`${API_BASE}/sysbooks/search?${params}`);
        const json = await resp.json();
        const d = json.data;

        if (!d.results.length) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📖</div>
                    <p>没有找到相关书目</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">找到 ${d.total.toLocaleString()} 条结果 (第${d.page}页)</p>
            <div class="sysbooks-list">
                ${d.results.map(r => `
                    <div class="sysbook-item" data-book-id="${r.id}">
                        <div class="sysbook-name">${escapeHtml(r.filename || r.path || '未知')}</div>
                        <div class="sysbook-meta">
                            ${r.domain ? `<span class="tag">${escapeHtml(r.domain)}</span>` : ''}
                            ${r.extension ? `<span class="tag">.${escapeHtml(r.extension)}</span>` : ''}
                            ${r.author ? `<span>👤 ${escapeHtml(r.author)}</span>` : ''}
                            ${r.year ? `<span>${r.year}</span>` : ''}
                            ${r.category ? `<span>${escapeHtml(r.category)}</span>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        resultsDiv.querySelectorAll('.sysbook-item').forEach(el => {
            el.addEventListener('click', () => {
                showSysbookDetail(parseInt(el.dataset.bookId));
            });
        });
    } catch (e) {
        resultsDiv.innerHTML = `<div class="error-state"><p>搜索失败：${escapeHtml(e.message)}</p></div>`;
    }
}

async function showSysbookDetail(bookId) {
    const modal = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载中...</p></div>';
    modal.classList.add('active');

    try {
        const resp = await fetch(`${API_BASE}/sysbooks/${bookId}`);
        const json = await resp.json();
        const d = json.data;

        const fields = [
            ['文件名', d.filename],
            ['路径', d.path],
            ['领域', d.domain],
            ['子分类', d.subcategory],
            ['作者', d.author],
            ['年份', d.year],
            ['分类', d.category],
            ['出版社', d.publisher],
            ['格式', d.extension],
            ['大小', d.size],
            ['来源', d.source],
        ].filter(([, v]) => v);

        content.innerHTML = `
            <button class="modal-close" onclick="document.getElementById('modal-overlay').classList.remove('active')">×</button>
            <h2>${escapeHtml(d.filename || '书目详情')}</h2>
            <div class="sysbook-detail-fields">
                ${fields.map(([label, val]) => `
                    <div class="detail-row">
                        <span class="detail-label">${label}</span>
                        <span class="detail-value">${escapeHtml(String(val))}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        content.innerHTML = `<div class="error-state"><p>加载失败：${escapeHtml(e.message)}</p></div>`;
    }
}

export { initSysbooks, loadSysbooksStats };
