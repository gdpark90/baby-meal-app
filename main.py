import os
import streamlit as st
import pandas as pd
import calendar
from datetime import date, timedelta, datetime
from dotenv import load_dotenv
from supabase import create_client

# ======================
# 1. 환경 설정 및 연결
# ======================
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

st.set_page_config(page_title="👶 이유식 매니저 PRO", layout="wide")

if "clipboard" not in st.session_state:
    st.session_state.clipboard = None

# ======================
# 2. 데이터 처리 함수
# ======================

def fetch_inventory():
    res = supabase.table("inventory").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def fetch_meals(start, end):
    res = supabase.table("meal_plan").select("*").gte("date", start).lte("date", end).execute()
    df = pd.DataFrame(res.data)
    required_cols = ['date', 'meal', 'base', 'toppings', 'snack', 'new_food', 'amount', 'is_eaten']
    if df.empty:
        return pd.DataFrame(columns=required_cols)
    for col in required_cols:
        if col not in df.columns:
            df[col] = None if col != 'amount' else 0
    return df

def save_meal(date_str, meal_type, base, toppings, snack, new_food, amount, eaten):
    existing = supabase.table("meal_plan").select("id").eq("date", date_str).eq("meal", meal_type).execute()
    data = {
        "date": date_str, "meal": meal_type, "base": base, 
        "toppings": toppings, "snack": snack, "new_food": new_food,
        "amount": amount, "is_eaten": eaten
    }
    try:
        if existing.data:
            supabase.table("meal_plan").update(data).eq("id", existing.data[0]['id']).execute()
        else:
            supabase.table("meal_plan").insert(data).execute()
        st.toast("✅ 저장 성공!")
        st.rerun()
    except Exception as e:
        st.error(f"저장 실패: {e}")

def update_inventory_qty(item_id, current_qty, delta):
    supabase.table("inventory").update({"quantity": max(0, current_qty + delta)}).eq("id", item_id).execute()
    st.rerun()

def update_inventory_name(item_id, new_name):
    supabase.table("inventory").update({"food": new_name}).eq("id", item_id).execute()
    st.rerun()

def delete_inventory_item(item_id):
    supabase.table("inventory").delete().eq("id", item_id).execute()
    st.rerun()

# ======================
# 3. 화면 구현
# ======================

inv_df = fetch_inventory()
food_options = {
    "베이스": ["없음"] + inv_df[inv_df['category'] == '베이스']['food'].tolist(),
    "토핑": inv_df[inv_df['category'] == '토핑']['food'].tolist(),
    "간식": ["없음"] + inv_df[inv_df['category'] == '간식']['food'].tolist()
}

st.title("👶 스마트 이유식 매니저")
main_tab1, main_tab2 = st.tabs(["📊 데일리 & 주간", "📅 월간 식단표"])

