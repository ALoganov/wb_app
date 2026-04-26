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
    
    # Формируем даты для запроса (сегодня и вчера)
    date_to = now.strftime('%Y-%m-%d')
    date_from = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        target_ids = [28255817, 27952577, 16936998]
        stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
        
        # Передаем ID и конкретные даты — это заставляет API выгрузить данные
        payload = [{"id": cid, "dates": [date_from, date_to]} for cid in target_ids]
        
        res = requests.post(stats_url, headers=headers, json=payload, timeout=15)
        
        final_results = []
        if res.status_code == 200:
            raw_stats = res.json()
            # Создаем словарь для быстрого доступа по ID
            stats_dict = {item.get('advertId'): item for item in raw_stats}
            
            for cid in target_ids:
                item = stats_dict.get(cid, {})
                days = item.get('days', [])
                
                # Ищем данные именно за сегодня
                current = next((d for d in days if d.get('date', '').startswith(date_to)), {})
                
                # Если за сегодня пусто (ВБ еще не обновил), берем последнюю запись (за вчера)
                if not current and days:
                    current = days[-1]

                name = "Поиск" if cid == 28255817 else ("АРК" if cid == 27952577 else f"Кампания {cid}")
                
                final_results.append({
                    "id": cid,
                    "name": name,
                    "status": "Идет" if current.get('views', 0) > 0 else "Активна",
                    "views": current.get('views', 0),
                    "clicks": current.get('clicks', 0),
                    "ctr": current.get('ctr', 0),
                    "cpm": current.get('cpm', 0),
                    "sum": current.get('sum', 0),
                    "atc": current.get('atc', 0),
                    "orders": current.get('orders', 0),
                    "date": current.get('date', date_to)
                })
        else:
             return {"status": "error", "message": f"WB API Error: {res.status_code}"}

        return {"status": "success", "campaigns": final_results}

    except Exception as e:
        return {"status": "error", "message": str(e)}
