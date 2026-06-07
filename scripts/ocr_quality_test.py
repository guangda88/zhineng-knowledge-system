#!/usr/bin/env python3
"""何氏医著 OCR 质量验证脚本

用 PaddleOCR PP-OCRv4 (2.7.3) 对钞本样本页验证竖排繁体识别效果。
"""
import sys
import time
from pathlib import Path

SAMPLES = [
    ("/tmp/ocr_sample_xulao-05.png", "何氏虛勞心傳 p5（清·何炫，钞本）"),
    ("/tmp/ocr_sample_sanhe-03.png", "重古三何醫案 p3（清，石印本）"),
]


def main():
    try:
        from paddleocr import PaddleOCR
    except ImportError as e:
        print(f"[ERROR] paddleocr 未安装: {e}")
        sys.exit(1)

    print("[INFO] 初始化 PaddleOCR PP-OCRv4 (lang=ch, use_angle_cls=True)...")
    t0 = time.time()
    ocr = PaddleOCR(
        lang="ch",
        use_angle_cls=True,
    )
    print(f"[INFO] 模型初始化完成，耗时 {time.time()-t0:.1f}s\n")

    for img_path, label in SAMPLES:
        if not Path(img_path).exists():
            print(f"[SKIP] {img_path} 不存在\n")
            continue

        print(f"{'='*60}")
        print(f"样本: {label}")
        print(f"文件: {img_path}")
        print(f"{'='*60}")

        t1 = time.time()
        result = ocr.ocr(img_path, cls=True)
        elapsed = time.time() - t1

        if not result or not result[0]:
            print(f"[WARN] 未识别到任何文本 (耗时 {elapsed:.1f}s)\n")
            continue

        lines = result[0]
        print(f"\n[结果] 识别到 {len(lines)} 个文本块 (耗时 {elapsed:.1f}s)\n")

        texts = []
        for i, line in enumerate(lines):
            box, (text, conf) = line
            texts.append(text)
            print(f"  [{i+1:2d}] (置信度={conf:.3f}) {text}")

        total_chars = sum(len(t) for t in texts)
        print(f"\n[统计] 总字数={total_chars} | 文本块={len(lines)} | 耗时={elapsed:.1f}s")

        full_text = "".join(texts)
        garbled = sum(1 for c in full_text if ord(c) < 0x4e00 and c not in "，。、：；！？「」（）()0123456789")
        garbled_ratio = garbled / max(len(full_text), 1)
        print(f"[质量] 总字符={len(full_text)} 非汉字={garbled} ({garbled_ratio:.1%})\n")

        out_file = img_path.replace(".png", "_ocr.txt")
        with open(out_file, "w") as f:
            f.write(f"# {label}\n# 字数={total_chars} 块数={len(lines)} 耗时={elapsed:.1f}s\n\n")
            for i, line in enumerate(lines):
                _, (text, conf) = line
                f.write(f"[{i+1}] ({conf:.3f}) {text}\n")
        print(f"[SAVED] {out_file}\n")


if __name__ == "__main__":
    main()
