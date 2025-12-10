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

@st.cache_data(ttl=600)  # TTL 추가: 10분마다 캐시 만료 (데이터 갱신 반영)
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
        # 세션에 입력된 값 가져오기
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
                # stores 키가 없을 경우를 대비해 빈 리스트 반환
                st.session_state["allowed_stores"] = \
                    st.session_state["secrets"].get("stores", {}).get(username, [])
                
                # 보안을 위해 비밀번호 세션 삭제
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

# Secrets 로드 (Streamlit Cloud 환경 호환)
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

# 로그인 완료 후 변수 할당
current_user = st.session_state["current_user"]
allowed_stores = st.session_state["allowed_stores"]

# Sidebar - Logout & Refresh
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

# 데이터 컬럼 수 확인 (인덱스 에러 방지)
if len(df.columns) >= 18:  # 탭2, 탭3에서 인덱스 17까지 사용하므로 최소 18개 필요

    # --- 1. 날짜 파싱 (Column I = Index 8) ---
    date_col_name = df.columns[8] # 실제 컬럼명 사용 권장

    def parse_date(val):
        if pd.isna(val): return pd.NaT
        val = str(val).strip()
        
        # 1차 시도: 일반적인 포맷
        parsed = pd.to_datetime(val, errors="coerce")
        if pd.notna(parsed): return parsed

        # 2차 시도: "MM/DD" 형태일 경우 현재 연도 붙이기
        try:
            current_year = datetime.now().year
            parsed = pd.to_datetime(f"{current_year}/" + val, format="%Y/%m/%d", errors="coerce")
            return parsed
        except:
            return pd.NaT

    df["parsed_date"] = df.iloc[:, 8].apply(parse_date) # 원본 보존을 위해 새 컬럼 생성
    
    # 날짜 없는 행 제거
    df = df[df["parsed_date"].notna()]
    
    # 표시용 날짜 문자열
    df[date_col_name] = df["parsed_date"].dt.strftime("%Y-%m-%d")

    # --- 2. 매장 필터 (Column D = Index 3 가정) ---
    filter_col_name = df.columns[3]
    unique_values = df[filter_col_name].unique()

    # 권한별 옵션 설정
    if "All" in allowed_stores:
        options = ["All"] + list(unique_values)
    else:
        # 권한이 있는 매장 중 실제 데이터에 존재하는 것만 필터링
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

    # 정렬 및 인덱스 재설정
    df_filtered = df_filtered.sort_values(by="parsed_date", ascending=False)
    
    # 화면 표시 전 파싱용 임시 컬럼 제거 (선택사항)
    # df_filtered = df_filtered.drop(columns=["parsed_date"]) 
    
    df_filtered.reset_index(drop=True, inplace=True)
    df_filtered.index = df_filtered.index + 1

else:
    st.error(f"데이터 형식이 올바르지 않습니다. (컬럼 수 부족: 현재 {len(df.columns)}개)")
    df_filtered = pd.DataFrame() # 빈 프레임


# -------------------------
# TABS & DISPLAY
# -------------------------

tab1, tab2, tab3 = st.tabs(["📅 일정현황", "📝 방문결과", "📊 관리현황"])

if not df_filtered.empty:
    with tab1:
        st.subheader("일정현황")
        # 구글 시트의 컬럼 순서가 바뀌면 아래 숫자를 수정해야 합니다.
        target_indices = [8, 9, 2, 10, 4, 5, 6] 
        st.dataframe(df_filtered.iloc[:, target_indices], use_container_width=True)

    with tab2:
        st.subheader("방문결과")
        target_indices = [8, 14, 10, 17, 15, 16]
        st.dataframe(df_filtered.iloc[:, target_indices], use_container_width=True)

    with tab3:
        st.subheader("관리현황")
        target_indices = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
        st.dataframe(df_filtered.iloc[:, target_indices], use_container_width=True)
else:
    st.info("조건에 맞는 데이터가 없습니다.")
