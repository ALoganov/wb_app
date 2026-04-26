import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WB_TOKEN = os.getenv("WB_TOKEN_KEY")

@app.get("/adv")
def get_adv():
    headers = {"Authorization": WB_TOKEN}
    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)
    
    # Интервал 3 дня (сегодня, вчера, позавчера)
    date_to = now.strftime('%Y-%m-%d')
    date_from = (now - timedelta(days=2)).strftime('%Y-%m-%d')
    
    target_ids = [28255817, 27952577]
    final_results = []

    for cid in target_ids:
        try:
            # Опрашиваем КАЖДУЮ кампанию отдельным POST-запросом
            url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
            payload = [{"id": cid, "dates": [date_from, date_to]}]
            
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            
            stats = {}
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    days = data[0].get('days', [])
                    # Ищем самый свежий день с показами
                    active_days = [d for d in days if d.get('views', 0) > 0]
                    stats = active_days[-1] if active_days else (days[-1] if days else {})
            
            name = "Поиск" if cid == 28255817 else "АРК"
            
            # Добавляем в результат, даже если данных нет (чтобы видеть статус)
            final_results.append({
                "id": cid,
                "name": name,
                "status": "Идет" if stats.get('views', 0) > 0 else "Нет данных",
                "views": stats.get('views', 0),
                "clicks": stats.get('clicks', 0),
                "ctr": stats.get('ctr', 0),
                "cpm": stats.get('cpm', 0),
                "sum": int(stats.get('sum', 0)),
                "atc": stats.get('atc', 0),
                "orders": stats.get('orders', 0),
                "date": stats.get('date', date_to)
            })
        except:
            continue

    return {"status": "success", "campaigns": final_results}
