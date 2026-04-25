import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone

app = FastAPI()

# Разрешаем запросы от твоего GitHub Pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Токен берем из переменных окружения Render
WB_TOKEN = os.getenv("WB_TOKEN_KEY")

@app.get("/stats")
def get_wb_stats():
    if not WB_TOKEN:
        return {"status": "error", "message": "API токен не настроен"}

    # Настройка времени (Московское)
    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Запрашиваем данные с запасом (3 дня)
    start_point = (now - timedelta(days=3)).strftime('%Y-%m-%dT00:00:00')
    
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    headers = {"Authorization": WB_TOKEN}
    params = {"dateFrom": start_point, "flag": 0}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return {"status": "error", "message": f"Ошибка WB: {response.status_code}"}
            
        data = response.json()
        if not isinstance(data, list):
            return {"status": "success", "today": {"orders": 0, "revenue": 0}, "yesterday": {"orders": 0, "revenue": 0}}

        # Фильтруем данные
        today_orders = [i for i in data if today_str in i.get('date', '')]
        yesterday_orders = [i for i in data if yesterday_str in i.get('date', '')]

        # Твоя уникальная формула расчета суммы
        def calculate_revenue(orders_list):
            return sum(
                item.get('totalPrice', 0) * (1 - (item.get('discountPercent', 0) - 1) / 100) 
                for item in orders_list
            )

        return {
            "status": "success",
            "today": {
                "orders": len(today_orders),
                "revenue": int(calculate_revenue(today_orders))
            },
            "yesterday": {
                "orders": len(yesterday_orders),
                "revenue": int(calculate_revenue(yesterday_orders))
            },
            "meta": {
                "server_time": now.strftime('%H:%M:%S'),
                "formula_used": "custom_discount_correction"
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    # Локальный запуск (для тестов)
    uvicorn.run(app, host="0.0.0.0", port=8000)
