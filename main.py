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

st.set_page_config(page_title="👶 주하 식단 매니저 PRO", layout="wide")

if "clipboard" not in st.session_state:
    st.session_state.clipboard = None

# ======================
# 2. 데이터 처리 및 헬퍼 함수
# ======================

# [추가된 콜백 함수] 사용자가 수량을 직접 변경했을 때 DB에 즉시 반영
def on_quantity_change(f_id, state_key):
    new_val = st.session_state[state_key]
    supabase.table("inventory").update({"quantity": int(new_val)}).eq("id", f_id).execute()

def fetch_inventory():
    res = supabase.table("inventory").select("*").order("food").execute()
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

def get_next_day_for_food(food_name, target_date_str):
    res = supabase.table("meal_plan").select("new_food").lt("date", target_date_str).execute()
    count = 0
    for row in res.data:
        nf_list = row.get('new_food', [])
        if nf_list:
            for item in nf_list:
                if item.split(':')[0] == food_name:
                    count += 1
    return count + 1

def calculate_depletion(inv_df):
    today_str = date.today().isoformat()
    future_end = (date.today() + timedelta(days=60)).isoformat()
    future_meals = fetch_meals(today_str, future_end)
    
    depletion_results = {}
    for _, item in inv_df.iterrows():
        food_name = item['food']
        current_qty = int(item['quantity'])
        usage_dates = []
        if not future_meals.empty:
            for _, meal in future_meals.iterrows():
                m_base_raw = meal['base'] if meal['base'] else ""
                m_bases = [b.strip() for b in m_base_raw.split(',') if b.strip() and b.strip() != "없음"]
                m_tops = meal['toppings'] if isinstance(meal['toppings'], list) else []
                m_snack = meal['snack'] if isinstance(meal['snack'], list) else []
                
                if food_name in m_bases:
                    if len(m_bases) > 1:
                        usage_dates.append(meal['date'])
                    else:
                        usage_dates.append(meal['date'])
                        usage_dates.append(meal['date'])
                
                if food_name in m_tops or food_name in m_snack:
                    usage_dates.append(meal['date'])
        
        usage_dates.sort()
        if current_qty <= 0:
            depletion_results[food_name] = "재고 없음"
        elif len(usage_dates) >= current_qty:
            depletion_results[food_name] = usage_dates[current_qty - 1]
        else:
            depletion_results[food_name] = "여유"
    return depletion_results

def update_inventory_stock(base_str, toppings, snack, change_direction):
    if base_str and base_str != "없음":
        bases = [b.strip() for b in base_str.split(',') if b.strip() and b.strip() != "없음"]
        qty_per_base = 1 if len(bases) > 1 else 2
        for b in bases:
            res = supabase.table("inventory").select("id", "quantity").eq("food", b).execute()
            if res.data:
                item_id = res.data[0]['id']
                new_q = max(0, int(res.data[0]['quantity']) + (qty_per_base * change_direction))
                supabase.table("inventory").update({"quantity": new_q}).eq("id", item_id).execute()
                st.session_state[f"q_{item_id}"] = new_q

    others = (toppings if isinstance(toppings, list) else []) + (snack if isinstance(snack, list) else [])
    for item_name in others:
        if not item_name or item_name == "없음": continue
        res = supabase.table("inventory").select("id", "quantity").eq("food", item_name).execute()
        if res.data:
            item_id = res.data[0]['id']
            new_q = max(0, int(res.data[0]['quantity']) + (1 * change_direction))
            supabase.table("inventory").update({"quantity": new_q}).eq("id", item_id).execute()
            st.session_state[f"q_{item_id}"] = new_q

