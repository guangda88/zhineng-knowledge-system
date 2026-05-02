const API_BASE = '/api/v1';

const state = {
    sessionId: null,
    interrupted: false
};

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function saveState() {
    try {
        localStorage.setItem('zhineng_session', JSON.stringify({
            sessionId: state.sessionId,
            interrupted: state.interrupted,
            savedAt: Date.now()
        }));
    } catch (e) {
        // localStorage may be unavailable
    }
}

function loadState() {
    try {
        const raw = localStorage.getItem('zhineng_session');
        if (raw) {
            const saved = JSON.parse(raw);
            if (saved.sessionId) {
                state.sessionId = saved.sessionId;
                state.interrupted = saved.interrupted || false;
                return true;
            }
        }
    } catch (e) {
        // ignore
    }
    return false;
}

function clearState() {
    state.sessionId = null;
    state.interrupted = false;
    try { localStorage.removeItem('zhineng_session'); } catch (e) {}
}

export { API_BASE, state, escapeHtml, saveState, loadState, clearState };
