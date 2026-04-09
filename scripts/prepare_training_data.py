"""
微调数据准备流水线 v2 (Fine-tuning Data Preparation Pipeline)

为灵研(LLM微调)和灵极优(自优化)提供训练数据：
1. 意图分类数据集 — 多数据源模板生成
2. 嵌入微调样本对 — 正例 + 跨领域硬负例
3. RAG 问答评估基准 — 标题+首句生成 Q&A 对
4. 数据质量报告 — 统计概览

数据源:
- documents (104K, 3 categories: 中医/儒家/气功)
- guji_documents (263K, category=古籍, 169K quality)
- textbook_knowledge (3.2K, category=教材)

输出目录: data/training/
"""

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)

TRAINING_DIR = Path(os.getenv("TRAINING_DATA_DIR", "data/training"))

INTENT_TEMPLATES = {
    "practice_method": {
        "keywords": ["怎么做", "如何练习", "动作要领", "步骤", "方法", "练法", "功法"],
        "templates": [
            "{title}怎么做",
            "如何练习{title}",
            "{title}的动作要领是什么",
            "{title}的练习步骤",
            "{title}练法",
            "请讲解{title}的方法",
        ],
    },
    "scientific_basis": {
        "keywords": ["科学依据", "研究", "证明", "实验", "数据", "论文", "现代医学"],
        "templates": [
            "{title}有科学依据吗",
            "关于{title}有什么研究",
            "{title}的现代科学研究",
            "有没有实验证明{title}的效果",
            "{title}的科学原理是什么",
        ],
    },
    "theory_explanation": {
        "keywords": ["什么是", "原理", "为什么", "解释", "含义", "概念", "理论"],
        "templates": [
            "什么是{title}",
            "{title}的原理是什么",
            "为什么要有{title}",
            "请解释{title}的含义",
            "{title}是什么概念",
            "介绍一下{title}的理论",
        ],
    },
    "book_search": {
        "keywords": ["哪本书", "出处", "参考", "来源", "章节", "文献", "典籍"],
        "templates": [
            "{title}出自哪本书",
            "{title}的出处是什么",
            "哪本书提到过{title}",
            "{title}的参考文献",
            "关于{title}的典籍有哪些",
        ],
    },
    "comparison": {
        "keywords": ["区别", "不同", "对比", "差异", "关系", "联系", "比较"],
        "templates": [
            "{title}和{other}有什么区别",
            "对比{title}和{other}",
            "{title}与{other}的差异",
            "{title}和{other}的关系",
            "比较{title}和{other}的不同",
        ],
    },
}

FILE_EXT_PATTERN = re.compile(
    r"\.(mp4|mp3|wav|jpg|jpeg|png|docx|pdf|doc|avi|mkv|flv|"
    r"mpg|mpeg|bmp|gif|txt|xlsx|xls|ppt|pptx|rar|zip|7z|wma|aac|ceb)"
    r"(\s|$)",
    re.IGNORECASE,
)

NOISE_PREFIXES = re.compile(
    r"^(IMG_|CIMG|DSC_|P\d{2,3}|\d{8}_|\d+\.\s|_|文件名|第[零一二三四五六七八九十百千\d]+[章节卷]|"
    r"UID\d|帖子\d|精华\d|\d{3,}[_\-\s])"
)


def _is_clean_title(title: str, max_len: int = 60) -> bool:
    if not title or len(title.strip()) < 2:
        return False
    title = title.strip()
    if len(title) > max_len:
        return False
    if FILE_EXT_PATTERN.search(title):
        return False
    if NOISE_PREFIXES.match(title):
        return False
    if re.match(r"^[0-9a-zA-Z.\-_]+$", title) and len(title) < 20:
        return False
    if title.count(".") > 3:
        return False
    if re.search(r"\d{5,}", title):
        return False
    chinese = len(re.findall(r"[\u4e00-\u9fff]", title))
    if chinese < 2:
        return False
    junk_ratio = len(re.findall(r"[\\/@#$%^&*<>|~`]", title)) / max(len(title), 1)
    if junk_ratio > 0.15:
        return False
    return True