def save_meal(date_str, meal_type, base_val, toppings, snack, new_food, amount, eaten, run_rerun=True):
    existing = supabase.table("meal_plan").select("*").eq("date", date_str).eq("meal", meal_type).execute()
    new_eaten = bool(eaten)
    old_eaten = existing.data[0]['is_eaten'] if existing.data else False
    
    final_base = ", ".join(base_val) if isinstance(base_val, list) else base_val

    if new_eaten and not old_eaten:
        update_inventory_stock(final_base, toppings, snack, -1)
    elif not new_eaten and old_eaten:
        update_inventory_stock(final_base, toppings, snack, 1)

    def filter_none(items):
        if not items: return []
        if isinstance(items, str): return [items]
        return [i for i in items if i and i != "없음"]
    
    data = {
        "date": date_str, "meal": meal_type, "base": final_base, 
        "toppings": filter_none(toppings), "snack": filter_none(snack), 
        "new_food": filter_none(new_food), "amount": int(amount), "is_eaten": new_eaten
    }
    
    if existing.data:
        supabase.table("meal_plan").update(data).eq("id", existing.data[0]['id']).execute()
    else:
        supabase.table("meal_plan").insert(data).execute()
    
    if run_rerun:
        st.toast(f"✅ {date_str} {meal_type} 저장 완료")
        st.rerun()

def clean_list_str(items, is_new_food=False):
    if not items: return ""
    if isinstance(items, str):
        items = items.replace('[', '').replace(']', '').replace('"', '').replace("'", "").split(',')
    cleaned = []
    for i in items:
        val = str(i).strip().replace('"', '').replace("'", "")
        if not val or val == "없음": continue
        if is_new_food and ":" in val:
            try:
                name, day = val.split(':')
                cleaned.append(f"{name}({day}일차)")
            except: cleaned.append(val)
        else:
            cleaned.append(val)
    return ", ".join(cleaned)

# ======================
# 3. 데이터 로드
# ======================
inv_df = fetch_inventory()
depletion_map = calculate_depletion(inv_df)
food_options = {
    "베이스": ["없음"] + inv_df[inv_df['category'] == '베이스']['food'].tolist(),
    "토핑": inv_df[inv_df['category'] == '토핑']['food'].tolist(),
    "간식": ["없음"] + inv_df[inv_df['category'] == '간식']['food'].tolist(),
    "전체": inv_df['food'].tolist()
}

# ======================
# 4. 메인 화면 레이아웃
# ======================
st.title("👶 주하 식단 매니저 PRO")
main_tab1, main_tab_week, main_tab2 = st.tabs(["📊 데일리", "📅 주간 식단표", "🗓️ 월간 식단표"])

