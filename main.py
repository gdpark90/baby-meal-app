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

st.title("👶 박주하 이유식 매니저")
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
# ---------------------------------------------------------
    # [3. 재료 관리 - 모바일 전용 가로 고정 레이아웃]
    # ---------------------------------------------------------
    st.divider()
    st.header("📦 재료 관리 & 예상 소진일")

    # [A] 소진일 계산 함수 및 데이터 로드
    future_meals = fetch_meals(date.today().isoformat(), (date.today() + timedelta(days=30)).isoformat())
    
    def get_exhaustion_date(food_name):
        planned = future_meals[future_meals['is_eaten'] == False]
        relevant_dates = []
        for _, row in planned.iterrows():
            toppings = row.get('toppings') or []
            if row['base'] == food_name or food_name in toppings or row.get('snack') == food_name:
                relevant_dates.append(row['date'])
        if not relevant_dates: return "계획 없음"
        last_dt = datetime.strptime(max(relevant_dates), '%Y-%m-%d')
        return last_dt.strftime('%m/%d')

    # [B] 재고임박 리스트 (5개 이하)
    low_stock_items = inv_df[inv_df['quantity'] <= 5]
    if not low_stock_items.empty:
        st.markdown(f"""
            <div style="background-color: #fff1f0; border: 1px solid #ffa39e; border-radius: 8px; padding: 10px; margin-bottom: 15px;">
                <h4 style="margin: 0 0 5px 0; color: #cf1322; font-size: 14px;">⚠️ 재고임박</h4>
                {''.join([f"<span style='font-size:12px; margin-right:8px;'>• {row['food']}({row['quantity']})</span>" for _, row in low_stock_items.iterrows()])}
            </div>
        """, unsafe_allow_html=True)

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

    # [C] 모바일 가로 강제 고정 스타일
    st.markdown("""
        <style>
        /* 모든 컬럼의 줄바꿈 방지 및 가로 정렬 */
        div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            gap: 2px !important;
        }
        div[data-testid="column"] {
            min-width: 0px !important;
            flex: 1 1 auto !important;
        }
        /* 버튼 크기 최적화 */
        .stButton > button {
            width: 100% !important;
            height: 40px !important;
            padding: 0px !important;
            font-size: 16px !important;
            font-weight: bold !important;
        }
        /* 재료명/소진일 폰트 크기 조절 */
        .small-text { font-size: 10px; line-height: 1; color: #666; }
        .name-text { font-size: 12px; font-weight: bold; line-height: 1.2; }
        </style>
    """, unsafe_allow_html=True)

    # [D] 재료 리스트 출력
    inv_tabs = st.tabs(["베이스", "토핑", "간식"])
    for idx, cat in enumerate(["베이스", "토핑", "간식"]):
        with inv_tabs[idx]:
            items = inv_df[inv_df['category'] == cat]
            for _, row in items.iterrows():
                ex_date = get_exhaustion_date(row['food'])
                
                # 가로 한 줄에 5개 컬럼 배치 (이름/편집, -, 숫자, +, 소진일)
                c1, c2, c3, c4, c5 = st.columns([2.8, 1, 1.2, 1, 1.8])
                
                with c1: # 재료명 & 설정
                    st.markdown(f"""
                        <div style="background-color:#f1f3f5; border:1px solid #dee2e6; border-radius:5px; height:40px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;">
                            <div class="name-text">{row['food']}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    with st.popover("⚙️", use_container_width=True):
                        new_name = st.text_input("수정", value=row['food'], key=f"n_{row['id']}")
                        if st.button("저장", key=f"s_{row['id']}"): update_inventory_name(row['id'], new_name)
                        if st.button("🗑️", key=f"d_{row['id']}", type="secondary"): delete_inventory_item(row['id'])
                
                with c2: # 감소
                    st.button("－", key=f"m_{row['id']}", on_click=update_inventory_qty, args=(row['id'], row['quantity'], -1))
                
                with c3: # 수량
                    st.markdown(f"""
                        <div style="border:2px solid #333; border-radius:5px; height:40px; display:flex; align-items:center; justify-content:center; background:white;">
                            <span style="font-weight:bold; font-size:16px;">{row['quantity']}</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                with c4: # 증가
                    st.button("＋", key=f"p_{row['id']}", on_click=update_inventory_qty, args=(row['id'], row['quantity'], 1))
                
                with c5: # 소진일
                    st.markdown(f"""
                        <div style="background-color:#e7f3ff; border:1px solid #b3d7ff; border-radius:5px; height:40px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;">
                            <span class="small-text">소진일</span>
                            <span style="font-size:10px; font-weight:bold; color:#007bff;">{ex_date}</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# [4. 월간 상세 식단표 - 가시성 개선 버전]
# ---------------------------------------------------------
with main_tab2:
    st.header("🗓️ 월간 상세 식단표")
    now = datetime.now()
    sel_y = st.selectbox("년", range(now.year-1, now.year+2), index=1, key="year_sel")
    sel_m = st.selectbox("월", range(1, 13), index=now.month-1, key="month_sel")
    
    m_start = date(sel_y, sel_m, 1).isoformat()
    m_end = date(sel_y, sel_m, calendar.monthrange(sel_y, sel_m)[1]).isoformat()
    m_data = fetch_meals(m_start, m_end)
    
    cal = calendar.monthcalendar(sel_y, sel_m)
    
    # 2. 요일 헤더 삭제 (요청사항 반영) - 바로 날짜 카드로 진입

    for week in cal:
        w_cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                target_dt = date(sel_y, sel_m, day)
                d_str = target_dt.isoformat()
                day_kr = ["월", "화", "수", "목", "금", "토", "일"][target_dt.weekday()]
                
                d_meals = m_data[m_data['date'] == d_str]
                bg = "#ffffff" if d_meals.empty else ("#e8f5e9" if d_meals['is_eaten'].all() else "#fff9c4")
                
                with w_cols[i]:
                    content = ""
                    sorted_meals = d_meals.copy()
                    if not sorted_meals.empty:
                        order = {"아침": 0, "점심": 1, "저녁": 2}
                        sorted_meals['sort'] = sorted_meals['meal'].map(order)
                        sorted_meals = sorted_meals.sort_values('sort')

                    for _, row in sorted_meals.iterrows():
                        m_icon = "🌅" if row['meal'] == "아침" else "☀️" if row['meal'] == "점심" else "🌙"
                        wt_list = row.get('toppings') or []
                        # 폰트 크기 확대(11px) 및 줄바꿈 방지 스타일 적용
                        content += f"""
                        <div style="margin-bottom:6px; line-height:1.4;">
                            <span style="font-size:11px;">{m_icon}<b>{row['base']}</b></span><br>
                            <span style="color:#666; font-size:10px; margin-left:5px;">└ {", ".join(wt_list) if wt_list else "X"}</span>
                        </div>
                        """
                    
                    st.markdown(f"""
                        <div style="background-color:{bg}; border:1px solid #ccc; border-radius:10px; 
                                    padding:6px; min-height:160px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                            <div style="text-align:center; font-weight:bold; font-size:11px; margin-bottom:8px; border-bottom: 2px solid #eee; padding-bottom:3px;">
                                {sel_m}/{day}({day_kr})
                            </div>
                            <div style="word-break: keep-all;">{content if content else '<p style="color:#ddd; text-align:center; padding-top:20px;">-</p>'}</div>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                w_cols[i].write("")