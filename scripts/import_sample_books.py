"""导入示例书籍数据

直接使用asyncpg导入数据，避免复杂的导入问题
"""
import asyncio
import os


async def import_sample_books():
    """导入示例书籍数据"""
    from backend.core.database import init_db_pool

    print("=== 开始导入示例书籍数据 ===\n")

    # 初始化数据库连接池
    pool = await init_db_pool()

    try:
        async with pool.acquire() as conn:
            # 获取本地数据源ID
            source_row = await conn.fetchrow(
                "SELECT id FROM data_sources WHERE code = 'local'"
            )
            if not source_row:
                print("❌ 未找到本地数据源")
                return

            source_id = source_row['id']
            print(f"✅ 使用数据源ID: {source_id}")

            # 示例书籍数据
            sample_books = [
                {
                    "title": "周易注疏",
                    "author": "王弼",
                    "category": "儒家",
                    "dynasty": "魏晋",
                    "year": "三国",
                    "description": "《周易》是中国古代最重要的哲学著作之一，王弼注疏是其经典注本。",
                },
                {
                    "title": "黄帝内经素问",
                    "author": "佚名",
                    "category": "中医",
                    "dynasty": "先秦",
                    "year": "战国",
                    "description": "《黄帝内经》是中国最早的医学典籍，奠定了中医学理论基础。",
                },
                {
                    "title": "道德经",
                    "author": "老子",
                    "category": "气功",
                    "dynasty": "春秋",
                    "year": "公元前6世纪",
                    "description": "《道德经》是道家哲学的经典著作，对气功修炼有重要指导意义。",
                },
                {
                    "title": "论语",
                    "author": "孔子",
                    "category": "儒家",
                    "dynasty": "春秋",
                    "year": "公元前5世纪",
                    "description": "《论语》是儒家学派的经典著作，记录了孔子及其弟子的言行。",
                },
                {
                    "title": "伤寒杂病论",
                    "author": "张仲景",
                    "category": "中医",
                    "dynasty": "东汉",
                    "year": "公元2世纪",
                    "description": "《伤寒杂病论》是中医临床医学的经典著作，确立了辨证论治体系。",
                },
                {
                    "title": "庄子",
                    "author": "庄周",
                    "category": "气功",
                    "dynasty": "战国",
                    "year": "公元前4世纪",
                    "description": "《庄子》是道家经典著作，包含丰富的气功修炼和养生思想。",
                },
                {
                    "title": "孟子",
                    "author": "孟子",
                    "category": "儒家",
                    "dynasty": "战国",
                    "year": "公元前4世纪",
                    "description": "《孟子》是儒家经典，继承和发展了孔子的思想。",
                },
                {
                    "title": "神农本草经",
                    "author": "佚名",
                    "category": "中医",
                    "dynasty": "东汉",
                    "year": "公元1-2世纪",
                    "description": "《神农本草经》是中国最早的药物学经典。",
                }
            ]

            # 插入书籍
            book_ids = []
            for book_data in sample_books:
                book_id = await conn.fetchval(
                    """
                    INSERT INTO books (title, author, category, dynasty, year, description, language, has_content, total_chars, source_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (title) DO UPDATE SET author = EXCLUDED.author
                    RETURNING id
                    """,
                    book_data['title'],
                    book_data['author'],
                    book_data['category'],
                    book_data['dynasty'],
                    book_data['year'],
                    book_data['description'],
                    'zh',
                    True,
                    50000,
                    source_id
                )
                book_ids.append(book_id)
                print(f"✅ 插入书籍: {book_data['title']} (ID: {book_id})")

            # 为前3本书添加示例章节
            print(f"\n--- 添加章节 ---")
            for book_id in book_ids[:3]:
                for j in range(1, 4):  # 每本书3个章节
                    chapter_title = f"第{j}章"
                    chapter_content = f"""
这是{chapter_title}的详细内容。

本章主要讲解了核心理论和实践方法。通过深入浅出的方式，阐述了重要的概念和原理。

内容包括：
- 基本概念的界定
- 理论框架的构建
- 实践方法的具体操作

这些内容对于理解和掌握相关知识具有重要意义。
                    """.strip()

                    chapter_id = await conn.fetchval(
                        """
                        INSERT INTO book_chapters (book_id, chapter_num, title, content, char_count, order_position)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT DO NOTHING
                        RETURNING id
                        """,
                        book_id, j, chapter_title, chapter_content, len(chapter_content), j
                    )
                    print(f"  ✅ 书籍 {book_id}: 添加章节 '{chapter_title}' (ID: {chapter_id})")

            # 统计
            total_books = await conn.fetchval("SELECT COUNT(*) FROM books")
            total_chapters = await conn.fetchval("SELECT COUNT(*) FROM book_chapters")

        print(f"\n=== 导入完成 ===")
        print(f"书籍总数: {total_books}")
        print(f"章节总数: {total_chapters}")

    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await pool.close()


async def generate_embeddings():
    """为书籍生成向量嵌入"""
    from backend.core.database import init_db_pool
    from backend.services.retrieval.vector import _get_model, _MODEL_DIM

    print("\n=== 生成向量嵌入 ===")

    pool = await init_db_pool()

    try:
        # 加载模型
        print("加载BGE模型...")
        model = await _get_model()
        print(f"✅ 模型加载成功，向量维度: {_MODEL_DIM}")

        async with pool.acquire() as conn:
            # 获取所有没有向量的书籍
            rows = await conn.fetch(
                "SELECT id, title, description FROM books WHERE embedding IS NULL"
            )

        total = len(rows)
        print(f"需要生成向量的书籍: {total} 本")

        if total == 0:
            print("✅ 所有书籍已有向量")
            return

        # 生成向量
        import asyncio
        loop = asyncio.get_event_loop()

        updated = 0
        for row in rows:
            try:
                # 组合文本
                text = f"{row['title']}\n{row['description'] or ''}"

                # 生成向量
                def _encode():
                    return model.encode(text, normalize_embeddings=True).tolist()

                embedding = await loop.run_in_executor(None, _encode)
                vector_str = "[" + ",".join(map(str, embedding)) + "]"

                # 更新数据库
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE books SET embedding = $1::vector WHERE id = $2",
                        vector_str, row['id']
                    )
                updated += 1
                print(f"✅ [{updated}/{total}] {row['title']}")

            except Exception as e:
                print(f"❌ {row['title']}: {e}")

        async with pool.acquire() as conn:
            with_embedding = await conn.fetchval("SELECT COUNT(*) FROM books WHERE embedding IS NOT NULL")

        print(f"\n向量生成完成: {updated}/{total}")
        print(f"总计有向量的书籍: {with_embedding}")

    except Exception as e:
        print(f"❌ 生成向量失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await pool.close()


async def main():
    """主函数"""
    # 导入书籍数据
    await import_sample_books()

    # 生成向量嵌入
    await generate_embeddings()


if __name__ == "__main__":
    asyncio.run(main())
