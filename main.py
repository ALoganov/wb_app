import os
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
import psycopg2
from psycopg2.extras import RealDictCursor
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WB_TOKEN   = os.getenv("WB_TOKEN_KEY")
DB_URL     = os.getenv("DATABASE_URL")
MSK        = timezone(timedelta(hours=3))


# ─── БД ───────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

def init_db():
    """Создаём таблицы если их нет."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date        DATE PRIMARY KEY,
                    orders_count INT  DEFAULT 0,
                    orders_rev   INT  DEFAULT 0,
                    sales_count  INT  DEFAULT 0,
                    sales_rev    INT  DEFAULT 0,
                    updated_at   TIMESTAMPTZ DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS adv_stats (
                    id          SERIAL PRIMARY KEY,
                    date        DATE NOT NULL,
                    campaign_id BIGINT NOT NULL,
                    name        TEXT,
                    status      TEXT,
                    views       INT  DEFAULT 0,
                    clicks      INT  DEFAULT 0,
                    ctr         NUMERIC(6,2) DEFAULT 0,
                    spend       NUMERIC(12,2) DEFAULT 0,
                    atc         INT  DEFAULT 0,
                    orders      INT  DEFAULT 0,
                    updated_at  TIMESTAMPTZ DEFAULT now(),
                    UNIQUE (date, campaign_id)
                );
            """)
        conn.commit()
    print("[DB] Таблицы готовы")


# ─── WB helpers ───────────────────────────────────────────────────────

def fetch_wb(url, headers, params=None):
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        return res.json() if res.status_code == 200 else None
    except:
        return None


# ─── Сборщик статистики продаж ────────────────────────────────────────

def collect_sales():
    print("[Scheduler] Сбор статистики продаж...")
    headers = {"Authorization": WB_TOKEN}
    now = datetime.now(MSK)

    # Берём данные за последние 14 дней (чтобы покрыть полную прошлую неделю)
    date_from = (now - timedelta(days=14)).replace(hour=0, minute=0, second=0).isoformat()

    orders_raw = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/orders", headers, {"dateFrom": date_from}) or []
    sales_raw  = fetch_wb("https://statistics-api.wildberries.ru/api/v1/supplier/sales",  headers, {"dateFrom": date_from}) or []

    # Группируем по датам
    days = set()
    for item in orders_raw + sales_raw:
        d = item.get("date", "")[:10]
        if d:
            days.add(d)

    with get_conn() as conn:
        with conn.cursor() as cur:
            for day in days:
                o_items = [i for i in orders_raw if i.get("date", "").startswith(day)]
                s_items = [i for i in sales_raw  if i.get("date", "").startswith(day)]

                cur.execute("""
                    INSERT INTO daily_stats (date, orders_count, orders_rev, sales_count, sales_rev, updated_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (date) DO UPDATE SET
                        orders_count = EXCLUDED.orders_count,
                        orders_rev   = EXCLUDED.orders_rev,
                        sales_count  = EXCLUDED.sales_count,
                        sales_rev    = EXCLUDED.sales_rev,
                        updated_at   = now()
                """, (
                    day,
                    len(o_items),
                    int(sum(i.get("finishedPrice", 0) for i in o_items)),
                    len(s_items),
                    int(sum(i.get("forPay", 0) for i in s_items)),
                ))
        conn.commit()
    print(f"[Scheduler] Продажи сохранены: {len(days)} дней")


# ─── Сборщик рекламной статистики ─────────────────────────────────────

def _get_active_campaign_ids(headers):
    count_data = fetch_wb("https://advert-api.wildberries.ru/adv/v1/promotion/count", headers)
    if not count_data:
        return []
    ids = []
    for group in count_data.get("adverts", []):
        if group.get("status") == 9:
            for advert in group.get("advert_list", []):
                ids.append(advert["advertId"])
    return ids

def _get_details_map(headers, all_ids):
    details_map = {}
    for i in range(0, len(all_ids), 50):
        chunk = all_ids[i:i+50]
        res = requests.get(
            "https://advert-api.wildberries.ru/api/advert/v2/adverts",
            headers=headers,
            params={"ids": ",".join(str(x) for x in chunk)},
            timeout=15,
        )
        if res.status_code == 200:
            for d in (res.json().get("adverts") or []):
                details_map[d["id"]] = d
    return details_map

