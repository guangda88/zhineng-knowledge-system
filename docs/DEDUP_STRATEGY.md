# 数据去重与清洗策略

> 审计日期: 2026-04-02
> 状态: 执行中

---

## 一、原始数据源全景

| 源文件 | 大小 | 行数 | 内容性质 | 角色 |
|--------|------|------|----------|------|
| `Sys_books.db` | 2.4 GB | 3,024,428 | 文件系统索引 (Z盘 + Ammiao + sunbo + yangxl) | **主索引** |
| `data.db` | 0.3 GB | 907,539 | 百度云文件索引 (`x_search_nodes`) | **云盘索引** |
| `guoxue.db` | 6.3 GB | 263,767 (110张 `wx*` 表) | 古籍正文 (`body` 字段, 2.08 GB 纯文本) | **正文内容** |
| `kxzd.db` | 0.02 GB | 48,709 | 康熙字典条目 | **字典** |
| `textbooks.db` | 0.48 GB | 教材体系 | 教材结构 + FTS | **教材** |

### 数据源间关系

```
Sys_books.db (文件索引)
  ├── 4 个来源: Z-disk(242万), Ammiao(52万), sunbo(5.6万), yangxl(2.1万)
  ├── 包含: 目录行、文档文件、图片、代码、音视频等全部文件类型
  └── cross_ref → data.db (已完成: 1,116,600 匹配, 36.9%)

data.db (百度云索引)
  ├── 825,290 个文件 + 82,249 个目录
  ├── 全部在 /百度云9080/ 路径下
  └── 已被 cross_ref 消化，无独立去重价值

guoxue.db (古籍正文)
  ├── 110 张 wx* 表，263,767 条记录
  ├── 2.08 GB 纯文本内容 (body 字段)
  ├── 19,000 个不同 book_id (bid)
  └── 与 sys_books 中 DJVU/PDF 是同一古籍的不同形态 (扫描件 vs OCR)

kxzd.db (康熙字典)
  └── 48,709 条独立字典条目，无重复问题
```

---

## 二、sys_books 行级分类审计

| 类型 | 行数 | 占比 | 价值 | 处理 |
|------|------|------|------|------|
| 目录 (size=0, 无扩展名) | 1,246,289 | 41.2% | 零 — 纯目录结构 | 排除 |
| 图片 (.jpg/.png/.TIF) | 410,553 | 13.6% | 极低 — 扫描页/封面 | 排除 |
| 代码 (.js/.ts/.py/.d.ts) | 146,596 | 4.8% | 零 — node_modules/npm 包 | 排除 |
| 音视频 (.mp3/.mp4/.flv/.dat) | 85,887 | 2.8% | 低 — 除非音频转写 | 排除 |
| **有价值文档** | **~568,000** | **18.8%** | **高** | **保留** |
| — PDF | 218,078 | | | |
| — TXT | 136,880 | | | |
| — DJVU | 170,847 | | | |
| — DOC/DOCX | 41,177 | | | |
| — PDG (超星) | 89,882 | | | |
| — EPUB | 1,922 | | | |
| — CHM | 376 | | | |
| OTHER (混杂) | 475,941 | 15.7% | 待分类 | 标记审查 |

### 关键发现

1. **3M 行中仅 ~57 万行 (18.8%) 有文档价值**，不是"去重"问题而是"筛选"问题
2. **Z-disk 来源占 80% (242万行)**，其中大量是 node_modules、npm 包、空目录
3. **1,246,289 行是纯目录** (size=0, 无扩展名)，对搜索和检索零价值
4. **data.db 已被 cross_ref 消化**，1,116,600 匹配已写入 sys_books.cloud_path

### Sys_books 重复特征

| 重复类型 | 数量 | 示例 |
|----------|------|------|
| filename+size 重复 | 786,901 对 | 同一文件在多个备份目录中 |
| 通用文件名重复 | — | `index.js`(9,764), `package.json`(7,998), `LICENSE`(4,712) |
| 百度云备份重复 | — | 同一目录在 9080 和 6015148 备份中各出现一次 |

---

## 三、修正后的去重策略

### Phase 0: 清洗 sys_books (3M → ~57万)

**目标**: 排除无价值行，大幅提升查询性能

