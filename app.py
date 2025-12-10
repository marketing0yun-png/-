import streamlit as st
import pandas as pd
from datetime import datetime

# Page configuration
st.set_page_config(page_title="체험단 관리현황", layout="wide")

# Title
st.title("체험단 관리현황")

# Google Sheet ID
SHEET_ID = "1JBQaSh7c1nla17u2OG0Tynp-mGYD7cRVSABIzZRYdCE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=600)  # 10분 캐시
def load_data(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return None

# -------------------------
# LOGIN FUNCTION (TOML MODE)
# -------------------------
def check_password():
    """Returns True if the correct password was entered."""

    def password_entered():
        # 세션에서 입력값 가져오기
        username = st.session_state.get("username", "")
        password = st.session_state.get("password", "")

        if "users" not in st.session_state["secrets"]:
            st.error("Secrets 설정이 잘못되었습니다. [users] 섹션을 확인하세요.")
            return

        # 유저 존재 & 비밀번호 확인
        if username in st.session_state["secrets"]["users"]:
            if st.session_state["secrets"]["users"][username] == password:
                st.session_state["password_correct"] = True
                st.session_state["current_user"] = username
                st.session_state["allowed_stores"] = \
                    st.session_state["secrets"].get("stores", {}).get(username, [])
                
                # 비밀번호 세션 삭제 (보안)
                if "password" in st.session_state:
                    del st.session_state["password"]
                return

        st.session_state["password_correct"] = False

    # UI 렌더링
    if st.session_state.get("password_correct", False):
        return True

    st.text_input("아이디 (Username)", key="username")
    st.text_input("비밀번호 (Password)", type="password", key="password", on_change=password_entered)
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 아이디가 없거나 비밀번호가 틀렸습니다.")
        
    return False

# -------------------------
# MAIN APP LOGIC
# -------------------------

# Secrets 로드
if "secrets" not in st.session_state:
    try:
        st.session_state["secrets"] = st.secrets
    except FileNotFoundError:
        st.error("secrets.toml 파일을 찾을 수 없습니다.")
        st.stop()

# LOGIN CHECK
if not check_password():
    st.stop()

# 데이터 로드
df = load_data(SHEET_URL)
if df is None:
    st.stop()

# 로그인 완료 변수
current_user = st.session_state["current_user"]
allowed_stores = st.session_state["allowed_stores"]

# Sidebar
with st.sidebar:
    st.success(f"접속자: {current_user}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("로그아웃"):
            for key in ["password_correct", "current_user", "allowed_stores", "username"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    with col2:
        if st.button("데이터 갱신"):
            load_data.clear()
            st.rerun()

    st.divider()

# -------------------------
# FILTERING
# -------------------------

# 컬럼 수 확인 (F, O, P, Q열은 각각 인덱스 5, 14, 15, 16이므로 최소 17개 이상 필요)
if len(df.columns) >= 17:

    # --- 1. 날짜 파싱 (Column I = Index 8) ---
    date_col_name = df.columns[8]

    def parse_date(val):
        if pd.isna(val): return pd.NaT
        val = str(val).strip()
        
        parsed = pd.to_datetime(val, errors="coerce")
        if pd.notna(parsed): return parsed

        try:
            current_year = datetime.now().year
            parsed = pd.to_datetime(f"{current_year}/" + val, format="%Y/%m/%d", errors="coerce")
            return parsed
        except:
            return pd.NaT

    df["parsed_date"] = df.iloc[:, 8].apply(parse_date)
    df = df[df["parsed_date"].notna()]
    df[date_col_name] = df["parsed_date"].dt.strftime("%Y-%m-%d")

    # --- 2. 매장 필터 (Column D = Index 3) ---
    filter_col_name = df.columns[3]
    unique_values = df[filter_col_name].unique()

    if "All" in allowed_stores:
        options = ["All"] + list(unique_values)
    else:
        options = [s for s in allowed_stores if s in unique_values]
        if not options:
            options = ["접근 권한 없음"]

    selected_store = st.sidebar.selectbox(
        f"매장 선택 ({filter_col_name})",
        options,
        key=f"store_selector_{current_user}"
    )

    if selected_store == "All":
        df_filtered = df.copy()
    elif selected_store == "접근 권한 없음":
        df_filtered = pd.DataFrame(columns=df.columns)
    else:
        df_filtered = df[df[filter_col_name] == selected_store].copy()

    # --- 3. 날짜 범위 필터 ---
    st.sidebar.subheader("기간 설정")
    if not df_filtered.empty:
        df_dates = df_filtered["parsed_date"]
        min_date = df_dates.min().date()
        max_date = df_dates.max().date()

        date_range = st.sidebar.date_input(
            "날짜 범위 선택",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"date_range_{current_user}"
        )

        if len(date_range) == 2:
            start_date, end_date = date_range
            df_filtered = df_filtered[
                (df_filtered["parsed_date"].dt.date >= start_date) &
                (df_filtered["parsed_date"].dt.date <= end_date)
            ]

    df_filtered = df_filtered.sort_values(by="parsed_date", ascending=False)
    df_filtered.reset_index(drop=True, inplace=True)
    df_filtered.index = df_filtered.index + 1

else:
    st.error(f"데이터 형식이 올바르지 않습니다. (컬럼 수 부족: 현재 {len(df.columns)}개)")
    df_filtered = pd.DataFrame()


# -------------------------
# TABS & DISPLAY (Hyperlink Added)
# -------------------------

# 하이퍼링크 설정을 위한 사전 준비
# F열(5), O열(14), P열(15), Q열(16)
link_target_indices = [5, 14, 15, 16]
column_config_settings = {}

if not df_filtered.empty:
    for idx in link_target_indices:
        if idx < len(df_filtered.columns):
            col_name = df_filtered.columns[idx]
            # 해당 컬럼을 LinkColumn으로 설정 (display_text는 '🔗 확인하기'으로 통일하거나, None이면 URL 그대로 노출)
            column_config_settings[col_name] = st.column_config.LinkColumn(
                label=col_name,
                display_text="🔗 확인하기"  # URL이 너무 길면 지저분하므로 '확인하기'이라는 글자로 대체 (원하시면 이 줄 삭제)
            )

tab1, tab2, tab3 = st.tabs(["📅 일정현황", "📝 방문결과", "📊 관리현황"])

if not df_filtered.empty:
    with tab1:
        st.subheader("일정현황")
        # F열(5) 포함됨
        target_indices = [8, 9, 2, 10, 4, 5, 6] 
        st.dataframe(
            df_filtered.iloc[:, target_indices], 
            column_config=column_config_settings, # 링크 설정 적용
            use_container_width=True
        )

    with tab2:
        st.subheader("방문결과")
        # O열(14), P열(15), Q열(16) 포함됨
        target_indices = [8, 14, 10, 17, 15, 16]
        st.dataframe(
            df_filtered.iloc[:, target_indices], 
            column_config=column_config_settings, # 링크 설정 적용
            use_container_width=True
        )

    with tab3:
        st.subheader("관리현황")
        # O열(14), P열(15), Q열(16) 포함됨
        target_indices = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
        st.dataframe(
            df_filtered.iloc[:, target_indices], 
            column_config=column_config_settings, # 링크 설정 적용
            use_container_width=True
        )
else:
    st.info("조건에 맞는 데이터가 없습니다.")