# --- [TAB 1: 데일리] ---
with main_tab1:
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
                c_base_raw, c_tops, c_snack, c_new, c_amt, c_eaten = tr['base'] or "없음", tr['toppings'] or [], tr['snack'] or [], tr['new_food'] or [], int(tr['amount'] or 0), bool(tr['is_eaten'])
            else:
                c_base_raw, c_tops, c_snack, c_new, c_amt, c_eaten = "없음", [], [], [], 0, False
            
            b_color = "#e8f5e9" if c_eaten else "#f0f2f6"
            base_display = clean_list_str(c_base_raw)
            tops_txt, snack_txt = clean_list_str(c_tops), clean_list_str(c_snack)
            new_txt = clean_list_str(c_new, is_new_food=True)

            new_tag = f'<div style="margin-top:5px;"><span style="background-color:yellow; color:red; font-size:10px; font-weight:bold; padding:2px;">🆕 {new_txt}</span></div>' if new_txt else ""
            st.markdown(f'<div style="background-color:{b_color}; padding:10px; border-radius:10px; border:2px solid #ddd; min-height:160px;"><strong style="font-size:14px;">☀️ {m_type}</strong><br><span style="font-size:12px;">🍚 {base_display}</span><br><span style="font-size:11px; color:#666;">🥗 {tops_txt if tops_txt else "토핑없음"}</span><br><span style="font-size:11px; color:#d4a017;">🍪 {snack_txt if snack_txt else "간식없음"}</span>{new_tag}<br><small>📏 {c_amt}ml/g {"✅" if c_eaten else ""}</small></div>', unsafe_allow_html=True)

            with st.popover(f"📝 {m_type} 편집", use_container_width=True):
                col_cp1, col_cp2 = st.columns(2)
                if col_cp1.button("📋 복사", key=f"cp_{m_type}"):
                    st.session_state.clipboard = {"base": c_base_raw, "toppings": c_tops, "snack": c_snack, "new_food": c_new, "amount": c_amt}
                    st.toast("클립보드에 복사되었습니다!")
                
                if col_cp2.button("📥 붙여넣기", key=f"ps_{m_type}"):
                    if st.session_state.clipboard:
                        cb = st.session_state.clipboard
                        save_meal(t_str, m_type, cb['base'], cb['toppings'], cb['snack'], cb['new_food'], cb['amount'], False)
                    else: st.warning("복사된 내용이 없습니다.")

                current_bases = [b.strip() for b in c_base_raw.split(',') if b.strip()]
                is_multiple = len(current_bases) > 1
                b_col1, b_col2 = st.columns([3, 1])
                with b_col1:
                    u_base1 = st.selectbox("🍚 베이스 1", food_options["베이스"], 
                                         index=food_options["베이스"].index(current_bases[0]) if current_bases and current_bases[0] in food_options["베이스"] else 0, 
                                         key=f"t_b1_{m_type}")
                with b_col2:
                    u_base_one = st.checkbox("1개", value=is_multiple, key=f"t_chk1_{m_type}")

                u_base_final = [u_base1]
                if u_base_one:
                    u_base2 = st.selectbox("🍚 베이스 2", food_options["베이스"], 
                                         index=food_options["베이스"].index(current_bases[1]) if len(current_bases) > 1 and current_bases[1] in food_options["베이스"] else 0, 
                                         key=f"t_b2_{m_type}")
                    u_base_final.append(u_base2)

                u_tops = st.multiselect("🥗 토핑", food_options["토핑"], default=[t for t in (c_tops if isinstance(c_tops, list) else []) if t in food_options["토핑"]], key=f"t_t_{m_type}")
                u_snack = st.multiselect("🍪 간식", food_options["간식"], default=[s for s in (c_snack if isinstance(c_snack, list) else []) if s in food_options["간식"]], key=f"t_s_{m_type}")
                
                selected_new_names = [n.split(':')[0] for n in (c_new if isinstance(c_new, list) else [])]
                u_new_base = st.multiselect("🆕 처음 재료 선택", food_options["전체"], default=[n for n in selected_new_names if n in food_options["전체"]], key=f"t_n_base_{m_type}")
                u_new_final = []
                if u_new_base:
                    for fn in u_new_base:
                        ex_day = 0
                        for n in (c_new if isinstance(c_new, list) else []):
                            if n.split(':')[0] == fn and ":" in n: ex_day = int(n.split(':')[1])
                        default_day = ex_day if ex_day > 0 else get_next_day_for_food(fn, t_str)
                        u_day = st.number_input(f"{fn} 일차", min_value=1, value=default_day, key=f"t_day_{m_type}_{fn}")
                        u_new_final.append(f"{fn}:{u_day}")

                u_amt = st.number_input("📏 양", min_value=0, value=c_amt, key=f"t_a_{m_type}")
                u_eaten = st.checkbox("✅ 완료", value=c_eaten, key=f"t_e_{m_type}")
                if st.button("저장", key=f"t_btn_{m_type}", type="primary", use_container_width=True):
                    save_meal(t_str, m_type, u_base_final, u_tops, u_snack, u_new_final, u_amt, u_eaten)

    with st.expander("📂 식단 일괄복사"):
        c_bulk1, c_bulk2 = st.columns(2)
        with c_bulk1:
            source_date = st.date_input("1. 복사할 식단 날짜 선택", target_date, key="bulk_src_date")
            source_meal = st.selectbox("2. 복사할 끼니 선택", ["아침", "점심", "저녁"], key="bulk_src_meal")
        with c_bulk2:
            target_dates = st.multiselect("3. 복사해넣을 날짜들 선택", pd.date_range(start=date.today(), periods=30).date, key="bulk_tgt_dates")
        if st.button("🚀 일괄 복사 실행", use_container_width=True):
            src_str = source_date.isoformat()
            src_meals = fetch_meals(src_str, src_str)
            target_meal_data = src_meals[src_meals['meal'] == source_meal]
            if not target_meal_data.empty and target_dates:
                row = target_meal_data.iloc[0]
                for d in target_dates:
                    save_meal(d.isoformat(), source_meal, row['base'], row['toppings'], row['snack'], row['new_food'], row['amount'], False, run_rerun=False)
                st.success("복사 완료!")
                st.rerun()