```sql
-- 排除规则 (按优先级):
-- 1. 目录行: size = 0 AND filename NOT LIKE '%.%'
-- 2. 代码文件: extension IN ('.js', '.ts', '.d.ts', '.py', '.css', '.map', '.json', '.xml', '.yml', '.yaml', '.sh', '.bat', '.md')
-- 3. 图片文件: extension IN ('.jpg', '.JPG', '.png', '.TIF', '.gif', '.bmp', '.svg', '.ico')
-- 4. 音视频文件: extension IN ('.mp3', '.mp4', '.flv', '.avi', '.wav', '.wma', '.dat')
-- 5. 其他低价值: extension IN ('.html', '.htm')  -- 除非是古籍 HTML
```

**保留规则**:
- PDF, TXT, DOC, DOCX, DJVU, PDG, EPUB, CHM, RTF
- 有扩展名但 size > 0 且不属于排除类的文件
- 包含中文文件名的文件 (可能是古籍资源)

**安全措施**:
- 清洗前创建 `sys_books_archive` 表保存完整原始数据
- 使用 `data_quality` 标记列替代 DELETE，保留回溯能力

### Phase 1: 精确去重 (~57万 → ~40-45万)

**策略**: `filename + size` 元组去重

```sql
-- 同 filename+size 保留最早(id最小)或最大文件的记录
-- 标记后续重复为 dupe
```

**保留优先级**:
1. 有 `cloud_path` 的记录 (已关联百度云)
2. `cross_ref_status = 'matched'` 的记录
3. id 最小的记录 (最早入库)

### Phase 2: 跨源关联 (非去重)

| 关联 | 方法 | 状态 |
|------|------|------|
| sys_books ↔ data.db | cross_ref (filename + path 子串) | ✅ 完成 |
| sys_books ↔ guoxue.db | DJVU/PDF 文件名 → wx* 表 book_id | 待执行 |
| sys_books ↔ documents (PG) | filename → title 匹配 | 待执行 |
| guoxue.db ↔ kxzd.db | 字典条目关联 | 不需要 (独立数据) |

### Phase 3: 语义去重 (依赖内容提取)

- 同一 PDF 的 TXT 版本 → 内容 hash 比对
- 扫描版 vs OCR 版 → SimHash 近似检测
- **前置条件**: 内容提取管道完成 (sys_book_contents 表有数据)

---

## 四、预估效果

| 阶段 | 行数变化 | 查询性能影响 |
|------|---------|-------------|
| 原始 | 3,024,428 | 基准 |
| Phase 0 清洗后 | ~568,000 (有价值) + ~475,000 (待分类) | SELECT 提升 3-5x |
| Phase 1 去重后 | ~400,000 - 450,000 | 索引体积减少 70% |
| Phase 2 关联后 | 行数不变，信息密度提升 | JOIN 查询可用 |
| Phase 3 语义去重后 | ~350,000 - 400,000 | 最终态 |

---

## 五、执行计划

### P0: 备份 + 清洗 (优先级最高)

1. 创建 `sys_books_archive` 表 (完整备份 3M 行)
2. 添加 `data_quality` 列 (VARCHAR: 'active', 'excluded_dir', 'excluded_code', 'excluded_image', 'excluded_media', 'excluded_other')
3. 执行清洗 UPDATE (标记排除行)
4. 验证: 活跃行数应为 ~57万

### P1: 精确去重

1. 添加 `dupe_group` 列 (INT: 同 filename+size 组的 id)
2. 按保留优先级标记重复行
3. 验证: 唯一文档数 ~40-45万

### P2: 跨源关联

1. guoxue.db → PostgreSQL 导入 (guji_documents 表)
2. 建立文件名 ↔ book_id 映射
3. documents (PG) ↔ sys_books 关联

### P3: 语义去重

- 依赖内容提取管道完成
- 使用内容 hash + SimHash

---

## 六、风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| 误删有价值文件 | 使用标记列 (data_quality) 替代 DELETE，保留完整数据 |
| 清洗规则过激 | 先 dry-run 统计，确认后再执行 |
| 索引重建耗时 | 512MB 容器上 GIN 索引需 ~10 分钟，安排低峰期 |
| 百度云路径丢失 | cloud_path 字段在清洗中不受影响 (只标记不删除) |

**回滚方案**: `UPDATE sys_books SET data_quality = 'active' WHERE data_quality != 'active'` — 一条命令恢复全部
