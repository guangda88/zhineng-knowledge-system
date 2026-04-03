# 用户价值追踪与反馈系统 - 前端集成指南

**版本**: 1.0.0
**日期**: 2026-04-01

---

## 📋 概述

本系统用于追踪用户实际使用情况，收集满意度反馈，验证灵知系统的用户价值。

**核心理念**：
- ✅ 追踪实际使用（用户做了什么）
- ✅ 收集用户反馈（有用吗？）
- ✅ 验证用户价值（是否改善生命状态）
- ❌ 不监督用户练习
- ❌ 不生成复杂计划

---

## 🚀 快速开始

### 1. 初始化追踪

```javascript
// 在应用启动时初始化
class Analytics {
  constructor() {
    this.sessionId = this.getOrCreateSessionId();
    this.userId = this.getUserId(); // JWT token中的user_id
    this.apiBase = '/api/v1/analytics';
  }

  getOrCreateSessionId() {
    let sessionId = localStorage.getItem('lingzhi_session_id');
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      localStorage.setItem('lingzhi_session_id', sessionId);
    }
    return sessionId;
  }

  getUserId() {
    // 从JWT token中解析user_id
    const token = localStorage.getItem('access_token');
    if (token) {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.sub;
    }
    return null;
  }

  async track(actionType, content, metadata = {}) {
    try {
      const response = await fetch(`${this.apiBase}/track`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': this.sessionId,
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          action_type: actionType,
          content: content,
          metadata: {
            ...metadata,
            timestamp: new Date().toISOString()
          }
        })
      });

      if (!response.ok) {
        console.error('Analytics track failed:', await response.text());
      }
    } catch (error) {
      console.error('Analytics track error:', error);
    }
  }
}

// 全局实例
const analytics = new Analytics();
```

---

## 📊 使用场景

### 场景1: 搜索追踪

```javascript
// 当用户执行搜索时
async function performSearch(query) {
  // 显示搜索中
  showLoading();

  const startTime = Date.now();

  try {
    const results = await fetch('/api/v1/search', {
      method: 'POST',
      body: JSON.stringify({ query: query })
    }).then(r => r.json());

    const responseTime = Date.now() - startTime;

    // 追踪搜索行为
    await analytics.track('search', query, {
      result_count: results.results?.length || 0,
      response_time_ms: responseTime,
      has_results: results.results?.length > 0
    });

    // 显示结果
    displayResults(results);

    // 显示反馈按钮
    showFeedbackButton('search', query);

  } catch (error) {
    console.error('Search failed:', error);
    showError('搜索失败，请重试');
  }
}
```

### 场景2: 问答追踪

```javascript
// 当用户提问时
async function askQuestion(question) {
  showLoading();

  const startTime = Date.now();

  try {
    const answer = await fetch('/api/v1/ask', {
      method: 'POST',
      body: JSON.stringify({
        question: question,
        use_rag: true
      })
    }).then(r => r.json());

    const responseTime = Date.now() - startTime;

    // 追踪问答行为
    await analytics.track('ask', question, {
      response_time_ms: responseTime,
      answer_length: answer.answer?.length || 0,
      sources_count: answer.sources?.length || 0,
      has_answer: !!answer.answer
    });

    displayAnswer(answer);

    // 显示反馈按钮
    showFeedbackButton('ask', question);

  } catch (error) {
    console.error('Ask failed:', error);
    showError('提问失败，请重试');
  }
}
```

### 场景3: 音频播放追踪

```javascript
// 当用户播放音频时
async function playAudio(audioId, audioTitle) {
  const audio = new Audio(`/api/v1/audio/${audioId}/stream`);

  audio.play();

  // 追踪音频播放
  await analytics.track('audio_play', audioId, {
    audio_title: audioTitle,
    duration: audio.duration
  });

  // 监听播放完成
  audio.addEventListener('ended', async () => {
    await analytics.track('audio_complete', audioId, {
      audio_title: audioTitle,
      completed: true
    });

    // 播放完成后显示反馈
    showFeedbackModal('audio', audioId, audioTitle);
  });
}
```

### 场景4: 书籍阅读追踪

```javascript
// 当用户打开书籍章节时
async function openChapter(bookId, chapterId, chapterTitle) {
  displayChapter(bookId, chapterId);

  // 追踪阅读行为
  await analytics.track('book_read', chapterId, {
    book_id: bookId,
    chapter_title: chapterTitle
  });
}
```

---

## 👍 满意度反馈

### 即时反馈（搜索/问答后）

