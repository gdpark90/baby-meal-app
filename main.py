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

def ensure_list(val):
    """어떤 형태의 데이터든 리스트로 안전하게 변환"""
    if not val: return []
    if isinstance(val, list): return val
    if isinstance(val, str):
        # "[item1, item2]" 형태의 문자열 처리
        cleaned = val.replace('[', '').replace(']', '').replace('"', '').replace("'", "")
        return [i.strip() for i in cleaned.split(',') if i.strip()]
    return [val]

def update_inventory_stock(base, toppings, snack, change):
    items_to_update = []
    if base and base != "없음": items_to_update.append(base)
    items_to_update.extend(ensure_list(toppings))
    items_to_update.extend(ensure_list(snack))
    
    for item_name in items_to_update:
        res = supabase.table("inventory").select("id", "quantity").eq("food", item_name).execute()
        if res.data:
            new_qty = max(0, int(res.data[0]['quantity']) + change)
            supabase.table("inventory").update({"quantity": new_qty}).eq("id", res.data[0]['id']).execute()

def save_meal(date_str, meal_type, base, toppings, snack, new_food, amount, eaten, run_rerun=True):
    existing = supabase.table("meal_plan").select("*").eq("date", date_str).eq("meal", meal_type).execute()
    
    new_eaten = bool(eaten)
    old_eaten = existing.data[0]['is_eaten'] if existing.data else False
    
    if new_eaten and not old_eaten:
        update_inventory_stock(base, toppings, snack, -1)
    elif not new_eaten and old_eaten:
        update_inventory_stock(base, toppings, snack, 1)

    data = {
        "date": date_str, "meal": meal_type, "base": base, 
        "toppings": ensure_list(toppings), "snack": ensure_list(snack), 
        "new_food": ensure_list(new_food), "amount": int(amount or 0), "is_eaten": new_eaten
    }
    
    if existing.data:
        supabase.table("meal_plan").update(data).eq("id", existing.data[0]['id']).execute()
    else:
        supabase.table("meal_plan").insert(data).execute()
    
    if run_rerun:
        st.toast(f"✅ 저장 완료 (재고 반영됨)")
        st.rerun()

def get_next_day_for_food(food_name, target_date_str):
    res = supabase.table("meal_plan").select("new_food").lt("date", target_date_str).execute()
    count = 0
    for row in res.data:
        nf_list = ensure_list(row.get('new_food', []))
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
        food_name, current_qty = item['food'], int(item['quantity'])
        usage_dates = []
        if not future_meals.empty:
            for _, meal in future_meals.iterrows():
                # 에러 수정 포인트: 모든 항목을 ensure_list로 감싸서 리스트 합치기 수행
                combined = ([meal['base']] if meal['base'] else []) + \
                           ensure_list(meal['toppings']) + \
                           ensure_list(meal['snack'])
                if food_name in combined: usage_dates.append(meal['date'])
        usage_dates.sort()
        if current_qty <= 0: depletion_results[food_name] = "재고 없음"
        elif len(usage_dates) >= current_qty: depletion_results[food_name] = usage_dates[current_qty - 1]
        else: depletion_results[food_name] = "여유"
    return depletion_results

