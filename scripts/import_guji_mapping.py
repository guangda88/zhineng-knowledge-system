#!/usr/bin/env python3
"""
导入 guji_mapping.json 到数据库并建立完整关联

1. 解析 guji_mapping.json
2. 导入到数据库映射表
3. 更新 guji_documents 的 book_id
4. 创建完整的关联视图
"""

import json
import subprocess
from pathlib import Path

# 配置
GUJI_MAPPING_FILE = Path("/home/ai/zhineng-knowledge-system/data/guji_mapping.json")
POSTGRES_CONTAINER = "dfdd3b278296_zhineng-postgres"


def load_guji_mapping():
    """加载 guji_mapping.json"""
    with open(GUJI_MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def execute_sql(sql: str):
    """执行SQL"""
    cmd = [
        "docker",
        "exec",
        POSTGRES_CONTAINER,
        "psql",
        "-U",
        "zhineng",
        "-d",
        "zhineng_kb",
        "-c",
        sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def main():
    print("=" * 70)
    print("📚 导入 guji_mapping.json 到数据库")
    print("=" * 70)

    # 1. 加载映射数据
    mapping_data = load_guji_mapping()
    print(f"✅ 加载了 {len(mapping_data)} 个书籍映射")

    # 2. 创建映射表
    print("\n" + "=" * 70)
    print("🔨 创建映射表")
    print("=" * 70)

    create_table_sql = """
    DROP TABLE IF EXISTS guji_file_book_mapping CASCADE;
    CREATE TABLE guji_file_book_mapping (
        id SERIAL PRIMARY KEY,
        book_name TEXT NOT NULL,
        file_name TEXT NOT NULL,
        content_source_table TEXT NOT NULL,
        content_source_id INTEGER NOT NULL,
        content_preview TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """

    execute_sql(create_table_sql)
    print("✅ 创建 guji_file_book_mapping 表")

    # 3. 插入映射数据
    print("\n" + "=" * 70)
    print("💾 插入映射数据")
    print("=" * 70)

    insert_count = 0
    for book_name, info in mapping_data.items():
        files = info.get("files", [])
        content_sources = info.get("content_sources", [])

        for file_name in files:
            for cs in content_sources:
                source_table = cs.get("source_table", "wx200")
                source_id = cs.get("source_id", 0)
                preview = cs.get("preview", "")[:500]

                # 清理预览文本中的单引号
                preview = preview.replace("'", "''")

                insert_sql = f"""
                INSERT INTO guji_file_book_mapping
                (book_name, file_name, content_source_table, content_source_id, content_preview)
                VALUES ('{book_name}', '{file_name}', '{source_table}', {source_id}, '{preview}')
                """

                execute_sql(insert_sql)
                insert_count += 1

    print(f"✅ 插入了 {insert_count} 条映射记录")

    # 4. 创建索引
    print("\n" + "=" * 70)
    print("🔍 创建索引")
    print("=" * 70)

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_guji_map_file ON guji_file_book_mapping(file_name)",
        "CREATE INDEX IF NOT EXISTS idx_guji_map_book ON guji_file_book_mapping(book_name)",
        "CREATE INDEX IF NOT EXISTS idx_guji_map_source ON guji_file_book_mapping(content_source_table, content_source_id)",
    ]

    for idx_sql in indexes:
        execute_sql(idx_sql)
        print(f"  ✅ {idx_sql.split()[3]}")

    # 5. 创建完整关联视图
    print("\n" + "=" * 70)
    print("📊 创建完整关联视图")
    print("=" * 70)

    view_sql = """
    CREATE OR REPLACE VIEW v_guji_complete AS
    SELECT
        s.id as scan_id,
        s.file_name,
        s.file_path,
        s.file_type,
        s.book_id as scan_book_id,
        m.book_name as mapped_book_name,
        d.id as document_id,
        d.source_id,
        d.title as document_title,
        LEFT(d.content, 100) as content_preview
    FROM guji_scan_mapping s
    LEFT JOIN guji_file_book_mapping m ON s.file_name = m.file_name
    LEFT JOIN guji_documents d ON
        d.source_table = m.content_source_table AND
        d.source_id = m.content_source_id
    ORDER BY s.id;
    """

    execute_sql(view_sql)
    print("✅ 创建 v_guji_complete 视图")

    # 6. 统计报告
    print("\n" + "=" * 70)
    print("📈 数据统计")
    print("=" * 70)

    stats_sql = """
    SELECT
        '扫描文档' as type, COUNT(*) as count FROM guji_scan_mapping
    UNION ALL
    SELECT
        '内容文档' as type, COUNT(*) as count FROM guji_documents
    UNION ALL
    SELECT
        '文件映射' as type, COUNT(*) as count FROM guji_file_book_mapping
    UNION ALL
    SELECT
        '完整关联' as type, COUNT(*) as count FROM v_guji_complete WHERE document_id IS NOT NULL;
    """

    result = execute_sql(stats_sql)
    print(result)

    # 7. 显示关联示例
    print("\n" + "=" * 70)
    print("📖 完整关联示例 (前10条)")
    print("=" * 70)

    sample_sql = """
    SELECT
        file_name as 文件名,
        COALESCE(mapped_book_name, '未映射') as 映射书名,
        COALESCE(document_title, '无标题') as 文档标题,
        COALESCE(content_preview, '无内容') as 内容预览
    FROM v_guji_complete
    WHERE document_id IS NOT NULL
    LIMIT 10;
    """

    result = execute_sql(sample_sql)
    print(result)


if __name__ == "__main__":
    main()
