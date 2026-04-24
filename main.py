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
    # Работаем с Московским временем
    offset = timezone(timedelta(hours=3))
    now_moscow = datetime.now(offset)
    today_str = now_moscow.strftime('%Y-%m-%d')
    
    # Чтобы WB точно отдал данные, запрашиваем со вчерашнего дня, 
    # а фильтровать будем уже сами внутри кода.
    yesterday = (now_moscow - timedelta(days=1)).strftime('%Y-%m-%dT00:00:00')
    
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    headers = {"Authorization": WB_TOKEN}
    params = {"dateFrom": yesterday}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 429:
            return {"status": "error", "message": "Слишком много запросов к WB. Подождите минуту."}
        
        data = response.json()
        
        if not isinstance(data, list):
            return {"status": "success", "orders": 0, "revenue": 0, "msg": "Нет данных от WB"}

        # Фильтруем заказы: оставляем только те, у которых дата совпадает с сегодняшней (по Москве)
        # Формат даты в WB обычно: '2026-04-24T12:34:56'
        today_orders = [
            item for item in data 
            if item.get('date', '').startswith(today_str)
        ]
        
        total_orders = len(today_orders)
        total_sum = sum(item.get('priceWithDisc', 0) for item in today_orders)
        
        return {
            "orders": total_orders,
            "revenue": int(total_sum),
            "status": "success",
            "check_date": today_str,
            "count_all_returned": len(data) # для отладки, сколько всего прислал WB
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
