import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WB_TOKEN = os.getenv("WB_TOKEN_KEY")

def fetch_wb(url, headers, params=None):
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        return res.json() if res.status_code == 200 else None
    except:
        return None

def fetch_wb_post(url, headers, payload):
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code != 200:
            print(f"[POST ERROR] {url} → {res.status_code}: {res.text[:300]}")
            return None
        return res.json()
    except Exception as e:
        print(f"[POST EXCEPTION] {url} → {e}")
        return None


@app.get("/stats")
def get_stats():
    headers = {"Authorization": WB_TOKEN}
    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)

    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    date_from = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()

    orders_raw = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/orders", headers, {"dateFrom": date_from}) or []
    sales_raw = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/sales", headers, {"dateFrom": date_from}) or []

    def calc(data, date_str, key):
        items = [item for item in data if item.get('date', '').startswith(date_str)]
        return {"count": len(items), "rev": int(sum(item.get(key, 0) for item in items))}

    return {
        "today": {
            "orders": calc(orders_raw, today_str, 'finishedPrice'),
            "sales": calc(sales_raw, today_str, 'forPay'),
        },
        "yesterday": {
            "orders": calc(orders_raw, yesterday_str, 'finishedPrice'),
            "sales": calc(sales_raw, yesterday_str, 'forPay'),
        },
    }


@app.get("/adv")
def get_adv():
    headers = {
        "Authorization": WB_TOKEN,
        "Content-Type": "application/json",
    }

    # 1. Получаем список всех кампаний
    count_data = fetch_wb("https://advert-api.wildberries.ru/adv/v1/promotion/count", headers)
    if not count_data:
        return {"status": "error", "campaigns": [], "message": "Не удалось получить список кампаний"}

    # Собираем id всех кампаний (любые статусы)
    all_ids = []
    for group in count_data.get("adverts", []):
        for advert in group.get("advert_list", []):
            all_ids.append(advert["advertId"])

    if not all_ids:
        return {"status": "success", "campaigns": []}

    # 2. Получаем детали кампаний — GET /api/advert/v2/adverts?ids=1,2,3 (до 50 за раз)
    details_map = {}
    for i in range(0, len(all_ids), 50):
        chunk = all_ids[i:i + 50]
        ids_str = ",".join(str(x) for x in chunk)
        res = requests.get(
            "https://advert-api.wildberries.ru/api/advert/v2/adverts",
            headers=headers,
            params={"ids": ids_str},
            timeout=15,
        )
        print(f"[DEBUG] details status={res.status_code} body={res.text[:300]}")
        if res.status_code == 200:
            data = res.json()
            for d in (data.get("adverts") or []):
                details_map[d["id"]] = d

    # 3. Получаем статистику за сегодня — GET /adv/v3/fullstats
    offset = timezone(timedelta(hours=3))
    today_str = datetime.now(offset).strftime("%Y-%m-%d")

    # /adv/v3/fullstats — GET, ids через запятую
    ids_str = ",".join(str(x) for x in all_ids)
    stats_res = requests.get(
        "https://advert-api.wildberries.ru/adv/v3/fullstats",
        headers=headers,
        params={"ids": ids_str, "dateFrom": today_str, "dateTo": today_str},
        timeout=15,
    )
    print(f"[DEBUG] stats status={stats_res.status_code} body={stats_res.text[:400]}")
    stats_raw = stats_res.json() if stats_res.status_code == 200 else []

    stats_map = {item["advertId"]: item for item in (stats_raw if isinstance(stats_raw, list) else [])}

    # 4. Статус → читаемый текст
    STATUS_LABELS = {
        4: "Готова к запуску",
        7: "Завершена",
        8: "Отказалась",
        9: "Идет показ",
        11: "Приостановлена",
    }

    # 5. Собираем итоговый список
    final_results = []
    for cid in all_ids:
        detail = details_map.get(cid, {})
        stat = stats_map.get(cid, {})

        # Суммируем метрики по всем дням в статистике
        days = stat.get("days", [])
        views = sum(d.get("views", 0) for d in days)
        clicks = sum(d.get("clicks", 0) for d in days)
        spend = sum(d.get("sum", 0) for d in days)
        atc = sum(d.get("atbs", 0) for d in days)       # добавлено в корзину
        orders = sum(d.get("orders", 0) for d in days)
        ctr = round(clicks / views * 100, 2) if views > 0 else 0.0

        status_code = detail.get("status", 0)
        # Новый API: имя внутри settings.name
        name = (detail.get("settings") or {}).get("name") or f"Кампания {cid}"

        final_results.append({
            "id": cid,
            "name": name,
            "status": STATUS_LABELS.get(status_code, f"Статус {status_code}"),
            "views": views,
            "clicks": clicks,
            "ctr": ctr,
            "sum": round(spend, 2),
            "atc": atc,
            "orders": orders,
            "date": today_str,
        })

    # Активные кампании — первыми
    final_results.sort(key=lambda x: (0 if "Идет" in x["status"] else 1, -x["views"]))

    return {"status": "success", "campaigns": final_results}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
