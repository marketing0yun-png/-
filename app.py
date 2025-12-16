import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

# -------------------------
# 1. 페이지 기본 설정
# -------------------------
st.set_page_config(
    page_title="체험단 관리 대시보드", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="auto"
)

# [수정] 한국 시간(KST) 설정 (UTC+9)
KST = timezone(timedelta(hours=9))

# 제목
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
                    st.session_state["secrets"].get("stores", {},).get(username, [])
                if "password" in st.session_state: del st.session_state["password"]
                return
        st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

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
# DATA PRE-PROCESSING & FILTERING
# -------------------------

if len(df.columns) >= 17:
    # 1. 날짜 컬럼 (I열, Index 8) 파싱 - *NaN 제거하지 않고 살려둠*
    date_col_name = df.columns[8]

    def parse_date(val):
        if pd.isna(val): return pd.NaT
        val = str(val).strip()
        parsed = pd.to_datetime(val, errors="coerce")
        if pd.notna(parsed): return parsed
        try:
            # [수정] 현재 연도 계산 시 KST 기준 적용
            current_year = datetime.now(KST).year
            parsed = pd.to_datetime(f"{current_year}/" + val, format="%Y/%m/%d", errors="coerce")
            return parsed
        except:
            return pd.NaT

    df["parsed_date"] = df.iloc[:, 8].apply(parse_date)
    df[date_col_name] = df["parsed_date"].dt.strftime("%Y-%m-%d")

    # 2. [요청반영] A열 (Index 0) 날짜 형식 변환 (시간 제거, YYYY-MM-DD)
    col_a_name = df.columns[0]
    df[col_a_name] = pd.to_datetime(df.iloc[:, 0], errors="coerce").dt.strftime("%Y-%m-%d")

    # 3. 매장 필터 (D열, Index 3)
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

    # 매장 필터 적용 (여기서 df_store 생성)
    if selected_store == "All":
        df_store = df.copy()
    elif selected_store == "접근 권한 없음":
        df_store = pd.DataFrame(columns=df.columns)
    else:
        df_store = df[df[filter_col_name] == selected_store].copy()

    # 4. 날짜 범위 필터 (I열 기준)
    df_valid_dates = df_store[df_store["parsed_date"].notna()]
    
    start_date, end_date = None, None
    
    if not df_valid_dates.empty:
        df_dates = df_valid_dates["parsed_date"]
        min_date, max_date = df_dates.min().date(), df_dates.max().date()
        
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
    
    # [데이터 분기점]
    # df_main: 날짜 필터가 적용된 데이터 (기존 탭 1, 2, 3용)
    if start_date and end_date:
        df_main = df_valid_dates[
            (df_valid_dates["parsed_date"].dt.date >= start_date) &
            (df_valid_dates["parsed_date"].dt.date <= end_date)
        ]
    else:
        df_main = df_valid_dates # 날짜 범위 선택 전이면 유효한 날짜 전체

    # 정렬 및 인덱스 리셋 (Main 데이터)
    df_main = df_main.sort_values(by="parsed_date", ascending=False)
    df_main.reset_index(drop=True, inplace=True)
    df_main.index = df_main.index + 1

    # df_store: 날짜 필터 적용 안 된 전체 데이터 (신규 탭 4용 - I열 없어도 나옴)
    # 접수일(A열) 기준으로 정렬
    df_store = df_store.sort_values(by=col_a_name, ascending=False)
    df_store.reset_index(drop=True, inplace=True)
    df_store.index = df_store.index + 1

else:
    st.error("데이터 컬럼 부족")
    df_main = pd.DataFrame()
    df_store = pd.DataFrame()


