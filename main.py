import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from typing import Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WB_TOKEN = os.getenv("WB_TOKEN_KEY")
CACHE_TTL = 30 * 60  # 30 минут в секундах

# ─── Простой in-memory кэш ────────────────────────────────────────────
_cache: dict[str, dict] = {}

def cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if not entry:
        return None
    if (datetime.utcnow() - entry["ts"]).total_seconds() > CACHE_TTL:
        del _cache[key]
        return None
    print(f"[CACHE HIT] {key}")
    return entry["data"]

def cache_set(key: str, data: Any):
    _cache[key] = {"ts": datetime.utcnow(), "data": data}
    print(f"[CACHE SET] {key}")

def cache_invalidate(key: str):
    _cache.pop(key, None)
    print(f"[CACHE DEL] {key}")
# ──────────────────────────────────────────────────────────────────────


def fetch_wb(url, headers, params=None):
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        return res.json() if res.status_code == 200 else None
    except:
        return None


@app.get("/stats")
def get_stats():
    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)
    today_str = now.strftime('%Y-%m-%d')

    cache_key = f"stats:{today_str}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    headers = {"Authorization": WB_TOKEN}
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    # Начало текущей недели (понедельник)
    this_monday = now - timedelta(days=now.weekday())  # weekday(): 0=пн, 6=вс
    this_monday = this_monday.replace(hour=0, minute=0, second=0, microsecond=0)

    # Прошлая неделя: пн–вс
    last_monday = this_monday - timedelta(weeks=1)
    last_sunday = this_monday - timedelta(days=1)

    # Самая ранняя дата которая нам нужна — понедельник прошлой недели
    date_from = last_monday.isoformat()

    orders_raw = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/orders", headers, {"dateFrom": date_from}) or []
    sales_raw  = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/sales",  headers, {"dateFrom": date_from}) or []

    def calc_day(data, date_str, key):
        """Статистика за один день."""
        items = [item for item in data if item.get('date', '').startswith(date_str)]
        return {"count": len(items), "rev": int(sum(item.get(key, 0) for item in items))}

    def calc_range(data, date_from_dt, date_to_dt, key):
        """Статистика за диапазон дат (включительно)."""
        items = [
            item for item in data
            if date_from_dt.strftime('%Y-%m-%d') <= item.get('date', '')[:10] <= date_to_dt.strftime('%Y-%m-%d')
        ]
        return {"count": len(items), "rev": int(sum(item.get(key, 0) for item in items))}

    result = {
        "today": {
            "orders": calc_day(orders_raw, today_str, 'finishedPrice'),
            "sales":  calc_day(sales_raw,  today_str, 'forPay'),
        },
        "yesterday": {
            "orders": calc_day(orders_raw, yesterday_str, 'finishedPrice'),
            "sales":  calc_day(sales_raw,  yesterday_str, 'forPay'),
        },
        # Текущая неделя: с понедельника по сегодня
        "this_week": {
            "orders": calc_range(orders_raw, this_monday, now, 'finishedPrice'),
            "sales":  calc_range(sales_raw,  this_monday, now, 'forPay'),
            "from":   this_monday.strftime('%Y-%m-%d'),
            "to":     today_str,
        },
        # Прошлая неделя: пн–вс
        "last_week": {
            "orders": calc_range(orders_raw, last_monday, last_sunday, 'finishedPrice'),
            "sales":  calc_range(sales_raw,  last_monday, last_sunday, 'forPay'),
            "from":   last_monday.strftime('%Y-%m-%d'),
            "to":     last_sunday.strftime('%Y-%m-%d'),
        },
    }
    cache_set(cache_key, result)
    return result


@app.get("/adv")
def get_adv():
    offset = timezone(timedelta(hours=3))
    today_str = datetime.now(offset).strftime("%Y-%m-%d")

    cache_key = f"adv:{today_str}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    headers = {
        "Authorization": WB_TOKEN,
        "Content-Type": "application/json",
    }

    # 1. Список активных кампаний
    count_data = fetch_wb("https://advert-api.wildberries.ru/adv/v1/promotion/count", headers)
    if not count_data:
        return {"status": "error", "campaigns": [], "message": "Не удалось получить список кампаний"}

    all_ids = []
    for group in count_data.get("adverts", []):
        if group.get("status") == 9:
            for advert in group.get("advert_list", []):
                all_ids.append(advert["advertId"])

    if not all_ids:
        result = {"status": "success", "campaigns": []}
        cache_set(cache_key, result)
        return result

    # 2. Детали кампаний (батчами по 50)
    details_map = {}
    for i in range(0, len(all_ids), 50):
        chunk = all_ids[i:i + 50]
        res = requests.get(
            "https://advert-api.wildberries.ru/api/advert/v2/adverts",
            headers=headers,
            params={"ids": ",".join(str(x) for x in chunk)},
            timeout=15,
        )
        if res.status_code == 200:
            for d in (res.json().get("adverts") or []):
                details_map[d["id"]] = d

    # 3. Статистика за сегодня
    stats_res = requests.get(
        "https://advert-api.wildberries.ru/adv/v3/fullstats",
        headers=headers,
        params={"ids": ",".join(str(x) for x in all_ids), "beginDate": today_str, "endDate": today_str},
        timeout=15,
    )
    stats_raw = stats_res.json() if stats_res.status_code == 200 else []
    stats_map = {item["advertId"]: item for item in (stats_raw if isinstance(stats_raw, list) else [])}

    STATUS_LABELS = {4: "Готова к запуску", 7: "Завершена", 8: "Отказалась", 9: "Идет показ", 11: "Приостановлена"}

    # 4. Сборка результата
    final_results = []
    for cid in all_ids:
        detail = details_map.get(cid, {})
        stat   = stats_map.get(cid, {})
        days   = stat.get("days", [])

        views  = sum(d.get("views",  0) for d in days)
        clicks = sum(d.get("clicks", 0) for d in days)
        spend  = sum(d.get("sum",    0) for d in days)
        atc    = sum(d.get("atbs",   0) for d in days)
        orders = sum(d.get("orders", 0) for d in days)
        ctr    = round(clicks / views * 100, 2) if views > 0 else 0.0

        name = (detail.get("settings") or {}).get("name") or f"Кампания {cid}"

        final_results.append({
            "id":     cid,
            "name":   name,
            "status": STATUS_LABELS.get(detail.get("status", 0), f"Статус {detail.get('status', 0)}"),
            "views":  views,
            "clicks": clicks,
            "ctr":    ctr,
            "sum":    round(spend, 2),
            "atc":    atc,
            "orders": orders,
            "date":   today_str,
        })

    final_results.sort(key=lambda x: (0 if "Идет" in x["status"] else 1, -x["views"]))

    result = {"status": "success", "campaigns": final_results}
    cache_set(cache_key, result)
    return result


# Ручной сброс кэша (если нужно обновить раньше 30 минут)
@app.post("/cache/clear")
def clear_cache():
    _cache.clear()
    print("[CACHE] Очищен вручную")
    return {"status": "ok", "message": "Кэш очищен"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
