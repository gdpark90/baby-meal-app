import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

DB_NAME = "baby.db"


# ✅ DB 연결 함수
def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


# ✅ inventory 가져오기
def load_inventory():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM inventory", conn)
    conn.close()
    return df


# ✅ 재고 차감
def use_food(name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE inventory
        SET quantity = quantity - 1
        WHERE name = ? AND quantity > 0
    """, (name,))

    conn.commit()
    conn.close()


# ✅ Streamlit UI 시작
st.title("🥣 아기 이유식 관리 앱")

st.divider()

# 오늘 날짜
today = date.today()
st.subheader(f"📅 오늘 날짜: {today}")


# 🔥 재고 표시
st.header("📦 재고 현황")

inventory_df = load_inventory()

if inventory_df.empty:
    st.warning("재고 데이터가 없습니다. DB Browser에서 먼저 추가하세요!")
else:
    cols = st.columns(3)

    for idx, row in inventory_df.iterrows():
        col = cols[idx % 3]

        with col:
            st.metric(
                label=row["name"],
                value=f"{row['quantity']} 개"
            )

            if st.button(f"{row['name']} 사용", key=row["name"]):
                use_food(row["name"])
                st.rerun()


st.divider()

# 🔥 오늘 식단 입력
st.header("🍽 오늘 식단 기록")

foods = inventory_df["name"].tolist()

breakfast = st.multiselect("아침", foods)
lunch = st.multiselect("점심", foods)
dinner = st.multiselect("저녁", foods)


if st.button("✅ 식단 저장"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meal_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            breakfast TEXT,
            lunch TEXT,
            dinner TEXT
        )
    """)

    cursor.execute("""
        INSERT INTO meal_log (date, breakfast, lunch, dinner)
        VALUES (?, ?, ?, ?)
    """, (
        str(today),
        ", ".join(breakfast),
        ", ".join(lunch),
        ", ".join(dinner)
    ))

    conn.commit()
    conn.close()

    st.success("오늘 식단 저장 완료!")
