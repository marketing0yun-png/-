import streamlit as st
import pandas as pd
from datetime import datetime

# -------------------------
# 1. 페이지 기본 설정
# -------------------------
st.set_page_config(
    page_title="체험단 관리 대시보드", 
    page_icon="📊", 
    layout="wide"
)

# 제목 (Markdown 활용)
st.markdown("## 📊 체험단 운영/관리 대시보드")
st.markdown("---")

# Google Sheet ID
SHEET_ID = "1JBQaSh7c1nla17u2OG0Tynp-mGYD7cRVSABIzZRYdCE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=600)
def load_data(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# -------------------------
# LOGIN FUNCTION
# -------------------------
def check_password():
    """Returns True if the correct password was entered."""
    def password_entered():
        username = st.session_state.get("username", "")
        password = st.session_state.get("password", "")

        if "users" not in st.session_state["secrets"]:
            st.error("Secrets 설정 오류: .streamlit/secrets.toml 파일을 확인하세요.")
            return

        if username in st.session_state["secrets"]["users"]:
            if st.session_state["secrets"]["users"][username] == password:
                st.session_state["password_correct"] = True
                st.session_state["current_user"] = username
                st.session_state["allowed_stores"] = \
                    st.session_state["secrets"].get("stores", {}).get(username, [])
                if "password" in st.session_state: del st.session_state["password"]
                return
        st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # 로그인 화면
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("🔒 관계자 외 접속을 제한합니다.")
        st.text_input("아이디 (Username)", key="username")
        st.text_input("비밀번호 (Password)", type="password", key="password", on_change=password_entered)
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("😕 로그인 정보가 올바르지 않습니다.")
    return False

# -------------------------
# MAIN APP LOGIC
# -------------------------

if "secrets" not in st.session_state:
    try:
        st.session_state["secrets"] = st.secrets
    except FileNotFoundError:
        st.error("secrets.toml 없음")
        st.stop()

if not check_password():
    st.stop()

df = load_data(SHEET_URL)
if df is None:
    st.stop()

current_user = st.session_state["current_user"]
allowed_stores = st.session_state["allowed_stores"]

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    st.header(f"👋 반가워요, {current_user}님")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 갱신", use_container_width=True):
            load_data.clear()
            st.rerun()
    with col2:
        if st.button("🚪 로그아웃", use_container_width=True):
            for key in ["password_correct", "current_user", "allowed_stores", "username"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
            
    st.info("💡 데이터는 10분마다 자동 갱신됩니다.")

# -------------------------
# FILTERING
# -------------------------

if len(df.columns) >= 17:
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

    filter_col_name = df.columns[3]
    unique_values = df[filter_col_name].unique()

    if "All" in allowed_stores:
        options = ["All"] + list(unique_values)
    else:
        options = [s for s in allowed_stores if s in unique_values]
        if not options: options = ["접근 권한 없음"]

    st.sidebar.subheader("🔍 검색 필터")
    selected_store = st.sidebar.selectbox(
        f"매장 선택",
        options,
        key=f"store_selector_{current_user}"
    )

    if selected_store == "All":
        df_filtered = df.copy()
    elif selected_store == "접근 권한 없음":
        df_filtered = pd.DataFrame(columns=df.columns)
    else:
        df_filtered = df[df[filter_col_name] == selected_store].copy()

    if not df_filtered.empty:
        df_dates = df_filtered["parsed_date"]
        min_date, max_date = df_dates.min().date(), df_dates.max().date()
        
        # 달력 포맷 지정 (YYYY-MM-DD)
        date_range = st.sidebar.date_input(
            "날짜 범위",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"date_range_{current_user}",
            format="YYYY-MM-DD" 
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
    st.error("데이터 컬럼 부족")
    df_filtered = pd.DataFrame()


# -------------------------
# DASHBOARD METRICS
# -------------------------
if not df_filtered.empty:
    st.markdown("### 📈 현황 요약")
    
    m1, m2, m3 = st.columns(3)
    
    total_count = len(df_filtered)
    today_count = len(df_filtered[df_filtered["parsed_date"].dt.date == datetime.now().date()])
    
    with m1:
        st.metric(label="전체 조회 건수", value=f"{total_count}건")
    with m2:
        st.metric(label="오늘 일정", value=f"{today_count}건", delta=f"기준: {datetime.now().strftime('%m-%d')}")
    with m3:
        st.metric(label="선택된 매장", value=selected_store)
        
    st.markdown("---")

# -------------------------
# TABS & DISPLAY
# -------------------------

link_target_indices = [5, 14, 15, 16]
column_config_settings = {}

if not df_filtered.empty:
    for idx in link_target_indices:
        if idx < len(df_filtered.columns):
            col_name = df_filtered.columns[idx]
            column_config_settings[col_name] = st.column_config.LinkColumn(
                label=col_name,
                display_text="🔗 바로가기"
            )

# 권한별 탭 구성
if current_user == "admin":
    tab_list = ["📅 일정현황", "📝 방문결과", "📊 관리현황"]
else:
    tab_list = ["📅 일정현황", "📝 방문결과"]

tabs = st.tabs(tab_list)

if not df_filtered.empty:
    # --- 1. 일정현황 ---
    with tabs[0]:
        st.subheader("📅 일정 리스트")
        target_indices = [8, 9, 2, 10, 4, 5, 6] 
        st.dataframe(
            df_filtered.iloc[:, target_indices], 
            column_config=column_config_settings,
            use_container_width=True
        )

    # --- 2. 방문결과 ---
    with tabs[1]:
        st.subheader("📝 결과 리포트")
        target_indices = [8, 14, 10, 17, 15, 16]
        st.dataframe(
            df_filtered.iloc[:, target_indices], 
            column_config=column_config_settings,
            use_container_width=True
        )

    # --- 3. 관리현황 (Admin Only) ---
    if current_user == "admin":
        with tabs[2]:
            # 관리현황 데이터 준비
            target_indices = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
            admin_df = df_filtered.iloc[:, target_indices]

            # [UI Upgrade] 제목과 미처리 현황을 좌우로 배치
            header_col, metric_col = st.columns([1, 4]) 
            
            with header_col:
                st.subheader("📊 상세 관리")
            
            with metric_col:
                # 미처리(NaN/None) 값 카운팅 로직
                null_counts = admin_df.isnull().sum()
                # 미처리 건수가 1개 이상인 컬럼만 필터링
                pending_tasks = null_counts[null_counts > 0]

                if not pending_tasks.empty:
                    # 미처리 항목 수만큼 컬럼 자동 생성
                    cols = st.columns(len(pending_tasks))
                    for idx, (col_name, count) in enumerate(pending_tasks.items()):
                        with cols[idx]:
                            # 빨간색 역삼각형(delta_color="inverse")으로 경고 표시
                            st.metric(
                                label=f"🚨 {col_name} 미처리", 
                                value=f"{count}건", 
                                delta="작성 필요",
                                delta_color="inverse"
                            )
                else:
                    st.success("✅ 모든 항목이 빠짐없이 입력되었습니다! (미처리 업무 없음)")

            # 데이터프레임 표시
            st.dataframe(
                admin_df, 
                column_config=column_config_settings,
                use_container_width=True
            )
else:
    st.warning("⚠️ 선택하신 조건에 맞는 데이터가 없습니다. 필터를 변경해 보세요.")
