import json
import os
import re
import time
import urllib.request

SEARCH_URL = "https://store.steampowered.com/search/results/"
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
DETAILS_CACHE_PATH = "app_details_cache.json"
DETAILS_FETCH_DELAY = 1.5
PAGE_SIZE = 100
MAX_PAGES = 10  # up to ~1000 deals
CATALOG_MAX_PAGES = 5  # up to ~500 extra (non-sale) searchable games

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
REVIEW_DESC_RE = re.compile(r'search_review_summary [a-z_]+" data-tooltip-html="([^"&]*)')

# 스팀 평가 등급 (숫자가 클수록 긍정적). 리뷰 수가 적은 게임엔 수식어 없는
# "긍정적"/"부정적" 등급이 붙는데, 이것도 순서상 자리를 맞춰준다.
REVIEW_RANK = {
    "압도적으로 긍정적": 9,
    "매우 긍정적": 8,
    "대체로 긍정적": 7,
    "긍정적": 6,
    "복합적": 5,
    "부정적": 4,
    "대체로 부정적": 3,
    "매우 부정적": 2,
    "압도적으로 부정적": 1,
}


def _parse_price(text):
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _fetch_page(start, count, specials_only):
    params = f"start={start}&count={count}&cc=kr&l=korean&ndl=1"
    if specials_only:
        params += "&specials=1"
    req = urllib.request.Request(f"{SEARCH_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_rows(html):
    deals = []
    row_count = len(APPID_COUNT_RE.findall(html))
    for match in ROW_RE.finditer(html):
        body = match.group("body")
        name_m = NAME_RE.search(body)
        discount_m = DISCOUNT_RE.search(body)
        final_m = FINAL_PRICE_RE.search(body)
        if not (name_m and discount_m and final_m):
            continue
        original_m = ORIGINAL_PRICE_RE.search(body)
        image_m = IMAGE_RE.search(body)
        review_m = REVIEW_DESC_RE.search(body)
        appid = match.group("appid")
        final_price = _parse_price(final_m.group(1))
        original_price = _parse_price(original_m.group(1)) if original_m else final_price
        discount_percent = int(discount_m.group(1))
        review_desc = review_m.group(1).strip() if review_m else None
        deals.append({
            "appid": int(appid),
            "name": name_m.group(1).strip(),
            "discount_percent": discount_percent,
            "original_price": original_price,
            "final_price": final_price,
            "currency": "KRW",
            "image": image_m.group(1) if image_m else None,
            "url": f"https://store.steampowered.com/app/{appid}",
            "on_sale": discount_percent > 0,
            "review_desc": review_desc,
            "review_rank": REVIEW_RANK.get(review_desc, 0),
        })
    return deals, row_count


def _fetch_listing(specials_only, max_pages, page_size=PAGE_SIZE):
    seen = set()
    items = []
    for page in range(max_pages):
        start = page * page_size
        try:
            html = _fetch_page(start, page_size, specials_only)
        except Exception:
            break

        rows, row_count = _parse_rows(html)
        if row_count == 0:
            break

        for item in rows:
            if item["appid"] in seen:
                continue
            seen.add(item["appid"])
            items.append(item)

        if row_count < page_size:
            break

        time.sleep(0.3)

    return items


def fetch_specials(max_pages=MAX_PAGES, page_size=PAGE_SIZE):
    deals = _fetch_listing(specials_only=True, max_pages=max_pages, page_size=page_size)
    deals.sort(key=lambda d: d["discount_percent"], reverse=True)
    return deals


def fetch_catalog(max_pages=CATALOG_MAX_PAGES, page_size=PAGE_SIZE):
    """Broader (mostly non-sale) listing so search can surface games that aren't on sale."""
    return _fetch_listing(specials_only=False, max_pages=max_pages, page_size=page_size)


def _load_details_cache(path=DETAILS_CACHE_PATH):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_details_cache(cache, path=DETAILS_CACHE_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _is_valid_cache_entry(entry):
    return isinstance(entry, dict) and "developers" in entry and "publishers" in entry


def _fetch_details(appid):
    url = f"{APPDETAILS_URL}?appids={appid}&cc=kr&l=korean"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    entry = data.get(str(appid), {})
    if not entry.get("success"):
        return {"genres": [], "developers": [], "publishers": []}
    info = entry.get("data", {})
    genres = [g["description"] for g in info.get("genres", []) if g.get("description")]
    return {
        "genres": genres,
        "developers": info.get("developers") or [],
        "publishers": info.get("publishers") or [],
    }


def attach_details(deals, cache_path=DETAILS_CACHE_PATH, delay=DETAILS_FETCH_DELAY):
    cache = _load_details_cache(cache_path)
    cache_updated = False
    for deal in deals:
        key = str(deal["appid"])
        entry = cache.get(key)
        if not _is_valid_cache_entry(entry):
            try:
                entry = _fetch_details(deal["appid"])
                cache[key] = entry
                cache_updated = True
            except Exception:
                entry = {"genres": [], "developers": [], "publishers": []}
            time.sleep(delay)
        deal["genres"] = entry.get("genres", [])
        deal["developers"] = entry.get("developers", [])
        deal["publishers"] = entry.get("publishers", [])

    if cache_updated:
        _save_details_cache(cache, cache_path)
    return deals


def fetch_all_games():
    """Sale items plus a broader catalog, so search can find non-sale games too."""
    by_appid = {}
    for item in fetch_catalog():
        by_appid[item["appid"]] = item
    for deal in fetch_specials():
        by_appid[deal["appid"]] = deal  # specials data wins (accurate discount info)

    games = list(by_appid.values())
    games.sort(key=lambda g: (not g["on_sale"], -g["discount_percent"]))
    return games


def fetch_and_save(path="data.json"):
    games = fetch_all_games()
    attach_details(games)
    payload = {"fetched_at": time.time(), "deals": games}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


if __name__ == "__main__":
    result = fetch_and_save("docs/data.json")
    on_sale = sum(1 for g in result["deals"] if g["on_sale"])
    print(f"{len(result['deals'])}개 게임 저장 (세일 {on_sale}개, 검색용 {len(result['deals']) - on_sale}개) -> docs/data.json")
