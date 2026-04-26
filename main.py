import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WB_TOKEN = os.getenv("WB_TOKEN_KEY")

@app.get("/adv")
def get_adv():
    headers = {"Authorization": WB_TOKEN}
    offset = timezone(timedelta(hours=3))
    today_date = datetime.now(offset).strftime('%Y-%m-%d')
    
    try:
        # Список твоих активных ID, которые мы нашли
        target_ids = [28255817, 27952577, 16936998]
        
        # Метод v2/fullstats работает только через POST
        stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
        
        # Формируем запрос: просим данные по конкретным ID
        payload = [{"id": cid} for cid in target_ids]
        
        res = requests.post(stats_url, headers=headers, json=payload, timeout=10)
        
        final_results = []
        stats_map = {}
        
        if res.status_code == 200:
            raw_stats = res.json()
            for item in raw_stats:
                # Ищем в массиве days запись за сегодня
                days = item.get('days', [])
                today_data = next((d for d in days if d.get('date', '').startswith(today_date)), {})
                
                # Если за сегодня еще нет данных (ВБ тормозит), берем самую последнюю доступную запись
                if not today_data and days:
                    today_data = days[-1]
                
                stats_map[item.get('advertId')] = today_data

        # Формируем ответ для фронтенда
        for cid in target_ids:
            s = stats_map.get(cid, {})
            
            # Определяем имя по твоим данным
            name = "Поиск" if cid == 28255817 else ("АРК" if cid == 27952577 else f"Кампания {cid}")
            
            final_results.append({
                "id": cid,
                "name": name,
                "status": "Идет" if s.get('views', 0) > 0 else "Активна",
                "views": s.get('views', 0),
                "clicks": s.get('clicks', 0),
                "ctr": s.get('ctr', 0),
                "cpm": s.get('cpm', 0),
                "sum": s.get('sum', 0),
                "atc": s.get('atc', 0),
                "orders": s.get('orders', 0),
                "date": s.get('date', today_date)
            })

        return {"status": "success", "campaigns": final_results}

    except Exception as e:
        return {"status": "error", "message": str(e)}
