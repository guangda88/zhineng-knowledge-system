const API_BASE = '/api/v1';

const state = {
    sessionId: null
};

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

export { API_BASE, state, escapeHtml };
