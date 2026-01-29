from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from datetime import date

app = FastAPI()

def get_db():
    return sqlite3.connect("baby.db")

@app.get("/", response_class=HTMLResponse)
def home(meal: str = Query("아침")):
    conn = get_db()
    cursor = conn.cursor()

    foods = cursor.execute("SELECT name FROM inventory").fetchall()

    today_meals = cursor.execute("""
        SELECT meal, food
        FROM meal_plan
        WHERE date = date('now')
        ORDER BY meal
    """).fetchall()

    inventory = cursor.execute("""
        SELECT name, quantity
        FROM inventory
    """).fetchall()

    # 🔥 최근 7일 사용량 가져오기
    usage = cursor.execute("""
        SELECT food, COUNT(*) as cnt
        FROM meal_plan
        WHERE date >= date('now', '-7 day')
        GROUP BY food
    """).fetchall()

    conn.close()

    usage_dict = {food: cnt for food, cnt in usage}

    today = date.today().isoformat()

    # 🍽 오늘 식단
    meal_html = "<h2>🍽 오늘 식단</h2>"

    if not today_meals:
        meal_html += "<p>아직 입력된 식단이 없어요 🙂</p>"
    else:
        for m, food in today_meals:
            meal_html += f"<p>{m} - {food}</p>"

    # 🔥 재고 + 소진일 계산
    inventory_html = "<h2>📦 재고 현황</h2>"

    for name, qty in inventory:

        weekly_use = usage_dict.get(name, 0)

        if weekly_use == 0:
            days_left = "사용 기록 없음 🙂"
            color = "black"

        else:
            daily_avg = weekly_use / 7
            est_days = int(qty / daily_avg) if daily_avg else 999

            if est_days <= 1:
                days_left = "🚨 오늘 소진"
                color = "red"
            elif est_days <= 3:
                days_left = f"⚠️ 약 {est_days}일"
                color = "orange"
            else:
                days_left = f"약 {est_days}일"
                color = "black"

        inventory_html += f"""
        <p style='font-size:18px; color:{color};'>
            {name} ({qty}) → {days_left}
        </p>
        """

    # 🍱 식사 선택
    meal_selector = f"""
    <h2>식사 선택</h2>
    <a href="/?meal=아침"><button>🌞 아침</button></a>
    <a href="/?meal=점심"><button>🍱 점심</button></a>
    <a href="/?meal=저녁"><button>🌙 저녁</button></a>

    <h3>👉 현재 선택: {meal}</h3>
    """

    # 🍚 재료 버튼
    buttons = ""
    for food in foods:
        buttons += f"""
        <form action="/add_food" method="post" style="display:inline;">
            <input type="hidden" name="food" value="{food[0]}">
            <input type="hidden" name="meal" value="{meal}">
            <button style="font-size:18px; padding:10px; margin:5px;">
                {food[0]}
            </button>
        </form>
        """

    html = f"""
    <h1>👶 이유식 관리 앱</h1>
    <h3>{today}</h3>

    <div style="display:flex; gap:40px;">
        
        <div style="flex:1;">
            {meal_html}
            <hr>
            {meal_selector}
            <h2>재료 추가</h2>
            {buttons}
        </div>

        <div style="flex:1;">
            {inventory_html}
        </div>

    </div>
    """

    return html


@app.post("/add_food")
def add_food(food: str = Form(...), meal: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO meal_plan (date, meal, food)
        VALUES (date('now'), ?, ?)
    """, (meal, food))

    cursor.execute("""
        UPDATE inventory
        SET quantity = quantity - 1
        WHERE name = ?
    """, (food,))

    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)
