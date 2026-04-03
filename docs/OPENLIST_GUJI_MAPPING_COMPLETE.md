# Openlist 古籍扫描文档映射完成报告

**日期**: 2026-04-02
**任务**: 建立导入的古籍数据与 openlist 扫描文档的映射关系

---

## 📊 执行结果

### 扫描统计
- **扫描路径**:
  - `/书籍/丛刊/殆知閣古代文獻2.0（旧版）` - 11,161 个文件
  - `/书籍/智能气功专业图书馆/2、古籍参考文献` - 2 个文件
  - `/书籍/丛刊/四部丛刊` - 1,669 个文件
- **总计**: 12,832 个扫描文档

### 映射结果
- **成功映射**: 1,664 个文件 (数字开头文件)
- **待处理**: 11,168 个中文文件名文件
- **唯一书籍**: 687 个 book_id
- **来源表**: wx201

### 文件类型分布
| 类型 | 数量 |
|------|------|
| .djvu | 1,649 |
| .zip | 12 |
| .pdf | 2 |
| .png | 1 |

---

## 🔗 映射原理

### 数字前缀文件
扫描文档中数字开头的文件 (如 `0001周易一.djvu`) 可以直接通过文件名中的数字匹配到数据库的 `bid` 字段：

```
0001周易一.djvu → book_id=1 → wx201 表
0002周易二.djvu → book_id=2 → wx201 表
```

### 中文文件名
中文文件名 (如 `韩非子.txt`) 需要通过标题匹配算法：
- 从本地 SQLite 数据库读取 wx 表的标题
- 使用文本相似度算法匹配文件名

---

## 📁 数据库结构

### guji_scan_mapping 表
```sql
CREATE TABLE guji_scan_mapping (
    file_name VARCHAR(255),      -- 文件名
    file_path TEXT,              -- 完整路径
    file_type VARCHAR(50),       -- 文件扩展名
    book_id INTEGER,             -- 对应的 book_id
    source_table VARCHAR(50),    -- 来源表 (如 wx201)
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 关联查询示例
```sql
-- 查找指定 book_id 的扫描文档
SELECT m.*, c.body_length
FROM guji_scan_mapping m
LEFT JOIN guoxue_content c ON c.book_id = m.book_id
WHERE m.book_id = 1001;

-- 统计每个表的映射数量
SELECT source_table, COUNT(*) as cnt
FROM guji_scan_mapping
GROUP BY source_table;
```

---

## 🛠️ 使用工具

### 查询工具
```bash
# 显示统计信息
python3 scripts/guji_query.py --stats

# 查找指定 book_id 的扫描文档
python3 scripts/guji_query.py --book-id 1001

# 按标题关键词搜索
python3 scripts/guji_query.py --title "周易"

# 显示文件列表
python3 scripts/guji_query.py --list 50

# 导出映射到 CSV
python3 scripts/guji_query.py --export mapping.csv
```

### 映射分析
```bash
# 重新分析映射关系
python3 scripts/guji_map_analysis.py

# 执行映射 (通过 Docker)
python3 scripts/guji_map_docker.py
```

---

## 📋 后续工作

### 1. 中文文件名映射
需要实现文本相似度匹配算法：
- 使用编辑距离 (Levenshtein distance)
- 使用 TF-IDF 余弦相似度
- 使用 jieba 分词进行中文匹配

### 2. 扩展映射范围
当前只映射了 wx201 表，其他表 (如 wx200, wx1038 等) 也有大量数据：
```
wx200: 105,214 条记录
wx1038: 22,502 条记录
wx242: 7,369 条记录
...
```

### 3. API 集成
创建 API 端点查询扫描文档：
```
GET /api/v1/guji/scans/{book_id}
GET /api/v1/guji/search?q={keyword}
```

---

## 📌 关键发现

### Openlist 目录结构
```
/书籍/
├── 丛刊/
│   ├── 殆知閣古代文獻2.0（旧版）/
│   │   ├── 道藏/
│   │   ├── 佛藏/
│   │   ├── 集藏/
│   │   ├── 儒藏/
│   │   ├── 诗藏/
│   │   ├── 史藏/
│   │   ├── 医藏/
│   │   ├── 艺藏/
│   │   ├── 易藏/
│   │   └── 子藏/
│   └── 四部丛刊/
├── 智能气功专业图书馆/
│   └── 2、古籍参考文献/
│       ├── 1、经部/
│       ├── 2、史部/
│       └── 3、子部/
```

### 数据库表结构
本地 SQLite 数据库 (guoxue.db) 包含 110 个 wx* 表：
- 每个表有 `id`, `body`, `bid` 字段
- `bid` 字段用于关联书籍 ID
- PostgreSQL 已导入约 26 万条记录

---

## ✅ 完成状态

- [x] 扫描 openlist 古籍目录
- [x] 建立数字前缀文件映射 (1,664 个)
- [x] 创建查询工具
- [x] 验证映射结果
- [ ] 中文文件名模糊匹配 (11,168 个待处理)
- [ ] 扩展其他 wx 表的映射
- [ ] API 集成

---

## 🔗 相关文件

- `scripts/guji_map_docker.py` - 映射执行脚本
- `scripts/guji_map_analysis.py` - 映射分析脚本
- `scripts/guji_query.py` - 查询工具
- `scripts/analyze_openlist_db.sh` - Openlist 数据库分析脚本
