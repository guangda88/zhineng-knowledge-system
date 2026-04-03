#!/usr/bin/env python3
"""医学维度词表完善脚本

完善中医、气功、古籍等领域的维度词表，支持自动标注和检索。

功能:
1. 创建医学维度词表
2. 扩充现有词表
3. 建立词间关联
4. 导入到数据库

使用方法:
    python scripts/enhance_tcm_vocabulary.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Set

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ===== 中医基础词表 =====

TCM_VOCABULARY = {
    "基础理论": {
        "阴阳": ["阴", "阳", "阴阳平衡", "阴虚", "阳虚", "阴盛", "阳盛", "阴阳两虚"],
        "五行": ["木", "火", "土", "金", "水", "五行相生", "五行相克", "五行生克"],
        "脏腑": ["五脏", "六腑", "心", "肝", "脾", "肺", "肾", "胆", "胃", "小肠", "大肠", "膀胱", "三焦"],
        "气血": ["气", "血", "气血", "气虚", "血虚", "气血两虚", "气滞", "血瘀"],
        "经络": ["经络", "经脉", "络脉", "十二经脉", "奇经八脉", "任脉", "督脉", "冲脉", "带脉"],
        "津液": ["津", "液", "津液", "痰", "饮", "水湿"],
        "精神": ["神", "魂", "魄", "意", "志", "精神", "神志"],
    },
    "诊断学": {
        "四诊": ["望诊", "闻诊", "问诊", "切诊", "脉诊", "舌诊"],
        "八纲": ["八纲", "阴阳", "表里", "寒热", "虚实", "表证", "里证", "寒证", "热证", "虚证", "实证"],
        "辨证": ["辨证论治", "病因辨证", "脏腑辨证", "经络辨证", "六经辨证", "卫气营血辨证", "三焦辨证"],
    },
    "中药学": {
        "本草": ["本草", "中药", "草药", "中成药", "方药"],
        "性味": ["四气", "五味", "寒", "热", "温", "凉", "酸", "苦", "甘", "辛", "咸"],
        "归经": ["归经", "引经", "经"],
        "功效": ["补气", "补血", "滋阴", "壮阳", "清热", "解毒", "活血", "化瘀", "祛风", "散寒"],
        "用法": ["煎服", "丸", "散", "膏", "丹", "汤", "酒"],
    },
    "方剂学": {
        "方剂": ["方剂", "汤方", "成方", "经方", "时方"],
        "组方": ["君药", "臣药", "佐药", "使药", "配伍"],
        "经典方": ["麻黄汤", "桂枝汤", "银翘散", "藿香正气散", "六味地黄丸", "补中益气汤", "归脾汤", "逍遥散"],
    },
    "针灸学": {
        "腧穴": ["穴位", "腧穴", "经穴", "奇穴", "阿是穴"],
        "特定穴": ["五输穴", "原穴", "络穴", "背俞穴", "募穴", "八会穴", "八脉交会穴", "下合穴"],
        "手法": ["针刺", "艾灸", "温针灸", "电针", "耳针", "头针", "拔罐", "刮痧"],
    },
    "内科": {
        "伤寒": ["伤寒", "太阳病", "阳明病", "少阳病", "太阴病", "少阴病", "厥阴病"],
        "温病": ["温病", "风温", "春温", "暑温", "湿温", "秋燥", "冬温"],
        "杂病": ["感冒", "咳嗽", "哮喘", "胃痛", "呕吐", "泄泻", "痢疾", "便秘", "黄疸", "水肿"],
    },
    "外科": {
        "外科病": ["疮疡", "疔疮", "痈疽", "瘰疬", "乳痈", "痔疮", "肛裂", "烧伤"],
        "伤科": ["骨折", "脱位", "伤筋", "内伤", "扭伤", "挫伤"],
    },
    "妇科": {
        "月经": ["月经", "月经不调", "痛经", "闭经", "崩漏", "经前期综合征"],
        "带下": ["带下", "白带", "黄带", "赤白带"],
        "妊娠": ["妊娠", "妊娠呕吐", "妊娠腹痛", "胎动不安", "堕胎", "小产"],
        "产后": ["产后", "产后腹痛", "产后恶露不绝", "产后发热"],
    },
    "儿科": {
        "儿科病": ["感冒", "咳嗽", "肺炎", "哮喘", "泄泻", "疳证", "水肿", "遗尿"],
        "新生儿": ["新生儿黄疸", "新生儿破伤风", "脐风"],
    },
    "五官科": {
        "眼科": ["目赤", "目翳", "针眼", "睑弦赤烂", "流泪症", "夜盲"],
        "耳鼻喉": ["耳鸣", "耳聋", "鼻塞", "鼻渊", "喉痹", "喉蛾", "乳蛾"],
        "口腔": ["口疮", "牙痛", "齿衄", "牙痈"],
    },
}


# ===== 气功维度词表 =====

QIGONG_VOCABULARY = {
    "基础理论": {
        "混元气": ["混元气", "原始混元气", "万物混元气", "人的混元气", "脏真混元气", "躯体混元气"],
        "意元体": ["意元体", "意识", "意念", "念头", "思维", "知觉"],
        "意识论": ["意识活动", "意识运动", "意识作用", "意念力", "意念致动"],
        "道德论": ["道德", "道德修养", "自然道德", "社会道德", "智能道德"],
        "优化生命": ["优化生命", "生命自由", "生命升华", "圆满", "通达"],
    },
    "技术理论": {
        "三套功夫": ["捧气贯顶法", "形神庄", "五元庄", "中脉混元", "脏真归元", "神形混元"],
        "智能气功": ["智能气功", "庞明", "庞鹤鸣", "智能气功科学"],
        "功法": ["鹤首", "龙头", "俯身", "转腰", "蹲墙", "颤抖", "发音"],
    },
    "应用理论": {
        "医疗": ["气功医疗", "第四医学", "气功治病", "组场", "发气", "查病"],
        "教育": ["气功教育", "开发智力", "涵养道德", "练气功"],
        "生产": ["农业气功", "工业气功", "增产", "提质"],
    },
}


# ===== 古籍维度词表 =====

GUJI_VOCABULARY = {
    "朝代": {
        "先秦": ["先秦", "春秋", "战国", "商", "周", "秦"],
        "汉": ["西汉", "东汉", "汉"],
        "三国": ["魏", "蜀", "吴", "三国"],
        "晋": ["西晋", "东晋", "晋"],
        "南北朝": ["南北朝", "南朝", "北朝"],
        "隋": ["隋"],
        "唐": ["唐", "初唐", "盛唐", "中唐", "晚唐"],
        "宋": ["北宋", "南宋", "宋"],
        "元": ["元"],
        "明": ["明"],
        "清": ["清", "晚清"],
    },
    "古籍分类": {
        "经部": ["经", "易", "书", "诗", "礼", "乐", "春秋", "论语", "孟子", "孝经"],
        "史部": ["史", "纪传", "编年", "纪事本末", "别史", "杂史", "诏令", "奏议"],
        "子部": ["子", "儒家", "道家", "法家", "墨家", "兵家", "农家", "医家", "天文", "术数"],
        "集部": ["集", "楚辞", "别集", "总集", "诗文评", "词曲"],
    },
}


# ===== 维度词表合并 =====

ALL_VOCABULARY = {
    "中医": TCM_VOCABULARY,
    "气功": QIGONG_VOCABULARY,
    "古籍": GUJI_VOCABULARY,
}


async def create_vocabulary_tables(conn: asyncpg.Connection) -> None:
    """创建词表数据表"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS medical_vocabulary (
            id SERIAL PRIMARY KEY,
            domain VARCHAR(50) NOT NULL,
            main_category VARCHAR(100) NOT NULL,
            sub_category VARCHAR(100),
            term TEXT NOT NULL,
            pinyin TEXT,
            definition TEXT,
            synonyms TEXT[] DEFAULT '{}',
            related_terms TEXT[] DEFAULT '{}',
            western_equivalent TEXT[],
            tags JSONB DEFAULT '{}'::jsonb,
            frequency INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(domain, main_category, term)
        );
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_vocab_domain ON medical_vocabulary(domain);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_vocab_category ON medical_vocabulary(main_category, sub_category);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_vocab_term ON medical_vocabulary USING gin(to_tsvector('chinese', term));
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_vocab_tags ON medical_vocabulary USING gin(tags);
    """)

    logger.info("词表数据表创建完成")


async def import_vocabulary(
    conn: asyncpg.Connection,
    domain: str,
    vocabulary: Dict
) -> int:
    """导入词表数据"""
    total = 0

    for main_category, sub_categories in vocabulary.items():
        for sub_category, terms in sub_categories.items():
            if isinstance(terms, list):
                for term in terms:
                    tags = {"main_category": main_category, "sub_category": sub_category}
                    await conn.execute(
                        """
                        INSERT INTO medical_vocabulary (domain, main_category, sub_category, term, tags)
                        VALUES ($1, $2, $3, $4, $5::jsonb)
                        ON CONFLICT (domain, main_category, term) DO UPDATE SET
                            tags = EXCLUDED.tags
                        """,
                        domain, main_category, sub_category, term, json.dumps(tags)
                    )
                    total += 1
            elif isinstance(terms, dict):
                for sub_sub_cat, sub_terms in terms.items():
                    for term in sub_terms:
                        tags = {"main_category": main_category, "sub_category": sub_category, "sub_sub_category": sub_sub_cat}
                        await conn.execute(
                            """
                            INSERT INTO medical_vocabulary (domain, main_category, sub_category, term, tags)
                            VALUES ($1, $2, $3, $4, $5::jsonb)
                            ON CONFLICT (domain, main_category, term) DO UPDATE SET
                                tags = EXCLUDED.tags
                            """,
                            domain, main_category, sub_category, term, json.dumps(tags)
                        )
                        total += 1

    logger.info(f"导入 {domain} 词表: {total} 条")
    return total


async def enhance_vocabulary(conn: asyncpg.Connection) -> Dict:
    """完善词表"""
    # 扩展词表 - 添加关联
    enhancements = []

    # 添加脏腑相关词关联
    enhancements.append("""
        UPDATE medical_vocabulary
        SET related_terms = ARRAY(
            SELECT term FROM medical_vocabulary v2
            WHERE v2.main_category = '脏腑'
            AND v2.domain = '中医'
        )
        WHERE domain = '中医' AND main_category = '经络';
    """)

    # 添加症状关联
    enhancements.append("""
        UPDATE medical_vocabulary
        SET tags = jsonb_set(tags, '{is_symptom}', 'true')
        WHERE domain = '中医'
        AND (term LIKE '%痛' OR term LIKE '%证' OR term LIKE '%病');
    """)

    for sql in enhancements:
        try:
            await conn.execute(sql)
        except Exception as e:
            logger.warning(f"扩展词表失败: {e}")

    # 获取统计
    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_terms,
            COUNT(DISTINCT domain) as total_domains,
            COUNT(DISTINCT main_category) as total_categories
        FROM medical_vocabulary
    """)

    return {
        "total_terms": stats["total_terms"],
        "total_domains": stats["total_domains"],
        "total_categories": stats["total_categories"],
    }


async def main():
    """主函数"""
    import os

    # 获取数据库URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = "postgresql://postgres:postgres@localhost:5432/zhineng"

    logger.info("开始完善医学维度词表...")

    conn = await asyncpg.connect(database_url)

    try:
        # 创建表
        await create_vocabulary_tables(conn)

        # 导入词表
        total = 0
        for domain, vocabulary in ALL_VOCABULARY.items():
            count = await import_vocabulary(conn, domain, vocabulary)
            total += count

        logger.info(f"词表导入完成: {total} 条")

        # 完善词表
        stats = await enhance_vocabulary(conn)

        await conn.close()

        logger.info("=" * 50)
        logger.info("医学维度词表完善完成!")
        logger.info(f"总词数: {stats['total_terms']:,}")
        logger.info(f"领域数: {stats['total_domains']}")
        logger.info(f"分类数: {stats['total_categories']}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"完善词表失败: {e}")
        await conn.close()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
