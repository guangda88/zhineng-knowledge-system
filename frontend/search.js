import { API_BASE, state, escapeHtml } from './core.js';
import { submitFeedback } from './feedback.js';

let searchPage = 1;
let searchQuery = '';
let searchCategory = '';
let searchHasMore = false;

function initSearch() {
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const categoryFilter = document.getElementById('category-filter');

    const doSearch = () => {
        const query = searchInput.value.trim();
        if (!query) return;

        searchQuery = query;
        searchCategory = categoryFilter.value;
        searchPage = 1;
        performSearch(searchQuery, searchCategory, searchPage, true);
    };

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') doSearch();
    });
    categoryFilter.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch();
    });
}

async function performSearch(query, category = '', page = 1, replace = true) {
    const resultsDiv = document.getElementById('search-results');
    if (replace) {
        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>搜索中...</p></div>';
    }

    try {
        const params = new URLSearchParams({ q: query, limit: 20, offset: (page - 1) * 20 });
        if (category) params.append('category', category);

        const response = await fetch(`${API_BASE}/search?${params}`);
        const data = await response.json();

        if (data.results.length === 0 && page === 1) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>没有找到相关结果</p>
                    <p>试试搜索：气功、八段锦、中医、儒家</p>
                </div>
            `;
            return;
        }

        searchHasMore = data.results.length >= 20;

        const newHtml = `
            ${page === 1 ? `<p class="result-meta">找到 ${data.total} 条结果</p>` : ''}
            ${data.results.map(item => createResultItem(item, query)).join('')}
            ${searchHasMore ? '<button id="load-more-search" class="btn btn-secondary" style="display:block;margin:16px auto;padding:10px 24px;">加载更多</button>' : ''}
        `;

        if (replace) {
            resultsDiv.innerHTML = newHtml;
        } else {
            const loadMoreBtn = resultsDiv.querySelector('#load-more-search');
            if (loadMoreBtn) loadMoreBtn.remove();
            resultsDiv.insertAdjacentHTML('beforeend', newHtml);
        }

        const loadMore = resultsDiv.querySelector('#load-more-search');
        if (loadMore) {
            loadMore.addEventListener('click', () => {
                searchPage++;
                loadMore.textContent = '加载中...';
                loadMore.disabled = true;
                performSearch(searchQuery, searchCategory, searchPage, false);
            });
        }
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