def _save_adv_for_date(headers, all_ids, details_map, date_str):
    """Собирает и сохраняет статистику рекламы за конкретный день."""
    payload = [
        {"id": cid, "interval": {"begin": date_str, "end": date_str}}
        for cid in all_ids
    ]
    stats_res = requests.post(
        "https://advert-api.wildberries.ru/adv/v2/fullstats",
        headers=headers,
        json=payload,
        timeout=15,
    )
    stats_raw = stats_res.json() if stats_res.status_code == 200 else []
    print(f"[Adv] {date_str} — статус {stats_res.status_code}, записей: {len(stats_raw) if isinstance(stats_raw, list) else 0}")
    stats_map = {item["advertId"]: item for item in (stats_raw if isinstance(stats_raw, list) else [])}

    STATUS_LABELS = {4: "Готова к запуску", 7: "Завершена", 8: "Отказалась", 9: "Идет показ", 11: "Приостановлена"}

    with get_conn() as conn:
        with conn.cursor() as cur:
            for cid in all_ids:
                detail = details_map.get(cid, {})
                stat   = stats_map.get(cid, {})
                days   = stat.get("days", [])

                views  = sum(d.get("views",  0) for d in days)
                clicks = sum(d.get("clicks", 0) for d in days)
                spend  = sum(d.get("sum",    0) for d in days)
                atc    = sum(d.get("atbs",   0) for d in days)
                orders = sum(d.get("orders", 0) for d in days)
                ctr    = round(clicks / views * 100, 2) if views > 0 else 0.0
                name   = (detail.get("settings") or {}).get("name") or f"Кампания {cid}"
                status = STATUS_LABELS.get(detail.get("status", 0), "—")

                cur.execute("""
                    INSERT INTO adv_stats (date, campaign_id, name, status, views, clicks, ctr, spend, atc, orders, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (date, campaign_id) DO UPDATE SET
                        name       = EXCLUDED.name,
                        status     = EXCLUDED.status,
                        views      = EXCLUDED.views,
                        clicks     = EXCLUDED.clicks,
                        ctr        = EXCLUDED.ctr,
                        spend      = EXCLUDED.spend,
                        atc        = EXCLUDED.atc,
                        orders     = EXCLUDED.orders,
                        updated_at = now()
                """, (date_str, cid, name, status, views, clicks, ctr, round(spend, 2), atc, orders))
        conn.commit()
    print(f"[Scheduler] Реклама за {date_str} сохранена")

def collect_adv():
    """Ежечасный сбор — только сегодня."""
    print("[Scheduler] Сбор рекламной статистики (сегодня)...")
    headers  = {"Authorization": WB_TOKEN, "Content-Type": "application/json"}
    all_ids  = _get_active_campaign_ids(headers)
    if not all_ids:
        print("[Scheduler] Нет активных кампаний")
        return
    details_map = _get_details_map(headers, all_ids)
    today = datetime.now(MSK).strftime("%Y-%m-%d")
    _save_adv_for_date(headers, all_ids, details_map, today)
    print(f"[Scheduler] Готово: {len(all_ids)} кампаний")

def collect_adv_history(days_back: int = 14):
    """Однократная загрузка истории рекламы за N дней — все кампании."""
    print(f"[History] Загрузка рекламы за {days_back} дней...")
    headers = {"Authorization": WB_TOKEN, "Content-Type": "application/json"}

    # Берём ВСЕ кампании (любой статус) для истории
    count_data = fetch_wb("https://advert-api.wildberries.ru/adv/v1/promotion/count", headers)
    if not count_data:
        print("[History] Не удалось получить список кампаний")
        return
    all_ids = []
    for group in count_data.get("adverts", []):
        for advert in group.get("advert_list", []):
            all_ids.append(advert["advertId"])

    if not all_ids:
        print("[History] Кампании не найдены")
        return

    print(f"[History] Найдено кампаний: {len(all_ids)}")
    details_map = _get_details_map(headers, all_ids)

    now = datetime.now(MSK)
    for i in range(days_back, -1, -1):
        date_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        _save_adv_for_date(headers, all_ids, details_map, date_str)

    print(f"[History] Загрузка завершена")


def collect_all():
    collect_sales()
    collect_adv()


# ─── API endpoints ────────────────────────────────────────────────────

