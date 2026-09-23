import re
import time

import esd_common

CATALOG_URL = "https://catalog.gog.com/v1/catalog"
PAGE_SIZE = 100
SPECIALS_MAX_PAGES = 20   # discounted=true has ~1700 results total
CATALOG_MAX_PAGES = 10    # broader (mostly non-sale) pool for search


def _fetch_page(page, discounted_only):
    params = (
        f"limit={PAGE_SIZE}&order=desc%3Atrending&productType=in%3Agame"
        f"&page={page}&countryCode=US&currencyCode=USD&locale=en-US"
    )
    if discounted_only:
        params += "&discounted=true"
    return esd_common.fetch_json(f"{CATALOG_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})


def _parse_discount(discount_text):
    if not discount_text:
        return 0
    digits = re.sub(r"[^\d]", "", discount_text)
    return int(digits) if digits else 0


def _parse_product(p):
    price = p.get("price") or {}
    final_money = price.get("finalMoney") or {}
    base_money = price.get("baseMoney") or {}
    if not final_money or not base_money:
        return None

    discount_percent = _parse_discount(price.get("discount"))
    reviews_count = p.get("reviewsCount") or 0
    reviews_rating = p.get("reviewsRating")
    review_desc = f"{reviews_rating / 10:.1f}★" if reviews_count and reviews_rating else None

    return {
        "appid": int(p["id"]),
        "name": p.get("title", ""),
        "discount_percent": discount_percent,
        "original_price": float(base_money.get("amount", 0)),
        "final_price": float(final_money.get("amount", 0)),
        "currency": final_money.get("currency", "USD"),
        "image": p.get("coverHorizontal"),
        "url": p.get("storeLink") or f"https://www.gog.com/game/{p.get('slug', '')}",
        "on_sale": discount_percent > 0,
        "genres": [g["name"] for g in p.get("genres", []) if g.get("name")],
        "developers": p.get("developers") or [],
        "publishers": p.get("publishers") or [],
        "review_desc": review_desc,
        "review_rank": reviews_rating or 0,
    }


def _fetch_listing(discounted_only, max_pages):
    seen = set()
    items = []
    for page in range(1, max_pages + 1):
        try:
            data = _fetch_page(page, discounted_only)
        except Exception:
            break

        products = data.get("products", [])
        if not products:
            break

        for raw in products:
            item = _parse_product(raw)
            if not item or item["appid"] in seen:
                continue
            seen.add(item["appid"])
            items.append(item)

        if page >= (data.get("pages") or 1):
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
    result = fetch_and_save("docs/gog_data.json")
    on_sale = sum(1 for g in result["deals"] if g["on_sale"])
    print(f"{len(result['deals'])}개 게임 저장 (세일 {on_sale}개, 검색용 {len(result['deals']) - on_sale}개) -> docs/gog_data.json")
