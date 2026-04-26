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
    
    # Берем интервал в 7 дней, чтобы API точно "проснулось"
    date_to = now.strftime('%Y-%m-%d')
    date_from = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    
    target_ids = [28255817, 27952577]
    
    try:
        # Самый актуальный метод для всех типов кампаний
        url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
        payload = [{"id": cid, "dates": [date_from, date_to]} for cid in target_ids]
        
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if res.status_code != 200:
            return {"status": "error", "message": f"Код ответа WB: {res.status_code}"}
            
        raw_data = res.json()
        final_results = []
        
        for item in raw_data:
            cid = item.get('advertId')
            days = item.get('days', [])
            
            # Фильтруем только те дни, где были реальные показы
            active_days = [d for d in days if d.get('views', 0) > 0]
            
            # Берем данные за самый свежий активный день, либо просто за последний в списке
            stats = active_days[-1] if active_days else (days[-1] if days else {})
            
            name = "Поиск" if cid == 28255817 else "АРК"
            
            final_results.append({
                "id": cid,
                "name": name,
                "status": "Идет" if stats.get('views', 0) > 0 else "Активна",
                "views": stats.get('views', 0),
                "clicks": stats.get('clicks', 0),
                "ctr": stats.get('ctr', 0),
                "cpm": stats.get('cpm', 0),
                "sum": int(stats.get('sum', 0)),
                "atc": stats.get('atc', 0),
                "orders": stats.get('orders', 0),
                "date": stats.get('date', date_to)
            })

        return {"status": "success", "campaigns": final_results}

    except Exception as e:
        return {"status": "error", "message": str(e)}