# --- [TAB: 주간 식단표] ---
with main_tab_week:
    st.header("📅 주간 식단 플래너")
    curr_week_start = target_date - timedelta(days=target_date.weekday())
    week_meals = fetch_meals(curr_week_start.isoformat(), (curr_week_start + timedelta(days=6)).isoformat())
    for i in range(7):
        current_dt = curr_week_start + timedelta(days=i)
        d_str = current_dt.isoformat()
        st.write(f"**{current_dt.strftime('%m/%d (%a)')}**")
        m_cols = st.columns(3)
        for idx, m_type in enumerate(["아침", "점심", "저녁"]):
            with m_cols[idx]:
                m_row = week_meals[(week_meals['date'] == d_str) & (week_meals['meal'] == m_type)]
                if not m_row.empty:
                    tr = m_row.iloc[0]
                    w_base_raw, w_tops, w_snack, w_new, w_amt, w_eaten = tr['base'] or "미등록", tr['toppings'] or [], tr['snack'] or [], tr['new_food'] or [], int(tr['amount'] or 0), bool(tr['is_eaten'])
                else:
                    w_base_raw, w_tops, w_snack, w_new, w_amt, w_eaten = "미등록", [], [], [], 0, False
                bg = "#e8f5e9" if w_eaten else "#fff3e0"
                base_disp, t_txt, s_txt = clean_list_str(w_base_raw), clean_list_str(w_tops), clean_list_str(w_snack)
                n_txt = clean_list_str(w_new, is_new_food=True)
                st.markdown(f'<div style="background-color:{bg}; padding:8px; border-radius:8px; border:1px solid #ddd; min-height:100px; font-size:12px;"><b>{m_type}</b><br>🍚 {base_disp}<br><span style="color:#666;">🥗 {t_txt if t_txt else "-"}</span><br><span style="color:#d4a017;">🍪 {s_txt if s_txt else ""}</span><br><span style="color:red; font-weight:bold; font-size:10px;">{f"🆕 {n_txt}" if n_txt else ""}</span></div>', unsafe_allow_html=True)
                with st.popover("📝", use_container_width=True):
                    cw1, cw2 = st.columns(2)
                    if cw1.button("📋", key=f"wcp_{d_str}_{m_type}"):
                        st.session_state.clipboard = {"base": w_base_raw, "toppings": w_tops, "snack": w_snack, "new_food": w_new, "amount": w_amt}
                        st.toast("복사 완료")
                    if cw2.button("📥", key=f"wps_{d_str}_{m_type}"):
                        if st.session_state.clipboard:
                            cb = st.session_state.clipboard
                            save_meal(d_str, m_type, cb['base'], cb['toppings'], cb['snack'], cb['new_food'], cb['amount'], False)
                    w_bases = [b.strip() for b in w_base_raw.split(',') if b.strip()]
                    wb_col1, wb_col2 = st.columns([3, 1])
                    with wb_col1:
                        u_wb1 = st.selectbox("베이스 1", food_options["베이스"], index=food_options["베이스"].index(w_bases[0]) if w_bases and w_bases[0] in food_options["베이스"] else 0, key=f"wb1_{d_str}_{m_type}")
                    with wb_col2:
                        u_wb_chk = st.checkbox("1개", value=len(w_bases)>1, key=f"wbchk_{d_str}_{m_type}")
                    u_wb_final = [u_wb1]
                    if u_wb_chk:
                        u_wb2 = st.selectbox("베이스 2", food_options["베이스"], index=food_options["베이스"].index(w_bases[1]) if len(w_bases)>1 and w_bases[1] in food_options["베이스"] else 0, key=f"wb2_{d_str}_{m_type}")
                        u_wb_final.append(u_wb2)
                    u_wt = st.multiselect("토핑", food_options["토핑"], default=[t for t in (w_tops if isinstance(w_tops, list) else []) if t in food_options["토핑"]], key=f"wt_{d_str}_{m_type}")
                    u_ws = st.multiselect("간식", food_options["간식"], default=[s for s in (w_snack if isinstance(w_snack, list) else []) if s in food_options["간식"]], key=f"ws_{d_str}_{m_type}")
                    u_wa = st.number_input("양", min_value=0, value=w_amt, key=f"wa_{d_str}_{m_type}")
                    u_we = st.checkbox("완료", value=w_eaten, key=f"we_{d_str}_{m_type}")
                    if st.button("저장", key=f"wbtn_{d_str}_{m_type}", type="primary", use_container_width=True):
                        save_meal(d_str, m_type, u_wb_final, u_wt, u_ws, w_new, u_wa, u_we)

