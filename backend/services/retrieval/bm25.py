"""
BM25 关键词检索服务模块
遵循开发规则：异步优先、类型注解、错误处理
"""
import re
import math
import logging
from typing import List, Dict, Any, Optional, Set
from collections import Counter, defaultdict
import asyncpg

logger = logging.getLogger(__name__)


class BM25Retriever:
    """
    BM25 关键词检索服务
    
    使用 BM25 算法进行相关性排序的关键词搜索
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        k1: float = 1.2,
        b: float = 0.75
    ):
        """
        初始化BM25检索器
        
        Args:
            db_pool: 数据库连接池
            k1: 词频饱和参数
            b: 长度归一化参数
        """
        self.db_pool = db_pool
        self.k1 = k1
        self.b = b
        self.doc_count: int = 0
        self.doc_lengths: Dict[int, int] = {}
        self.avg_doc_length: float = 0.0
        self.document_frequencies: Dict[str, int] = {}
    
    async def initialize(self) -> None:
        """初始化索引统计"""
        async with self.db_pool.acquire() as conn:
            # 获取文档数量
            self.doc_count = await conn.fetchval(
                "SELECT COUNT(*) FROM documents"
            )
            
            # 获取文档长度
            rows = await conn.fetch(
                "SELECT id, title, content FROM documents"
            )
            
            total_length = 0
            for row in rows:
                text = f"{row['title']} {row['content']}"
                words = self._tokenize(text)
                length = len(words)
                self.doc_lengths[row['id']] = length
                total_length += length
            
            self.avg_doc_length = total_length / self.doc_count if self.doc_count > 0 else 0
            
            # 计算文档频率
            word_docs: Dict[str, Set[int]] = defaultdict(set)
            for row in rows:
                text = f"{row['title']} {row['content']}"
                words = set(self._tokenize(text))
                for word in words:
                    word_docs[word].add(row['id'])
            
            self.document_frequencies = {
                word: len(doc_ids) for word, doc_ids in word_docs.items()
            }
        
        logger.info(f"BM25索引初始化完成: {self.doc_count}个文档, 平均长度={self.avg_doc_length:.1f}")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        中文分词（简单实现）
        
        Args:
            text: 输入文本
        
        Returns:
            分词列表
        """
        # 简单按空格和标点分词
        # 生产环境建议使用 jieba 等专业分词工具
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        words = text.lower().split()
        return [w for w in words if len(w) > 1]
    
    def _idf(self, word: str) -> float:
        """
        计算逆文档频率
        
        Args:
            word: 词语
        
        Returns:
            IDF值
        """
        df = self.document_frequencies.get(word, 0)
        if df == 0:
            return 0.0
        return math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
    
    def _score(
        self,
        query_words: List[str],
        doc_id: int,
        doc_text: str
    ) -> float:
        """
        计算BM25得分
        
        Args:
            query_words: 查询词列表
            doc_id: 文档ID
            doc_text: 文档文本
        
        Returns:
            BM25得分
        """
        doc_words = self._tokenize(doc_text)
        doc_length = len(doc_words)
        word_counts = Counter(doc_words)
        
        score = 0.0
        for word in query_words:
            if word not in word_counts:
                continue
            
            tf = word_counts[word]
            idf = self._idf(word)
            
            # BM25公式
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_length / self.avg_doc_length)
            )
            score += idf * (numerator / denominator)
        
        return score
    
    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        BM25关键词搜索
        
        Args:
            query: 查询文本
            category: 分类筛选
            top_k: 返回数量
        
        Returns:
            检索结果列表
        """
        if self.doc_count == 0:
            await self.initialize()
        
        # 分词
        query_words = self._tokenize(query)
        if not query_words:
            return []
        
        # 获取候选文档
        async with self.db_pool.acquire() as conn:
            if category:
                rows = await conn.fetch(
                    """SELECT id, title, content, category
                       FROM documents
                       WHERE category = $1""",
                    category
                )
            else:
                rows = await conn.fetch(
                    """SELECT id, title, content, category
                       FROM documents"""
                )
        
        # 计算得分
        scores = []
        for row in rows:
            text = f"{row['title']} {row['content']}"
            score = self._score(query_words, row['id'], text)
            
            # 只保留有匹配的结果
            if score > 0:
                scores.append({
                    'id': row['id'],
                    'title': row['title'],
                    'content': row['content'],
                    'category': row['category'],
                    'score': score,
                    'method': 'bm25'
                })
        
        # 排序并返回top_k
        scores.sort(key=lambda x: x['score'], reverse=True)
        results = scores[:top_k]
        
        logger.info(f"BM25搜索: query='{query}', found={len(results)}")
        return results
