"""Fetch Tingwu transcription data - try XHR API endpoints used by the SPA."""

import requests
import json
import os
import re

OUTPUT_DIR = "/home/ai/zhineng-knowledge-system/data/tingwu_exports"

RAW_COOKIES = """account_info_switch=close; login_current_pk=1936339930532323; yunpk=1936339930532323; cnaui=1936339930532323; aui=1936339930532323; t=9526c411797878f69f4b234494a868ab; currentRegionId=cn-hangzhou; cna=707AIewNgkwCAXe3pvNuqNSD; sca=72043460; aliyun_enable_passkey=1; login_aliyunid_pk=1936339930532323; aliyun_country=CN; partitioned_cookie_flag=doubleRemove; aliyun_site=CN; aliyun_lang=zh; login_aliyunid=6bsh%E5%88%98%E5%8D%9A%E5%A3%AB; hsite=6"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://tingwu.aliyun.com/folders/265086",
    "Cookie": RAW_COOKIES,
    "Content-Type": "application/json",
}

FOLDER_ID = "265086"


def fetch_js_and_find_api(session):
    """Download the umi.js to find actual API endpoints."""
    print("Fetching umi.js to discover API endpoints...")
    url = "https://g.alicdn.com/idst-fe/mind-meeting-assistant2/0.1.32/umi.js"
    resp = session.get(url, timeout=30)
    print(f"  umi.js size: {len(resp.text)} bytes")

    js_text = resp.text

    # Save for analysis
    js_path = os.path.join(OUTPUT_DIR, "umi.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_text)

    # Search for API patterns
    patterns = [
        r'["\'](?:https?)?/api/[^"\']+["\']',
        r'["\'](?:https?)?/openapi/[^"\']+["\']',
        r'["\'](?:https?)?/gw/[^"\']+["\']',
        r'"/[a-zA-Z]+/[a-zA-Z]+/[a-zA-Z]+"',
        r'transcri|meeting|folder|task|file',
    ]

    api_urls = set()
    for pattern in patterns[:4]:
        matches = re.findall(pattern, js_text)
        for m in matches:
            clean = m.strip('"').strip("'")
            if len(clean) > 5 and len(clean) < 200:
                api_urls.add(clean)

    # Filter for likely API endpoints
    api_like = sorted([u for u in api_urls if any(kw in u.lower() for kw in
        ['api', 'task', 'folder', 'file', 'meeting', 'transcri', 'audio', 'media', 'list', 'query'])])

    print(f"\nFound {len(api_like)} potential API endpoints:")
    for u in api_like[:50]:
        print(f"  {u}")

    # Also look for specific Tingwu API patterns
    tw_patterns = re.findall(r'["\']/(api[^"\']*)["\']', js_text)
    print(f"\nDirect /api paths ({len(tw_patterns)}):")
    seen = set()
    for p in sorted(tw_patterns):
        if p not in seen:
            print(f"  /{p}")
            seen.add(p)

    return api_like


def try_dashboard_api(session):
    """Try Tingwu dashboard/task listing APIs."""
    endpoints = [
        # Tingwu dashboard/list APIs
        ("GET", "https://tingwu.aliyun.com/api/dashboard"),
        ("GET", f"https://tingwu.aliyun.com/api/folders/list?parentId={FOLDER_ID}"),
        ("POST", "https://tingwu.aliyun.com/api/folders/list", {"folderId": FOLDER_ID}),
        ("GET", f"https://tingwu.aliyun.com/api/tasks/list?folderId={FOLDER_ID}"),
        ("POST", "https://tingwu.aliyun.com/api/tasks/list", {"folderId": FOLDER_ID, "pageSize": 50}),
        ("GET", "https://tingwu.aliyun.com/api/me/list"),
        ("GET", "https://tingwu.aliyun.com/api/user/info"),
        ("GET", "https://tingwu.aliyun.com/api/account/v2/user/info"),
        # OpenAPI style
        ("POST", "https://tingwu.aliyun.com/openapi/api/v2/task/list", {"folderId": FOLDER_ID}),
        ("GET", "https://tingwu.aliyun.com/openapi/api/v2/folders"),
        # Possible new API
        ("POST", "https://tingwu.aliyun.com/api/transcription/list", {"folderId": FOLDER_ID}),
        ("GET", f"https://tingwu.aliyun.com/api/media/list?folderId={FOLDER_ID}"),
        ("POST", "https://tingwu.aliyun.com/api/file/list", {"folderId": FOLDER_ID}),
    ]

    for method, url, *body in endpoints:
        body = body[0] if body else None
        try:
            print(f"\n{method} {url}")
            if body:
                print(f"  Body: {json.dumps(body, ensure_ascii=False)}")
            if method == "GET":
                resp = session.get(url, timeout=10)
            else:
                resp = session.post(url, json=body, timeout=10)

            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    text = json.dumps(data, ensure_ascii=False)
                    print(f"  Response: {text[:500]}")

                    # Save successful responses
                    safe_name = url.replace("https://tingwu.aliyun.com", "").replace("/", "_")[:80]
                    out_path = os.path.join(OUTPUT_DIR, f"resp{safe_name}.json")
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception:
                    print(f"  Text: {resp.text[:300]}")
            else:
                print(f"  Body: {resp.text[:200]}")
        except Exception as e:
            print(f"  Error: {e}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: Discover APIs from JS
    print("=" * 60)
    api_urls = fetch_js_and_find_api(session)

    # Step 2: Try known patterns
    print("\n" + "=" * 60)
    print("Trying Tingwu API endpoints")
    print("=" * 60)
    try_dashboard_api(session)

    print("\nDone.")


if __name__ == "__main__":
    main()
