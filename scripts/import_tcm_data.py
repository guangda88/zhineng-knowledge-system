#!/usr/bin/env python3
"""中医数据导入脚本

从知识字典和其他中医数据源导入约7.7万条中医数据。

数据来源:
- kxzd.db: 康熙字典/知识字典 (约4.8万条)
- TCM相关文本和文献数据

使用方法:
    python scripts/import_tcm_data.py
"""

import asyncio
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from tqdm import tqdm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# 数据源路径
KXZD_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "kxzd.db"
TCM_DATA_DIR = Path(__file__).parent.parent / "data" / "tcm"

# 中医分类体系
TCM_CATEGORIES = {
    "基础理论": ["阴阳", "五行", "脏腑", "经络", "气血", "津液", "精神", "体质"],
    "诊断学": ["望诊", "闻诊", "问诊", "切诊", "八纲", "辨证"],
    "中药学": ["本草", "性味", "归经", "功效", "用法", "禁忌"],
    "方剂学": ["方剂", "组方", "配伍", "剂型", "用法"],
    "针灸学": ["经络", "腧穴", "刺法", "灸法", "治疗"],
    "内科学": ["伤寒", "温病", "内科杂病"],
    "外科学": ["外科", "伤科", "皮肤病"],
    "妇科学": ["妇科", "产科", "月经", "带下", "妊娠", "产后"],
    "儿科学": ["儿科", "新生儿", "婴幼儿", "喂养"],
    "五官科": ["眼科", "耳鼻喉", "口腔"],
    "骨伤科": ["骨折", "脱位", "伤筋", "内伤"],
    "养生学": ["养生", "保健", "食疗", "导引", "气功"],
}

# 中医朝代关键词
DYNASTY_KEYWORDS = {
    "先秦": ["内经", "素问", "灵枢"],
    "汉": ["伤寒", "金匮", "本草经"],
    "唐": ["千金", "外台"],
    "宋": ["太平", "圣惠", "和剂"],
    "金元": ["河间", "东垣", "丹溪", "从正"],
    "明": ["景岳", "本草纲目", "濒湖"],
    "清": ["医宗", "金鉴", "温病", "温热"],
}


async def create_tcm_tables(conn: asyncpg.Connection) -> None:
    """创建中医数据表"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tcm_documents (
            id SERIAL PRIMARY KEY,
            source_type VARCHAR(50) NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            title TEXT,
            author TEXT,
            content TEXT,
            content_length INTEGER,

            -- 中医分类
            main_category VARCHAR(50),
            sub_categories TEXT[] DEFAULT '{}',
            tags JSONB DEFAULT '{}'::jsonb,

            -- 元数据
            dynasty VARCHAR(50),
            year INTEGER,
            source_reference TEXT,

            -- 现代标注
            western_equivalent TEXT[],
            indications TEXT[],
            contraindications TEXT[],

            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(source_type, source_id)
        );
    """)

    # 创建索引
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tcm_source ON tcm_documents(source_type, source_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tcm_category ON tcm_documents(main_category, sub_categories);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tcm_title ON tcm_documents USING gin(to_tsvector('chinese', title));
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tcm_content ON tcm_documents USING gin(to_tsvector('chinese', content));
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tcm_tags ON tcm_documents USING gin(tags);
    """)

    # 创建中医词表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tcm_vocabulary (
            id SERIAL PRIMARY KEY,
            term TEXT NOT NULL UNIQUE,
            pinyin TEXT,
            category VARCHAR(50),
            sub_category VARCHAR(50),
            definition TEXT,
            synonyms TEXT[] DEFAULT '{}',
            related_terms TEXT[] DEFAULT '{}',
            western_terms TEXT[],
            frequency INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tcm_vocab_term ON tcm_vocabulary USING gin(to_tsvector('chinese', term));
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tcm_vocab_category ON tcm_vocabulary(category);
    """)

    logger.info("中医数据表创建完成")


def categorize_tcm_content(title: str, content: str) -> Tuple[str, List[str]]:
    """根据内容分类中医文档"""
    if not title and not content:
        return "其他", []

    text = (title + " " + (content or "")).lower()

    main_cat = "其他"
    sub_cats = []

    for category, keywords in TCM_CATEGORIES.items():
        for keyword in keywords:
            if keyword in text:
                if main_cat == "其他":
                    main_cat = category
                if keyword not in sub_cats:
                    sub_cats.append(keyword)

    return main_cat, sub_cats


def detect_dynasty(title: str, content: str) -> str:
    """检测中医文档的朝代"""
    text = (title + " " + (content or ""))

    for dynasty, keywords in DYNASTY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return dynasty

    return "未知"


