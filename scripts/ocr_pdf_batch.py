#!/usr/bin/env python3
"""OCR批量提取PDF全文 — PaddleOCR繁体竖排 (宿主机.venv-ocr)
用法: python3 scripts/ocr_pdf_batch.py <pdf_path> <output_txt>
"""
import sys
import os
import time

os.environ.setdefault("FLAGS_call_stack_level", "0")

import fitz
from paddleocr import PaddleOCR


def ocr_pdf(pdf_path, output_path):
    t0 = time.time()
    ocr = PaddleOCR(use_angle_cls=True, lang="chinese_cht", show_log=False)
    t1 = time.time()
    print(f"Model init: {t1 - t0:.1f}s")

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    print(f"PDF: {pdf_path} ({total_pages} pages)")

    all_text = []
    total_lines = 0
    total_chars = 0

    for page_idx in range(total_pages):
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=300)
        img_path = f"/tmp/ocr_page_{page_idx}.png"
        pix.save(img_path)

        result = ocr.ocr(img_path, cls=True)
        os.remove(img_path)

        page_lines = []
        if result:
            for pr in result:
                if pr is None:
                    continue
                for line in pr:
                    box, (text, conf) = line
                    if text.strip():
                        page_lines.append(text.strip())

        page_text = "\n".join(page_lines)
        all_text.append(f"--- Page {page_idx + 1} ---\n{page_text}")
        total_lines += len(page_lines)
        total_chars += len(page_text)

        if (page_idx + 1) % 5 == 0 or page_idx + 1 == total_pages:
            elapsed = time.time() - t1
            speed = (page_idx + 1) / elapsed
            eta = (total_pages - page_idx - 1) / speed
            print(f"  {page_idx + 1}/{total_pages} pages | "
                  f"{total_lines} lines | {total_chars} chars | "
                  f"{speed:.1f}pg/s | ETA {eta:.0f}s")

    doc.close()

    header = (
        f"OCR提取结果\n"
        f"来源: {os.path.basename(pdf_path)}\n"
        f"页数: {total_pages}\n"
        f"识别行数: {total_lines}\n"
        f"识别字符: {total_chars}\n"
        f"工具: PaddleOCR chinese_cht DPI=300\n\n"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(all_text))

    elapsed = time.time() - t0
    print(f"\nDone: {total_pages} pages, {total_lines} lines, {total_chars} chars in {elapsed:.0f}s")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/ocr_pdf_batch.py <pdf_path> <output_txt>")
        sys.exit(1)
    ocr_pdf(sys.argv[1], sys.argv[2])
