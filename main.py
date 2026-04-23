import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta

app = FastAPI()

# РАЗРЕШАЕМ GitHub Pages обращаться к нашему серверу
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В идеале замени на свою ссылку github.io
    allow_methods=["*"],
    allow_headers=["*"],
)

WB_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjYwMzAydjEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjMsImVudCI6MSwiZXhwIjoxNzkyNzMxNTY3LCJmb3IiOiJzZWxmIiwiaWQiOiIwMTlkYmI0OC00MGMyLTc4Y2QtOWJhYS03NTNmMjJkMTkwNjIiLCJpaWQiOjU2MjYyODg3LCJvaWQiOjQwMDgxMDEsInMiOjEwNzM3NDE5MjQsInNpZCI6IjUyMTQ2YjUxLWRhY2QtNDdmNC04Njk3LTNhZTgxODRjZmVkYiIsInQiOmZhbHNlLCJ1aWQiOjU2MjYyODg3fQ.lWe-pechdZHPQr5DWn34XiQP7ISv7ba5tECz7UrqUgQWZaSlIonLX8tSZfN8QLac-2rJi4QKS7q_RbZhj2LZRw"

@app.get("/stats")
def get_wb_stats():
    # Получаем дату начала дня (сегодня с 00:00)
    date_from = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT00:00:00')
    
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    headers = {"Authorization": WB_TOKEN}
    params = {"dateFrom": date_from}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        # Считаем количество заказов и общую сумму
        total_orders = len(data)
        total_sum = sum(item.get('priceWithDisc', 0) for item in data) / 100 # Если цена в копейках
        
        return {
            "orders": total_orders,
            "revenue": round(total_sum, 2),
            "status": "success"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)