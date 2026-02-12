import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta
import os
import google.generativeai as genai
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
st.set_page_config(page_title="Life Update v2 🚀", layout="wide")

# PASTE YOUR GOOGLE SHEET URL HERE
SHEET_URL = "https://docs.google.com/spreadsheets/d/13fL8zmgz9jrwcNA4z97pu7HA7CE0O1SndubOap4UNIA/edit?gid=1264245434#gid=1264245434"

# Load local env vars (for laptop)
load_dotenv()

# --- GOOGLE SHEETS SETUP ---
@st.cache_resource
def get_google_sheet():
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = None

    # 1. TRY CLOUD SECRETS
    # We wrap this in a try-block so it doesn't crash on your laptop
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    except FileNotFoundError:
        pass  # No secrets.toml file — expected when running locally
    except Exception as e:
        st.warning(f"Cloud credentials found but failed to load: {e}")

    # 2. FALLBACK TO LOCAL FILE
    # If we haven't found credentials yet, look for the local JSON file
    if creds is None and os.path.exists('secrets.json'):
        creds = Credentials.from_service_account_file('secrets.json', scopes=scopes)

    if creds is None:
        st.error("Google Sheets credentials not found. Configure gcp_service_account in Streamlit secrets or provide a local secrets.json file.")
        st.stop()

    client = gspread.authorize(creds)
    return client.open_by_url(SHEET_URL)

def load_data(tab_name):
    sh = get_google_sheet()
    worksheet = sh.worksheet(tab_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_entry(tab_name, data_list):
    sh = get_google_sheet()
    worksheet = sh.worksheet(tab_name)
    worksheet.append_row(data_list)

def update_contacts_sheet(df):
    sh = get_google_sheet()
    worksheet = sh.worksheet("Contacts")
    worksheet.clear()
    worksheet.append_row(df.columns.tolist())
    worksheet.append_rows(df.values.tolist())

# --- GEMINI AI SETUP ---
api_key = None

# 1. Try Cloud
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except FileNotFoundError:
    pass  # No secrets.toml file — expected when running locally

# 2. Try Local
if api_key is None:
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("GEMINI_API_KEY not found. Set it in Streamlit Cloud secrets, a .env file, or as an environment variable.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

st.title("Life Update v2 🚀")

tab1, tab2, tab3, tab4 = st.tabs(["The Rolodex", "The Refresher", "Life Journal", "Work Updates"])

# --- TAB 1: THE ROLODEX ---
with tab1:
    header_col, upload_col = st.columns([2, 1])
    with header_col:
        st.header("My Network")
    with upload_col:
        uploaded_file = st.file_uploader("Import New Contacts (Overwrite)", type=["csv"])

    try:
        contact_data = load_data("Contacts")
    except Exception as e:
        st.warning(f"Could not load contacts: {e}")
        contact_data = pd.DataFrame()

    if uploaded_file is not None:
        new_data = pd.read_csv(uploaded_file)
        if "Category" not in new_data.columns:
            new_data["Category"] = "Uncategorized"
        update_contacts_sheet(new_data)
        st.success("Uploaded to Cloud!")
        st.rerun()

    if not contact_data.empty:
        categories = ["All Contacts"] + list(contact_data["Category"].unique())
        selected_category = st.selectbox("Filter View:", categories)
        
        if selected_category == "All Contacts":
            filtered_data = contact_data
        else:
            filtered_data = contact_data[contact_data["Category"] == selected_category]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"Showing {len(filtered_data)} contacts")
            st.dataframe(filtered_data, use_container_width=True, hide_index=True)

        with col2:
            st.write("### Actions")
            if st.button("🎲 Pick someone to call!", type="primary"):
                if not filtered_data.empty:
                    random_person = filtered_data.sample().iloc[0]
                    st.success(f"**Call: {random_person['Name']}**")
                    st.dataframe(random_person.to_frame().T, hide_index=True)
                else:
                    st.warning("No contacts found!")
    else:
        st.info("Your cloud contact list is empty. Upload a CSV to start.")


# --- TAB 2: THE REFRESHER ---
with tab2:
    st.header("The Executive Briefing")
    timeframe = st.selectbox("Look back period:", ["Last 7 Days", "Last 30 Days", "All Time"])
    col_life, col_work = st.columns(2)
    
    with col_life:
        st.subheader("🏡 Life Update")
        if st.button("Generate Life Summary", type="primary"):
            try:
                df = load_data("Life_Journal")
                if not df.empty:
                    df['Date'] = pd.to_datetime(df['Date']).dt.date
                    prompt = f"Summarize these LIFE entries: {df.tail(10).to_string()}"
                    res = model.generate_content(prompt)
                    st.markdown(res.text)
                else:
                    st.warning("No entries found.")
            except Exception as e:
                st.warning(f"Could not load Life Journal: {e}")

    with col_work:
        st.subheader("💼 Work Update")
        if st.button("Generate Work Summary", type="primary"):
            try:
                df = load_data("Work_Journal")
                if not df.empty:
                    df['Date'] = pd.to_datetime(df['Date']).dt.date
                    prompt = f"Summarize these WORK entries: {df.tail(10).to_string()}"
                    res = model.generate_content(prompt)
                    st.markdown(res.text)
                else:
                    st.warning("No entries found.")
            except Exception as e:
                st.warning(f"Could not load Work Journal: {e}")

# --- HELPER FOR JOURNALS ---
def render_cloud_journal(tab_name, sheet_tab_name):
    st.header(f"{tab_name}")
    try:
        past_entries = load_data(sheet_tab_name)
    except Exception as e:
        st.warning(f"Could not load {tab_name}: {e}")
        past_entries = pd.DataFrame()

    entry_date = st.date_input("Date", value=datetime.date.today(), key=f"d_{sheet_tab_name}")
    t1 = st.text_area("1.", height=100, key=f"t1_{sheet_tab_name}")
    t2 = st.text_area("2.", height=100, key=f"t2_{sheet_tab_name}")
    t3 = st.text_area("3.", height=100, key=f"t3_{sheet_tab_name}")
    
    if st.button("Save Entry", key=f"s_{sheet_tab_name}"):
        date_str = entry_date.strftime("%Y-%m-%d")
        save_entry(sheet_tab_name, [date_str, t1, t2, t3])
        st.success("Saved to Cloud!")
        st.rerun()

    st.divider()
    if not past_entries.empty:
        st.write("### History")
        st.dataframe(past_entries, use_container_width=True)

with tab3:
    render_cloud_journal("Life Journal", "Life_Journal")
with tab4:
    render_cloud_journal("Work Updates", "Work_Journal")