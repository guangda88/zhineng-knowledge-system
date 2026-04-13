# UI Regression Checklist — ES Module Split

> Post-split verification for `frontend/app.js` → 7 ES modules + main.js entry point.
> Date: 2026-04-11

## How to Test

1. Start the stack: `docker-compose up -d`
2. Open `http://localhost:8008` in browser
3. Open browser DevTools Console (F12) — check for module load errors
4. Work through each section below

---

## 1. General (3 items)

- [ ] **G1**: Page loads without JS errors in console
- [ ] **G2**: All 7 tabs (搜索/文档/书籍/国学经典/书目检索/问答/推理) render correctly
- [ ] **G3**: Tab switching works — clicking each tab shows the correct section content

## 2. Search Tab (3 items)

- [ ] **S1**: Type "气功" and click 搜索 → results appear
- [ ] **S2**: Category filter (气功/中医/儒家) works — changes refine results
- [ ] **S3**: Feedback buttons (👍/👎) on search results are clickable and submit without error

## 3. Documents Tab (2 items)

- [ ] **D1**: Click 文档 tab → documents list loads
- [ ] **D2**: Category filter + 刷新 button work correctly

## 4. Books Tab (5 items)

- [ ] **B1**: Click 书籍 tab → default book list loads (uses /api/v2)
- [ ] **B2**: Search "道德经" → results appear
- [ ] **B3**: Toggle between 书籍搜索 and 全文搜索 works, placeholder text changes
- [ ] **B4**: Click a book card → book detail modal opens with chapters list
- [ ] **B5**: Click a chapter → chapter detail modal opens with content

## 5. Guoxue Tab (4 items)

- [ ] **G1**: Click 国学经典 tab → stats badges load (典籍/内容/字)
- [ ] **G2**: Book sidebar loads, typing in filter filters the list
- [ ] **G3**: Click a book → chapters load in main area
- [ ] **G4**: Click a chapter → modal overlay opens with chapter content
- [ ] **G5**: Search "论语" → search results appear with preview text

## 6. Sysbooks Tab (3 items)

- [ ] **Y1**: Click 书目检索 tab → stats badge loads
- [ ] **Y2**: Domain and format filters populate from API
- [ ] **Y3**: Search for a term → results appear, click opens detail modal

## 7. Chat Tab (3 items)

- [ ] **C1**: Type a question and click 发送 → user message appears
- [ ] **C2**: Assistant response appears with formatted markdown
- [ ] **C3**: Feedback buttons (有帮助/没帮助) on assistant response work

## 8. Reasoning Tab (4 items)

- [ ] **R1**: Enter a question, select mode, click 开始推理 → loading spinner appears
- [ ] **R2**: Reasoning result displays with steps, answer, and sources
- [ ] **R3**: Click 构建图谱 → graph build triggers, stats update
- [ ] **R4**: Graph canvas renders entities and relations when data available

## 9. Shared State (2 items)

- [ ] **SS1**: sessionId persists across chat messages (check in DevTools Network tab)
- [ ] **SS2**: Feedback in chat and search both use the same session context

---

## Summary

- **Total items**: 30
- **Critical path**: G1 (page loads), G2 (tabs render), G3 (tab switching), B1 (books load via /api/v2)
- **Known risk**: `onclick` handlers in HTML require `window.*` exposure — verified in main.js

## Rollback

If issues are found:
1. In `frontend/index.html`, change `<script type="module" src="main.js">` back to `<script src="app.js">`
2. Original `app.js` is backed up as `app.js.bak`