```javascript
// 显示反馈按钮
function showFeedbackButton(feature, contentId) {
  const feedbackHtml = `
    <div class="feedback-prompt" style="margin-top: 1rem; padding: 1rem; background: #f5f5f5; border-radius: 8px;">
      <p style="margin: 0 0 0.5rem 0; font-size: 0.9rem;">这个结果对您有帮助吗？</p>
      <div class="feedback-buttons">
        <button onclick="submitFeedback('good', '${feature}', '${contentId}')" class="btn-feedback-good">
          👍 好
        </button>
        <button onclick="submitFeedback('neutral', '${feature}', '${contentId}')" class="btn-feedback-neutral">
          😐 中
        </button>
        <button onclick="submitFeedback('poor', '${feature}', '${contentId}')" class="btn-feedback-poor">
          👎 差
        </button>
      </div>
    </div>
  `;

  // 插入到结果下方
  document.querySelector('.results-container').insertAdjacentHTML('beforeend', feedbackHtml);
}

// 提交反馈
async function submitFeedback(rating, feature, contentId) {
  try {
    const response = await fetch('/api/v1/analytics/feedback/instant', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': analytics.sessionId
      },
      body: JSON.stringify({
        rating: rating,
        context: {
          feature: feature,
          content_id: contentId
        }
      })
    });

    if (response.ok) {
      // 显示感谢
      const feedbackPrompt = document.querySelector('.feedback-prompt');
      feedbackPrompt.innerHTML = '<p style="color: green;">✓ 感谢您的反馈！</p>';

      // 如果是差评，询问详细意见
      if (rating === 'poor') {
        setTimeout(() => {
          showDetailedFeedbackForm();
        }, 1000);
      }
    }
  } catch (error) {
    console.error('Feedback submission failed:', error);
  }
}

// 差评详细反馈表单
function showDetailedFeedbackForm() {
  const modalHtml = `
    <div class="modal" style="display: block;">
      <div class="modal-content">
        <h3>请告诉我们如何改进</h3>
        <textarea id="feedback-comment" rows="4" placeholder="请详细描述问题或建议..."></textarea>
        <button onclick="submitDetailedFeedback()">提交</button>
        <button onclick="closeModal()">取消</button>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function submitDetailedFeedback() {
  const comment = document.getElementById('feedback-comment').value;

  if (!comment || comment.trim().length < 10) {
    alert('请至少输入10个字的建议');
    return;
  }

  try {
    const response = await fetch('/api/v1/analytics/feedback/instant', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': analytics.sessionId
      },
      body: JSON.stringify({
        rating: 'poor',
        comment: comment
      })
    });

    if (response.ok) {
      closeModal();
      alert('感谢您的详细反馈！我们会认真改进。');
    }
  } catch (error) {
    console.error('Detailed feedback submission failed:', error);
  }
}
```

### 深度反馈（周度/月度）

```javascript
// 每周弹窗（仅在有使用记录时显示）
async function showWeeklyFeedback() {
  // 检查用户本周是否有活动
  const profile = await fetch('/api/v1/analytics/me').then(r => r.json());

  const lastFeedbackDate = profile.last_feedback_date;
  const today = new Date();
  const daysSinceLastFeedback = lastFeedbackDate
    ? Math.floor((today - new Date(lastFeedbackDate)) / (1000 * 60 * 60 * 24))
    : 999;

  // 如果7天内未反馈，且有使用记录
  if (daysSinceLastFeedback >= 7 && profile.total_sessions > 0) {
    const modalHtml = `
      <div class="modal weekly-feedback" style="display: block;">
        <div class="modal-content" style="max-width: 500px;">
          <h2>🙏 每周反馈</h2>
          <p>感谢您使用灵知系统！请告诉我们本周的使用体验：</p>

          <div class="rating-options">
            <label>
              <input type="radio" name="weekly-rating" value="good">
              👍 <strong>好</strong> - 系统对我的练习很有帮助
            </label>
            <label>
              <input type="radio" name="weekly-rating" value="neutral">
              😐 <strong>中</strong> - 有一些帮助，但还可以更好
            </label>
            <label>
              <input type="radio" name="weekly-rating" value="poor">
              👎 <strong>差</strong> - 没有达到预期
            </label>
          </div>

          <div style="margin-top: 1rem;">
            <label for="weekly-comment"><strong>您的意见和建议：</strong></label>
            <textarea id="weekly-comment" rows="4"
              placeholder="请告诉我们做得好的地方和需要改进的地方..."></textarea>
          </div>

          <div style="margin-top: 1rem; text-align: right;">
            <button onclick="closeWeeklyFeedback()">稍后再说</button>
            <button onclick="submitWeeklyFeedback()" class="btn-primary">提交反馈</button>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }
}

async function submitWeeklyFeedback() {
  const rating = document.querySelector('input[name="weekly-rating"]:checked')?.value;
  const comment = document.getElementById('weekly-comment').value;

  if (!rating) {
    alert('请选择评价');
    return;
  }

  if (!comment || comment.trim().length < 10) {
    alert('请至少输入10个字的建议');
    return;
  }

  try {
    const response = await fetch('/api/v1/analytics/feedback/extended', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': analytics.sessionId
      },
      body: JSON.stringify({
        feedback_type: 'weekly',
        rating: rating,
        comment: comment
      })
    });

    if (response.ok) {
      closeWeeklyFeedback();
      alert('✅ 感谢您的反馈！我们会认真对待每一条建议。');
    }
  } catch (error) {
    console.error('Weekly feedback submission failed:', error);
  }
}

function closeWeeklyFeedback() {
  document.querySelector('.weekly-feedback')?.remove();
}

// 页面加载时检查
window.addEventListener('load', () => {
  setTimeout(() => {
    showWeeklyFeedback();
  }, 3000); // 3秒后显示，不打扰用户
});
```

---

## 🔒 隐私设置

### 隐私模式切换

```javascript
// 隐私设置页面
async function updatePrivacySettings(privacyMode) {
  // privacyMode: 'anonymous' | 'standard' | 'full'

  try {
    const response = await fetch('/api/v1/analytics/me/preferences', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': analytics.sessionId
      },
      body: JSON.stringify({
        privacy_mode: privacyMode
      })
    });

    if (response.ok) {
      alert(`隐私模式已更新为：${privacyMode}`);

      // 显示隐私模式说明
      showPrivacyInfo(privacyMode);
    }
  } catch (error) {
    console.error('Privacy settings update failed:', error);
  }
}

function showPrivacyInfo(privacyMode) {
  const info = {
    'anonymous': `
      <strong>匿名模式</strong>
      <ul>
        <li>✓ 不记录搜索关键词和问题内容</li>
        <li>✓ 仅记录功能类型（搜索/问答/音频/书籍）</li>
        <li>✓ 90天后自动删除数据</li>
      </ul>
    `,
    'standard': `
      <strong>标准模式</strong>
      <ul>
        <li>✓ 记录搜索关键词和问题内容（7天）</li>
        <li>✓ 7天后转为匿名hash</li>
        <li>✓ 永久保留登录用户数据</li>
      </ul>
    `,
    'full': `
      <strong>完整记录模式</strong>
      <ul>
        <li>✓ 记录所有搜索和问题内容</li>
        <li>✓ 帮助改进系统准确性</li>
        <li>✓ 永久保留数据</li>
      </ul>
    `
  };

  // 显示隐私政策弹窗
  const modalHtml = `
    <div class="modal privacy-info" style="display: block;">
      <div class="modal-content">
        <h3>隐私设置</h3>
        ${info[privacyMode]}
        <button onclick="this.closest('.modal').remove()">知道了</button>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);
}
```

---

## 📉 数据删除

### 用户请求删除数据

```javascript
async function requestUserDataDeletion() {
  if (!confirm('确定要删除所有追踪数据吗？此操作不可恢复。')) {
    return;
  }

  const email = prompt('请输入您的联系邮箱（用于确认）：');

  if (!email || !email.includes('@')) {
    alert('请输入有效的邮箱地址');
    return;
  }

  try {
    const response = await fetch('/api/v1/analytics/request-deletion', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': analytics.sessionId
      },
      body: JSON.stringify({
        contact_email: email
      })
    });

    if (response.ok) {
      alert('✅ 删除请求已提交。我们将在7个工作日内处理。');
    } else {
      alert('❌ 删除请求失败，请稍后重试。');
    }
  } catch (error) {
    console.error('Deletion request failed:', error);
    alert('❌ 请求失败，请稍后重试。');
  }
}
```

---

## 🎨 UI建议

### 反馈按钮样式

```css
/* 反馈按钮容器 */
.feedback-buttons {
  display: flex;
  gap: 0.5rem;
}

