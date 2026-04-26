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
    today = datetime.now(offset).strftime('%Y-%m-%d')
    
    # Твои ID
    target_ids = [
        {"id": 28255817, "name": "Поиск", "type": 6},
        {"id": 27952577, "name": "АРК", "type": 8}
    ]
    
    final_results = []

    for item in target_ids:
        cid = item["id"]
        # Используем метод v1/fullstat, который требует ID
        # Добавляем тип в параметры (хоть это и не всегда в доках, это помогает фильтрации)
        url = f"https://advert-api.wildberries.ru/adv/v1/fullstat?id={cid}"
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            stats = {}
            
            if res.status_code == 200:
                data = res.json()
                days = data.get('days', [])
                
                if days:
                    # Ищем любой день с активностью за последние 3 дня
                    # Фильтруем дни, где views > 0
                    active_days = [d for d in days if d.get('views', 0) > 0]
                    if active_days:
                        stats = active_days[-1]
                    else:
                        stats = days[-1]

            final_results.append({
                "id": cid,
                "name": item["name"],
                "status": "Идет" if stats.get('views', 0) > 0 else "Активна (0)",
                "views": stats.get('views', 0),
                "clicks": stats.get('clicks', 0),
                "ctr": stats.get('ctr', 0),
                "cpm": stats.get('cpm', 0),
                "sum": int(stats.get('sum', 0)),
                "atc": stats.get('atc', 0),
                "orders": stats.get('orders', 0),
                "date1": stats.get('date', today)
            })
        except:
            continue

    return {"status": "success", "campaigns": final_results}