with main_tab1:
    # [1. 오늘의 식단]
    target_date = st.date_input("📅 날짜 선택", date.today())
    t_str = target_date.isoformat()
    t_meals = fetch_meals(t_str, t_str)

    st.subheader(f"📍 {target_date.strftime('%Y-%m-%d')} 식단")
    t_cols = st.columns(3)
    for idx, m_type in enumerate(["아침", "점심", "저녁"]):
        with t_cols[idx]:
            m_row = t_meals[t_meals['meal'] == m_type]
            if not m_row.empty:
                tr = m_row.iloc[0]
                c_base = tr.get('base') or "없음"
                c_tops = tr.get('toppings') or []
                c_snack = tr.get('snack') or "없음"
                c_new = tr.get('new_food') or []
                c_amt = int(tr.get('amount') or 0)
                c_eaten = bool(tr.get('is_eaten'))
            else:
                c_base, c_tops, c_snack, c_new, c_amt, c_eaten = "없음", [], "없음", [], 0, False
            
            b_color = "#e8f5e9" if c_eaten else "#f0f2f6"
            st.markdown(f"""
                <div style="background-color:{b_color}; padding:12px; border-radius:10px; border:2px solid #ddd; min-height:160px;">
                    <strong style="font-size:16px;">☀️ {m_type}</strong><br>
                    🍚 {c_base} | 🍪 {c_snack}<br>
                    🥗 {', '.join(c_tops) if c_tops else '토핑없음'}<br>
                    {f'🆕 <span style="background-color: yellow; color: red; font-weight: bold; padding: 2px 5px; border-radius: 3px;">NEW: {", ".join(c_new)}</span>' if c_new else ''}<br>
                    <small>📏 {c_amt}ml/g {'✅' if c_eaten else ''}</small>
                </div>
            """, unsafe_allow_html=True)

            with st.popover(f"📝 {m_type} 편집", use_container_width=True):
                u_base = st.selectbox("🍚 베이스", food_options["베이스"], index=food_options["베이스"].index(c_base) if c_base in food_options["베이스"] else 0, key=f"t_b_{m_type}")
                u_tops = st.multiselect("🥗 토핑", food_options["토핑"], default=[t for t in c_tops if t in food_options["토핑"]], key=f"t_t_{m_type}")
                u_snack = st.selectbox("🍪 간식", food_options["간식"], index=food_options["간식"].index(c_snack) if c_snack in food_options["간식"] else 0, key=f"t_s_{m_type}")
                u_new = st.multiselect("🆕 처음 먹는 재료", food_options["베이스"] + food_options["토핑"], default=c_new, key=f"t_n_{m_type}")
                u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"t_a_{m_type}")
                u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"t_e_{m_type}")
                if st.button("저장", key=f"t_btn_{m_type}", type="primary"):
                    save_meal(t_str, m_type, u_base, u_tops, u_snack, u_new, u_amt, u_eaten)

    st.divider()