async def import_kxzd_data(conn: asyncpg.Connection, kxzd_db: str) -> int:
    """导入知识字典数据"""
    if not Path(kxzd_db).exists():
        logger.warning(f"知识字典数据库不存在: {kxzd_db}")
        return 0

    sqlite_conn = sqlite3.connect(kxzd_db)
    cursor = sqlite_conn.cursor()

    # 获取总数
    cursor.execute("SELECT COUNT(*) FROM kxzd")
    total = cursor.fetchone()[0]
    logger.info(f"知识字典记录数: {total}")

    # 获取数据
    cursor.execute("SELECT * FROM kxzd")
    rows = cursor.fetchall()
    sqlite_conn.close()

    # 准备插入数据
    insert_docs = []
    insert_vocab = []

    def to_str(val):
        """转换为字符串"""
        if val is None:
            return None
        if isinstance(val, bytes):
            return val.decode('utf-8', errors='ignore')
        return str(val)

    for row in tqdm(rows, desc="处理知识字典"):
        # kxzd表结构: ID, a(字), b(部首), c(笔画), d(释义), yin(拼音), uc(Unicode)
        kxzd_id = row[0]
        char = to_str(row[1]) if len(row) > 1 else None
        radical = to_str(row[2]) if len(row) > 2 else None
        strokes = to_str(row[3]) if len(row) > 3 else None
        definition = to_str(row[4]) if len(row) > 4 else None
        pinyin = to_str(row[5]) if len(row) > 5 else None
        unicode_val = to_str(row[6]) if len(row) > 6 else None

        if not char:
            continue

        # 判断是否为中医相关字符
        is_tcm = False
        category = "基础理论"
        if definition:
            tcm_keywords = ["医", "药", "病", "症", "治", "穴", "经", "脉", "脏", "腑"]
            if any(kw in definition for kw in tcm_keywords):
                is_tcm = True
                category = "基础理论"

        # 作为文档导入
        content = f"【字】{char}\n【拼音】{pinyin or ''}\n【部首】{radical or ''}\n【笔画】{strokes or ''}\n【释义】{definition or ''}"

        main_cat, sub_cats = categorize_tcm_content(char, definition)

        insert_docs.append((
            "kxzd",                    # source_type
            str(kxzd_id),              # source_id
            char,                      # title
            content,                   # content
            len(content),              # content_length
            main_cat,                  # main_category
            sub_cats,                  # sub_categories
            {"radical": radical, "strokes": strokes},  # tags
            f"知识字典 ID: {kxzd_id}", # source_reference
        ))

        # 作为词汇导入
        if is_tcm or definition:
            insert_vocab.append((
                char,
                pinyin,
                category,
                definition,
            ))

    # 批量插入 - 转换tags为JSONB
    if insert_docs:
        prepared_docs = []
        for doc in insert_docs:
            # doc: (source_type, source_id, title, content, content_length, main_category, sub_categories, tags, source_reference)
            prepared_docs.append((
                doc[0], doc[1], doc[2], doc[3], doc[4], doc[5], doc[6], json.dumps(doc[7]), doc[8]
            ))
        await conn.executemany(
            """
            INSERT INTO tcm_documents (source_type, source_id, title, content, content_length, main_category, sub_categories, tags, source_reference)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
            ON CONFLICT (source_type, source_id) DO NOTHING
            """,
            prepared_docs
        )

    if insert_vocab:
        await conn.executemany(
            """
            INSERT INTO tcm_vocabulary (term, pinyin, category, definition)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (term) DO UPDATE SET
                definition = EXCLUDED.definition,
                pinyin = EXCLUDED.pinyin
            """,
            insert_vocab
        )

    logger.info(f"导入知识字典: {len(insert_docs)} 条文档, {len(insert_vocab)} 条词汇")
    return len(insert_docs)


async def import_tcm_data(database_url: str) -> dict:
    """导入所有中医数据"""
    # 连接数据库
    conn = await asyncpg.connect(database_url)

    try:
        # 创建表
        await create_tcm_tables(conn)

        total_imported = 0

        # 导入知识字典数据
        if KXZD_DB.exists():
            count = await import_kxzd_data(conn, str(KXZD_DB))
            total_imported += count

        # 导入其他中医文本数据
        if TCM_DATA_DIR.exists():
            for file_path in TCM_DATA_DIR.glob("*.txt"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                    main_cat, sub_cats = categorize_tcm_content(file_path.stem, content)
                    dynasty = detect_dynasty(file_path.stem, content)

                    await conn.execute(
                        """
                        INSERT INTO tcm_documents (source_type, source_id, title, content, content_length, main_category, sub_categories, dynasty)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (source_type, source_id) DO NOTHING
                        """,
                        ("file", str(file_path), file_path.stem, content, len(content), main_cat, sub_cats, dynasty)
                    )
                    total_imported += 1

        # 获取统计
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_documents,
                COUNT(DISTINCT main_category) as total_categories,
                SUM(content_length) as total_content,
                COUNT(DISTINCT dynasty) as distinct_dynasties
            FROM tcm_documents
        """)

        vocab_stats = await conn.fetchrow("SELECT COUNT(*) as count FROM tcm_vocabulary")

        await conn.close()

        return {
            "status": "success",
            "total_imported": total_imported,
            "stats": {
                "total_documents": stats["total_documents"],
                "total_categories": stats["total_categories"],
                "total_content_chars": stats["total_content"],
                "dynasties": stats["distinct_dynasties"],
                "vocabulary_count": vocab_stats["count"]
            }
        }

    except Exception as e:
        logger.error(f"导入失败: {e}")
        await conn.close()
        return {"status": "error", "message": str(e)}


async def main():
    """主函数"""
    import os

    # 获取数据库URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = "postgresql://postgres:postgres@localhost:5432/zhineng"

    logger.info(f"开始导入中医数据...")
    logger.info(f"知识字典: {KXZD_DB}")

    result = await import_tcm_data(database_url)

    if result["status"] == "success":
        logger.info("=" * 50)
        logger.info("中医数据导入完成!")
        logger.info(f"总计导入: {result['total_imported']:,} 条记录")
        if "stats" in result:
            logger.info(f"文档总数: {result['stats']['total_documents']:,}")
            logger.info(f"分类数: {result['stats']['total_categories']}")
            logger.info(f"总字符数: {result['stats']['total_content_chars']:,}")
            logger.info(f"词表数: {result['stats']['vocabulary_count']:,}")
        logger.info("=" * 50)
    else:
        logger.error(f"导入失败: {result.get('message')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