/* 反馈按钮基础样式 */
.btn-feedback-good,
.btn-feedback-neutral,
.btn-feedback-poor {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 1rem;
}

.btn-feedback-good:hover {
  background: #e8f5e9;
  border-color: #4caf50;
}

.btn-feedback-neutral:hover {
  background: #fff3e0;
  border-color: #ff9800;
}

.btn-feedback-poor:hover {
  background: #ffebee;
  border-color: #f44336;
}

/* 模态框样式 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: none;
}

.modal-content {
  background: white;
  margin: 10% auto;
  padding: 2rem;
  border-radius: 8px;
  max-width: 600px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* 评分选项 */
.rating-options {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 1rem 0;
}

.rating-options label {
  display: flex;
  align-items: center;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.rating-options label:hover {
  background: #f5f5f5;
}

.rating-options input[type="radio"] {
  margin-right: 0.5rem;
}
```

---

## 📊 管理员仪表板

### 显示统计数据

```javascript
async function loadDashboardStats(period = '7d') {
  try {
    const response = await fetch(`/api/v1/analytics/dashboard?period=${period}`);
    const stats = await response.json();

    // 显示统计卡片
    document.getElementById('total-users').textContent = stats.total_users;
    document.getElementById('active-users').textContent = stats.active_users;
    document.getElementById('total-activities').textContent = stats.total_activities;
    document.getElementById('avg-rating').textContent = stats.avg_rating.toFixed(1) + ' / 5.0';

    // 显示评分分布
    displayRatingDistribution(stats.rating_distribution);

    // 显示Top功能
    displayTopFeatures(stats.top_features);

    // 显示NPS
    if (stats.nps_score !== null) {
      document.getElementById('nps-score').textContent = stats.nps_score;
      document.getElementById('nps-badge').className = getNPSBadgeClass(stats.nps_score);
    }

    // 显示留存率
    document.getElementById('retention-7d').textContent = (stats.retention_7d * 100).toFixed(1) + '%';
    document.getElementById('retention-30d').textContent = (stats.retention_30d * 100).toFixed(1) + '%';

  } catch (error) {
    console.error('Failed to load dashboard stats:', error);
  }
}

function displayRatingDistribution(distribution) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0);

  const goodPercent = ((distribution.good || 0) / total * 100).toFixed(1);
  const neutralPercent = ((distribution.neutral || 0) / total * 100).toFixed(1);
  const poorPercent = ((distribution.poor || 0) / total * 100).toFixed(1);

  const html = `
    <div class="rating-distribution">
      <div class="rating-bar good" style="width: ${goodPercent}%"></div>
      <div class="rating-bar neutral" style="width: ${neutralPercent}%"></div>
      <div class="rating-bar poor" style="width: ${poorPercent}%"></div>
      <div class="rating-labels">
        <span>👍 ${goodPercent}%</span>
        <span>😐 ${neutralPercent}%</span>
        <span>👎 ${poorPercent}%</span>
      </div>
    </div>
  `;

  document.getElementById('rating-distribution').innerHTML = html;
}

