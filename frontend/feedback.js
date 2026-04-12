import { API_BASE, state } from './core.js';

async function submitFeedback(evt, docId, feedbackType, query) {
    const btn = evt.target.closest('.feedback-btn');
    if (btn.classList.contains('submitted')) return;

    const container = btn.closest('.feedback-buttons');
    container.querySelectorAll('.feedback-btn').forEach(b => b.classList.add('submitted'));
    btn.style.opacity = '1';
    btn.style.fontWeight = 'bold';

    try {
        await fetch(`${API_BASE}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                doc_id: docId,
                feedback_type: feedbackType,
                session_id: state.sessionId
            })
        });
    } catch (error) {
        container.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('submitted'));
        btn.style.opacity = '';
        btn.style.fontWeight = '';
        console.error('反馈提交失败:', error);
    }
}

async function submitChatFeedback(evt, feedbackType, query) {
    const container = evt.target.closest('.answer-feedback');
    if (container.classList.contains('submitted')) return;
    container.classList.add('submitted');

    container.querySelectorAll('.feedback-btn').forEach(b => {
        b.disabled = true;
        b.style.opacity = '0.5';
    });
    evt.target.style.opacity = '1';
    evt.target.style.fontWeight = 'bold';
    const label = container.querySelector('.feedback-label');
    if (label) label.textContent = '感谢您的反馈！';

    try {
        await fetch(`${API_BASE}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                feedback_type: feedbackType,
                session_id: state.sessionId
            })
        });
    } catch (error) {
        container.classList.remove('submitted');
        console.error('反馈提交失败:', error);
    }
}

export { submitFeedback, submitChatFeedback, submitAIAnswerFeedback };

async function submitAIAnswerFeedback(evt, feedbackType, query, aiAnswer, evidence) {
    const container = evt.target.closest('.ai-feedback-section');
    if (container.classList.contains('submitted')) return;
    container.classList.add('submitted');

    container.querySelectorAll('.feedback-btn').forEach(b => {
        b.disabled = true;
        b.style.opacity = '0.5';
    });
    evt.target.style.opacity = '1';
    evt.target.style.fontWeight = 'bold';
    const label = container.querySelector('.feedback-label');
    if (label) label.textContent = '感谢您的反馈！已用于改进AI准确性';

    try {
        await fetch(`${API_BASE}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                feedback_type: feedbackType,
                comment: `AI回答反馈\n回答：${aiAnswer.substring(0, 200)}...\n证据：${JSON.stringify(evidence)}`,
                session_id: state.sessionId,
                metadata: {
                    source: 'ai_answer',
                    answer_preview: aiAnswer.substring(0, 500),
                    evidence_count: evidence?.length || 0
                }
            })
        });
    } catch (error) {
        container.classList.remove('submitted');
        console.error('AI回答反馈提交失败:', error);
    }
}
