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
                u_snack = st.multiselect(
    "🍪 간식 (최대 3개)", 
    food_options["간식"], 
    default=[s for s in (c_snack if isinstance(c_snack, list) else [c_snack]) if s in food_options["간식"]],
    max_selections=3,
    key=f"t_s_{m_type}"
)
                u_new = st.multiselect("🆕 처음 재료", food_options["베이스"] + food_options["토핑"], 
                                       default=c_new, key=f"t_n_{m_type}")
                u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"t_a_{m_type}")
                u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"t_e_{m_type}")
                
                if st.button("저장", key=f"t_btn_{m_type}", type="primary", use_container_width=True):
                    save_meal(t_str, m_type, u_base, u_tops, u_snack, u_new, u_amt, u_eaten)

    st.divider()

# ---------------------------------------------------------
    # [1-2. 식단 일괄 복사 도구] - 오늘의 식단 바로 아래 추가
    # ---------------------------------------------------------
    with st.expander("🚀 **식단 일괄 복사 도구 (여러 날짜에 한 번에 넣기)**", expanded=False):
        st.info("특정 날짜의 식단을 복사하여 선택한 여러 날짜들에 동일하게 적용합니다.")
        
        c1, c2 = st.columns(2)
        with c1:
            source_date = st.date_input("📋 원본 식단 날짜", date.today(), key="src_date")
        with c2:
            source_meal = st.selectbox("🍴 복사할 끼니", ["아침", "점심", "저녁"], key="src_meal")

        # 원본 데이터 가져오기
        src_str = source_date.isoformat()
        src_data = fetch_meals(src_str, src_str)
        target_row = src_data[src_data['meal'] == source_meal]

        if not target_row.empty:
            tr = target_row.iloc[0]
            st.warning(f"선택된 식단: **{tr['base']}** (+{', '.join(tr['toppings']) if tr['toppings'] else '토핑없음'})")
            
            # 대상 날짜 선택 (복수 선택 가능)
            target_dates = st.multiselect(
                "📅 복사해 넣을 날짜들을 선택하세요 (여러 날 선택 가능)",
                [(date.today() + timedelta(days=x)) for x in range(-7, 21)], # 과거 1주 ~ 미래 3주
                format_func=lambda x: x.strftime("%m/%d (%a)"),
                key="target_dates_multi"
            )

            if st.button("✨ 선택한 날짜들에 일괄 복사하기", type="primary", use_container_width=True):
                if not target_dates:
                    st.error("복사할 대상 날짜를 선택해주세요.")
                else:
                    success_count = 0
                    for t_date in target_dates:
                        t_str = t_date.isoformat()
                        # 원본 데이터를 대상 날짜의 동일한 끼니에 저장
                        save_meal(
                            t_str, 
                            source_meal, 
                            tr['base'], 
                            tr['toppings'], 
                            tr['snack'], 
                            tr['new_food'], 
                            tr['amount'], 
                            False # 복사 시 완료 여부는 항상 미완료로 설정
                        )
                        success_count += 1
                    st.success(f"✅ {success_count}개의 날짜에 {source_meal} 식단 복사 완료!")
                    st.rerun()
        else:
            st.error("해당 날짜와 끼니에 등록된 식단이 없습니다. 먼저 식단을 등록해주세요.")
            
