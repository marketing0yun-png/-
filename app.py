import streamlit as st
import pandas as pd
import json

# Page configuration
st.set_page_config(page_title="체험단 관리현황", layout="wide")

# Title
st.title("체험단 관리현황")

# Google Sheet ID
SHEET_ID = "1JBQaSh7c1nla17u2OG0Tynp-mGYD7cRVSABIzZRYdCE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] in st.session_state["secrets"] and \
           st.session_state["password"] == st.session_state["secrets"][st.session_state["username"]]["password"]:
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = st.session_state["username"] # Persist username
            st.session_state["user_info"] = st.session_state["secrets"][st.session_state["username"]]
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for username + password.
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 User not known or password incorrect")
        return False
    else:
        # Password correct.
        return True

# Load data first to get stores for the mock user
df = load_data(SHEET_URL)

if df is not None:
    # Secrets / User DB
    if "secrets" not in st.session_state:
        try:
            with open("secrets.json", "r", encoding="utf-8") as f:
                users = json.load(f)
        except FileNotFoundError:
            # Fallback if file doesn't exist
            users = {
                "admin": {"password": "123", "stores": ["All"]}
            }
            st.warning("secrets.json not found. Only admin login available. Run update_secrets.py to fetch users.")
            
        st.session_state["secrets"] = users

    if check_password():
        # User is logged in
        user_info = st.session_state["user_info"]
        allowed_stores = user_info["stores"]
        
        # Sidebar
        with st.sidebar:
            # Use current_user instead of username to avoid KeyError
            current_user = st.session_state.get("current_user", "Unknown")
            st.success(f"Logged in as {current_user}")
            if st.button("Logout"):
                st.session_state["password_correct"] = False
                del st.session_state["password_correct"]  # This will trigger a rerun and show login
                if "current_user" in st.session_state:
                    del st.session_state["current_user"]
                st.rerun()
            
            st.divider()
            if st.button("Refresh Data"):
                load_data.clear()
                st.rerun()
        
        # Filter Sidebar (Column D -> Index 3)
        st.sidebar.header("Filter")
        
        if len(df.columns) >= 9: # Need at least up to Column I (Index 8)
            # Parse Column I (Index 8) as datetime with custom parser
            date_col_name = df.columns[8]
            
            def parse_date(val):
                """Handle multiple date formats: '2025. 9. 7', '10/2', '12/13', etc."""
                if pd.isna(val):
                    return pd.NaT
                val_str = str(val).strip()
                # Try standard parsing first
                parsed = pd.to_datetime(val_str, errors='coerce')
                if pd.notna(parsed):
                    return parsed
                # Try adding year for short format like '10/2' or '12/13'
                try:
                    parsed = pd.to_datetime(f"2025/{val_str}", format="%Y/%m/%d", errors='coerce')
                    if pd.notna(parsed):
                        return parsed
                except:
                    pass
                return pd.NaT
            
            df[date_col_name] = df.iloc[:, 8].apply(parse_date)
            
            # Filter out rows where Column I (Index 8) is empty/NaN
            df = df[df[date_col_name].notna()]
            
            # Convert datetime to date-only string for display (remove 00:00:00)
            df[date_col_name] = df[date_col_name].dt.strftime('%Y-%m-%d')
            
            # Store filter
            filter_col_name = df.columns[3] # Column D
            unique_values = df[filter_col_name].unique()
            
            # Determine options based on access
            if "All" in allowed_stores:
                options = ["All"] + list(unique_values)
                index = 0
            else:
                # Only show allowed stores that exist in the data
                options = [s for s in allowed_stores if s in unique_values]
                # If the user has access to stores not currently in data, we might want to handle that, 
                # but for now let's just show what's available.
                if not options:
                     options = ["No Data Access"]
                index = 0

            selected_value = st.sidebar.selectbox(f"Select {filter_col_name}", options, index=index, key=f"store_selector_{current_user}")
            
            if selected_value == "All":
                df_filtered = df.copy()
            elif selected_value == "No Data Access":
                df_filtered = pd.DataFrame(columns=df.columns) # Empty
            else:
                df_filtered = df[df[filter_col_name] == selected_value].copy()
            
            # Date Range Filter
            st.sidebar.subheader("기간 설정")
            if not df_filtered.empty:
                # Parse string dates to date for range picker
                df_filtered_dates = pd.to_datetime(df_filtered[date_col_name])
                min_date = df_filtered_dates.min().date()
                max_date = df_filtered_dates.max().date()
                
                date_range = st.sidebar.date_input(
                    "날짜 범위 선택",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key=f"date_range_{current_user}"
                )
                
                # Filter by date range (handle case where user selects only start date)
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    df_filtered = df_filtered[
                        (pd.to_datetime(df_filtered[date_col_name]).dt.date >= start_date) & 
                        (pd.to_datetime(df_filtered[date_col_name]).dt.date <= end_date)
                    ]
                
                # Sort by date descending (newest first) - string sort works for YYYY-MM-DD
                df_filtered = df_filtered.sort_values(by=date_col_name, ascending=False)
            
            # Reset Index to start from 1 sequentially
            df_filtered.reset_index(drop=True, inplace=True)
            df_filtered.index = df_filtered.index + 1
            
        else:
            st.warning("Data does not have enough columns for filtering.")
            df_filtered = df

        # Tabs
        tab1, tab2, tab3 = st.tabs(["일정현황", "방문결과", "관리현황"])

        with tab1:
            st.subheader("일정현황")
            # I, J, C, K, E, F, G -> Indices: 8, 9, 2, 10, 4, 5, 6
            target_indices_1 = [8, 9, 2, 10, 4, 5, 6]
            if len(df.columns) > max(target_indices_1):
                st.dataframe(df_filtered.iloc[:, target_indices_1])
            else:
                st.error("Not enough columns for View 1")

        with tab2:
            st.subheader("방문결과")
            # I, O, K, R, P, Q -> Indices: 8, 14, 10, 17, 15, 16
            target_indices_2 = [8, 14, 10, 17, 15, 16]
            if len(df.columns) > max(target_indices_2):
                st.dataframe(df_filtered.iloc[:, target_indices_2])
            else:
                st.error("Not enough columns for View 2")

        with tab3:
            st.subheader("관리현황")
            # I, J, K, L, M, N, O, P, Q, R -> Indices: 8, 9, 10, 11, 12, 13, 14, 15, 16, 17
            target_indices_3 = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
            if len(df.columns) > max(target_indices_3):
                st.dataframe(df_filtered.iloc[:, target_indices_3])
            else:
                st.error("Not enough columns for View 3")

else:
    st.info("Please check if the Google Sheet is published to the web or accessible via link.")
