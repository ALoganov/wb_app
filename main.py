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
    now_moscow = datetime.now(offset)
    
    # Попробуем самый надежный формат: запрашиваем данные за последние 24 часа 
    # без привязки к 00:00, чтобы увидеть хоть что-то
    start_point = (now_moscow - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')
    
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    headers = {"Authorization": WB_TOKEN}
    params = {"dateFrom": start_point, "flag": 0} # flag=0 для всех заказов
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        if not isinstance(data, list):
            return {"status": "error", "message": "WB вернул не список", "raw": str(data)[:200]}

        # ОТЛАДКА: Посмотрим на дату самого первого заказа в списке
        sample_date = data[0].get('date') if len(data) > 0 else "Нет данных"
        
        # Считаем заказы за сегодня (24 апреля)
        today_str = now_moscow.strftime('%Y-%m-%d')
        today_orders = [item for item in data if today_str in item.get('date', '')]
        
        return {
            "status": "success",
            "orders": len(today_orders),
            "revenue": int(sum(item.get('priceWithDisc', 0) for item in today_orders)),
            "debug": {
                "total_in_response": len(data),
                "first_order_date": sample_date,
                "searching_for": today_str,
                "requested_from": start_point
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