# ---------------------------------------------------------
# ---------------------------------------------------------
    # [2. 주간 식단표 - 간식 다중 선택(최대 3개) 버전]
    # ---------------------------------------------------------
    st.divider()
    st.header("📅 2주 식단 플래너")
    
    curr_week_start = target_date - timedelta(days=target_date.weekday())
    days_kr = ["월", "화", "수", "목", "금", "토", "일"]

    for week_idx in range(2):
        st.subheader("🌟 이번 주" if week_idx == 0 else "📅 다음 주")
        
        start_dt = curr_week_start + timedelta(weeks=week_idx)
        end_dt = start_dt + timedelta(days=6)
        week_meals = fetch_meals(start_dt.isoformat(), end_dt.isoformat())
        
        for i in range(7):
            current_dt = start_dt + timedelta(days=i)
            d_str = current_dt.isoformat()
            is_today = current_dt == date.today()
            date_label = f"{days_kr[i]} ({current_dt.strftime('%m/%d')})"
            
            if is_today:
                st.markdown(f"<p style='color:#ff4b4b; font-weight:bold; margin-bottom:5px; border-left:3px solid #ff4b4b; padding-left:10px;'>📍 {date_label}</p>", unsafe_allow_html=True)
            else:
                st.markdown(f"<p style='font-weight:bold; margin-bottom:5px; color:#31333F;'>{date_label}</p>", unsafe_allow_html=True)

            m_cols = st.columns(3)
            for idx, m_type in enumerate(["아침", "점심", "저녁"]):
                with m_cols[idx]:
                    m_row = week_meals[(week_meals['date'] == d_str) & (week_meals['meal'] == m_type)]
                    
                    if not m_row.empty:
                        tr = m_row.iloc[0]
                        c_base = tr['base']
                        c_tops = tr['toppings'] or []
                        # 간식 데이터가 문자열일 경우 리스트로 변환하여 처리
                        raw_snack = tr['snack']
                        c_snack = raw_snack if isinstance(raw_snack, list) else ([raw_snack] if raw_snack and raw_snack != "없음" else [])
                        c_new = tr['new_food'] or []
                        c_amt = int(tr['amount'])
                        c_eaten = bool(tr['is_eaten'])
                        
                        state_color = "#e8f5e9" if c_eaten else "#fff3e0"
                        border_color = "#c8e6c9" if c_eaten else "#ffe0b2"
                        display_name = f"{'✅' if c_eaten else '📝'} {c_base}"
                        tops_text = f"+{', '.join(c_tops)}" if c_tops else "토핑없음"
                        snack_text = f"🍪 {', '.join(c_snack)}" if c_snack else ""
                    else:
                        c_base, c_tops, c_snack, c_new, c_amt, c_eaten = "없음", [], [], [], 0, False
                        state_color, border_color, display_name, tops_text, snack_text = "#f9f9f9", "#eeeeee", "미등록", "", ""

                    unique_key = f"wk_{d_str}_{m_type}"

                    with st.popover(f"{m_type}\n{display_name}", use_container_width=True):
                        st.write(f"### {current_dt.strftime('%m/%d')} {m_type}")
                        
                        # 복사/붙여넣기
                        cp_col1, cp_col2 = st.columns(2)
                        with cp_col1:
                            if st.button("📋 복사", key=f"btn_cp_{unique_key}"):
                                st.session_state.clipboard = {"base": c_base, "toppings": c_tops, "snack": c_snack, "new_food": c_new, "amount": c_amt}
                                st.toast("복사됨")
                        with cp_col2:
                            if st.button("📥 붙여넣기", key=f"btn_ps_{unique_key}", disabled=st.session_state.clipboard is None):
                                cb = st.session_state.clipboard
                                save_meal(d_str, m_type, cb["base"], cb["toppings"], cb["snack"], cb["new_food"], cb["amount"], False)
                        
                        st.divider()
                        u_base = st.selectbox("🍚 베이스", food_options["베이스"], index=food_options["베이스"].index(c_base) if c_base in food_options["베이스"] else 0, key=f"sel_b_{unique_key}")
                        u_tops = st.multiselect("🥗 토핑", food_options["토핑"], default=[t for t in c_tops if t in food_options["토핑"]], key=f"sel_t_{unique_key}")
                        
                        # --- 간식 다중 선택 적용 (최대 3개) ---
                        u_snack = st.multiselect(
                            "🍪 간식 (최대 3개)", 
                            food_options["간식"], 
                            default=[s for s in c_snack if s in food_options["간식"]],
                            max_selections=3,
                            key=f"sel_s_{unique_key}"
                        )
                        
                        u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"num_a_{unique_key}")
                        u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"chk_e_{unique_key}")
                        
                        if st.button("저장", key=f"btn_sv_{unique_key}", type="primary", use_container_width=True):
                            save_meal(d_str, m_type, u_base, u_tops, u_snack, c_new, u_amt, u_eaten)

                    # 카드 하단 정보 표시 (토핑 및 간식)
                    info_html = f"<div style='margin-top:-15px; margin-bottom:10px; padding:2px 8px; font-size:10px; color:#888; border:1px solid {border_color}; border-top:none; border-radius:0 0 5px 5px; background-color:{state_color};'>"
                    if tops_text: info_html += f"<span>{tops_text}</span>"
                    if snack_text: info_html += f"<br><span style='color:#d4a017;'>{snack_text}</span>"
                    info_html += "</div>"
                    if tops_text or snack_text:
                        st.markdown(info_html, unsafe_allow_html=True)

