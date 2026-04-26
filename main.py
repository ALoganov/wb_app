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
    
    # Пробуем метод специально для АРК (Автоматических кампаний)
    # Это самый актуальный метод на 2026 год
    auto_url = "https://advert-api.wildberries.ru/adv/v1/auto/stat"
    
    # Для начала попробуем получить список всех кампаний через общую информацию
    info_url = "https://advert-api.wildberries.ru/adv/v1/promotion/count"
    
    try:
        # Пытаемся понять, какие кампании вообще есть
        r_info = requests.get(info_url, headers=headers, timeout=10)
        
        if r_info.status_code == 404:
             return {
                "status": "error", 
                "message": "Метод не найден (404). Проверьте права токена на 'Продвижение'."
            }

        data = r_info.json()
        campaigns = []
        
        # Если есть данные по кампаниям, вытащим их
        adverts = data.get('adverts', [])
        for group in adverts:
            for item in group.get('advert_list', []):
                # Нам нужны только те, что сейчас работают (статус 9)
                if item.get('status') == 9:
                    campaigns.append({
                        "id": item.get('advertId'),
                        "name": f"Кампания {item.get('advertId')}",
                        "views": "-", "clicks": "-", "ctr": "-", "cpm": "-", "sum": "-", "orders": "-",
                        "date": "Ожидание данных"
                    })

        if not campaigns:
            return {"status": "success", "campaigns": [], "msg": "Нет активных кампаний в статусе 9"}

        return {"status": "success", "campaigns": campaigns}

    except Exception as e:
        return {"status": "error", "message": str(e)}
