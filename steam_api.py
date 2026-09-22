import json
import time
import urllib.request

FEATURED_URL = "https://store.steampowered.com/api/featuredcategories?cc=kr&l=korean"


def fetch_specials():
    req = urllib.request.Request(FEATURED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)

    items = data.get("specials", {}).get("items", [])
    deals = []
    for item in items:
        if not item.get("discounted"):
            continue
        deals.append({
            "appid": item.get("id"),
            "name": item.get("name"),
            "discount_percent": item.get("discount_percent", 0),
            "original_price": item.get("original_price", 0) / 100,
            "final_price": item.get("final_price", 0) / 100,
            "currency": item.get("currency", "KRW"),
            "image": item.get("header_image") or item.get("large_capsule_image") or item.get("small_capsule_image"),
            "url": f"https://store.steampowered.com/app/{item.get('id')}",
        })

    deals.sort(key=lambda d: d["discount_percent"], reverse=True)
    return deals


def fetch_and_save(path="data.json"):
    deals = fetch_specials()
    payload = {"fetched_at": time.time(), "deals": deals}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


if __name__ == "__main__":
    result = fetch_and_save()
    print(f"{len(result['deals'])}개 할인 게임을 data.json에 저장했습니다.")