# --- [공통: 재료 관리] ---
st.divider()
st.header("📦 재료 관리 & 소진 예측")

with st.expander("➕ 새 재료 추가하기", expanded=False):
    new_f_col1, new_f_col2, new_f_col3 = st.columns([2, 2, 1])
    with new_f_col1: n_name = st.text_input("재료 이름 (예: 연어)")
    with new_f_col2: n_cat = st.selectbox("카테고리", ["베이스", "토핑", "간식"])
    with new_f_col3:
        st.write("") 
        if st.button("추가", type="primary", use_container_width=True):
            if n_name:
                supabase.table("inventory").insert({"food": n_name, "category": n_cat, "quantity": 0}).execute()
                st.rerun()

st.subheader("⚠️ 재고 주의 현황")
low_stock, imminent_stock = {"베이스": [], "토핑": [], "간식": []}, {"베이스": [], "토핑": [], "간식": []}
today_dt = date.today()
seven_days_later = today_dt + timedelta(days=7)

for _, row in inv_df.iterrows():
    f_name, f_qty, f_cat = row['food'], int(row['quantity']), row['category']
    if f_qty <= 5: low_stock[f_cat].append(f"{f_name}({f_qty}개)")
    d_val = depletion_map.get(f_name)
    if d_val and d_val not in ["여유", "재고 없음", "미정"]:
        try:
            d_date = date.fromisoformat(d_val)
            if today_dt <= d_date <= seven_days_later:
                imminent_stock[f_cat].append(f"{f_name}({d_date.strftime('%m/%d')}, {f_qty}개 남음)")
        except: pass

if any(low_stock.values()) or any(imminent_stock.values()):
    c1, c2 = st.columns(2)
    with c1:
        if any(low_stock.values()):
            st.error("🚨 **재고 부족 (5개 이하)**")
            for cat, items in low_stock.items():
                if items: st.write(f"**{cat}**: {', '.join(items)}")
    with c2:
        if any(imminent_stock.values()):
            st.warning("⏰ **소진 임박 (7일 내)**")
            for cat, items in imminent_stock.items():
                if items: st.write(f"**{cat}**: {', '.join(items)}")
else: st.success("재고가 충분합니다. 😊")

