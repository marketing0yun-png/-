import pandas as pd
import json
import os

# Google Sheet ID
SHEET_ID = "1JBQaSh7c1nla17u2OG0Tynp-mGYD7cRVSABIzZRYdCE"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def update_secrets():
    print("Fetching data from Google Sheet...")
    try:
        df = pd.read_csv(SHEET_URL)
        
        users = {
            "admin": {"password": "123", "stores": ["All"]}
        }
        
        if len(df.columns) >= 25:
            for index, row in df.iterrows():
                # Column X (index 23) = User ID (also used as Store Name for filtering)
                # Column Y (index 24) = Password
                user_id = row.iloc[23]  # Column X - User ID
                password = row.iloc[24]  # Column Y - Password
                
                # Check for valid data
                if pd.notna(user_id) and pd.notna(password):
                    user_id = str(user_id).strip()
                    # User ID IS the Store Name to filter by
                    store = user_id
                    
                    # Handle float passwords (e.g., 123.0 -> "123")
                    password = str(password).strip()
                    if password.endswith(".0"):
                        password = password[:-2]
                    
                    if user_id in users:
                        if store not in users[user_id]["stores"]:
                            users[user_id]["stores"].append(store)
                    else:
                        users[user_id] = {"password": password, "stores": [store]}
        
        with open("secrets.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
            
        print("Successfully updated secrets.json")
        print(f"Total users: {len(users)}")
        
    except Exception as e:
        print(f"Error updating secrets: {e}")

if __name__ == "__main__":
    update_secrets()
