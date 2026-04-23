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
    # Устанавливаем московское время (UTC+3)
    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)
    
    # Берем данные с начала текущих суток по Москве
    date_from = now.strftime('%Y-%m-%dT00:00:00')
    
    # Метод /orders показывает свежие заказы
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    headers = {"Authorization": WB_TOKEN}
    params = {"dateFrom": date_from}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return {"status": "error", "message": f"WB Error: {response.status_code}"}
            
        data = response.json()
        
        # Фильтруем заказы, которые были сделаны именно сегодня (на всякий случай)
        today_orders = [
            item for item in data 
            if item.get('date').split('T')[0] == now.strftime('%Y-%m-%d')
        ]
        
        total_orders = len(today_orders)
        # Считаем сумму с учетом скидки WB (priceWithDisc)
        total_sum = sum(item.get('priceWithDisc', 0) for item in today_orders)
        
        return {
            "orders": total_orders,
            "revenue": int(total_sum),
            "status": "success",
            "server_time": now.strftime('%H:%M:%S')
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
