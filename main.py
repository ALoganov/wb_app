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
    today_date = datetime.now(offset).strftime('%Y-%m-%d')
    
    # Твои подтвержденные ID
    target_ids = [28255817, 27952577, 16936998]
    final_results = []

    for cid in target_ids:
        # Используем индивидуальный метод GET, который часто стабильнее
        url = f"https://advert-api.wildberries.ru/adv/v1/fullstat?id={cid}"
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            s_data = {}
            
            if res.status_code == 200:
                data = res.json()
                # WB возвращает список дней в поле 'days'
                days = data.get('days', [])
                if days:
                    # Ищем сегодняшний день, если нет - берем самый последний доступный
                    today_entry = next((d for d in days if d.get('date', '').startswith(today_date)), days[-1])
                    s_data = today_entry
            
            # Определяем имя
            if cid == 28255817: name = "Поиск"
            elif cid == 27952577: name = "АРК"
            else: name = f"Кампания {cid}"

            final_results.append({
                "id": cid,
                "name": name,
                "status": "Идет" if s_data.get('views', 0) > 0 else "Активна",
                "views": s_data.get('views', 0),
                "clicks": s_data.get('clicks', 0),
                "ctr": s_data.get('ctr', 0),
                "cpm": s_data.get('cpm', 0),
                "sum": s_data.get('sum', 0),
                "atc": s_data.get('atc', 0),
                "orders": s_data.get('orders', 0),
                "date": s_data.get('date', today_date)
            })
        except:
            continue

    if not final_results:
        return {"status": "error", "message": "Не удалось получить данные ни по одной кампании"}

    return {"status": "success", "campaigns": final_results}
