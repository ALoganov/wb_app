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
    target_ids = [28255817, 27952577, 16936998]
    final_results = []

    for cid in target_ids:
        # Запрашиваем статистику без фильтра по дате, чтобы получить историю
        url = f"https://advert-api.wildberries.ru/adv/v1/fullstat?id={cid}"
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            best_data = {}
            
            if res.status_code == 200:
                data = res.json()
                days = data.get('days', [])
                
                if days:
                    # Ищем самый свежий день, где были просмотры (views > 0)
                    # Идем с конца списка (от новых к старым)
                    active_days = [d for d in days if d.get('views', 0) > 0]
                    if active_days:
                        best_data = active_days[-1] # Самый свежий активный день
                    else:
                        best_data = days[-1] # Если везде 0, просто берем последний день
            
            # Определяем имя
            if cid == 28255817: name = "Поиск"
            elif cid == 27952577: name = "АРК"
            else: name = f"Кампания {cid}"

            final_results.append({
                "id": cid,
                "name": name,
                "status": "Идет" if best_data.get('views', 0) > 0 else "Пауза/Нули",
                "views": best_data.get('views', 0),
                "clicks": best_data.get('clicks', 0),
                "ctr": best_data.get('ctr', 0),
                "cpm": best_data.get('cpm', 0),
                "sum": best_data.get('sum', 0),
                "atc": best_data.get('atc', 0),
                "orders": best_data.get('orders', 0),
                "date": best_data.get('date', 'Нет данных'),
                "res": res.status_code
            })
        except:
            continue

    return {"status": "success", "campaigns": final_results}
