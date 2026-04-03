# guoxue.db 与古籍扫描文档关联方案

## 数据源结构

### 1. guoxue_content (PostgreSQL)
```
已导入 263,767 条文献内容
- source_table: wx200, wx1038, wx201... (108个表)
- book_id: 200, 1038, 201... (对应 wx 表数字部分)
- chapter_id (bid): 0 ~ 21177 (章节ID)
- body: 文献正文内容
```

### 2. 扫描文档目录结构
```
Z:\115\国学大师\guji\                    (2TB)
├── 11(1)\                           (分类目录)
│   ├── 208666.djvu                  (扫描文档)
│   ├── 208050.djvu
│   └── ...
├── 17\                              (363GB)
├── 502\                             (354GB, 按地区分类)
├── 506\                             (206GB)
│   └── 汉籍.txt                   ← **索引文件！**
├── 16\                              (336GB)
└── ...
```

### 3. 索引文件: 汉籍.txt
**路径**: `Z:\115\国学大师\guji\506\汉籍.txt`

**内容格式** (推测):
```
DVD-XX
编号 [分类]书名 卷数
1 [十三经注疏]周易兼義九卷
2 [十三经注疏]尚書註疏二十卷
...
```

### 4. 文件ID关联规则

**扫描文档命名**: `{数字ID}.djvu` (如 `208666.djvu`)

**可能的关联方式**:
- 方案A: 通过 `汉籍.txt` 索引文件建立映射
- 方案B: 通过 chapter_id (bid) 匹配
- 方案C: 通过书名匹配

## 实现步骤

### 步骤1: 获取索引文件

```bash
# 通过 OpenList API 下载索引文件
curl "http://100.66.1.8:2455/115/国学大师/guji/506/汉籍.txt" -o hanji_index.txt
```

### 步骤2: 解析索引文件

```python
def parse_hanji_index(file_path):
    """解析汉籍索引文件"""
    records = []

    with open(file_path, 'r', encoding='gbk') as f:
        for line in f:
            line = line.strip()
            # 解析格式: "1 [十三经注疏]周易兼義九卷"
            match = re.match(r'^(\d+)\s*\[([^\]]+)\](.+)', line)
            if match:
                record_id = int(match.group(1))
                category = match.group(2)
                title = match.group(3)
                records.append({
                    'id': record_id,
                    'category': category,
                    'title': title
                })

    return records
```

### 步骤3: 建立映射表

```sql
-- 在 guji_scan_mapping 表中添加字段
ALTER TABLE guji_scan_mapping ADD COLUMN scan_document_id INTEGER;
ALTER TABLE guji_scan_mapping ADD COLUMN scan_title VARCHAR(500);
ALTER TABLE guji_scan_mapping ADD COLUMN scan_category VARCHAR(100);
```

### 步骤4: 批量关联

```python
# 将索引数据与 guoxue_content 关联
for record in hanji_records:
    # 通过标题匹配 guoxue_content 中的记录
    matches = await conn.fetch("""
        SELECT source_table, book_id, chapter_id,
               SUBSTRING(body, 1, 100) as preview
        FROM guoxue_content
        WHERE body LIKE $1 || '%'
        LIMIT 5
    """, record['title'])

    if matches:
        for match in matches:
            await conn.execute("""
                INSERT INTO guji_scan_mapping
                (scan_title, scan_category, book_id, source_table, chapter_id)
                VALUES ($1, $2, $3, $4, $5)
                """, record['title'], record['category'], ...)
```

## 关键问题待确认

1. ✅ 扫描文档位置: `Z:\115\国学大师\guji\`
2. ❌ 索引文件访问: 需要通过 OpenList 下载
3. ❌ ID对应关系: 需要解析 `汉籍.txt` 确认

## API 访问路径修正

用户提供的路径: `http://100.66.1.8:2455/115/国学大师/guji`

可能需要转换为实际存储路径进行访问。