def clean_list_str(items, is_new_food=False):
    lst = ensure_list(items)
    cleaned = []
    for val in lst:
        if not val or val == "없음": continue
        if is_new_food and ":" in val:
            try:
                name, day = val.split(':')
                cleaned.append(f"{name}({day}일차)")
            except: cleaned.append(val)
        else: cleaned.append(val)
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
# 4. UI 렌더링 함수
# ======================
def render_meal_editor(prefix, d_str, m_type, current_data):
    c_base, c_tops, c_snack, c_new, c_amt, c_eaten = current_data
    
    cp_col1, cp_col2 = st.columns(2)
    if cp_col1.button("📋 복사", key=f"cp_{prefix}_{d_str}_{m_type}"):
        st.session_state.clipboard = {"base": c_base, "toppings": c_tops, "snack": c_snack, "new_food": c_new, "amount": c_amt}
        st.toast("복사되었습니다!")
    if cp_col2.button("📥 붙여넣기", key=f"ps_{prefix}_{d_str}_{m_type}"):
        if st.session_state.clipboard:
            cb = st.session_state.clipboard
            save_meal(d_str, m_type, cb['base'], cb['toppings'], cb['snack'], cb['new_food'], cb['amount'], False)
        else: st.warning("복사된 내용이 없습니다.")

    u_base = st.selectbox("🍚 베이스", food_options["베이스"], index=food_options["베이스"].index(c_base) if c_base in food_options["베이스"] else 0, key=f"b_{prefix}_{d_str}_{m_type}")
    u_tops = st.multiselect("🥗 토핑", food_options["토핑"], default=[t for t in ensure_list(c_tops) if t in food_options["토핑"]], key=f"t_{prefix}_{d_str}_{m_type}")
    u_snack = st.multiselect("🍪 간식", food_options["간식"], default=[s for s in ensure_list(c_snack) if s in food_options["간식"]], key=f"s_{prefix}_{d_str}_{m_type}")
    
    s_new_names = [n.split(':')[0] for n in ensure_list(c_new)]
    u_new_base = st.multiselect("🆕 처음 재료", food_options["전체"], default=[n for n in s_new_names if n in food_options["전체"]], key=f"n_b_{prefix}_{d_str}_{m_type}")
    u_new_final = []
    if u_new_base:
        for fn in u_new_base:
            ex_day = 0
            for n in ensure_list(c_new):
                if n.split(':')[0] == fn and ":" in n: ex_day = int(n.split(':')[1])
            default_day = ex_day if ex_day > 0 else get_next_day_for_food(fn, d_str)
            u_day = st.number_input(f"{fn} 일차", min_value=1, value=default_day, key=f"n_d_{prefix}_{d_str}_{m_type}_{fn}")
            u_new_final.append(f"{fn}:{u_day}")

    # 요청하신 5g 단위 조절 버튼 (step=5)
    u_amt = st.number_input("📏 양(g/ml)", min_value=0, value=int(c_amt or 0), step=5, key=f"a_{prefix}_{d_str}_{m_type}")
    u_eaten = st.checkbox("✅ 완료(체크 시 재고차감)", value=c_eaten, key=f"e_{prefix}_{d_str}_{m_type}")
    
    if st.button("저장", key=f"btn_{prefix}_{d_str}_{m_type}", type="primary", use_container_width=True):
        save_meal(d_str, m_type, u_base, u_tops, u_snack, u_new_final, u_amt, u_eaten)

# ======================
# 5. 메인 레이아웃
# ======================
st.title("👶 주하 식단 매니저 PRO")
tab1, tab2 = st.tabs(["📊 데일리 & 주간", "📅 월간 식단표"])

