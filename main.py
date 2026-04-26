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
    # Твои ID
    ark_id = 27952577
    search_id = 28255817
    
    final_results = []

    # 1. Запрашиваем АРК
    try:
        # Для АРК используем метод авто-статистики
        res_ark = requests.get(f"https://advert-api.wildberries.ru/adv/v1/auto/stat-words?id={ark_id}", headers=headers, timeout=10)
        ark_data = {}
        if res_ark.status_code == 200:
            d = res_ark.json()
            # Суммируем показатели по всем ключевым словам за сегодня
            stat = d.get('stat', [])
            ark_data = {
                "views": sum(x.get('views', 0) for x in stat),
                "clicks": sum(x.get('clicks', 0) for x in stat),
                "sum": sum(x.get('sum', 0) for x in stat),
                "atc": sum(x.get('atc', 0) for x in stat),
                "orders": sum(x.get('orders', 0) for x in stat),
            }
        
        final_results.append({
            "id": ark_id, "name": "АРК", "status": "Идет" if ark_data.get('views', 0) > 0 else "Активна",
            "views": ark_data.get('views', 0), "clicks": ark_data.get('clicks', 0),
            "ctr": round((ark_data.get('clicks', 0) / ark_data.get('views', 1) * 100), 2) if ark_data.get('views', 0) > 0 else 0,
            "cpm": "-", "sum": int(ark_data.get('sum', 0)), "atc": ark_data.get('atc', 0), "orders": ark_data.get('orders', 0),
            "date": "Сегодня"
        })
    except: pass

    # 2. Запрашиваем Поиск
    try:
        res_search = requests.get(f"https://advert-api.wildberries.ru/adv/v1/stat/words?id={search_id}", headers=headers, timeout=10)
        search_data = {}
        if res_search.status_code == 200:
            d = res_search.json()
            # В поиске данные лежат в корне или в списке words
            words = d.get('words', {}).get('keywords', [])
            search_data = {
                "views": sum(x.get('views', 0) for x in words),
                "clicks": sum(x.get('clicks', 0) for x in words),
                "sum": sum(x.get('sum', 0) for x in words),
            }

        final_results.append({
            "id": search_id, "name": "Поиск", "status": "Идет" if search_data.get('views', 0) > 0 else "Активна",
            "views": search_data.get('views', 0), "clicks": search_data.get('clicks', 0),
            "ctr": round((search_data.get('clicks', 0) / search_data.get('views', 1) * 100), 2) if search_data.get('views', 0) > 0 else 0,
            "cpm": "-", "sum": int(search_data.get('sum', 0)), "atc": "-", "orders": "-",
            "date": "Сегодня"
        })
    except: pass

    return {"status": "success", "campaigns": final_results}
