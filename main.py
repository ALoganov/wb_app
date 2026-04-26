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
    # 1. Получаем список кампаний
    adv_list_url = "https://advert-api.wildberries.ru/adv/v1/promotion/count"
    adv_data = fetch_wb(adv_list_url, headers)
    
    if not adv_data: return {"status": "error", "message": "Нет данных по рекламе"}

    # Собираем ID всех активных и приостановленных кампаний (статусы 9 и 11)
    campaign_ids = []
    if 'adverts' in adv_data:
        for group in adv_data['adverts']:
            for adv in group.get('advert_list', []):
                if adv.get('status') in [9, 11]:
                    campaign_ids.append(adv.get('advertId'))

    if not campaign_ids: return {"status": "success", "campaigns": []}

    # 2. Получаем детальную статистику по этим ID
    stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
    # WB принимает список ID в теле запроса (POST) или через JSON
    stats_res = requests.post(stats_url, headers=headers, json=[{"id": cid} for cid in campaign_ids[:10]])
    
    result = []
    if stats_res.status_code == 200:
        raw_stats = stats_res.json()
        for c_stat in raw_stats:
            # Берем данные за сегодня (последний день в списке days)
            days = c_stat.get('days', [])
            today_data = days[-1] if days else {}
            
            result.append({
                "id": c_stat.get('advertId'),
                "views": today_data.get('views', 0),
                "clicks": today_data.get('clicks', 0),
                "ctr": today_data.get('ctr', 0),
                "cpm": today_data.get('cpm', 0),
                "sum": today_data.get('sum', 0),
                "atc": today_data.get('atc', 0), # корзины
                "orders": today_data.get('orders', 0)
            })

    return {"status": "success", "campaigns": result}