with tab1:
    target_date = st.date_input("📅 날짜 선택", date.today())
    t_str = target_date.isoformat()
    t_meals = fetch_meals(t_str, t_str)

    st.subheader(f"📍 {target_date.strftime('%Y-%m-%d')} 식단")
    cols = st.columns(3)
    for idx, m_type in enumerate(["아침", "점심", "저녁"]):
        with cols[idx]:
            m_row = t_meals[t_meals['meal'] == m_type]
            if not m_row.empty:
                tr = m_row.iloc[0]
                curr_data = (tr['base'] or "없음", tr['toppings'] or [], tr['snack'] or [], tr['new_food'] or [], int(tr['amount'] or 0), bool(tr['is_eaten']))
            else: curr_data = ("없음", [], [], [], 0, False)
            
            bg = "#e8f5e9" if curr_data[5] else "#f0f2f6"
            n_txt = clean_list_str(curr_data[3], True)
            new_tag = f'<div style="margin-top:5px;"><span style="background-color:yellow; color:red; font-size:10px; font-weight:bold; padding:2px;">🆕 {n_txt}</span></div>' if n_txt else ""
            
            st.markdown(f'<div style="background-color:{bg}; padding:10px; border-radius:10px; border:2px solid #ddd; min-height:160px;"><strong style="font-size:14px;">☀️ {m_type}</strong><br><span style="font-size:12px;">🍚 {curr_data[0]}</span><br><span style="font-size:11px; color:#666;">🥗 {clean_list_str(curr_data[1]) or "-"}</span><br><span style="font-size:11px; color:#d4a017;">🍪 {clean_list_str(curr_data[2]) or "-"}</span>{new_tag}<br><small>📏 {curr_data[4]}g {"✅" if curr_data[5] else ""}</small></div>', unsafe_allow_html=True)
            with st.popover(f"📝 {m_type} 편집", use_container_width=True):
                render_meal_editor("today", t_str, m_type, curr_data)

    # 일괄 복사 섹션
    with st.expander("📂 식단 일괄복사"):
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            src_date = st.date_input("복사할 날짜", target_date, key="b_src_d")
            src_meal = st.selectbox("복사할 끼니", ["아침", "점심", "저녁"], key="b_src_m")
        with b_col2:
            tgt_dates = st.multiselect("붙여넣을 날짜들", pd.date_range(start=date.today(), periods=30).date, key="b_tgt_ds")
        if st.button("🚀 일괄 복사 실행", use_container_width=True):
            res = fetch_meals(src_date.isoformat(), src_date.isoformat())
            row = res[res['meal'] == src_meal]
            if not row.empty and tgt_dates:
                r = row.iloc[0]
                for d in tgt_dates: save_meal(d.isoformat(), src_meal, r['base'], r['toppings'], r['snack'], r['new_food'], r['amount'], False, False)
                st.rerun()

    # 주간 식단표 (이번주만)
    st.divider()
    st.header("📅 이번 주 식단 플래너")
    week_start = target_date - timedelta(days=target_date.weekday())
    w_meals = fetch_meals(week_start.isoformat(), (week_start + timedelta(days=6)).isoformat())
    for i in range(7):
        curr_dt = week_start + timedelta(days=i)
        d_str = curr_dt.isoformat()
        st.write(f"**{curr_dt.strftime('%m/%d (%a)')}**")
        w_cols = st.columns(3)
        for idx, m_type in enumerate(["아침", "점심", "저녁"]):
            with w_cols[idx]:
                m_row = w_meals[(w_meals['date'] == d_str) & (w_meals['meal'] == m_type)]
                if not m_row.empty:
                    tr = m_row.iloc[0]
                    wd = (tr['base'] or "미등록", tr['toppings'] or [], tr['snack'] or [], tr['new_food'] or [], int(tr['amount'] or 0), bool(tr['is_eaten']))
                else: wd = ("미등록", [], [], [], 0, False)
                
                bg = "#e8f5e9" if wd[5] else "#fff3e0"
                n_txt = clean_list_str(wd[3], True)
                new_line = f'<br><span style="color:red; font-weight:bold; font-size:10px;">🆕 {n_txt}</span>' if n_txt else ""
                st.markdown(f'<div style="background-color:{bg}; padding:8px; border-radius:8px; border:1px solid #ddd; min-height:100px; font-size:12px;"><b>{m_type}</b><br>🍚 {wd[0]}<br><span style="color:#666;">🥗 {clean_list_str(wd[1]) or "-"}</span><br><span style="color:#d4a017;">🍪 {clean_list_str(wd[2]) or "-"}</span>{new_line}</div>', unsafe_allow_html=True)
                with st.popover("📝", use_container_width=True):
                    render_meal_editor("week", d_str, m_type, wd)

    # 재료 관리 & 재고부족 알림
    st.divider()
    st.header("📦 재료 관리")
    st.subheader("⚠️ 재고부족주의")
    low_stock = {"베이스": [], "토핑": [], "간식": []}
    for _, row in inv_df.iterrows():
        if int(row['quantity']) <= 5: low_stock[row['category']].append(f"{row['food']}({row['quantity']}개 남음)")
    
    if any(low_stock.values()):
        st.markdown('<div style="background-color:#fff5f5; padding:15px; border-radius:10px; border:1px solid #ffcfcf;">', unsafe_allow_html=True)
        for cat, items in low_stock.items():
            if items: st.markdown(f"**• {cat}** : {', '.join(items)}")
        st.markdown('</div>', unsafe_allow_html=True)
    else: st.success("재고가 충분합니다. 😊")

    inv_tabs = st.tabs(["🍚 베이스", "🥗 토핑", "🍪 간식"])
    for idx, cat in enumerate(["베이스", "토핑", "간식"]):
        with inv_tabs[idx]:
            for _, row in inv_df[inv_df['category'] == cat].iterrows():
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1: st.markdown(f"**{row['food']}**\n<small style='color:#666;'>소진예상: {depletion_map.get(row['food'], '미정')}</small>", unsafe_allow_html=True)
                with col2:
                    new_q = st.number_input("수량", min_value=0, value=int(row['quantity']), key=f"inv_q_{row['id']}", label_visibility="collapsed")
                    if new_q != int(row['quantity']):
                        supabase.table("inventory").update({"quantity": int(new_q)}).eq("id", row['id']).execute()
                        st.rerun()
                with col3:
                    if st.button("🗑️", key=f"inv_del_{row['id']}"):
                        supabase.table("inventory").delete().eq("id", row['id']).execute()
                        st.rerun()
                st.divider()