function getNPSBadgeClass(npsScore) {
  if (npsScore >= 50) return 'badge-excellent';
  if (npsScore >= 20) return 'badge-good';
  if (npsScore >= 0) return 'badge-neutral';
  return 'badge-poor';
}
```

---

## 🧪 测试

### 本地测试

```javascript
// 测试追踪
await analytics.track('search', '三心 mindful awareness');

// 测试反馈
await fetch('/api/v1/analytics/feedback/instant', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Session-ID': analytics.sessionId
  },
  body: JSON.stringify({
    rating: 'good',
    context: { feature: 'search', content_id: 'test' }
  })
});

// 查看用户状态
const profile = await fetch('/api/v1/analytics/me').then(r => r.json());
console.log('User profile:', profile);

// 查看仪表板（管理员）
const dashboard = await fetch('/api/v1/analytics/dashboard?period=7d').then(r => r.json());
console.log('Dashboard stats:', dashboard);
```

---

## ✅ 集成检查清单

- [ ] 初始化Analytics类，生成session_id
- [ ] 搜索功能添加追踪
- [ ] 问答功能添加追踪
- [ ] 音频播放添加追踪
- [ ] 书籍阅读添加追踪
- [ ] 搜索/问答后显示即时反馈按钮
- [ ] 差评时弹出详细反馈表单
- [ ] 每周弹窗显示深度反馈（7天后）
- [ ] 隐私设置页面
- [ ] 数据删除功能
- [ ] 管理员仪表板页面

---

## 📝 注意事项

1. **不打扰用户**：反馈提示要简洁，不要过度弹窗
2. **隐私优先**：默认使用标准模式，明确告知数据用途
3. **即时反馈**：用户操作后立即显示反馈按钮，不要等待
4. **差评必填**：差评时要求填写建议，帮助改进
5. **性能优化**：追踪请求失败不应影响主功能
6. **数据安全**：session_id存储在localStorage，不上报敏感信息

---

**众智混元，万法灵通** ⚡🚀