@app.get("/stats")
def get_stats():
    now         = datetime.now(MSK)
    today       = now.strftime("%Y-%m-%d")
    yesterday   = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    this_monday = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    last_monday = (now - timedelta(days=now.weekday() + 7)).strftime("%Y-%m-%d")
    last_sunday = (now - timedelta(days=now.weekday() + 1)).strftime("%Y-%m-%d")

    def empty():
        return {"count": 0, "rev": 0}

    def row_to_dict(row, key_count, key_rev):
        if not row:
            return empty()
        return {"count": row[key_count] or 0, "rev": row[key_rev] or 0}

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Сегодня и вчера — одним запросом
            cur.execute("SELECT * FROM daily_stats WHERE date IN (%s, %s)", (today, yesterday))
            rows = {str(r["date"]): r for r in cur.fetchall()}

            today_row     = rows.get(today)
            yesterday_row = rows.get(yesterday)

            # Эта неделя (пн — сегодня)
            cur.execute("""
                SELECT
                    COALESCE(SUM(orders_count),0) AS orders_count,
                    COALESCE(SUM(orders_rev),  0) AS orders_rev,
                    COALESCE(SUM(sales_count), 0) AS sales_count,
                    COALESCE(SUM(sales_rev),   0) AS sales_rev,
                    MIN(date)::text AS date_from,
                    MAX(date)::text AS date_to
                FROM daily_stats WHERE date >= %s AND date <= %s
            """, (this_monday, today))
            tw = cur.fetchone()

            # Прошлая неделя (пн — вс)
            cur.execute("""
                SELECT
                    COALESCE(SUM(orders_count),0) AS orders_count,
                    COALESCE(SUM(orders_rev),  0) AS orders_rev,
                    COALESCE(SUM(sales_count), 0) AS sales_count,
                    COALESCE(SUM(sales_rev),   0) AS sales_rev,
                    MIN(date)::text AS date_from,
                    MAX(date)::text AS date_to
                FROM daily_stats WHERE date >= %s AND date <= %s
            """, (last_monday, last_sunday))
            lw = cur.fetchone()

    return {
        "today": {
            "orders": row_to_dict(today_row, "orders_count", "orders_rev"),
            "sales":  row_to_dict(today_row, "sales_count",  "sales_rev"),
        },
        "yesterday": {
            "orders": row_to_dict(yesterday_row, "orders_count", "orders_rev"),
            "sales":  row_to_dict(yesterday_row, "sales_count",  "sales_rev"),
        },
        "this_week": {
            "orders": {"count": int(tw["orders_count"]), "rev": int(tw["orders_rev"])},
            "sales":  {"count": int(tw["sales_count"]),  "rev": int(tw["sales_rev"])},
            "from":   tw["date_from"] or this_monday,
            "to":     tw["date_to"]   or today,
        },
        "last_week": {
            "orders": {"count": int(lw["orders_count"]), "rev": int(lw["orders_rev"])},
            "sales":  {"count": int(lw["sales_count"]),  "rev": int(lw["sales_rev"])},
            "from":   lw["date_from"] or last_monday,
            "to":     lw["date_to"]   or last_sunday,
        },
    }


