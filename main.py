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

def update_inventory_name(item_id, new_name):
    supabase.table("inventory").update({"food": new_name}).eq("id", item_id).execute()
    st.rerun()

def delete_inventory_item(item_id):
    supabase.table("inventory").delete().eq("id", item_id).execute()
    st.rerun()

def add_inventory_item(category, name, qty):
    if name:
        supabase.table("inventory").insert({"category": category, "food": name, "quantity": qty}).execute()
        st.success(f"✅ {name} 추가 완료!")
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
                raw_snack = tr.get('snack')
                c_snack = raw_snack if isinstance(raw_snack, list) else ([raw_snack] if raw_snack and raw_snack != "없음" else [])
                c_new = tr.get('new_food') or []
                c_amt = int(tr.get('amount') or 0)
                c_eaten = bool(tr.get('is_eaten'))
            else:
                c_base, c_tops, c_snack, c_new, c_amt, c_eaten = "없음", [], [], [], 0, False
            
            b_color = "#e8f5e9" if c_eaten else "#f0f2f6"
            st.markdown(f"""
                <div style="background-color:{b_color}; padding:10px; border-radius:10px; border:2px solid #ddd; min-height:150px;">
                    <strong style="font-size:14px;">☀️ {m_type}</strong><br>
                    <span style="font-size:12px;">🍚 {c_base}</span><br>
                    <span style="font-size:11px; color:#666;">🥗 {', '.join(c_tops) if c_tops else '토핑없음'}</span><br>
                    <span style="font-size:11px; color:#d4a017;">🍪 {', '.join(c_snack) if c_snack else '간식없음'}</span><br>
                    {f'🆕 <span style="background-color: yellow; color: red; font-size:10px; font-weight: bold;">NEW: {", ".join(c_new)}</span>' if c_new else ''}<br>
                    <small>📏 {c_amt}ml/g {'✅' if c_eaten else ''}</small>
                </div>
            """, unsafe_allow_html=True)

            with st.popover(f"📝 {m_type} 편집", use_container_width=True):
                col_copy, col_paste = st.columns(2)
                with col_copy:
                    if st.button("📋 복사", key=f"cp_{t_str}_{m_type}"):
                        st.session_state.clipboard = {"base": c_base, "toppings": c_tops, "snack": c_snack, "new_food": c_new, "amount": c_amt}
                        st.toast("복사됨")
                with col_paste:
                    if st.button("📥 붙여넣기", key=f"ps_{t_str}_{m_type}", disabled=st.session_state.clipboard is None):
                        cb = st.session_state.clipboard
                        save_meal(t_str, m_type, cb["base"], cb["toppings"], cb["snack"], cb["new_food"], cb["amount"], False)

                st.divider()
                u_base = st.selectbox("🍚 베이스", food_options["베이스"], index=food_options["베이스"].index(c_base) if c_base in food_options["베이스"] else 0, key=f"t_b_{m_type}")
                u_tops = st.multiselect("🥗 토핑", food_options["토핑"], default=[t for t in c_tops if t in food_options["토핑"]], key=f"t_t_{m_type}")
                u_snack = st.multiselect("🍪 간식(최대3)", food_options["간식"], default=[s for s in c_snack if s in food_options["간식"]], max_selections=3, key=f"t_s_{m_type}")
                u_new = st.multiselect("🆕 처음 재료", food_options["베이스"] + food_options["토핑"], default=c_new, key=f"t_n_{m_type}")
                u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"t_a_{m_type}")
                u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"t_e_{m_type}")
                if st.button("저장", key=f"t_btn_{m_type}", type="primary", use_container_width=True):
                    save_meal(t_str, m_type, u_base, u_tops, u_snack, u_new, u_amt, u_eaten)

    # ---------------------------------------------------------
    # [1-2. 식단 일괄 복사 도구]
    # ---------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🚀 **식단 일괄 복사 도구 (여러 날짜에 한 번에 넣기)**", expanded=False):
        st.info("특정 날짜의 식단을 복사하여 선택한 여러 날짜들에 한 번에 적용합니다.")
        c1, c2 = st.columns(2)
        with c1: source_date = st.date_input("📋 원본 날짜", date.today(), key="src_date")
        with c2: source_meal = st.selectbox("🍴 끼니 선택", ["아침", "점심", "저녁"], key="src_meal")

        src_data = fetch_meals(source_date.isoformat(), source_date.isoformat())
        target_row = src_data[src_data['meal'] == source_meal]

        if not target_row.empty:
            tr = target_row.iloc[0]
            st.warning(f"선택됨: **{tr['base']}** (+{', '.join(tr['toppings']) if tr['toppings'] else 'X'})")
            target_dates = st.multiselect("📅 붙여넣을 날짜들 선택", [(date.today() + timedelta(days=x)) for x in range(-7, 21)], format_func=lambda x: x.strftime("%m/%d (%a)"), key="target_dates_multi")
            if st.button("✨ 일괄 복사 실행", type="primary", use_container_width=True):
                if target_dates:
                    for t_date in target_dates:
                        save_meal(t_date.isoformat(), source_meal, tr['base'], tr['toppings'], tr['snack'], tr['new_food'], tr['amount'], False)
                    st.rerun()
        else: st.error("원본 식단이 없습니다.")

    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # [2. 주간 식단표] - 가독성 최적화 버전
    # ---------------------------------------------------------
    st.divider()
    st.header("📅 2주 식단 플래너")
    curr_week_start = target_date - timedelta(days=target_date.weekday())
    days_kr = ["월", "화", "수", "목", "금", "토", "일"]

    for week_idx in range(2):
        st.subheader("🌟 이번 주" if week_idx == 0 else "📅 다음 주")
        start_dt = curr_week_start + timedelta(weeks=week_idx)
        week_meals = fetch_meals(start_dt.isoformat(), (start_dt + timedelta(days=6)).isoformat())
        
        for i in range(7):
            current_dt = start_dt + timedelta(days=i)
            d_str = current_dt.isoformat()
            is_today = current_dt == date.today()
            
            st.markdown(f"""
                <div style='margin-top:15px; margin-bottom:5px;'>
                    <span style='color:{"#ff4b4b" if is_today else "#31333F"}; font-weight:bold;'>
                        {'📍 ' if is_today else ''}{days_kr[i]} ({current_dt.strftime('%m/%d')})
                    </span>
                </div>
            """, unsafe_allow_html=True)

            m_cols = st.columns(3)
            for idx, m_type in enumerate(["아침", "점심", "저녁"]):
                with m_cols[idx]:
                    m_row = week_meals[(week_meals['date'] == d_str) & (week_meals['meal'] == m_type)]
                    
                    # 데이터 추출
                    if not m_row.empty:
                        tr = m_row.iloc[0]
                        c_base = tr['base'] or "미등록"
                        c_tops = tr['toppings'] or []
                        raw_snack = tr['snack']
                        c_snack = raw_snack if isinstance(raw_snack, list) else ([raw_snack] if raw_snack and raw_snack != "없음" else [])
                        c_amt, c_eaten = int(tr['amount'] or 0), bool(tr['is_eaten'])
                        bg_color = "#e8f5e9" if c_eaten else "#fff3e0"
                    else:
                        c_base, c_tops, c_snack, c_amt, c_eaten = "미등록", [], [], 0, False
                        bg_color = "#f9f9f9"

                    # --- [UI 카드 노출] ---
                    st.markdown(f"""
                        <div style="background-color:{bg_color}; padding:10px; border-radius:8px; border:1px solid #ddd; min-height:80px; margin-bottom:5px;">
                            <div style="font-size:12px; font-weight:bold; margin-bottom:3px;">{m_type} {'✅' if c_eaten else ''}</div>
                            <div style="font-size:13px; color:#333;">🍚 {c_base}</div>
                            <div style="font-size:11px; color:#666;">🥗 {', '.join(c_tops) if c_tops else '-'}</div>
                            {f'<div style="font-size:11px; color:#d4a017;">🍪 {", ".join(c_snack)}</div>' if c_snack else ''}
                        </div>
                    """, unsafe_allow_html=True)

                    # --- [편집용 팝오버] ---
                    unique_key = f"wk_{d_str}_{m_type}"
                    with st.popover("📝 편집", use_container_width=True):
                        st.write(f"### {current_dt.strftime('%m/%d')} {m_type}")
                        c1, c2 = st.columns(2)
                        with c1: 
                            if st.button("📋 복사", key=f"btn_cp_{unique_key}"):
                                st.session_state.clipboard = {"base": c_base, "toppings": c_tops, "snack": c_snack, "new_food": tr.get('new_food', []) if not m_row.empty else [], "amount": c_amt}
                                st.toast("복사됨")
                        with c2:
                            if st.button("📥 붙여넣기", key=f"btn_ps_{unique_key}", disabled=st.session_state.clipboard is None):
                                cb = st.session_state.clipboard
                                save_meal(d_str, m_type, cb["base"], cb["toppings"], cb["snack"], cb["new_food"], cb["amount"], False)
                        st.divider()
                        u_base = st.selectbox("🍚 베이스", food_options["베이스"], index=food_options["베이스"].index(c_base) if c_base in food_options["베이스"] else 0, key=f"sel_b_{unique_key}")
                        u_tops = st.multiselect("🥗 토핑", food_options["토핑"], default=[t for t in c_tops if t in food_options["토핑"]], key=f"sel_t_{unique_key}")
                        u_snack = st.multiselect("🍪 간식", food_options["간식"], default=[s for s in c_snack if s in food_options["간식"]], max_selections=3, key=f"sel_s_{unique_key}")
                        u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"num_a_{unique_key}")
                        u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"chk_e_{unique_key}")
                        if st.button("저장", key=f"btn_sv_{unique_key}", type="primary", use_container_width=True):
                            save_meal(d_str, m_type, u_base, u_tops, u_snack, tr.get('new_food', []) if not m_row.empty else [], u_amt, u_eaten)

    # ---------------------------------------------------------
    # [3. 재료 관리 & 새 재료 추가]
    # ---------------------------------------------------------
    st.divider()
    st.header("📦 재료 관리 & 예상 소진일")

    # [새 재료 추가 섹션] - 이 부분이 누락되었었습니다!
    with st.expander("➕ 새 재료 추가하기"):
        c1, c2, c3 = st.columns([2, 3, 2])
        with c1: new_cat = st.selectbox("분류", ["베이스", "토핑", "간식"])
        with c2: new_name = st.text_input("재료 이름 (예: 소고기무죽)")
        with c3: new_qty = st.number_input("초기 수량", min_value=0, value=10)
        if st.button("재료 추가", use_container_width=True, type="primary"):
            add_inventory_item(new_cat, new_name, new_qty)

    # 재고 리스트 및 소진일 계산
    future_meals = fetch_meals(date.today().isoformat(), (date.today() + timedelta(days=30)).isoformat())
    def get_exhaustion_date(food_name):
        relevant_dates = []
        for _, row in future_meals[future_meals['is_eaten'] == False].iterrows():
            if row['base'] == food_name or food_name in (row.get('toppings') or []) or food_name in (row.get('snack') or []):
                relevant_dates.append(row['date'])
        return datetime.strptime(max(relevant_dates), '%Y-%m-%d').strftime('%m/%d') if relevant_dates else "없음"

    inv_tabs = st.tabs(["베이스", "토핑", "간식"])
    for idx, cat in enumerate(["베이스", "토핑", "간식"]):
        with inv_tabs[idx]:
            items = inv_df[inv_df['category'] == cat]
            for _, row in items.iterrows():
                ex_date = get_exhaustion_date(row['food'])
                c1, c2, c3 = st.columns([3, 3, 2])
                with c1:
                    with st.popover(f"**{row['food']}**", use_container_width=True):
                        n_nm = st.text_input("이름 수정", value=row['food'], key=f"edit_nm_{row['id']}")
                        if st.button("수정 저장", key=f"btn_nm_{row['id']}"): update_inventory_name(row['id'], n_nm)
                        if st.button("🗑️ 삭제", key=f"del_{row['id']}", type="secondary"): delete_inventory_item(row['id'])
                with c2:
                    new_qty = st.number_input("수량", min_value=0, value=int(row['quantity']), key=f"qty_{row['id']}", step=1)
                    if new_qty != row['quantity']:
                        supabase.table("inventory").update({"quantity": new_qty}).eq("id", row['id']).execute()
                        st.rerun()
                with c3:
                    st.markdown(f"<div style='background-color:#e7f3ff; border:1px solid #b3d7ff; border-radius:5px; height:42px; text-align:center;'><span style='font-size:8px;'>소진일</span><br><span style='font-size:11px; font-weight:bold;'>{ex_date}</span></div>", unsafe_allow_html=True)

