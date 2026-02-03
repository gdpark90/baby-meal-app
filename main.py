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
    
    # 모바일에서 한 줄씩 보이지 않게 하려면 columns 유지
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
            
            # 식단 카드 디자인
            b_color = "#e8f5e9" if c_eaten else "#f0f2f6"
            st.markdown(f"""
                <div style="background-color:{b_color}; padding:10px; border-radius:10px; border:2px solid #ddd; min-height:150px;">
                    <strong style="font-size:14px;">☀️ {m_type}</strong><br>
                    <span style="font-size:12px;">🍚 {c_base} | 🍪 {c_snack}</span><br>
                    <span style="font-size:12px;">🥗 {', '.join(c_tops) if c_tops else '토핑없음'}</span><br>
                    {f'🆕 <span style="background-color: yellow; color: red; font-size:11px; font-weight: bold; padding: 1px 3px; border-radius: 3px;">NEW: {", ".join(c_new)}</span>' if c_new else ''}<br>
                    <small>📏 {c_amt}ml/g {'✅' if c_eaten else ''}</small>
                </div>
            """, unsafe_allow_html=True)

            # 편집 및 복사/붙여넣기 팝오버
            with st.popover(f"📝 {m_type} 편집", use_container_width=True):
                # --- 식단 복사/붙여넣기 버튼 ---
                col_copy, col_paste = st.columns(2)
                with col_copy:
                    if st.button("📋 복사", key=f"cp_{t_str}_{m_type}", use_container_width=True):
                        st.session_state.clipboard = {
                            "base": c_base, "toppings": c_tops, "snack": c_snack,
                            "new_food": c_new, "amount": c_amt
                        }
                        st.toast(f"{m_type} 식단 복사 완료!")
                
                with col_paste:
                    # 복사된 데이터가 있을 때만 버튼 활성화
                    is_empty = st.session_state.clipboard is None
                    if st.button("📥 붙여넣기", key=f"ps_{t_str}_{m_type}", use_container_width=True, disabled=is_empty):
                        cb = st.session_state.clipboard
                        save_meal(t_str, m_type, cb["base"], cb["toppings"], cb["snack"], cb["new_food"], cb["amount"], False)

                st.divider()

                # --- 편집 폼 ---
                u_base = st.selectbox("🍚 베이스", food_options["베이스"], 
                                      index=food_options["베이스"].index(c_base) if c_base in food_options["베이스"] else 0, 
                                      key=f"t_b_{m_type}")
                u_tops = st.multiselect("🥗 토핑", food_options["토핑"], 
                                        default=[t for t in c_tops if t in food_options["토핑"]], 
                                        key=f"t_t_{m_type}")
                u_snack = st.selectbox("🍪 간식", food_options["간식"], 
                                       index=food_options["간식"].index(c_snack) if c_snack in food_options["간식"] else 0, 
                                       key=f"t_s_{m_type}")
                u_new = st.multiselect("🆕 처음 재료", food_options["베이스"] + food_options["토핑"], 
                                       default=c_new, key=f"t_n_{m_type}")
                u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"t_a_{m_type}")
                u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"t_e_{m_type}")
                
                if st.button("저장", key=f"t_btn_{m_type}", type="primary", use_container_width=True):
                    save_meal(t_str, m_type, u_base, u_tops, u_snack, u_new, u_amt, u_eaten)

    st.divider()