@app.get("/adv")
def get_adv():
    now         = datetime.now(MSK)
    today       = now.strftime("%Y-%m-%d")
    this_monday = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    last_monday = (now - timedelta(days=now.weekday() + 7)).strftime("%Y-%m-%d")
    last_sunday = (now - timedelta(days=now.weekday() + 1)).strftime("%Y-%m-%d")

    with get_conn() as conn:
        with conn.cursor() as cur:

            # Только активные кампании сегодня
            cur.execute("""
                SELECT campaign_id FROM adv_stats
                WHERE date = %s AND status = 'Идет показ'
            """, (today,))
            campaign_ids = [r["campaign_id"] for r in cur.fetchall()]

            if not campaign_ids:
                return {"status": "success", "campaigns": []}

            result = []
            for cid in campaign_ids:

                # Сегодня
                cur.execute("""
                    SELECT name, status, views, clicks, ctr, spend AS sum, atc, orders, date::text AS date
                    FROM adv_stats WHERE date = %s AND campaign_id = %s
                """, (today, cid))
                today_row = dict(cur.fetchone() or {})

                # Эта неделя
                cur.execute("""
                    SELECT
                        COALESCE(SUM(views),  0)::int     AS views,
                        COALESCE(SUM(clicks), 0)::int     AS clicks,
                        COALESCE(SUM(spend),  0)::numeric AS spend,
                        COALESCE(SUM(atc),    0)::int     AS atc,
                        COALESCE(SUM(orders), 0)::int     AS orders,
                        MIN(date)::text AS date_from,
                        MAX(date)::text AS date_to
                    FROM adv_stats WHERE campaign_id = %s AND date >= %s AND date <= %s
                """, (cid, this_monday, today))
                tw = dict(cur.fetchone())

                # Прошлая неделя
                cur.execute("""
                    SELECT
                        COALESCE(SUM(views),  0)::int     AS views,
                        COALESCE(SUM(clicks), 0)::int     AS clicks,
                        COALESCE(SUM(spend),  0)::numeric AS spend,
                        COALESCE(SUM(atc),    0)::int     AS atc,
                        COALESCE(SUM(orders), 0)::int     AS orders,
                        MIN(date)::text AS date_from,
                        MAX(date)::text AS date_to
                    FROM adv_stats WHERE campaign_id = %s AND date >= %s AND date <= %s
                """, (cid, last_monday, last_sunday))
                lw = dict(cur.fetchone())

                def week_ctr(row):
                    return round(row["clicks"] / row["views"] * 100, 2) if row["views"] > 0 else 0.0

                result.append({
                    "id":     cid,
                    "name":   today_row.get("name", f"Кампания {cid}"),
                    "status": today_row.get("status", "—"),
                    "date":   today_row.get("date", today),
                    "today": {
                        "views":  today_row.get("views", 0),
                        "clicks": today_row.get("clicks", 0),
                        "ctr":    today_row.get("ctr", 0),
                        "spend":  float(today_row.get("sum", 0)),
                        "atc":    today_row.get("atc", 0),
                        "orders": today_row.get("orders", 0),
                    },
                    "this_week": {
                        "views":  tw["views"],
                        "clicks": tw["clicks"],
                        "ctr":    week_ctr(tw),
                        "spend":  float(tw["spend"]),
                        "atc":    tw["atc"],
                        "orders": tw["orders"],
                        "from":   tw["date_from"] or this_monday,
                        "to":     tw["date_to"]   or today,
                    },
                    "last_week": {
                        "views":  lw["views"],
                        "clicks": lw["clicks"],
                        "ctr":    week_ctr(lw),
                        "spend":  float(lw["spend"]),
                        "atc":    lw["atc"],
                        "orders": lw["orders"],
                        "from":   lw["date_from"] or last_monday,
                        "to":     lw["date_to"]   or last_sunday,
                    },
                })

    return {"status": "success", "campaigns": result}


# История статистики за N дней (для будущих графиков)
@app.get("/stats/history")
def get_stats_history(days: int = 30):
    date_from = (datetime.now(MSK) - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT date::text, orders_count, orders_rev, sales_count, sales_rev
                FROM daily_stats
                WHERE date >= %s
                ORDER BY date
            """, (date_from,))
            rows = cur.fetchall()
    return {"days": days, "data": [dict(r) for r in rows]}


# Ручной запуск сбора (для теста без ожидания часа)
@app.post("/collect")
def manual_collect():
    collect_all()
    return {"status": "ok", "message": "Сбор данных запущен"}

# Отладка — посмотреть что в БД за период
@app.get("/debug/adv")
def debug_adv(campaign_id: int, date_from: str = "2026-07-13", date_to: str = "2026-07-26"):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT date::text, views, clicks, spend, orders
                FROM adv_stats
                WHERE campaign_id = %s AND date >= %s AND date <= %s
                ORDER BY date
            """, (campaign_id, date_from, date_to))
            rows = [dict(r) for r in cur.fetchall()]
    return {"campaign_id": campaign_id, "rows": rows}
def manual_adv_history(days_back: int = 14):
    collect_adv_history(days_back)
    return {"status": "ok", "message": f"История рекламы за {days_back} дней загружена"}


# ─── Старт ────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()

    # Сразу собираем данные при старте
    collect_all()

    # Планировщик — каждый час
    scheduler = BackgroundScheduler(timezone=MSK)
    scheduler.add_job(collect_all, "interval", hours=1)
    scheduler.start()
    print("[Scheduler] Запущен, следующий сбор через 1 час")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
