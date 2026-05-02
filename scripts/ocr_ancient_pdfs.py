#!/usr/bin/env python3
"""
PDF OCR 处理脚本 (RapidOCR + GPU/CPU)

将扫描版 PDF 转为文本，支持古籍竖排、繁体字。
用法:
    python scripts/ocr_ancient_pdfs.py data/susong_import/道光本/GJ27471-1.pdf
    python scripts/ocr_ancient_pdfs.py data/susong_import/道光本/*.pdf --save-text
    python scripts/ocr_ancient_pdfs.py --all    # 处理所有待OCR的文件
"""

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_DSN = "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
DPI = 300


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pdf_to_images(pdf_path, output_dir, dpi=300):
    """Convert PDF pages to images using pdftoppm."""
    prefix = Path(pdf_path).stem
    cmd = [
        "pdftoppm", "-png", "-r", str(dpi),
        pdf_path, os.path.join(output_dir, prefix)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"pdftoppm failed: {result.stderr}")

    images = sorted(Path(output_dir).glob(f"{prefix}*.png"))
    return [str(img) for img in images]


def ocr_images(images, use_gpu=True):
    """OCR images using RapidOCR (based on PaddleOCR models via ONNX Runtime)."""
    import cv2
    from rapidocr_onnxruntime import RapidOCR

    r = RapidOCR()

    all_text = []
    for i, img_path in enumerate(images):
        img = cv2.imread(img_path)
        result, elapse = r(img)
        page_lines = []
        if result:
            for line in result:
                text = line[1]
                confidence = line[2]
                if confidence > 0.5 and text.strip():
                    page_lines.append(text.strip())
        page_text = "\n".join(page_lines)
        all_text.append(page_text)
        if (i + 1) % 10 == 0:
            log(f"  OCR'd {i+1}/{len(images)} pages")

    return "\n\n".join(all_text)


def ocr_pdf(pdf_path, use_gpu=True):
    """Full pipeline: PDF -> images -> OCR -> text."""
    log(f"Processing: {pdf_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        log(f"  Converting to images (DPI={DPI})...")
        images = pdf_to_images(pdf_path, tmpdir, dpi=DPI)
        log(f"  Got {len(images)} pages")

        if not images:
            log(f"  No images extracted from {pdf_path}")
            return None

        log(f"  Running OCR on {len(images)} pages...")
        text = ocr_images(images, use_gpu=use_gpu)

    char_count = len(text)
    log(f"  Done: {char_count} chars from {len(images)} pages")
    return text


async def import_to_db(title, content, category, tags):
    """Insert OCR result into database."""
    import asyncpg

    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)
    try:
        doc_id = await pool.fetchval(
            """INSERT INTO documents (title, content, category, tags)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT DO NOTHING
               RETURNING id""",
            title, content, category, tags
        )
        return doc_id
    finally:
        await pool.close()


# All ancient book PDFs that need OCR
ANCIENT_BOOKS = [
    {
        "path": "data/susong_import/道光本/GJ27471-1.pdf",
        "title": "苏魏公文集·道光本·第1册(卷前~目录)",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "道光本"],
    },
    {
        "path": "data/susong_import/道光本/GJ27471-2.pdf",
        "title": "苏魏公文集·道光本·第2册",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "道光本"],
    },
    {
        "path": "data/susong_import/陆抄本/GJ08055-1.pdf",
        "title": "苏魏公文集·陆抄本·第1册",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "陆抄本"],
    },
    {
        "path": "data/susong_import/陆抄本/GJ08055-2.pdf",
        "title": "苏魏公文集·陆抄本·第2册",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "陆抄本"],
    },
    {
        "path": "data/susong_import/目录_苏魏公文集.pdf",
        "title": "苏魏公文集目录",
        "category": "儒家",
        "tags": ["苏颂研究", "苏魏公文集", "目录"],
    },
    {
        "path": "data/susong_import/苏颂年表.pdf",
        "title": "苏颂年表",
        "category": "哲学",
        "tags": ["苏颂研究", "生平年考", "年表"],
    },
]

# Scanned research PDFs that need OCR
SCANNED_PAPERS = [
    {
        "path": "data/susong_import/天文科技/略论苏颂的政治生涯.pdf",
        "title": "略论苏颂的政治生涯",
        "category": "哲学",
        "tags": ["苏颂研究", "政治思想"],
    },
    {
        "path": "data/susong_import/天文科技/宰相科学家——苏颂.pdf",
        "title": "宰相科学家——苏颂",
        "category": "科学",
        "tags": ["苏颂研究", "天文科技"],
    },
]


async def process_all(do_import=True, use_gpu=True):
    """Process all pending OCR files."""
    all_files = ANCIENT_BOOKS + SCANNED_PAPERS
    stats = {"total": 0, "success": 0, "failed": 0}

    for entry in all_files:
        path = entry["path"]
        if not os.path.exists(path):
            log(f"  SKIP (not found): {path}")
            continue

        stats["total"] += 1
        try:
            text = ocr_pdf(path, use_gpu=use_gpu)
            if not text or len(text.strip()) < 50:
                log(f"  SKIP (too short): {entry['title']}")
                continue

            stats["success"] += 1

            if do_import:
                doc_id = await import_to_db(
                    entry["title"], text, entry["category"], entry["tags"]
                )
                log(f"  IMPORTED: {entry['title']} -> ID {doc_id} ({len(text)} chars)")
            else:
                log(f"  OCR OK: {entry['title']} ({len(text)} chars) [dry run]")

                # Save OCR text to file
                out_path = path.rsplit(".", 1)[0] + ".ocr.txt"
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                log(f"  Saved to: {out_path}")

        except Exception as e:
            log(f"  FAILED: {entry['title']} - {e}")
            stats["failed"] += 1

    log(f"\nTOTAL: {stats['success']}/{stats['total']} OK, {stats['failed']} failed")


def main():
    parser = argparse.ArgumentParser(description="OCR ancient book PDFs")
    parser.add_argument("files", nargs="*", help="PDF files to OCR")
    parser.add_argument("--all", action="store_true", help="Process all pending OCR files")
    parser.add_argument("--no-import", action="store_true", help="OCR only, don't import to DB")
    parser.add_argument("--no-gpu", action="store_true", help="Use CPU only")
    parser.add_argument("--save-text", action="store_true", help="Save OCR text alongside PDFs")
    args = parser.parse_args()

    use_gpu = not args.no_gpu
    do_import = not args.no_import

    log("OCR Ancient Book PDFs (RapidOCR)")

    if args.all:
        asyncio.run(process_all(do_import=do_import, use_gpu=use_gpu))
    elif args.files:
        for pdf_path in args.files:
            try:
                text = ocr_pdf(pdf_path, use_gpu=use_gpu)
                if text:
                    if do_import:
                        title = Path(pdf_path).stem
                        doc_id = asyncio.run(import_to_db(
                            title, text, "儒家", ["苏颂研究", "OCR"]
                        ))
                        log(f"  IMPORTED: {title} -> ID {doc_id}")
                    if args.save_text or not do_import:
                        out_path = pdf_path.rsplit(".", 1)[0] + ".ocr.txt"
                        with open(out_path, "w", encoding="utf-8") as f:
                            f.write(text)
                        log(f"  Saved: {out_path}")
            except Exception as e:
                log(f"  FAILED: {pdf_path} - {e}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
