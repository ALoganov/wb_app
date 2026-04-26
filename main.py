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
    result_ids = []
    
    # ТЕСТ 1: Пробуем метод /adverts (основной)
    r1 = requests.get("https://advert-api.wildberries.ru/adv/v1/promotion/adverts", headers=headers)
    if r1.status_code == 200:
        data = r1.json()
        if isinstance(data, list):
            result_ids = [{"id": c.get('advertId'), "name": c.get('name')} for c in data if c.get('status') in [9, 11]]

    # ТЕСТ 2: Если первый пуст, пробуем метод /count (альтернативный)
    if not result_ids:
        r2 = requests.get("https://advert-api.wildberries.ru/adv/v1/promotion/count", headers=headers)
        if r2.status_code == 200:
            data = r2.json()
            adverts = data.get('adverts', [])
            for group in adverts:
                for a in group.get('advert_list', []):
                    result_ids.append({"id": a.get('advertId'), "name": f"ID: {a.get('advertId')}"})

    if not result_ids:
        # Если всё еще пусто, возвращаем детальный статус ответов для диагностики
        return {
            "status": "error", 
            "message": "Кампании не найдены ни одним методом",
            "debug": {
                "method_adverts_status": r1.status_code,
                "method_count_status": r2.status_code if 'r2' in locals() else "not_tried",
                "token_preview": f"{WB_TOKEN[:10]}..." if WB_TOKEN else "MISSING"
            }
        }

    # Если нашли ID, запрашиваем статистику по первым 10
    stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
    payload = [{"id": c['id']} for c in result_ids[:10]]
    
    try:
        res = requests.post(stats_url, headers=headers, json=payload, timeout=15)
        if res.status_code != 200:
            return {"status": "error", "message": f"Статистика недоступна (Код {res.status_code})"}
        
        raw_stats = res.json()
        final_campaigns = []
        
        # Мапим имена
        names = {c['id']: c['name'] for c in result_ids}
        
        for s in raw_stats:
            days = s.get('days', [])
            # Берем самый свежий день из доступных
            current = days[-1] if days else {}
            
            final_campaigns.append({
                "id": s.get('advertId'),
                "name": names.get(s.get('advertId'), "Без имени"),
                "views": current.get('views', 0),
                "clicks": current.get('clicks', 0),
                "ctr": current.get('ctr', 0),
                "cpm": current.get('cpm', 0),
                "sum": current.get('sum', 0),
                "orders": current.get('orders', 0),
                "date": current.get('date', 'Нет данных')
            })
            
        return {"status": "success", "campaigns": final_campaigns}
    except Exception as e:
        return {"status": "error", "message": str(e)}
