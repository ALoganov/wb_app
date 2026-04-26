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
    
    try:
        # 1. Получаем список кампаний через count, чтобы понять типы (8 - Авто, 6 - Поиск)
        r_info = requests.get("https://advert-api.wildberries.ru/adv/v1/promotion/count", headers=headers, timeout=10)
        if r_info.status_code != 200:
            return {"status": "error", "message": "Ошибка доступа к WB"}

        data = r_info.json()
        campaigns_to_check = []
        
        # Разбираем кампании по типам
        adverts = data.get('adverts', [])
        for group in adverts:
            adv_type = group.get('type') # 8 - АРК, 6 - Поиск
            for item in group.get('advert_list', []):
                # Нам интересны только активные (9) или те, что недавно работали
                if item.get('status') in [9, 11]:
                    campaigns_to_check.append({
                        "id": item.get('advertId'),
                        "type": adv_type
                    })

        # Если активных не нашли, возьмем последние 3 из списка вообще
        if not campaigns_to_check:
             for group in adverts:
                for item in group.get('advert_list', []):
                    campaigns_to_check.append({"id": item.get('advertId'), "type": group.get('type')})
             campaigns_to_check = campaigns_to_check[-3:]

        final_results = []

        for camp in campaigns_to_check:
            cid = camp['id']
            ctype = camp['type']
            
            # Для АРК (8) и Поиска (6) у WB сейчас лучше работают отдельные запросы
            # Попробуем универсальный метод получения краткой статистики за сегодня
            stat_url = f"https://advert-api.wildberries.ru/adv/v1/fullstat?id={cid}"
            res_s = requests.get(stat_url, headers=headers, timeout=10)
            
            s_data = {}
            if res_s.status_code == 200:
                # Берем последнюю запись из статистики
                days = res_s.json().get('days', [])
                s_data = days[-1] if days else {}

            final_results.append({
                "id": cid,
                "name": "АРК" if ctype == 8 else ("Поиск" if ctype == 6 else f"Тип {ctype}"),
                "status": "Активна" if camp.get('type') else "В списке",
                "views": s_data.get('views', 0),
                "clicks": s_data.get('clicks', 0),
                "ctr": s_data.get('ctr', 0),
                "cpm": s_data.get('cpm', 0),
                "sum": s_data.get('sum', 0),
                "atc": s_data.get('atc', 0),
                "orders": s_data.get('orders', 0),
                "date": s_data.get('date', 'Нет данных')
            })

        return {"status": "success", "campaigns": final_results}

    except Exception as e:
        return {"status": "error", "message": str(e)}
