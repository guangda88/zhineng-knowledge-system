"""Fetch Tingwu transcription data from user's folder."""

import requests
import json
import os

COOKIES = {
    "account_info_switch": "close",
    "login_current_pk": "1936339930532323",
    "yunpk": "1936339930532323",
    "cnaui": "1936339930532323",
    "aui": "1936339930532323",
    "t": "9526c411797878f69f4b234494a868ab",
    "currentRegionId": "cn-hangzhou",
    "cna": "707AIewNgkwCAXe3pvNuqNSD",
    "sca": "72043460",
    "aliyun_enable_passkey": "1",
    "login_aliyunid_pk": "1936339930532323",
    "aliyun_country": "CN",
    "partitioned_cookie_flag": "doubleRemove",
    "aliyun_site": "CN",
    "aliun_lang": "zh",
    "login_aliyunid": "6bsh%E5%88%98%E5%8D%9A%E5%A3%AB",
    "hsite": "6",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://tingwu.aliyun.com/folders/265086",
}

FOLDER_ID = "265086"
OUTPUT_DIR = "/home/ai/zhineng-knowledge-system/data/tingwu_exports"


def try_api_endpoints(session):
    """Try various known Tingwu API endpoints to find the right one."""

    # Common Tingwu API patterns
    api_patterns = [
        f"https://tingwu.aliyun.com/api/folders/{FOLDER_ID}/tasks",
        f"https://tingwu.aliyun.com/api/v2/folders/{FOLDER_ID}/tasks",
        f"https://tingwu.aliyun.com/api/tasks?folderId={FOLDER_ID}",
        f"https://tingwu.aliyun.com/api/v2/tasks?folderId={FOLDER_ID}",
        f"https://tingwu.aliyun.com/api/meetings?folderId={FOLDER_ID}",
        f"https://tingwu.aliyun.com/api/v1/folders/{FOLDER_ID}",
        f"https://tingwu.aliyun.com/api/folders/{FOLDER_ID}",
        f"https://tingwu.aliyun.com/openapi/api/v2/tasks?folderId={FOLDER_ID}",
    ]

    for url in api_patterns:
        try:
            print(f"\nTrying: {url}")
            resp = session.get(url, timeout=10)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"  Response: {json.dumps(data, ensure_ascii=False)[:500]}")
                    return url, data
                except Exception:
                    print(f"  Body (first 500): {resp.text[:500]}")
            elif resp.status_code in [301, 302, 303, 307]:
                print(f"  Redirect: {resp.headers.get('Location', 'N/A')}")
            else:
                print(f"  Body (first 300): {resp.text[:300]}")
        except Exception as e:
            print(f"  Error: {e}")

    return None, None


def fetch_page(session):
    """Fetch the main folder page to find API hints."""
    url = f"https://tingwu.aliyun.com/folders/{FOLDER_ID}"
    print(f"Fetching page: {url}")
    resp = session.get(url, timeout=15)
    print(f"Status: {resp.status_code}")

    # Save HTML for analysis
    html_path = os.path.join(OUTPUT_DIR, "folder_page.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"HTML saved to {html_path} ({len(resp.text)} bytes)")

    # Look for API hints in the HTML
    text = resp.text
    api_hints = []
    for keyword in ["api", "fetch(", "axios", "XHR", "/api/", "graphql", "endpoint"]:
        idx = text.lower().find(keyword)
        if idx >= 0:
            snippet = text[max(0, idx - 50):idx + 100]
            api_hints.append(snippet)

    if api_hints:
        print(f"\nFound {len(api_hints)} API-related snippets:")
        for h in api_hints[:10]:
            print(f"  ...{h}...")

    return resp.text


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = requests.Session()

    # Set all cookies
    for k, v in COOKIES.items():
        session.cookies.set(k, v, domain=".aliyun.com")

    session.headers.update(HEADERS)

    # Also set the important cookies from the raw string
    raw_cookies = """account_info_switch=close; login_current_pk=1936339930532323; yunpk=1936339930532323; cnaui=1936339930532323; aui=1936339930532323; t=9526c411797878f69f4b234494a868ab; currentRegionId=cn-hangzhou; cna=707AIewNgkwCAXe3pvNuqNSD; sca=72043460; aliyun_enable_passkey=1; login_aliyunid_pk=1936339930532323; aliyun_country=CN; partitioned_cookie_flag=doubleRemove; aliyun_site=CN; aliyun_lang=zh; login_aliyunid=6bsh%E5%88%98%E5%8D%9A%E5%A3%AB; hsite=6"""

    session.headers["Cookie"] = raw_cookies

    # Step 1: Fetch the folder page
    print("=" * 60)
    print("Step 1: Fetching folder page")
    print("=" * 60)
    fetch_page(session)

    # Step 2: Try API endpoints
    print("\n" + "=" * 60)
    print("Step 2: Trying API endpoints")
    print("=" * 60)
    api_url, api_data = try_api_endpoints(session)

    if api_data:
        # Save the API response
        result_path = os.path.join(OUTPUT_DIR, "folder_tasks.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(api_data, f, ensure_ascii=False, indent=2)
        print(f"\nAPI response saved to {result_path}")

    print("\nDone. Check output directory:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