inv_tabs = st.tabs(["🍚 베이스", "🥗 토핑", "🍪 간식"])
for idx, cat in enumerate(["베이스", "토핑", "간식"]):
    with inv_tabs[idx]:
        cat_items = inv_df[inv_df['category'] == cat]
        for _, row in cat_items.iterrows():
            f_name, f_id, f_qty = row['food'], row['id'], int(row['quantity'])
            d_date = depletion_map.get(f_name, "미정")
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{f_name}** \n<small style='color:#666;'>소진예정: {d_date}</small>", unsafe_allow_html=True)
            with col2:
                # [수정 핵심] 사용자가 입력한 값(세션)이 DB값보다 우선하도록 설정하여 튕김 방지
                state_key = f"q_{f_id}"
                if state_key not in st.session_state:
                    st.session_state[state_key] = f_qty
                
                # 사용자가 입력을 마치면(on_change) 콜백 함수를 통해 DB에 먼저 저장
                st.number_input(
                    "수량", 
                    min_value=0, 
                    key=state_key, 
                    on_change=on_quantity_change, 
                    args=(f_id, state_key), 
                    label_visibility="collapsed"
                )
            with col3:
                with st.popover("⚙️"):
                    new_name = st.text_input("이름 수정", value=f_name, key=f"edit_{f_id}")
                    if st.button("저장", key=f"save_n_{f_id}"):
                        supabase.table("inventory").update({"food": new_name}).eq("id", f_id).execute()
                        st.rerun()
                    if st.button("🗑️ 삭제", key=f"del_{f_id}"):
                        supabase.table("inventory").delete().eq("id", f_id).execute()
                        if state_key in st.session_state:
                            del st.session_state[state_key]
                        st.rerun()
            st.divider()

# --- [TAB: 월간 식단표] ---
with main_tab2:
    st.header("🗓️ 월간 상세 식단표")
    sel_y = st.selectbox("년", [2025, 2026], index=1)
    sel_m = st.selectbox("월", range(1, 13), index=datetime.now().month-1)
    m_data = fetch_meals(date(sel_y, sel_m, 1).isoformat(), date(sel_y, sel_m, calendar.monthrange(sel_y, sel_m)[1]).isoformat())
    cal, m_order = calendar.monthcalendar(sel_y, sel_m), {"아침": 0, "점심": 1, "저녁": 2}
    days_kr = ["월", "화", "수", "목", "금", "토", "일"]
    for week in cal:
        w_cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                dt_obj = date(sel_y, sel_m, day)
                d_str, wd = dt_obj.isoformat(), dt_obj.weekday()
                day_color = "blue" if i == 5 else ("red" if i == 6 else "black")
                d_meals = m_data[m_data['date'] == d_str].copy()
                bg = "#ffffff" if d_meals.empty else ("#e8f5e9" if d_meals['is_eaten'].all() else "#fff9c4")
                with w_cols[i]:
                    inner = ""
                    if not d_meals.empty:
                        d_meals['order'] = d_meals['meal'].map(m_order)
                        for _, row in d_meals.sort_values('order').iterrows():
                            icon = "🌅" if row['meal'] == "아침" else "☀️" if row['meal'] == "점심" else "🌙"
                            b_disp, t_txt, s_txt = clean_list_str(row['base']), clean_list_str(row['toppings']), clean_list_str(row['snack'])
                            n_txt = clean_list_str(row['new_food'], is_new_food=True)
                            inner += f"<div style='margin-bottom:3px; font-size:9px;'>{icon}<b>{b_disp}</b>"
                            if t_txt: inner += f"<br><span style='color:#666;'>└ {t_txt}</span>"
                            if n_txt: inner += f"<br><span style='color:red;'>🆕 {n_txt}</span>"
                            inner += "</div>"
                    st.markdown(f"<div style='background-color:{bg}; border:1px solid #ddd; border-radius:5px; padding:3px; min-height:100px;'><div style='text-align:center; font-weight:bold; font-size:10px; color:{day_color};'>{sel_m}/{day}({days_kr[wd]})</div>{inner}</div>", unsafe_allow_html=True)