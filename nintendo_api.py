import json
import re

import esd_common

DEALS_URL = "https://www.nintendo.com/us/store/sales-and-deals/"
IMAGE_BASE = "https://assets.nintendo.com/image/upload"
STORE_BASE = "https://www.nintendo.com/us/store/products"

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def _fetch_next_data():
    html = esd_common.fetch_text(DEALS_URL, headers={"User-Agent": "Mozilla/5.0"})
    match = NEXT_DATA_RE.search(html)
    if not match:
        raise RuntimeError("nintendo.com 딜 페이지에서 __NEXT_DATA__를 찾지 못했습니다 (페이지 구조가 바뀌었을 수 있음).")
    return json.loads(match.group(1))


def _parse_item(item):
    if (item.get("topLevelCategory") or {}).get("code") != "GAMES":
        return None
    prices = item.get("prices")
    if not prices:
        return None

    url_key = item.get("urlKey") or ""
    image = item.get("productImage") or {}
    public_id = image.get("publicId")
    discount_percent = round(prices.get("percentOff") or 0)

    return {
        "appid": int(item["nsuid"]),
        "name": item.get("name", ""),
        "discount_percent": discount_percent,
        "original_price": float(prices.get("regularPrice") or 0),
        "final_price": float(prices.get("finalPrice") or 0),
        "currency": prices.get("currency", "USD"),
        "image": f"{IMAGE_BASE}/{public_id}" if public_id else None,
        "url": f"{STORE_BASE}/{url_key}/" if url_key else STORE_BASE,
        "on_sale": bool(prices.get("discounted")) and discount_percent > 0,
        "platform": item.get("fullNamePlatform") or item.get("platform") or "",
        "genres": item.get("gameGenreLabels") or [],
        "developers": [item["softwareDeveloper"]] if item.get("softwareDeveloper") else [],
        "publishers": [item["softwarePublisher"]] if item.get("softwarePublisher") else [],
        "review_desc": None,
        "review_rank": 0,
    }


def fetch_specials():
    """The nintendo.com sales-and-deals hub page (stable URL; the featured
    campaign underneath it rotates, but /sales-and-deals/ itself is the
    permanent link Nintendo redirects campaign-specific slugs to).
    """
    data = _fetch_next_data()
    grid = data["props"]["pageProps"]["page"]["content"]["merchandisedGrid"]

    seen = set()
    deals = []
    for raw in grid:
        item = _parse_item(raw)
        if not item or item["appid"] in seen:
            continue
        seen.add(item["appid"])
        deals.append(item)

    deals.sort(key=lambda d: d["discount_percent"], reverse=True)
    return deals


def fetch_catalog():
    """No stable non-sale browse source found yet, so search only covers sale
    items for now (unlike Steam/GOG/GMG, which also pull a broader catalog)."""
    return []


def fetch_all_games():
    return esd_common.merge_catalog_and_specials(fetch_catalog, fetch_specials)


def fetch_and_save(path="data.json"):
    games = fetch_all_games()
    rate = esd_common.get_usd_krw_rate()
    return esd_common.save_games(path, games, extra={"usd_krw_rate": rate})


if __name__ == "__main__":
    result = fetch_and_save("docs/nintendo_data.json")
    on_sale = sum(1 for g in result["deals"] if g["on_sale"])
    print(f"{len(result['deals'])}개 게임 저장 (세일 {on_sale}개, 검색용 {len(result['deals']) - on_sale}개) -> docs/nintendo_data.json")