def _is_quality_content(content: str, min_len: int = 100, chinese_ratio: float = 0.25) -> bool:
    if not content or len(content) < min_len:
        return False
    if content.startswith("文件名:") or content.startswith("路径:") or content.startswith("来源:"):
        return False
    file_meta_count = len(re.findall(r"(文件名|路径|大小|分类):", content[:200]))
    if file_meta_count >= 2:
        return False
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
    if chinese_chars < min_len * chinese_ratio:
        return False
    noise = len(
        re.findall(r"(注册时间|最后登录|威望|金钱|阅读权限|帖子|精华\d|UID\d)", content[:300])
    )
    if noise >= 3:
        return False
    return True


def _extract_first_sentence(content: str, max_len: int = 200) -> Optional[str]:
    sentences = re.split(r"[。！？\n]", content)
    for s in sentences:
        s = s.strip()
        if len(s) > 15:
            return s[:max_len]
    return None


def _extract_meaningful_sentence(content: str, max_len: int = 200) -> Optional[str]:
    sentences = re.split(r"[。！？\n]", content)
    candidates = [s.strip() for s in sentences if 15 < len(s.strip()) <= max_len + 50]
    if not candidates:
        return None
    for s in candidates[:5]:
        chinese = len(re.findall(r"[\u4e00-\u9fff]", s))
        if chinese / max(len(s), 1) > 0.4:
            return s[:max_len]
    return candidates[0][:max_len]


