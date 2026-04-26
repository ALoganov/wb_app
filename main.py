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
    
    # 1. Получаем список всех ID через метод count (он самый стабильный)
    info_url = "https://advert-api.wildberries.ru/adv/v1/promotion/count"
    
    try:
        r_info = requests.get(info_url, headers=headers, timeout=10)
        if r_info.status_code != 200:
            return {"status": "error", "message": f"WB Error: {r_info.status_code}"}

        data = r_info.json()
        all_ids = []
        
        # Собираем вообще все кампании из всех групп
        adverts = data.get('adverts', [])
        for group in adverts:
            # Тип группы: 6 - Поиск, 8 - Авто, 9 - Поиск+Каталог
            for item in group.get('advert_list', []):
                all_ids.append({
                    "id": item.get('advertId'),
                    "status": item.get('status'),
                    "type": group.get('type')
                })

        if not all_ids:
            return {"status": "success", "campaigns": [], "msg": "Кампаний не найдено"}

        # 2. Теперь запрашиваем информацию по этим ID (метод /adverts более подробный)
        # Ограничимся последними 10 кампаниями, чтобы не спамить
        target_ids = [c['id'] for c in all_ids[-10:]]
        
        # Метод /adverts вернет нам названия и текущие ставки
        list_url = "https://advert-api.wildberries.ru/adv/v1/promotion/adverts"
        r_list = requests.get(list_url, headers=headers, params={"params": 0}, timeout=10)
        
        names_map = {}
        if r_list.status_code == 200:
            names_map = {c.get('advertId'): c.get('name') for c in r_list.json()}

        # 3. Запрашиваем статистику (v2/fullstats) для этих ID
        stats_url = "https://advert-api.wildberries.ru/adv/v2/fullstats"
        payload = [{"id": cid} for cid in target_ids]
        r_stats = requests.post(stats_url, headers=headers, json=payload, timeout=10)
        
        final_campaigns = []
        stats_data = {}
        if r_stats.status_code == 200:
            # Группируем статистику по ID
            for s in r_stats.json():
                days = s.get('days', [])
                stats_data[s.get('advertId')] = days[-1] if days else {}

        for c in all_ids[-10:]:
            cid = c['id']
            s = stats_data.get(cid, {})
            
            # Статусы для понимания пользователем
            status_names = {7: "Завершена", 8: "Отказ", 9: "Идет", 11: "Пауза"}
            
            final_campaigns.append({
                "id": cid,
                "name": names_map.get(cid, f"Кампания {cid}"),
                "status": status_names.get(c['status'], f"Статус {c['status']}"),
                "views": s.get('views', 0),
                "clicks": s.get('clicks', 0),
                "ctr": s.get('ctr', 0),
                "cpm": s.get('cpm', 0),
                "sum": s.get('sum', 0),
                "orders": s.get('orders', 0),
                "atc": s.get('atc', 0),
                "date": s.get('date', 'Нет данных')
            })

        return {"status": "success", "campaigns": final_campaigns}

    except Exception as e:
        return {"status": "error", "message": str(e)}
