import json
import time

import esd_common

# GMG's own storefront uses this Algolia search-only key client-side (visible in
# the page source of https://www.greenmangaming.com/all-games/on-sale/). It's
# referer-locked, not a secret credential.
ALGOLIA_APP_ID = "SCZIZSP09Z"
ALGOLIA_API_KEY = "5420d3ea58371da39dacf5a666ee94da"
ALGOLIA_INDEX = "prod_ProductSearch_GS_KR"
QUERY_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
REFERER = "https://www.greenmangaming.com/all-games/on-sale/"

IMAGE_BASE = "https://images.greenmangaming.com"
STORE_BASE = "https://www.greenmangaming.com"

PAGE_SIZE = 100
SPECIALS_MAX_PAGES = 10   # Regions.KR.IsOnSale:true has ~3300 results total
CATALOG_MAX_PAGES = 10    # broader (mostly non-sale) pool for search


def _fetch_page(page, discounted_only):
    body = {"query": "", "hitsPerPage": PAGE_SIZE, "page": page}
    if discounted_only:
        body["filters"] = "Regions.KR.IsOnSale:true"
    return esd_common.fetch_json(
        QUERY_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Referer": REFERER,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
        },
    )


def _parse_hit(hit):
    if not hit.get("IsSellable"):
        return None
    region = (hit.get("Regions") or {}).get("KR")
    if not region:
        return None

    discount_percent = int(region.get("DrpDiscountPercentage") or 0)
    url_path = hit.get("Url") or ""
    image_path = hit.get("ImageUrl") or ""

    return {
        "appid": int(hit["GameVariantId"]),
        "name": hit.get("DisplayName", ""),
        "discount_percent": discount_percent,
        "original_price": float(region.get("Rrp") or 0),
        "final_price": float(region.get("Drp") or 0),
        "currency": region.get("CurrencyCode", "KRW"),
        "image": f"{IMAGE_BASE}{image_path}" if image_path else None,
        "url": f"{STORE_BASE}{url_path}" if url_path else STORE_BASE,
        "on_sale": bool(region.get("IsOnSale")) and discount_percent > 0,
        "genres": hit.get("Genre") or [],
        "developers": [],
        "publishers": [hit["PublisherName"]] if hit.get("PublisherName") else [],
        "review_desc": None,
        "review_rank": 0,
    }


def _fetch_listing(discounted_only, max_pages):
    seen = set()
    items = []
    for page in range(max_pages):
        try:
            data = _fetch_page(page, discounted_only)
        except Exception:
            break

        hits = data.get("hits", [])
        if not hits:
            break

        for raw in hits:
            item = _parse_hit(raw)
            if not item or item["appid"] in seen:
                continue
            seen.add(item["appid"])
            items.append(item)

        if page + 1 >= (data.get("nbPages") or 1):
            break

        time.sleep(0.3)

    return items


def fetch_specials(max_pages=SPECIALS_MAX_PAGES):
    deals = _fetch_listing(discounted_only=True, max_pages=max_pages)
    deals.sort(key=lambda d: d["discount_percent"], reverse=True)
    return deals


def fetch_catalog(max_pages=CATALOG_MAX_PAGES):
    """Broader (mostly non-sale) listing so search can surface games that aren't on sale."""
    return _fetch_listing(discounted_only=False, max_pages=max_pages)


def fetch_all_games():
    return esd_common.merge_catalog_and_specials(fetch_catalog, fetch_specials)


def fetch_and_save(path="data.json"):
    games = fetch_all_games()
    return esd_common.save_games(path, games)


if __name__ == "__main__":
    result = fetch_and_save("docs/gmg_data.json")
    on_sale = sum(1 for g in result["deals"] if g["on_sale"])
    print(f"{len(result['deals'])}개 게임 저장 (세일 {on_sale}개, 검색용 {len(result['deals']) - on_sale}개) -> docs/gmg_data.json")