# [4. 월간 식단표] - 코드 노출 오류 수정 버전
with main_tab2:
    st.header("🗓️ 월간 상세 식단표")
    now = datetime.now()
    sel_y = st.selectbox("년", range(now.year-1, now.year+2), index=1)
    sel_m = st.selectbox("월", range(1, 13), index=now.month-1)
    
    m_data = fetch_meals(date(sel_y, sel_m, 1).isoformat(), date(sel_y, sel_m, calendar.monthrange(sel_y, sel_m)[1]).isoformat())
    cal = calendar.monthcalendar(sel_y, sel_m)

    for week in cal:
        w_cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                target_dt = date(sel_y, sel_m, day)
                d_str = target_dt.isoformat()
                d_meals = m_data[m_data['date'] == d_str]
                
                # 배경색 결정
                if d_meals.empty:
                    bg = "#ffffff"
                elif d_meals['is_eaten'].all():
                    bg = "#e8f5e9"
                else:
                    bg = "#fff9c4"

                with w_cols[i]:
                    content = ""
                    for _, row in d_meals.sort_values('meal').iterrows():
                        m_icon = "🌅" if row['meal'] == "아침" else "☀️" if row['meal'] == "점심" else "🌙"
                        r_base = row['base'] or "없음"
                        r_tops = row['toppings'] or []
                        r_snack = row['snack']
                        r_snack_list = r_snack if isinstance(r_snack, list) else ([r_snack] if r_snack and r_snack != "없음" else [])
                        
                        # 내용 구성
                        content += f"<div style='margin-bottom:4px; border-bottom:1px solid #f0f0f0;'>"
                        content += f"<span style='font-size:10px;'>{m_icon}<b>{r_base}</b></span>"
                        if r_tops:
                            content += f"<div style='color:#666; font-size:8px; padding-left:12px;'>└ {','.join(r_tops)}</div>"
                        if r_snack_list:
                            content += f"<div style='color:#d4a017; font-size:8px; padding-left:12px;'>🍪 {','.join(r_snack_list)}</div>"
                        content += "</div>"
                    
                    # 최종 렌더링
                    st.markdown(f"""
                        <div style='background-color:{bg}; border:1px solid #ddd; border-radius:8px; padding:5px; min-height:130px;'>
                            <div style='text-align:center; font-weight:bold; font-size:11px; border-bottom:1px solid #eee; margin-bottom:5px;'>{day}</div>
                            {content}
                        </div>
                    """, unsafe_allow_html=True)