# ---------------------------------------------------------
    # [3. 재료 관리 - 숫자 직접 입력(속도 최적화) 버전]
    # ---------------------------------------------------------
    st.divider()
    st.header("📦 재료 관리 & 예상 소진일")

    # [A] 소진일 계산 함수 (기존 유지)
    future_meals = fetch_meals(date.today().isoformat(), (date.today() + timedelta(days=30)).isoformat())
    def get_exhaustion_date(food_name):
        planned = future_meals[future_meals['is_eaten'] == False]
        relevant_dates = []
        for _, row in planned.iterrows():
            toppings = row.get('toppings') or []
            if row['base'] == food_name or food_name in toppings or row.get('snack') == food_name:
                relevant_dates.append(row['date'])
        if not relevant_dates: return "없음"
        return datetime.strptime(max(relevant_dates), '%Y-%m-%d').strftime('%m/%d')

    # [B] 모바일 최적화 CSS (입력창 높이 조절)
    st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"] {
            gap: 5px !important;
            align-items: center !important;
        }
        /* 입력창(Number Input) 높이와 폰트 조절 */
        .stNumberInput input {
            height: 42px !important;
            font-size: 16px !important;
            font-weight: bold !important;
            text-align: center !important;
        }
        /* 라벨 숨기기 (공간 절약) */
        div[data-testid="stNumberInput"] label {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # [C] 재료 리스트 UI
    inv_tabs = st.tabs(["베이스", "토핑", "간식"])
    for idx, cat in enumerate(["베이스", "토핑", "간식"]):
        with inv_tabs[idx]:
            items = inv_df[inv_df['category'] == cat]
            for _, row in items.iterrows():
                ex_date = get_exhaustion_date(row['food'])
                
                # 비율 조정: 이름(3) | 수량 입력창(3) | 소진일(2)
                c1, c2, c3 = st.columns([3, 3, 2])
                
                with c1: # 재료명 & 편집
                    with st.popover(f"**{row['food']}**", use_container_width=True):
                        new_name = st.text_input("이름 수정", value=row['food'], key=f"edit_nm_{row['id']}")
                        if st.button("저장", key=f"btn_nm_{row['id']}"): update_inventory_name(row['id'], new_name)
                        if st.button("🗑️ 삭제", key=f"del_{row['id']}", type="secondary"): delete_inventory_item(row['id'])

                with c2: # 수량 직접 입력 (Number Input)
                    # 수량이 변경되면 바로 DB에 업데이트됨
                    new_qty = st.number_input(
                        "수량", 
                        min_value=0, 
                        value=int(row['quantity']), 
                        key=f"qty_{row['id']}",
                        step=1
                    )
                    # 현재 값과 입력값이 다를 때만 업데이트 실행 (무한 로딩 방지)
                    if new_qty != row['quantity']:
                        supabase.table("inventory").update({"quantity": new_qty}).eq("id", row['id']).execute()
                        st.rerun()

                with c3: # 소진일 표시
                    st.markdown(f"""
                        <div style="background-color:#e7f3ff; border:1px solid #b3d7ff; border-radius:5px; height:42px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;">
                            <span style="font-size:8px; color:#555;">소진일</span>
                            <span style="font-size:11px; font-weight:bold; color:#007bff;">{ex_date}</span>
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