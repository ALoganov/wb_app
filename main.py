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
    
    # 1. Получаем список кампаний
    r1 = requests.get("https://advert-api.wildberries.ru/adv/v1/promotion/adverts", headers=headers)
    if r1.status_code != 200:
        return {"status": "error", "message": f"Ошибка доступа к списку: {r1.status_code}"}
    
    data = r1.json()
    if not isinstance(data, list) or not data:
        return {"status": "success", "campaigns": [], "msg": "Кампании не найдены"}

    # Берем активные (9) и на паузе (11)
    target_campaigns = [c for c in data if c.get('status') in [9, 11]]
    if not target_campaigns:
        target_campaigns = data[-2:] # Если активных нет, берем 2 последних для теста

    # 2. Пробуем получить статистику
    stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
    payload = [{"id": c.get('advertId')} for c in target_campaigns]
    
    final_list = []
    try:
        res = requests.post(stats_url, headers=headers, json=payload, timeout=10)
        
        # Если статистика доступна (200)
        if res.status_code == 200:
            raw_stats = res.json()
            stats_map = {s.get('advertId'): s.get('days', [{}])[-1] for s in raw_stats}
            
            for c in target_campaigns:
                cid = c.get('advertId')
                s = stats_map.get(cid, {})
                final_list.append({
                    "id": cid,
                    "name": c.get('name', 'Без имени'),
                    "views": s.get('views', 0),
                    "clicks": s.get('clicks', 0),
                    "ctr": s.get('ctr', 0),
                    "cpm": s.get('cpm', 0),
                    "sum": s.get('sum', 0),
                    "orders": s.get('orders', 0),
                    "date": s.get('date', 'Нет данных')
                })
        else:
            # Если 404 или любая другая ошибка — показываем только названия
            for c in target_campaigns:
                final_list.append({
                    "id": c.get('advertId'),
                    "name": c.get('name', 'Без имени'),
                    "views": "-", "clicks": "-", "ctr": "-", "cpm": "-", "sum": "-", "orders": "-",
                    "date": "Статистика пока недоступна"
                })

        return {"status": "success", "campaigns": final_list}

    except Exception as e:
        return {"status": "error", "message": str(e)}
