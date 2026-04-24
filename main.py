import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WB_TOKEN= os.getenv("WB_TOKEN_KEY")

@app.get("/stats")
def get_wb_stats():
    # Проверка на случай, если забыли прописать токен в настройках
    if not WB_TOKEN:
        return {"status": "error", "message": "API токен не настроен на сервере"}
    
    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)
    
    # Берем данные за 3 дня
    start_point = (now - timedelta(days=3)).strftime('%Y-%m-%dT00:00:00')
    
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    headers = {"Authorization": WB_TOKEN}
    params = {"dateFrom": start_point, "flag": 0}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        if not isinstance(data, list):
            return {"status": "error", "message": "API WB временно недоступно"}

        today_str = now.strftime('%Y-%m-%d')
        yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')

        today_orders = [i for i in data if today_str in i.get('date', '')]
        yesterday_orders = [i for i in data if yesterday_str in i.get('date', '')]
        
        return {
            "status": "success",
            "today": {
                "orders": len(today_orders),
                "revenue": int(sum(i.get('finishedPrice', 0) for i in today_orders))
            },
            "yesterday": {
                "orders": len(yesterday_orders),
                "revenue": int(sum(i.get('finishedPrice', 0) for i in yesterday_orders))
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
