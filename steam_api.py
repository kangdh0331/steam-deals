import json
import re
import time
import urllib.request

SEARCH_URL = "https://store.steampowered.com/search/results/"
PAGE_SIZE = 100
MAX_PAGES = 10  # up to ~1000 deals

ROW_RE = re.compile(
    r'<a\s+href="https://store\.steampowered\.com/app/(?P<appid>\d+)/[^"]*"'
    r'[^>]*>(?P<body>.*?)</a>\s*'
    r'(?=<a\s+href="https://store\.steampowered\.com/app/|\Z)',
    re.DOTALL,
)
APPID_COUNT_RE = re.compile(r'data-ds-appid="(\d+)"')
NAME_RE = re.compile(r'class="title">([^<]*)</span>')
IMAGE_RE = re.compile(r'<img src="([^"]*)"')
DISCOUNT_RE = re.compile(r'data-discount="(\d+)"')
ORIGINAL_PRICE_RE = re.compile(r'discount_original_price">([^<]*)</div>')
FINAL_PRICE_RE = re.compile(r'discount_final_price">([^<]*)</div>')


def _parse_price(text):
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _fetch_page(start, count):
    url = f"{SEARCH_URL}?start={start}&count={count}&specials=1&cc=kr&l=korean&ndl=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_rows(html):
    deals = []
    row_count = len(APPID_COUNT_RE.findall(html))
    for match in ROW_RE.finditer(html):
        body = match.group("body")
        name_m = NAME_RE.search(body)
        discount_m = DISCOUNT_RE.search(body)
        original_m = ORIGINAL_PRICE_RE.search(body)
        final_m = FINAL_PRICE_RE.search(body)
        if not (name_m and discount_m and original_m and final_m):
            continue
        image_m = IMAGE_RE.search(body)
        appid = match.group("appid")
        deals.append({
            "appid": int(appid),
            "name": name_m.group(1).strip(),
            "discount_percent": int(discount_m.group(1)),
            "original_price": _parse_price(original_m.group(1)),
            "final_price": _parse_price(final_m.group(1)),
            "currency": "KRW",
            "image": image_m.group(1) if image_m else None,
            "url": f"https://store.steampowered.com/app/{appid}",
        })
    return deals, row_count


def fetch_specials(max_pages=MAX_PAGES, page_size=PAGE_SIZE):
    seen = set()
    deals = []
    for page in range(max_pages):
        start = page * page_size
        try:
            html = _fetch_page(start, page_size)
        except Exception:
            break

        rows, row_count = _parse_rows(html)
        if row_count == 0:
            break

        for deal in rows:
            if deal["appid"] in seen:
                continue
            seen.add(deal["appid"])
            deals.append(deal)

        if row_count < page_size:
            break

        time.sleep(0.3)

    deals.sort(key=lambda d: d["discount_percent"], reverse=True)
    return deals


def fetch_and_save(path="data.json"):
    deals = fetch_specials()
    payload = {"fetched_at": time.time(), "deals": deals}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


if __name__ == "__main__":
    result = fetch_and_save("docs/data.json")
    print(f"{len(result['deals'])}개 할인 게임을 docs/data.json에 저장했습니다.")