class TrainingDataPipeline:
    def __init__(self, db_url: str = DB_URL, training_dir: Path = TRAINING_DIR):
        self.db_url = db_url
        self.training_dir = training_dir
        self.pool: Optional[asyncpg.Pool] = None
        self.stats: Dict[str, Any] = {}

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.db_url, min_size=2, max_size=8)
        logger.info("DB pool connected")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def run_all(self):
        logger.info("=== 微调数据准备流水线 v2 启动 ===")
        await self.connect()
        try:
            self.stats["started_at"] = datetime.now().isoformat()
            self.stats["data_sources"] = await self._audit_sources()
            self.stats["intent"] = await self.generate_intent_dataset()
            self.stats["embedding"] = await self.generate_embedding_pairs()
            self.stats["qa_benchmark"] = await self.generate_qa_benchmark()
            self.stats["completed_at"] = datetime.now().isoformat()
            await self._write_report()
            logger.info("=== 流水线完成 ===")
        finally:
            await self.close()

    async def _audit_sources(self) -> Dict[str, Any]:
        logger.info("[审计] 统计数据源...")
        sources = {}
        tables = [
            ("documents", "category"),
            ("guji_documents", "category"),
            ("textbook_knowledge", "category"),
        ]
        for table, col in tables:
            try:
                rows = await self.pool.fetch(
                    f"SELECT {col}, COUNT(*) as cnt FROM {table} GROUP BY {col}"
                )
                sources[table] = {r[col]: r["cnt"] for r in rows}
            except Exception as e:
                logger.warning(f"  跳过 {table}: {e}")
        return sources

    async def _fetch_from_documents(
        self, category: Optional[str] = None, limit: int = 5000
    ) -> List[Dict[str, Any]]:
        query = (
            "SELECT id, title, content, category FROM documents "
            "WHERE content IS NOT NULL AND length(content) > 200 "
            "AND length(title) BETWEEN 2 AND 60 "
        )
        params: list = []
        if category:
            query += " AND category = $1 ORDER BY id LIMIT $2"
            params = [category, limit]
        else:
            query += " ORDER BY id LIMIT $1"
            params = [limit]
        rows = await self.pool.fetch(query, *params)
        return [
            dict(r)
            for r in rows
            if _is_clean_title(r["title"] or "") and _is_quality_content(r["content"] or "")
        ]

    async def _fetch_from_guji(
        self, limit: int = 5000, min_content: int = 300, max_content: int = 50000
    ) -> List[Dict[str, Any]]:
        sample_pct = min(5, max(1, limit // 500))
        rows = await self.pool.fetch(
            "SELECT id, title, author, dynasty, content, category "
            "FROM guji_documents TABLESAMPLE BERNOULLI($1) "
            "WHERE content IS NOT NULL "
            "AND length(content) BETWEEN $2 AND $3 "
            "AND length(title) BETWEEN 2 AND 60 "
            "AND title ~ '[\u4e00-\u9fff]{2,}' "
            "AND title !~ '\\d{5,}' "
            "LIMIT $4",
            sample_pct,
            min_content,
            max_content,
            limit,
        )
        result = []
        for r in rows:
            d = dict(r)
            d["category"] = "古籍"
            content = d.get("content", "")
            if _is_quality_content(content, min_len=min_content):
                result.append(d)
        return result

    async def _fetch_from_textbook(self, limit: int = 3000) -> List[Dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT id, name, category, char_count FROM textbook_knowledge "
            "WHERE char_count > $1 ORDER BY id LIMIT $2",
            200,
            limit,
        )
        result = []
        for r in rows:
            d = dict(r)
            name = d.get("name", "")
            if _is_clean_title(name, max_len=80) and _is_quality_content(name, min_len=50):
                d["title"] = name
                d["content"] = name
                d["category"] = "教材"
                result.append(d)
        return result

    async def _fetch_titles_by_category(
        self, category: str, limit: int = 200, source: str = "documents"
    ) -> List[str]:
        if source == "guji":
            rows = await self.pool.fetch(
                "SELECT title FROM guji_documents TABLESAMPLE BERNOULLI(1) "
                "WHERE length(title) BETWEEN 2 AND 60 "
                "AND length(content) > 300 "
                "AND title ~ '[\u4e00-\u9fff]{2,}' "
                "AND title !~ '\\d{5,}' "
                "LIMIT $1",
                limit,
            )
        elif source == "textbook":
            rows = await self.pool.fetch(
                "SELECT name as title FROM textbook_knowledge "
                "WHERE char_count > 200 AND length(name) BETWEEN 2 AND 80 "
                "ORDER BY id LIMIT $1",
                limit,
            )
        else:
            rows = await self.pool.fetch(
                "SELECT title FROM documents WHERE category = $1 "
                "AND length(title) BETWEEN 2 AND 60 "
                "AND length(content) > 200 "
                "ORDER BY id LIMIT $2",
                category,
                limit,
            )
        return [r["title"] for r in rows if _is_clean_title(r["title"])]

    async def generate_intent_dataset(self) -> Dict[str, Any]:
        logger.info("[1/3] 生成意图分类数据集...")
        output_dir = self.training_dir / "intent_classifier"
        output_dir.mkdir(parents=True, exist_ok=True)

        samples = []

        all_titles = []
        for cat in ["气功", "中医", "儒家"]:
            titles = await self._fetch_titles_by_category(cat, 200)
            all_titles.extend([(t, cat) for t in titles])

        guji_titles = await self._fetch_titles_by_category("古籍", 300, source="guji")
        all_titles.extend([(t, "古籍") for t in guji_titles])

        textbook_titles = await self._fetch_titles_by_category("教材", 200, source="textbook")
        all_titles.extend([(t, "教材") for t in textbook_titles])

        logger.info(f"  收集到 {len(all_titles)} 个有效标题")

        for intent, cfg in INTENT_TEMPLATES.items():
            for template in cfg["templates"]:
                if "{other}" in template:
                    random.shuffle(all_titles)
                    for i in range(0, min(len(all_titles) - 1, 300), 2):
                        t1, cat1 = all_titles[i]
                        t2, cat2 = all_titles[i + 1]
                        if t1 != t2 and (cat1 != cat2 or random.random() < 0.3):
                            query = template.format(title=t1, other=t2)
                            samples.append({"query": query, "intent": intent})
                else:
                    random.shuffle(all_titles)
                    for title, cat in all_titles[:400]:
                        query = template.format(title=title)
                        samples.append({"query": query, "intent": intent})

        random.shuffle(samples)
        split_idx = int(len(samples) * 0.8)
        train = samples[:split_idx]
        test = samples[split_idx:]

        self._write_jsonl(output_dir / "train.jsonl", train)
        self._write_jsonl(output_dir / "test.jsonl", test)

        intents_yaml = self._generate_intents_yaml()
        (output_dir / "intents.yaml").write_text(intents_yaml, encoding="utf-8")

        intent_counts = {}
        for s in samples:
            intent_counts[s["intent"]] = intent_counts.get(s["intent"], 0) + 1

        stats = {
            "total": len(samples),
            "train": len(train),
            "test": len(test),
            "intent_distribution": intent_counts,
        }
        logger.info(
            f"  意图数据集: {stats['total']} 条 (train={stats['train']}, test={stats['test']})"
        )
        return stats

    async def generate_embedding_pairs(self) -> Dict[str, Any]:
        logger.info("[2/3] 生成嵌入微调样本对...")
        output_dir = self.training_dir / "embedding_pairs"
        output_dir.mkdir(parents=True, exist_ok=True)

        pairs = []

        for cat in ["气功", "中医", "儒家"]:
            docs = await self._fetch_from_documents(category=cat, limit=500)
            for i, doc in enumerate(docs):
                content = doc["content"]
                title = doc["title"]
                if not _is_quality_content(content, 50):
                    continue

                anchor = title if _is_clean_title(title) else content[:80]
                positive = content[:400]
                pairs.append(
                    {
                        "anchor": anchor,
                        "positive": positive,
                        "category": cat,
                        "doc_id": doc["id"],
                        "source": "documents",
                        "pair_type": "title_content",
                    }
                )

                if i > 0 and i % 3 == 0:
                    prev = docs[i - 1]
                    prev_content = prev.get("content", "")
                    if _is_quality_content(prev_content, 50):
                        pairs.append(
                            {
                                "anchor": content[:400],
                                "positive": prev_content[:400],
                                "category": cat,
                                "doc_id": doc["id"],
                                "source": "documents",
                                "pair_type": "same_category",
                            }
                        )

        guji_docs = await self._fetch_from_guji(limit=2000, min_content=300)
        logger.info(f"  古籍高质量文档: {len(guji_docs)}")
        for doc in guji_docs:
            title = doc["title"]
            content = doc["content"]
            author_info = ""
            if doc.get("author"):
                author_info = f"（{doc['author']}"
                if doc.get("dynasty"):
                    author_info += f"，{doc['dynasty']}"
                author_info += "）"
            anchor = title
            positive = content[:400]
            pairs.append(
                {
                    "anchor": anchor,
                    "positive": positive,
                    "category": "古籍",
                    "doc_id": doc["id"],
                    "source": "guji_documents",
                    "pair_type": "title_content",
                }
            )

        textbook_docs = await self._fetch_from_textbook(limit=2000)
        logger.info(f"  教材高质量条目: {len(textbook_docs)}")
        for doc in textbook_docs:
            title = doc["title"]
            content = doc["content"]
            pairs.append(
                {
                    "anchor": title[:80],
                    "positive": content[:400],
                    "category": "教材",
                    "doc_id": doc["id"],
                    "source": "textbook_knowledge",
                    "pair_type": "title_content",
                }
            )

        neg_pairs = await self._generate_hard_negatives()

        random.shuffle(pairs)
        random.shuffle(neg_pairs)

        split_idx = int(len(pairs) * 0.9)
        train_pairs = pairs[:split_idx]
        val_pairs = pairs[split_idx:]

        self._write_jsonl(output_dir / "train_pairs.jsonl", train_pairs)
        self._write_jsonl(output_dir / "val_pairs.jsonl", val_pairs)
        self._write_jsonl(output_dir / "hard_negatives.jsonl", neg_pairs)

        stats = {
            "positive_pairs": len(pairs),
            "train_pairs": len(train_pairs),
            "val_pairs": len(val_pairs),
            "hard_negatives": len(neg_pairs),
            "sources": {
                "documents": sum(1 for p in pairs if p.get("source") == "documents"),
                "guji_documents": sum(1 for p in pairs if p.get("source") == "guji_documents"),
                "textbook_knowledge": sum(
                    1 for p in pairs if p.get("source") == "textbook_knowledge"
                ),
            },
        }
        logger.info(
            f"  嵌入样本对: {stats['positive_pairs']} 正例 + {stats['hard_negatives']} 负例"
        )
        return stats

    async def _generate_hard_negatives(self, target: int = 1000) -> List[Dict]:
        logger.info("  生成跨领域硬负例...")
        neg_pairs = []

        domain_pairs = [
            ("气功", "古籍"),
            ("中医", "古籍"),
            ("儒家", "古籍"),
            ("教材", "古籍"),
            ("气功", "教材"),
            ("中医", "教材"),
            ("儒家", "教材"),
            ("气功", "中医"),
            ("中医", "儒家"),
        ]

        for cat_a, cat_b in domain_pairs:
            docs_a = (
                await self._fetch_from_documents(category=cat_a, limit=100)
                if cat_a in ("气功", "中医", "儒家")
                else []
            )
            if cat_a == "古籍":
                docs_a = await self._fetch_from_guji(limit=100)
            elif cat_a == "教材":
                docs_a = await self._fetch_from_textbook(limit=100)

            if cat_b in ("气功", "中医", "儒家"):
                docs_b = await self._fetch_from_documents(category=cat_b, limit=100)
            elif cat_b == "古籍":
                docs_b = await self._fetch_from_guji(limit=100)
            else:
                docs_b = await self._fetch_from_textbook(limit=100)

            quality_a = [
                d
                for d in docs_a
                if _is_quality_content(d.get("content", ""), 50)
                and _is_clean_title(d.get("title", ""))
            ][:20]
            candidates_b = [d for d in docs_b if len(d.get("content", "")) > 50]

            for da in quality_a:
                anchor = da["title"]
                sample_size = min(3, len(candidates_b))
                if sample_size == 0:
                    continue
                for db in random.sample(candidates_b, sample_size):
                    neg_pairs.append(
                        {
                            "anchor": anchor,
                            "negative": db["content"][:300],
                            "category_anchor": cat_a,
                            "category_negative": cat_b,
                            "pair_type": "cross_domain_hard_negative",
                        }
                    )

        random.shuffle(neg_pairs)
        return neg_pairs[:target]

    async def generate_qa_benchmark(self) -> Dict[str, Any]:
        logger.info("[3/3] 生成 RAG 问答评估基准...")
        output_dir = self.training_dir / "qa_benchmark"
        output_dir.mkdir(parents=True, exist_ok=True)

        qa_pairs = []

        for cat in ["气功", "中医", "儒家"]:
            docs = await self._fetch_from_documents(category=cat, limit=500)
            for doc in docs:
                title = doc["title"]
                content = doc["content"]
                if not _is_clean_title(title):
                    continue
                if not _is_quality_content(content, 100):
                    continue
                answer = _extract_meaningful_sentence(content)
                if not answer:
                    continue

                qa_pairs.append(
                    {
                        "query": f"什么是{title}",
                        "answer": answer,
                        "doc_id": doc["id"],
                        "category": cat,
                        "source": "documents",
                        "source_title": title,
                    }
                )
                qa_pairs.append(
                    {
                        "query": f"{title}是什么",
                        "answer": answer,
                        "doc_id": doc["id"],
                        "category": cat,
                        "source": "documents",
                        "source_title": title,
                    }
                )

                if len(content) > 500:
                    mid_answer = _extract_meaningful_sentence(content[len(content) // 3 :])
                    if mid_answer:
                        qa_pairs.append(
                            {
                                "query": f"请详细介绍{title}",
                                "answer": mid_answer,
                                "doc_id": doc["id"],
                                "category": cat,
                                "source": "documents",
                                "source_title": title,
                            }
                        )

        guji_docs = await self._fetch_from_guji(limit=2000, min_content=300)
        for doc in guji_docs:
            title = doc["title"]
            content = doc["content"]
            answer = _extract_meaningful_sentence(content)
            if not answer:
                continue

            author_tag = ""
            if doc.get("author"):
                author_tag = f"（{doc['author']}）"

            qa_pairs.append(
                {
                    "query": f"什么是{title}",
                    "answer": answer,
                    "doc_id": doc["id"],
                    "category": "古籍",
                    "source": "guji_documents",
                    "source_title": title,
                }
            )
            qa_pairs.append(
                {
                    "query": (
                        f"{title}{author_tag}的内容是什么" if author_tag else f"{title}讲了什么"
                    ),
                    "answer": answer,
                    "doc_id": doc["id"],
                    "category": "古籍",
                    "source": "guji_documents",
                    "source_title": title,
                }
            )

        textbook_docs = await self._fetch_from_textbook(limit=2000)
        for doc in textbook_docs:
            title = doc["title"]
            content = doc["content"]
            if len(content) < 50:
                continue
            qa_pairs.append(
                {
                    "query": f"什么是{title}",
                    "answer": content[:200],
                    "doc_id": doc["id"],
                    "category": "教材",
                    "source": "textbook_knowledge",
                    "source_title": title,
                }
            )

        random.shuffle(qa_pairs)
        split_idx = int(len(qa_pairs) * 0.8)
        train_qa = qa_pairs[:split_idx]
        test_qa = qa_pairs[split_idx:]

        self._write_jsonl(output_dir / "train_qa.jsonl", train_qa)
        self._write_jsonl(output_dir / "test_qa.jsonl", test_qa)

        category_counts = {}
        source_counts = {}
        for q in qa_pairs:
            category_counts[q["category"]] = category_counts.get(q["category"], 0) + 1
            source_counts[q["source"]] = source_counts.get(q["source"], 0) + 1

        stats = {
            "total": len(qa_pairs),
            "train": len(train_qa),
            "test": len(test_qa),
            "category_distribution": category_counts,
            "source_distribution": source_counts,
        }
        logger.info(
            f"  问答基准: {stats['total']} 条 (train={stats['train']}, test={stats['test']})"
        )
        return stats

    def _generate_intents_yaml(self) -> str:
        lines = ["intents:"]
        for intent, cfg in INTENT_TEMPLATES.items():
            lines.append(f"  {intent}:")
            lines.append(f"    keywords: {json.dumps(cfg['keywords'], ensure_ascii=False)}")
            lines.append(f"    templates: {json.dumps(cfg['templates'], ensure_ascii=False)}")
        return "\n".join(lines)

    @staticmethod
    def _write_jsonl(path: Path, records: List[Dict]):
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    async def _write_report(self):
        report = {
            "pipeline": "training_data_preparation",
            "version": "2.0.0",
            "generated_at": datetime.now().isoformat(),
            "stats": self.stats,
        }
        report_path = self.training_dir / "pipeline_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"报告已写入: {report_path}")

        s = self.stats
        print("\n" + "=" * 60)
        print("  微调数据准备流水线 v2 — 完成报告")
        print("=" * 60)

        if "data_sources" in s:
            print("  数据源:")
            for table, cats in s["data_sources"].items():
                total = sum(cats.values())
                print(f"    {table}: {total} 条 ({', '.join(f'{k}={v}' for k, v in cats.items())})")

        print(f"\n  意图分类: {s['intent']['total']} 条")
        print(f"    ├─ 训练集: {s['intent']['train']}")
        print(f"    └─ 测试集: {s['intent']['test']}")
        print(f"  嵌入样本: {s['embedding']['positive_pairs']} 正例")
        print(f"    ├─ 训练对: {s['embedding']['train_pairs']}")
        print(f"    ├─ 验证对: {s['embedding']['val_pairs']}")
        print(f"    └─ 负例:   {s['embedding']['hard_negatives']}")
        if "sources" in s["embedding"]:
            print(f"    数据来源: {s['embedding']['sources']}")
        print(f"  问答基准: {s['qa_benchmark']['total']} 条")
        print(f"    ├─ 训练集: {s['qa_benchmark']['train']}")
        print(f"    └─ 测试集: {s['qa_benchmark']['test']}")
        if "source_distribution" in s["qa_benchmark"]:
            print(f"    数据来源: {s['qa_benchmark']['source_distribution']}")
        print(f"\n  输出目录: {self.training_dir}/")
        print("=" * 60)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    pipeline = TrainingDataPipeline()
    await pipeline.run_all()


if __name__ == "__main__":
    asyncio.run(main())