with tab2:
    st.header("🗓️ 월간 상세 식단표")
    sel_y = st.selectbox("년", [2025, 2026], index=1)
    sel_m = st.selectbox("월", range(1, 13), index=datetime.now().month-1)
    m_data = fetch_meals(date(sel_y, sel_m, 1).isoformat(), date(sel_y, sel_m, calendar.monthrange(sel_y, sel_m)[1]).isoformat())
    cal = calendar.monthcalendar(sel_y, sel_m)
    w_days = ["월", "화", "수", "목", "금", "토", "일"]
    
    h_cols = st.columns(7)
    for i, wd in enumerate(w_days): h_cols[i].markdown(f"<div style='text-align:center; font-weight:bold; background-color:#f0f2f6; padding:5px; border-radius:5px;'>{wd}</div>", unsafe_allow_html=True)

    for w_idx, week in enumerate(cal):
        st.markdown(f"<div style='margin-top:15px; border-top:3px solid #333; padding-top:5px; font-weight:bold;'>📍 {w_idx+1}주차</div>", unsafe_allow_html=True)
        w_cols = st.columns(7)
        for i, day in enumerate(week):
            if day != 0:
                cur_dt = date(sel_y, sel_m, day)
                d_str = cur_dt.isoformat()
                d_meals = m_data[m_data['date'] == d_str].copy()
                bg = "#ffffff" if d_meals.empty else ("#e8f5e9" if d_meals['is_eaten'].all() else "#fff9c4")
                
                with w_cols[i]:
                    st.markdown(f"<div style='background-color:{bg}; border:1px solid #ddd; border-radius:5px; padding:5px; min-height:160px;'>", unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align:center; font-weight:bold; font-size:11px;'>{sel_m}/{day}({w_days[cur_dt.weekday()]})</div>", unsafe_allow_html=True)
                    
                    if not d_meals.empty:
                        m_order = {"아침": 0, "점심": 1, "저녁": 2}
                        d_meals['order'] = d_meals['meal'].map(m_order)
                        for _, row in d_meals.sort_values('order').iterrows():
                            icon = "🌅" if row['meal'] == "아침" else "☀️" if row['meal'] == "점심" else "🌙"
                            t_txt, s_txt = clean_list_str(row['toppings']), clean_list_str(row['snack'])
                            n_txt = clean_list_str(row['new_food'], True)
                            
                            content = f"<b>{row['base']}</b>"
                            if t_txt: content += f"<br><span style='color:#666;'>🥗{t_txt}</span>"
                            if s_txt: content += f"<br><span style='color:#d4a017;'>🍪{s_txt}</span>"
                            if n_txt: content += f"<br><span style='color:red;'>🆕{n_txt}</span>"
                            if row['is_eaten']: content += " ✅"
                            
                            st.markdown(f"<div style='font-size:9px; border-bottom:1px solid #eee; padding:2px 0;'>{icon} {content}</div>", unsafe_allow_html=True)
                            with st.popover("⚙️", use_container_width=True):
                                render_meal_editor("month", d_str, row['meal'], (row['base'], row['toppings'], row['snack'], row['new_food'], row['amount'], row['is_eaten']))
                    st.markdown("</div>", unsafe_allow_html=True)