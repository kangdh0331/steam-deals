"""Shared helpers for the per-platform fetchers (steam_api.py, gog_api.py, gmg_api.py).

Keeps the network/IO plumbing (retries, atomic writes, "don't overwrite good
data with garbage") in one place instead of duplicated three times.
"""
import json
import os
import tempfile
import time
import urllib.request

DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.5

FX_RATE_URL = "https://api.frankfurter.app/latest?from=USD&to=KRW"
FX_CACHE_PATH = "fx_rate_cache.json"
FX_FALLBACK_RATE = 1380.0  # only used if we've never fetched a live rate before


def fetch_bytes(req, timeout=DEFAULT_TIMEOUT, retries=DEFAULT_RETRIES, backoff=DEFAULT_BACKOFF):
    """Open a urllib.request.Request, retrying transient failures with backoff."""
    last_exc = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - network errors vary by platform
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise last_exc


def fetch_json(url, headers=None, data=None, **kwargs):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    body = fetch_bytes(req, **kwargs)
    return json.loads(body.decode("utf-8"))


def fetch_text(url, headers=None, **kwargs):
    req = urllib.request.Request(url, headers=headers or {})
    body = fetch_bytes(req, **kwargs)
    return body.decode("utf-8", errors="replace")


def get_usd_krw_rate(cache_path=FX_CACHE_PATH):
    """USD->KRW rate for platforms that price in USD (GOG, Nintendo).

    Falls back to the last cached rate (or a rough fixed constant if we've
    never fetched one) so a hiccup on the FX API doesn't fail the whole run.
    """
    try:
        data = fetch_json(FX_RATE_URL, headers={"User-Agent": "Mozilla/5.0"})
        rate = float(data["rates"]["KRW"])
        atomic_write_json(cache_path, {"usd_krw_rate": rate, "fetched_at": time.time()})
        return rate
    except Exception:
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return float(json.load(f)["usd_krw_rate"])
            except Exception:
                pass
        return FX_FALLBACK_RATE


def merge_catalog_and_specials(fetch_catalog_fn, fetch_specials_fn):
    """Combine a broad (mostly non-sale) catalog with an accurate sale list.

    Specials data wins on overlap since it has the precise discount info;
    the catalog just fills in games that aren't currently on sale so search
    can still find them.
    """
    by_appid = {}
    for item in fetch_catalog_fn():
        by_appid[item["appid"]] = item
    for deal in fetch_specials_fn():
        by_appid[deal["appid"]] = deal

    games = list(by_appid.values())
    games.sort(key=lambda g: (not g["on_sale"], -g["discount_percent"]))
    return games


def atomic_write_json(path, payload):
    """Write JSON via a temp file + rename so a crash mid-write can't corrupt the file."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def save_games(path, games, min_ratio=0.3, min_absolute=20, extra=None):
    """Write {fetched_at, deals: games} to path, refusing an obviously-broken result.

    If a source API breaks or a run only partially succeeds, games can come
    back much smaller than usual. Overwriting a good data.json with that
    would quietly wreck the live site, so: if there's a previous file, the
    new count must be at least min_ratio of it (and at least min_absolute);
    if there's no previous file yet, just require a non-empty result.
    """
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                previous_count = len(json.load(f).get("deals", []))
        except Exception:
            previous_count = 0
        if previous_count > 0 and len(games) < max(min_absolute, previous_count * min_ratio):
            raise RuntimeError(
                f"새로 가져온 게임 수({len(games)}개)가 기존({previous_count}개)보다 "
                f"너무 적어서 저장을 중단합니다. 원본 사이트 구조가 바뀌었을 수 있어요."
            )
    elif not games:
        raise RuntimeError("가져온 게임이 없어서 저장을 중단합니다.")

    payload = {"fetched_at": time.time(), "deals": games}
    if extra:
        payload.update(extra)
    atomic_write_json(path, payload)
    return payload
