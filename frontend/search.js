import { API_BASE, state, escapeHtml } from './core.js';
import { submitFeedback } from './feedback.js';

function initSearch() {
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const categoryFilter = document.getElementById('category-filter');

    const doSearch = () => {
        const query = searchInput.value.trim();
        if (!query) return;

        const category = categoryFilter.value;
        performSearch(query, category);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });
    categoryFilter.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch();
    });
}

async function performSearch(query, category = '') {
    const resultsDiv = document.getElementById('search-results');
    resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';

    try {
        const params = new URLSearchParams({ q: query });
        if (category) params.append('category', category);

        const response = await fetch(`${API_BASE}/search?${params}`);
        const data = await response.json();

        if (data.results.length === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>没有找到相关结果</p>
                    <p>试试搜索：气功、八段锦、中医、儒家</p>
                </div>
            `;
            return;
        }

        resultsDiv.innerHTML = `
            <p class="result-meta">找到 ${data.total} 条结果</p>
            ${data.results.map(item => createResultItem(item, query)).join('')}
        `;
    } catch (error) {
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>搜索失败：${error.message}</p>
            </div>
        `;
    }
}

function createResultItem(item, query) {
    const content = item.content.length > 200
        ? item.content.substring(0, 200) + '...'
        : item.content;

    const safeQuery = escapeHtml(query || '');
    return `
        <div class="result-item" data-doc-id="${item.id}">
            <h3 class="result-title">${escapeHtml(item.title)}</h3>
            <p class="result-content">${escapeHtml(content)}</p>
            <div class="result-meta">
                <span class="category-tag ${item.category}">${item.category}</span>
                <span>ID: ${item.id}</span>
                <div class="feedback-buttons">
                    <button class="feedback-btn helpful-btn" onclick="submitFeedback(event, ${item.id}, 'helpful', '${safeQuery}')" title="有帮助">
                        👍
                    </button>
                    <button class="feedback-btn not-helpful-btn" onclick="submitFeedback(event, ${item.id}, 'not_helpful', '${safeQuery}')" title="没帮助">
                        👎
                    </button>
                </div>
            </div>
        </div>
    `;
}

export { initSearch, performSearch };
