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
        r = requests.get(url, headers=headers, params=params, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

@app.get("/stats")
def get_stats():
    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)
    today = now.strftime('%Y-%m-%d')
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    start = (now - timedelta(days=3)).strftime('%Y-%m-%dT00:00:00')
    
    headers = {"Authorization": WB_TOKEN}
    orders = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/orders", headers, {"dateFrom": start, "flag": 0}) or []
    sales = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/sales", headers, {"dateFrom": start, "flag": 0}) or []

    def process(src, dt, is_s=False):
        items = [i for i in src if dt in i.get('date', '')]
        if is_s: rev = sum(i.get('finishedPrice', 0) for i in items)
        else: rev = sum(i.get('totalPrice', 0) * (1 - (i.get('discountPercent', 0) - 1) / 100) for i in items)
        return {"count": len(items), "rev": int(rev)}

    return {
        "status": "success",
        "today": {"orders": process(orders, today), "sales": process(sales, today, True)},
        "yesterday": {"orders": process(orders, yesterday), "sales": process(sales, yesterday, True)}
    }

@app.get("/adv")
def get_adv():
    headers = {"Authorization": WB_TOKEN}
    
    # 1. Получаем реальный список всех кампаний (метод /adverts более надежный)
    # Статусы: 7 - завершена, 8 - отказался, 9 - идет, 11 - пауза
    list_url = "https://advert-api.wildberries.ru/adv/v1/promotion/adverts"
    all_campaigns = fetch_wb(list_url, headers)
    
    if not all_campaigns or not isinstance(all_campaigns, list):
        # Если /adverts не сработал, пробуем /count как запасной
        return {"status": "error", "message": "Не удалось получить список кампаний"}

    # Отбираем только те, что не удалены (например, статусы 9 и 11)
    # И ограничимся последними 10, чтобы не "повесить" запрос
    active_ids = [c.get('advertId') for c in all_campaigns if c.get('status') in [9, 11]]
    
    # Если активных нет, возьмем просто последние 5 любых для теста
    if not active_ids:
        active_ids = [c.get('advertId') for c in all_campaigns[-5:]]

    if not active_ids:
        return {"status": "success", "campaigns": [], "debug": "Кампании вообще не найдены"}

    # 2. Запрашиваем статистику через v2/fullstats
    stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
    payload = [{"id": cid} for cid in active_ids]
    
    try:
        stats_res = requests.post(stats_url, headers=headers, json=payload, timeout=15)
        if stats_res.status_code != 200:
             return {"status": "error", "message": f"WB Stats Error: {stats_res.status_code}"}
             
        raw_stats = stats_res.json()
        result = []

        # Создаем словарь для быстрого поиска имен кампаний
        names = {c.get('advertId'): c.get('name') for c in all_campaigns}

        for c_stat in raw_stats:
            cid = c_stat.get('advertId')
            days = c_stat.get('days', [])
            
            # Берем данные за сегодня (последний элемент в days)
            # Если сегодня данных нет, берем вчера (индекс -1 всегда даст последнее событие)
            current = days[-1] if days else {}
            
            result.append({
                "id": cid,
                "name": names.get(cid, "Без названия"),
                "views": current.get('views', 0),
                "clicks": current.get('clicks', 0),
                "ctr": current.get('ctr', 0),
                "cpm": current.get('cpm', 0),
                "sum": current.get('sum', 0),
                "atc": current.get('atc', 0),
                "orders": current.get('orders', 0),
                "date": current.get('date', 'Нет данных')
            })

        return {"status": "success", "campaigns": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