# ---------------------------------------------------------
    # [2. 주간 식단표 - 2주일치 확대 버전]
    # ---------------------------------------------------------
    st.divider()
    st.header("📅 2주 식단 플래너 (이번 주 & 다음 주)")
    
    # 기준일로부터 이번 주 월요일 계산
    curr_week_start = target_date - timedelta(days=target_date.weekday())
    
    # 요일 이름 정의
    days_kr = ["월", "화", "수", "목", "금", "토", "일"]

    # 2주 반복 (week_idx 0: 이번 주, 1: 다음 주)
    for week_idx in range(2):
        week_label = "🌟 이번 주" if week_idx == 0 else "📅 다음 주"
        st.subheader(week_label)
        
        # 해당 주차의 시작일과 종료일 계산
        start_dt = curr_week_start + timedelta(weeks=week_idx)
        end_dt = start_dt + timedelta(days=6)
        
        # 해당 주차 데이터 한 번에 가져오기
        week_meals = fetch_meals(start_dt.isoformat(), end_dt.isoformat())
        
        w_cols = st.columns(7)
        for i, col in enumerate(w_cols):
            current_dt = start_dt + timedelta(days=i)
            d_str = current_dt.isoformat()
            
            with col:
                # 날짜 헤더 (오늘 날짜는 강조)
                is_today = current_dt == date.today()
                date_color = "#ff4b4b" if is_today else "#31333F"
                st.markdown(f"<div style='text-align:center; color:{date_color}; font-weight:bold;'>{days_kr[i]} ({current_dt.strftime('%m/%d')})</div>", unsafe_allow_html=True)
                
                # 아침, 점심, 저녁 루프
                for m_type in ["아침", "점심", "저녁"]:
                    m_row = week_meals[(week_meals['date'] == d_str) & (week_meals['meal'] == m_type)]
                    
                    if not m_row.empty:
                        tr = m_row.iloc[0]
                        wt = tr.get('toppings') or []
                        wn = tr.get('new_food') or []
                        ws = tr.get('snack') or "X"
                        
                        # 주간 요약 카드 디자인
                        st.markdown(f"""
                            <div style='border:1px solid #ddd; padding:6px; border-radius:5px; margin-bottom:5px; 
                                        background-color:{"#e8f5e9" if tr["is_eaten"] else "white"}; font-size:10px; line-height:1.2;'>
                                <b style='color:#555;'>{m_type}</b><br>
                                🍚 {tr["base"]}<br>
                                🥗 {", ".join(wt) if wt else "X"}<br>
                                🍪 {str(ws)[:3]}
                                {f'<br><span style="color:red; font-weight:bold;">🆕 {", ".join(wn)}</span>' if wn else ''}
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        # 식단이 없는 경우 빈 칸 표시
                        st.markdown("""
                            <div style='border:1px dashed #eee; padding:6px; border-radius:5px; margin-bottom:5px; 
                                        text-align:center; color:#ccc; font-size:10px;'>
                                미등록
                            </div>
                        """, unsafe_allow_html=True)
        
        if week_idx == 0:
            st.write("") # 주차 사이 간격

# ---------------------------------------------------------
    # [3. 재료 관리 - 예상 소진일 반영 버전]
    # ---------------------------------------------------------
    st.divider()
    st.header("📦 재료 관리 & 예상 소진일")

    # 모든 미래 식단 가져오기 (소진일 계산용)
    future_meals = fetch_meals(date.today().isoformat(), (date.today() + timedelta(days=30)).isoformat())
    
    # 재료별 마지막 사용일 계산 함수
    def get_exhaustion_date(food_name):
        # 베이스나 토핑, 간식 컬럼 중 어디든 해당 재료가 포함된 미래 식단 필터링
        # is_eaten이 False인 계획된 식단만 대상
        planned = future_meals[future_meals['is_eaten'] == False]
        
        relevant_dates = []
        for _, row in planned.iterrows():
            # 베이스, 토핑, 간식 중 하나라도 일치하면 날짜 추가
            toppings = row.get('toppings') or []
            snack = row.get('snack') or ""
            if row['base'] == food_name or food_name in toppings or row['snack'] == food_name:
                relevant_dates.append(row['date'])
        
        if not relevant_dates:
            return "계획 없음"
        
        # 가장 마지막 날짜 반환
        last_date = max(relevant_dates)
        return datetime.strptime(last_date, '%Y-%m-%d').strftime('%m/%d')

    with st.expander("🆕 새로운 재료 추가하기"):
        with st.form("new_food_form", clear_on_submit=True):
            f_name = st.text_input("재료 이름")
            f_cat = st.radio("카테고리", ["베이스", "토핑", "간식"], horizontal=True)
            f_qty = st.number_input("현재 수량", min_value=0, value=0)
            if st.form_submit_button("재료 등록"):
                if f_name:
                    if f_name in inv_df['food'].values: st.error("이미 있는 재료입니다.")
                    else:
                        supabase.table("inventory").insert({"food": f_name, "category": f_cat, "quantity": f_qty}).execute()
                        st.rerun()

    inv_tabs = st.tabs(["베이스", "토핑", "간식"])
    for idx, cat in enumerate(["베이스", "토핑", "간식"]):
        with inv_tabs[idx]:
            items = inv_df[inv_df['category'] == cat]
            
            # 헤더
            h1, h2, h3, h4 = st.columns([2, 1, 1.5, 1.5])
            h1.caption("재료명 (수정/삭제)")
            h2.caption("재고")
            h3.caption("소진 예정일")
            h4.caption("수량 조절")
            
            for _, row in items.iterrows():
                ic1, ic2, ic3, ic4 = st.columns([2, 1, 1.5, 1.5])
                is_low = row['quantity'] <= 3 # 재고 부족 알림 기준
                
                # 1. 재료명 및 편집
                with ic1:
                    with st.popover(f"{'⚠️ ' if is_low else ''}{row['food']}", use_container_width=True):
                        new_name = st.text_input("이름 수정", value=row['food'], key=f"edit_nm_{row['id']}")
                        if st.button("수정", key=f"btn_nm_{row['id']}"): update_inventory_name(row['id'], new_name)
                        if st.button("🗑️ 삭제", key=f"del_{row['id']}", type="secondary"): delete_inventory_item(row['id'])
                
                # 2. 현재 재고
                with ic2:
                    color = "red" if is_low else "black"
                    st.markdown(f"<p style='text-align:center; font-weight:bold; color:{color}; padding-top:5px;'>{row['quantity']}</p>", unsafe_allow_html=True)
                
                # 3. 예상 소진일 (핵심 추가 기능)
                with ic3:
                    ex_date = get_exhaustion_date(row['food'])
                    date_style = "color: #ff4b4b; font-weight: bold;" if ex_date != "계획 없음" else "color: #aaa;"
                    st.markdown(f"<p style='text-align:center; font-size:12px; {date_style} padding-top:5px;'>{ex_date}</p>", unsafe_allow_html=True)
                
                # 4. 수량 조절 버튼
                with ic4:
                    c_m, c_p = st.columns(2)
                    c_m.button("－", key=f"m_{row['id']}", on_click=update_inventory_qty, args=(row['id'], row['quantity'], -1))
                    c_p.button("＋", key=f"p_{row['id']}", on_click=update_inventory_qty, args=(row['id'], row['quantity'], 1))

# ---------------------------------------------------------
# [4. 월간 식단표 - 가독성 극대화 버전]
# ---------------------------------------------------------
with main_tab2:
    st.header("🗓️ 월간 상세 식단표")
    now = datetime.now()
    sel_y = st.selectbox("년", range(now.year-1, now.year+2), index=1, key="year_sel")
    sel_m = st.selectbox("월", range(1, 13), index=now.month-1, key="month_sel")
    
    # 해당 월의 데이터 가져오기
    m_start = date(sel_y, sel_m, 1).isoformat()
    m_end = date(sel_y, sel_m, calendar.monthrange(sel_y, sel_m)[1]).isoformat()
    m_data = fetch_meals(m_start, m_end)
    
    cal = calendar.monthcalendar(sel_y, sel_m)
    
    # 요일 헤더
    h_cols = st.columns(7)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    for i, day_name in enumerate(weekdays):
        h_cols[i].markdown(f"<p style='text-align:center; font-weight:bold; margin-bottom:5px;'>{day_name}</p>", unsafe_allow_html=True)

    for week in cal:
        w_cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                d_str = date(sel_y, sel_m, day).isoformat()
                d_meals = m_data[m_data['date'] == d_str]
                
                # 배경색 결정 (완료 여부)
                if d_meals.empty:
                    bg = "#ffffff"
                else:
                    bg = "#e8f5e9" if d_meals['is_eaten'].all() else "#fff9c4"
                
                with w_cols[i]:
                    content = ""
                    # 끼니 순서대로 정렬 (아침, 점심, 저녁)
                    order = {"아침": 0, "점심": 1, "저녁": 2}
                    sorted_meals = d_meals.copy()
                    if not sorted_meals.empty:
                        sorted_meals['sort'] = sorted_meals['meal'].map(order)
                        sorted_meals = sorted_meals.sort_values('sort')

                    for _, row in sorted_meals.iterrows():
                        m_icon = "🌅" if row['meal'] == "아침" else "☀️" if row['meal'] == "점심" else "🌙"
                        wt_list = row.get('toppings') or []
                        wt_str = ",".join(wt_list)
                        
                        # 한 줄씩 깔끔하게 표현 (폰트 크기 9px로 조정)
                        content += f"""
                        <div style="margin-bottom:4px; border-bottom:1px dotted #ccc; padding-bottom:2px;">
                            <span style="font-weight:bold; color:#555;">{m_icon}</span> 
                            <b>{row['base']}</b><br>
                            <span style="color:#666;">└ {wt_str if wt_str else '토핑X'}</span>
                        </div>
                        """
                    
                    # 카드 디자인
                    st.markdown(f"""
                        <div style="background-color:{bg}; border:1px solid #ddd; border-radius:8px; 
                                    padding:5px; min-height:140px; max-height:180px; overflow-y:auto; 
                                    box-shadow: 1px 1px 3px rgba(0,0,0,0.05);">
                            <div style="text-align:right; font-weight:bold; font-size:12px; margin-bottom:5px;">{day}</div>
                            <div style="font-size:9.5px; line-height:1.3;">{content if content else '<p style="color:#ccc; text-align:center;">-</p>'}</div>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                w_cols[i].write("") # 빈 칸 처리