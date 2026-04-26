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
    
    # 1. Получаем список ID всех кампаний без фильтрации по статусу (v1/promotion/count)
    adv_list_url = "https://advert-api.wildberries.ru/adv/v1/promotion/count"
    adv_data = fetch_wb(adv_list_url, headers)
    
    if not adv_data or 'adverts' not in adv_data:
        return {"status1": "error", "message": "Не удалось получить список кампаний"}

    campaign_ids = []
    # Собираем ID из всех возможных групп (9 - идут, 11 - на паузе, 7 - завершены и т.д.)
    for group in adv_data['adverts']:
        for adv in group.get('advert_list', []):
            cid = adv.get('advertId')
            if cid:
                campaign_ids.append(cid)

    if not campaign_ids:
        return {"status1": "success", "campaigns": [], "msg": "Кампании не найдены в списке"}

    # 2. Запрашиваем статистику. 
    # ВАЖНО: берем только последние 10-20 кампаний, чтобы не перегрузить API
    stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
    
    # Мы запрашиваем список словарей [{"id": ...}, ...]
    payload = [{"id": cid} for cid in campaign_ids[-15:]] 
    stats_res = requests.post(stats_url, headers=headers, json=payload)
    
    result = []
    if stats_res.status_code == 200:
        raw_stats = stats_res.json()
        
        for c_stat in raw_stats:
            days = c_stat.get('days', [])
            # Если кампании старые, в списке 'days' может не быть сегодняшней даты.
            # Берем самые свежие данные из имеющихся:
            current_metrics = days[-1] if days else {}
            
            # Если данных за сегодня/вчера вообще нет в статистике, пропустим пустые
            if not current_metrics and not c_stat.get('advertId'):
                continue

            result.append({
                "id": c_stat.get('advertId'),
                "views": current_metrics.get('views', 0),
                "clicks": current_metrics.get('clicks', 0),
                "ctr": current_metrics.get('ctr', 0),
                "cpm": current_metrics.get('cpm', 0),
                "sum": current_metrics.get('sum', 0),
                "atc": current_metrics.get('atc', 0),
                "orders": current_metrics.get('orders', 0),
                "date": current_metrics.get('date', 'Нет данных') # Посмотрим, за какое число данные
            })

    return {"status1": "success", "campaigns": result}