# ---------------------------------------------------------
# ---------------------------------------------------------
    # [2. 주간 식단표 - 정보 가시성 복구 및 편집 버튼 축소]
    # ---------------------------------------------------------
    st.divider()
    st.header("📅 2주 식단 플래너")
    
    curr_week_start = target_date - timedelta(days=target_date.weekday())
    days_kr = ["월", "화", "수", "목", "금", "토", "일"]

    # 팝오버/버튼 크기 강제 축소 CSS
    st.markdown("""
        <style>
        .stPopover > button {
            padding: 0px !important;
            height: 25px !important;
            min-height: 25px !important;
            font-size: 10px !important;
            line-height: 1 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    for week_idx in range(2):
        st.subheader("🌟 이번 주" if week_idx == 0 else "📅 다음 주")
        
        start_dt = curr_week_start + timedelta(weeks=week_idx)
        end_dt = start_dt + timedelta(days=6)
        week_meals = fetch_meals(start_dt.isoformat(), end_dt.isoformat())
        
        w_cols = st.columns(7)
        for i, col in enumerate(w_cols):
            current_dt = start_dt + timedelta(days=i)
            d_str = current_dt.isoformat()
            
            with col:
                is_today = current_dt == date.today()
                date_color = "#ff4b4b" if is_today else "#31333F"
                st.markdown(f"<div style='text-align:center; color:{date_color}; font-weight:bold; font-size:11px;'>{days_kr[i]}<br>{current_dt.strftime('%m/%d')}</div>", unsafe_allow_html=True)
                
                for m_type in ["아침", "점심", "저녁"]:
                    m_row = week_meals[(week_meals['date'] == d_str) & (week_meals['meal'] == m_type)]
                    
                    if not m_row.empty:
                        tr = m_row.iloc[0]
                        c_base, c_tops, c_snack, c_new, c_amt, c_eaten = tr['base'], tr['toppings'] or [], tr['snack'], tr['new_food'] or [], int(tr['amount']), bool(tr['is_eaten'])
                        
                        # 카드에 표시할 내용 (베이스 + 토핑 요약)
                        tops_str = f"+{', '.join(c_tops)}" if c_tops else ""
                        card_content = f"<b>{c_base}</b><br><span style='color:#666;'>{tops_str}</span>"
                        card_bg = "#e8f5e9" if c_eaten else "white"
                        border_style = "1px solid #ddd"
                    else:
                        c_base, c_tops, c_snack, c_new, c_amt, c_eaten = "없음", [], "없음", [], 0, False
                        card_content = "<span style='color:#ccc;'>미등록</span>"
                        card_bg = "#fdfdfd"
                        border_style = "1px dashed #eee"

                    # 끼니 정보 출력
                    st.markdown(f"""
                        <div style='border:{border_style}; padding:4px; border-radius:4px; margin-bottom:2px; 
                                    background-color:{card_bg}; font-size:9px; line-height:1.2; min-height:45px;'>
                            <span style='color:#999;'>{m_type}</span><br>
                            {card_content}
                        </div>
                    """, unsafe_allow_html=True)

                    # [축소된 편집 버튼]
                    with st.popover("📝 Edit", use_container_width=True):
                        st.caption(f"{current_dt.strftime('%m/%d')} {m_type}")
                        
                        cp1, cp2 = st.columns(2)
                        with cp1:
                            if st.button("📋 복사", key=f"wk_cp_{d_str}_{m_type}"):
                                st.session_state.clipboard = {"base": c_base, "toppings": c_tops, "snack": c_snack, "new_food": c_new, "amount": c_amt}
                                st.toast("복사됨")
                        with cp2:
                            if st.button("📥 붙여넣기", key=f"wk_ps_{d_str}_{m_type}", disabled=st.session_state.clipboard is None):
                                cb = st.session_state.clipboard
                                save_meal(d_str, m_type, cb["base"], cb["toppings"], cb["snack"], cb["new_food"], cb["amount"], False)

                        st.divider()
                        u_base = st.selectbox("🍚 베이스", food_options["베이스"], index=food_options["베이스"].index(c_base) if c_base in food_options["베이스"] else 0, key=f"v_b_{d_str}_{m_type}")
                        u_tops = st.multiselect("🥗 토핑", food_options["toppings"] if "toppings" in food_options else food_options["토핑"], default=[t for t in c_tops if t in (food_options["toppings"] if "toppings" in food_options else food_options["토핑"])], key=f"v_t_{d_str}_{m_type}")
                        u_snack = st.selectbox("🍪 간식", food_options["간식"], index=food_options["간식"].index(c_snack) if c_snack in food_options["간식"] else 0, key=f"v_s_{d_str}_{m_type}")
                        u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"v_a_{d_str}_{m_type}")
                        u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"v_e_{d_str}_{m_type}")
                        
                        if st.button("저장", key=f"v_save_{d_str}_{m_type}", type="primary", use_container_width=True):
                            save_meal(d_str, m_type, u_base, u_tops, u_snack, c_new, u_amt, u_eaten)


# ---------------------------------------------------------
# ---------------------------------------------------------
    # [3. 재료 관리 - UI 전면 개편 및 재고임박 리스트 추가]
    # ---------------------------------------------------------
    st.divider()
    st.header("📦 재료 관리 & 예상 소진일")

    # 모든 미래 식단 가져오기 (소진일 계산용)
    future_meals = fetch_meals(date.today().isoformat(), (date.today() + timedelta(days=30)).isoformat())
    
    def get_exhaustion_date(food_name):
        planned = future_meals[future_meals['is_eaten'] == False]
        relevant_dates = []
        for _, row in planned.iterrows():
            toppings = row.get('toppings') or []
            if row['base'] == food_name or food_name in toppings or row.get('snack') == food_name:
                relevant_dates.append(row['date'])
        if not relevant_dates: return "계획 없음"
        # 요일 추가 형식으로 반환
        last_dt = datetime.strptime(max(relevant_dates), '%Y-%m-%d')
        day_kr = ["월", "화", "수", "목", "금", "토", "일"][last_dt.weekday()]
        return last_dt.strftime(f'%m/%d({day_kr})')

    # 새로운 재료 추가 폼
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

    # --- 1. 재고임박 리스트 추가 (재고 5개 이하) ---
    low_stock_items = inv_df[inv_df['quantity'] <= 5]
    if not low_stock_items.empty:
        st.markdown("""
            <div style="background-color: #fff1f0; border: 1px solid #ffa39e; border-radius: 10px; padding: 12px; margin: 10px 0;">
                <h4 style="margin: 0 0 8px 0; color: #cf1322; font-size: 15px;">⚠️ 재고임박 리스트</h4>
        """, unsafe_allow_html=True)
        for _, row in low_stock_items.iterrows():
            st.markdown(f"<p style='margin: 0; font-size: 13px; color: #333;'>• {row['category']} : <b>{row['food']}</b> ({row['quantity']}개 남음)</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- 2. 재료 관리 UI 개선 (첨부 이미지 형태 반영) ---
    inv_tabs = st.tabs(["베이스", "토핑", "간식"])
    for idx, cat in enumerate(["베이스", "토핑", "간식"]):
        with inv_tabs[idx]:
            items = inv_df[inv_df['category'] == cat]
            
            for _, row in items.iterrows():
                ex_date = get_exhaustion_date(row['food'])
                
                # 이미지의 가로형 배치를 구현하기 위한 컬럼 나누기
                # 이름/편집 | - | 숫자 | + | 소진일
                c1, c2, c3, c4, c5 = st.columns([2.5, 0.8, 1, 0.8, 1.8])
                
                with c1:
                    # 배경색이 들어간 재료 이름 박스
                    st.markdown(f"""
                        <div style="background-color: #e9ecef; padding: 8px; border-radius: 8px; text-align: center; border: 1px solid #ced4da;">
                            <span style="font-weight: bold; font-size: 14px;">{row['food']}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    # 바로 아래 편집/삭제 팝오버 배치
                    with st.popover("⚙️ 편집/삭제", use_container_width=True):
                        new_name = st.text_input("이름 수정", value=row['food'], key=f"edit_nm_{row['id']}")
                        if st.button("수정", key=f"btn_nm_{row['id']}"): update_inventory_name(row['id'], new_name)
                        if st.button("🗑️ 삭제", key=f"del_{row['id']}", type="secondary"): delete_inventory_item(row['id'])
                
                with c2:
                    st.button("－", key=f"m_{row['id']}", on_click=update_inventory_qty, args=(row['id'], row['quantity'], -1), use_container_width=True)
                
                with c3:
                    # 숫자 박스 스타일
                    st.markdown(f"""
                        <div style="border: 2px solid #333; border-radius: 8px; height: 38px; display: flex; align-items: center; justify-content: center;">
                            <span style="font-weight: bold; font-size: 18px;">{row['quantity']}</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                with c4:
                    st.button("＋", key=f"p_{row['id']}", on_click=update_inventory_qty, args=(row['id'], row['quantity'], 1), use_container_width=True)
                
                with c5:
                    # 재고소진일 정보 박스
                    st.markdown(f"""
                        <div style="background-color: #e7f3ff; padding: 4px; border-radius: 6px; border: 1px solid #b3d7ff; height: 38px; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                            <span style="font-size: 9px; color: #555;">재고소진일</span>
                            <span style="font-size: 11px; font-weight: bold; color: #007bff;">{ex_date}</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("<div style='margin-bottom: 15px; border-bottom: 1px solid #f0f0f0; padding-bottom: 5px;'></div>", unsafe_allow_html=True)

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