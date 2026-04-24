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

WB_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjYwMzAydjEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjMsImVudCI6MSwiZXhwIjoxNzkyNzMxNTY3LCJmb3IiOiJzZWxmIiwiaWQiOiIwMTlkYmI0OC00MGMyLTc4Y2QtOWJhYS03NTNmMjJkMTkwNjIiLCJpaWQiOjU2MjYyODg3LCJvaWQiOjQwMDgxMDEsInMiOjEwNzM3NDE5MjQsInNpZCI6IjUyMTQ2YjUxLWRhY2QtNDdmNC04Njk3LTNhZTgxODRjZmVkYiIsInQiOmZhbHNlLCJ1aWQiOjU2MjYyODg3fQ.lWe-pechdZHPQr5DWn34XiQP7ISv7ba5tECz7UrqUgQWZaSlIonLX8tSZfN8QLac-2rJi4QKS7q_RbZhj2LZRw"

@app.get("/stats")
def get_wb_stats():
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
                "revenue": int(sum(i.get('priceWithDisc', 0) for i in today_orders))
            },
            "yesterday": {
                "orders": len(yesterday_orders),
                "revenue": int(sum(i.get('priceWithDisc', 0) for i in yesterday_orders))
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
