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

WB_TOKEN = os.getenv("WB_TOKEN_KEY")

def fetch_wb_data(method, date_from):
    url = f"https://statistics-api.wildberries.ru/api/v1/supplier/{method}"
    headers = {"Authorization": WB_TOKEN}
    params = {"dateFrom": date_from, "flag": 0}
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json() if response.status_code == 200 else []
    except:
        return []

@app.get("/stats")
def get_wb_stats():
    if not WB_TOKEN: return {"status": "error", "message": "API токен не настроен"}

    offset = timezone(timedelta(hours=3))
    now = datetime.now(offset)
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    start_point = (now - timedelta(days=3)).strftime('%Y-%m-%dT00:00:00')
    
    # Получаем данные из двух разных методов
    orders_data = fetch_wb_data("orders", start_point)
    sales_data = fetch_wb_data("sales", start_point)

    # Функции фильтрации и расчета
    def process_data(source, date_str, is_sales=False):
        items = [i for i in source if date_str in i.get('date', '')]
        count = len(items)
        if is_sales:
            # Для выкупов обычно используем finishedPrice (сколько реально заплатил клиент)
            # revenue = sum(i.get('finishedPrice', 0) for i in items)
            # Моя эмперическая формула для заказов
            revenue = sum(i.get('totalPrice', 0) * (1 - (i.get('discountPercent', 0) - 1) / 100) for i in items)
        else:
            # Для выкупов обычно используем finishedPrice (сколько реально заплатил клиент)
            # revenue = sum(i.get('finishedPrice', 0) for i in items)
            # Моя эмперическая формула для заказов
            revenue = sum(i.get('totalPrice', 0) * (1 - (i.get('discountPercent', 0) - 1) / 100) for i in items)
        return {"count": count, "rev": int(revenue)}

    return {
        "status": "success",
        "today": {
            "orders": process_data(orders_data, today_str),
            "sales": process_data(sales_data, today_str, is_sales=True)
        },
        "yesterday": {
            "orders": process_data(orders_data, yesterday_str),
            "sales": process_data(sales_data, yesterday_str, is_sales=True)
        }
    }
