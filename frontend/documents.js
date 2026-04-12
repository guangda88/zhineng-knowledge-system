import { API_BASE, escapeHtml } from './core.js';

function initDocuments() {
    const refreshBtn = document.getElementById('refresh-docs');
    const categoryFilter = document.getElementById('doc-category-filter');

    const loadDocs = () => {
        const category = categoryFilter.value;
        loadDocuments(category);
    };

    refreshBtn.addEventListener('click', loadDocs);
    categoryFilter.addEventListener('change', loadDocs);
}

async function loadDocuments(category = '') {
    const listDiv = document.getElementById('documents-list');
    listDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>加载中...</p></div>';

    try {
        const params = new URLSearchParams();
        if (category) params.append('category', category);
        params.append('limit', '50');

        const response = await fetch(`${API_BASE}/documents?${params}`);
        const data = await response.json();

        if (data.documents.length === 0) {
            listDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📄</div>
                    <p>暂无文档</p>
                </div>
            `;
            return;
        }

        listDiv.innerHTML = `
            <p class="result-meta">共 ${data.total} 篇文档</p>
            ${data.documents.map(item => createDocItem(item)).join('')}
        `;
    } catch (error) {
        listDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <p>加载失败：${error.message}</p>
            </div>
        `;
    }
}

function createDocItem(item) {
    const tags = item.tags && Array.isArray(item.tags)
        ? item.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join(' ')
        : '';

    return `
        <div class="doc-item">
            <h3 class="doc-title">${escapeHtml(item.title)}</h3>
            <div class="doc-meta">
                <span class="category-tag ${item.category}">${item.category}</span>
                ${tags}
                <span>ID: ${item.id}</span>
            </div>
        </div>
    `;
}

export { initDocuments, loadDocuments };
