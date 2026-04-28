import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone

app = FastAPI()

# Разрешаем запросы из Telegram
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

@app.get("/stats")
def get_stats():
    headers = {"Authorization": WB_TOKEN}
    offset = timezone(timedelta(hours=3)) # Московское время
    now = datetime.now(offset)
    
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    # Загружаем заказы и продажи (за последние 2 дня для надежности)
    date_from = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
    
    orders_raw = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/orders", headers, {"dateFrom": date_from}) or []
    sales_raw = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/sales", headers, {"dateFrom": date_from}) or []

    def calc(data, date_str, key):
        items = [item for item in data if item.get('date', '').startswith(date_str)]
        count = len(items)
        rev = sum(item.get(key, 0) for item in items)
        return {"count": count, "rev": int(rev)}

    return {
        "today": {
            "orders": calc(orders_raw, today_str, 'finishedPrice'),
            "sales": calc(sales_raw, today_str, 'forPay')
        },
        "yesterday": {
            "orders": calc(orders_raw, yesterday_str, 'finishedPrice'),
            "sales": calc(sales_raw, yesterday_str, 'forPay')
        }
    }

@app.get("/adv")
def get_adv():
    headers = {"Authorization": WB_TOKEN}

    #debugging
    url=f"https://advert-api.wildberries.ru/adv/v1/promotion/count"

    try:
        adv_data = requests.get(url, headers=headers, timeout=10)
                       
        if adv_data.status_code == 200 :
            #return adv_data['adverts'].get('status')
            if not adv_data: return {"status": "error", "message": "Нет данных по рекламе ", "code": adv_data.status_code}

            if 'adverts' in adv_data: return {"status_adv": adv_data.status_code}
            else: return {"status_not_adv": adv_data.status_code}
            #if 'adverts' in adv_data:
                #for advert in data['adverts']:
            #return {"adv_data": adv_data, "status": adv_data.status_code}
 
            
            #return {"status": adv_data.status_code}
        else: 
            return {"statusE": adv_data.status_code}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

    #debugging
    
    # Твои подтвержденные ID кампаний
    target_ids = [
        {"id": 28255817, "name": "Поиск"},
        {"id": 27952577, "name": "АРК"}
    ]
    
    final_results = []

    for item in target_ids:
        cid = item["id"]
        # Используем индивидуальный GET запрос - самый стабильный метод для разных типов кампаний
        url = f"https://advert-api.wildberries.ru/adv/v1/fullstat?id={cid}"
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            best_stats = {}
            
            if res.status_code == 200:
                days = res.json().get('days', [])
                if days:
                    # Ищем последний день, где были показы, чтобы не показывать нули по воскресеньям
                    active_days = [d for d in days if d.get('views', 0) > 0]
                    best_stats = active_days[-1] if active_days else days[-1]

            final_results.append({
                "id": cid,
                "name": item["name"],
                "status": "Идет" if best_stats.get('views', 0) > 0 else "Активна",
                "views": best_stats.get('views', 0),
                "clicks": best_stats.get('clicks', 0),
                "ctr": best_stats.get('ctr', 0),
                "cpm": best_stats.get('cpm', 0),
                "sum": int(best_stats.get('sum', 0)),
                "atc": best_stats.get('atc', 0),
                "orders": best_stats.get('orders', 0),
                "date": best_stats.get('date', "Нет данных")
            })
        except:
            continue

    return {"status": "success", "campaigns": final_results}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
