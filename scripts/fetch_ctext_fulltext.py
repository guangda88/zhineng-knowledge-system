#!/usr/bin/env python3
"""从ctext下载何氏医著全文并保存为纯文本

ctext.org 对直接 urllib 403，需要先访问首页获取 session cookies。
"""
import http.cookiejar
import re
import sys
import time
import urllib.request


def fetch_ctext(chapter_id, title, author, outpath):
    """从ctext获取章节全文"""
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )
    opener.addheaders = [
        ('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0'),
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
        ('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8'),
    ]

    # Step 1: 先访问首页获取 cookies
    print(f"[{title}] 访问 ctext 首页获取 session...")
    try:
        opener.open('https://ctext.org/', timeout=15)
    except Exception as e:
        print(f"  首页访问失败（继续尝试）: {e}")

    time.sleep(1)

    # Step 2: 访问目标页面
    url = f'https://ctext.org/wiki.pl?if=gb&chapter={chapter_id}&remap=gb'
    print(f"[{title}] 获取全文: {url}")
    resp = opener.open(url, timeout=30)
    html = resp.read().decode('utf-8')
    print(f"  HTML 大小: {len(html)} 字符")

    # Step 3: 提取正文 (ctext 正文在 td class="ctext" 中)
    blocks = re.findall(r'<td[^>]*class="ctext"[^>]*>(.*?)</td>', html, re.S)
    print(f"  提取到 {len(blocks)} 个文本块")

    if not blocks:
        # fallback: 尝试提取所有可能的文本块
        blocks = re.findall(r'<td[^>]*>(.*?)</td>', html, re.S)
        print(f"  fallback: 提取到 {len(blocks)} 个 td 块")

    lines = []
    for block in blocks:
        clean = re.sub(r'<[^>]+>', '', block).strip()
        clean = clean.replace('&amp;', '&').replace('&lt;', '<')
        clean = clean.replace('&gt;', '>').replace('&nbsp;', ' ')
        clean = clean.replace('&quot;', '"')
        if clean and len(clean) > 1:
            lines.append(clean)

    full_text = '\n\n'.join(lines)
    total_chars = len(full_text)

    # Step 4: 保存
    with open(outpath, 'w') as f:
        f.write(f"{title}\n")
        f.write(f"作者：{author}\n")
        f.write(f"来源：ctext.org (ctp:ws{chapter_id}, OCR自动识别)\n")
        f.write(f"字数：约{total_chars}字\n\n")
        f.write(full_text)

    print(f"  ✅ 已保存: {outpath} ({total_chars}字)")
    return total_chars


if __name__ == '__main__':
    books = [
        # (chapter_id, title, author, outpath)
        ('608522', '何氏虛勞心傳', '清·何炫',
         'data/books/何氏医著/何氏虛勞心傳_ctext全文.txt'),
    ]

    for ch_id, title, author, path in books:
        try:
            fetch_ctext(ch_id, title, author, path)
        except Exception as e:
            print(f"  ❌ 失败: {e}", file=sys.stderr)
        print()
