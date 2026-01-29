import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

conn = sqlite3.connect("baby_food.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS foods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food TEXT,
    stock INTEGER,
    daily_use INTEGER
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    meal_type TEXT,
    food TEXT
)
""")

conn.commit()


############################################
# 기본 함수
############################################

def get_foods():
    return pd.read_sql("SELECT * FROM foods", conn)

def get_meals():
    return pd.read_sql("SELECT * FROM meals", conn)


def expected_days(stock, daily):
    if daily == 0:
        return "∞"
    return f"{stock // daily}일"


############################################
# 재고 화면
############################################

st.title("🍼 이유식 재고 관리")

st.header("📦 재고 현황")

foods = get_foods()

if not foods.empty:

    cols = st.columns(4)
    cols[0].write("### 음식")
    cols[1].write("### 재고")
    cols[2].write("### 하루 사용량")
    cols[3].write("### 예상 소진")

    for _, row in foods.iterrows():

        color = "red" if row.stock <= row.daily_use * 3 else "black"

        cols = st.columns(4)

        cols[0].write(row.food)
        cols[1].write(f":{color}[{row.stock}]")
        cols[2].write(row.daily_use)
        cols[3].write(expected_days(row.stock, row.daily_use))

else:
    st.info("음식을 먼저 등록하세요 🙂")


############################################
# 음식 추가
############################################

with st.expander("➕ 음식 추가"):

    food = st.text_input("음식 이름")

    col1, col2 = st.columns(2)
    stock = col1.number_input("재고", 0, 100, 10)
    daily = col2.number_input("하루 사용량", 0, 10, 1)

    if st.button("추가"):
        c.execute("INSERT INTO foods (food, stock, daily_use) VALUES (?, ?, ?)",
                  (food, stock, daily))
        conn.commit()
        st.rerun()


############################################
# 오늘 식단
############################################

st.divider()
st.header("🍽 오늘 식단")

today = datetime.today().strftime("%Y-%m-%d")
meals = get_meals()

today_meals = meals[meals.date == today]

meal_types = ["아침", "점심", "저녁"]

for meal in meal_types:

    st.subheader(meal)

    cols = st.columns(6)

    if not foods.empty:

        for i, (_, row) in enumerate(foods.iterrows()):

            if cols[i % 6].button(row.food, key=f"{meal}_{row.food}"):

                c.execute("""
                INSERT INTO meals (date, meal_type, food)
                VALUES (?, ?, ?)
                """, (today, meal, row.food))

                c.execute("""
                UPDATE foods
                SET stock = stock - 1
                WHERE food = ?
                """, (row.food,))

                conn.commit()
                st.rerun()

    eaten = today_meals[today_meals.meal_type == meal]

    if not eaten.empty:
        st.write("👉 ", ", ".join(eaten.food.tolist()))
    else:
        st.write("없음")


############################################
# 주간 보기
############################################

st.divider()
st.header("📅 주간 보기")

week_ago = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")

weekly = meals[meals.date >= week_ago]

if not weekly.empty:

    pivot = pd.pivot_table(
        weekly,
        index="date",
        columns="meal_type",
        values="food",
        aggfunc=lambda x: ", ".join(x)
    )

    st.dataframe(pivot, use_container_width=True)

else:
    st.info("기록이 없습니다.")


############################################
# 월간 보기
############################################

st.divider()
st.header("🗓 월간 보기")

month_ago = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")

monthly = meals[meals.date >= month_ago]

if not monthly.empty:

    pivot = pd.pivot_table(
        monthly,
        index="date",
        columns="meal_type",
        values="food",
        aggfunc=lambda x: ", ".join(x)
    )

    st.dataframe(pivot, use_container_width=True)

else:
    st.info("기록이 없습니다.")