# -------------------------
# DASHBOARD METRICS (Main 기준)
# -------------------------
if not df_main.empty:
    st.markdown("### 📈 현황 요약")

    # 1. 오늘 데이터 필터링 (KST 기준 날짜 사용)
    today_date_kst = datetime.now(KST).date()
    today_df = df_main[df_main["parsed_date"].dt.date == today_date_kst]
    
    # [요청사항 수정] 오늘 일정을 최상단에, 펼쳐진 상태(expander X)로 배치 + 날짜 표시
    if not today_df.empty:
        # 날짜 포맷팅 (YYYY.MM.DD)
        today_str = today_date_kst.strftime("%Y.%m.%d")
        
        st.markdown(f"**📋 오늘 방문 일정 ({len(today_df)}건) | 기준일자: {today_str}**")
        
        # 순서 변경: 시간(J/9) -> 이름(C/2) -> 참여유형(E/4) -> 선택키워드(K/10)
        today_details_indices = [9, 2, 4, 10]
        today_display_df = today_df.iloc[:, today_details_indices]

        # 컬럼 설정 (이름 변경 및 너비 조정)
        today_column_config = {
            df.columns[9]: st.column_config.TextColumn("방문시간", width="small"),
            df.columns[2]: st.column_config.TextColumn("이름", width="medium"),
            df.columns[4]: st.column_config.TextColumn("참여유형", width="medium"),
            df.columns[10]: st.column_config.TextColumn("선택키워드", width="large"),
        }
        
        st.dataframe(
            today_display_df,
            column_config=today_column_config,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(f"📌 {today_date_kst.strftime('%Y-%m-%d')} 기준, 예정된 방문 일정이 없습니다.")
    
    # 2. 통계 지표 (표 아래로 배치)
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    
    total_count = len(df_main)
    today_count = len(today_df)
    
    with m1:
        st.metric(label="전체 조회 건수", value=f"{total_count}건")
    with m2:
        # [수정] 기준 시간 표시도 KST로
        st.metric(label="오늘 일정", value=f"{today_count}건", delta=f"기준: {datetime.now(KST).strftime('%m-%d')}")
    with m3:
        st.metric(label="선택된 매장", value=selected_store)

    st.markdown("---")

# -------------------------
# TABS & DISPLAY
# -------------------------

link_target_indices = [5, 14, 15, 16]
column_config_settings = {}

# 링크 설정은 전체 컬럼 기준으로
for idx in link_target_indices:
    if len(df.columns) > idx:
        col_name = df.columns[idx]
        column_config_settings[col_name] = st.column_config.LinkColumn(
            label=col_name,
            display_text="🔗 바로가기"
        )

# [권한 체크 및 탭 설정]
if current_user == "admin":
    # 접수현황 탭 추가
    tab_list = ["📅 일정현황", "📝 방문결과", "📊 관리현황", "📥 접수현황"]
else:
    tab_list = ["📅 일정현황", "📝 방문결과"]

tabs = st.tabs(tab_list)

# --- 1. 일정현황 (df_main 사용) ---
if len(tabs) > 0:
    with tabs[0]:
        st.subheader("📅 일정 리스트")
        if not df_main.empty:
            target_indices = [8, 9, 2, 10, 4, 5, 6] 
            st.dataframe(
                df_main.iloc[:, target_indices], 
                column_config=column_config_settings,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("조회된 일정이 없습니다.")

# --- 2. 방문결과 (df_main 사용) ---
if len(tabs) > 1:
    with tabs[1]:
        st.subheader("📝 결과 리포트")
        if not df_main.empty:
            # 방문결과 탭: 날짜(I/8), 이름(C/2), SNS포스팅(O/14), 선택키워드(K/10), 노출키워드(R/17), 맘카페(P/15), 기타(Q/16)
            target_indices = [8, 2, 14, 10, 17, 15, 16]
            st.dataframe(
                df_main.iloc[:, target_indices], 
                column_config=column_config_settings,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("조회된 결과가 없습니다.")

if current_user == "admin":
    # --- 3. 관리현황 (df_main 사용) ---
    with tabs[2]:
        header_col, metric_col = st.columns([1, 4]) 
        with header_col:
            st.subheader("📊 상세 관리")
        
        if not df_main.empty:
            # 관리현황: I(8) / J(9) / C(2) / K(10) / L(11) / M(12) / N(13) / O(14) / R(17) / P(15) / Q(16)
            target_indices = [8, 9, 2, 10, 11, 12, 13, 14, 17, 15, 16]
            admin_df = df_main.iloc[:, target_indices]

            with metric_col:
                null_counts = admin_df.isnull().sum()
                pending_tasks = null_counts[null_counts > 0]

                if not pending_tasks.empty:
                    cols = st.columns(len(pending_tasks))
                    for idx, (col_name, count) in enumerate(pending_tasks.items()):
                        with cols[idx]:
                            st.metric(
                                label=f"🚨 {col_name} 미처리", 
                                value=f"{count}건", 
                                delta="작성 필요",
                                delta_color="inverse"
                            )
                else:
                    st.success("✅ 모든 항목이 입력되었습니다!")

            st.dataframe(
                admin_df, 
                column_config=column_config_settings,
                use_container_width=True,
                hide_index=True
            )
        else:
             st.info("조회된 데이터가 없습니다.")

    # --- 4. 접수현황 (df_store 사용: 날짜 필터 무시) ---
    with tabs[3]:
        # 레이아웃: 제목 + 요약 지표
        header_col, metric_col = st.columns([1, 4])
        with header_col:
            st.subheader("📥 접수 현황")
        
        col_h_name = df.columns[7] # H열 (선정여부/안내 등)
        
        # 카운팅 로직
        pending_advice_count = len(df_store[
            (df_store[col_h_name] == "안내") & 
            (df_store["parsed_date"].isna())
        ])
        
        with metric_col:
            if pending_advice_count > 0:
                st.metric(
                    label="📌 미확정 접수 건 (안내+날짜미정)",
                    value=f"{pending_advice_count}건",
                    delta="일정 확정 필요",
                    delta_color="inverse"
                )
            else:
                st.success("✅ 미확정된 접수 건이 없습니다.")

        # 표 필터링: '선정여부'(H열)가 '안내'인 것만 표시
        if not df_store.empty:
            df_reception = df_store[df_store[col_h_name] == "안내"].copy()
            
            target_indices_4 = [0, 2, 3, 4, 5, 6, 7, 8]
            
            if not df_reception.empty:
                st.dataframe(
                    df_reception.iloc[:, target_indices_4],
                    column_config=column_config_settings,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("표시할 '안내' 상태의 데이터가 없습니다.")
        else:
            st.info("접수된 데이터가 없습니다.")
