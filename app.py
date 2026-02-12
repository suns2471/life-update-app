import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta
import os
import google.generativeai as genai
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
st.set_page_config(page_title="Life Update v3 ✨", layout="wide", page_icon="🚀")

# PASTE YOUR GOOGLE SHEET URL HERE
SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_LONG_ID_HERE/edit"

# --- CUSTOM CSS FOR "APP-LIKE" FEEL ---
st.markdown("""
<style>
    /* Hide default menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Card Style */
    .st-emotion-cache-1r6slb0 {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Button Polish */
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        font-weight: bold;
    }
    
    /* Metrics/Stats */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
    }
</style>
""", unsafe_allow_html=True)

# Load local env vars (for laptop)
load_dotenv()

# --- GOOGLE SHEETS SETUP ---
@st.cache_resource
def get_google_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = None
    
    # 1. TRY CLOUD SECRETS
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except:
        pass

    # 2. FALLBACK TO LOCAL FILE
    if creds is None:
        creds = ServiceAccountCredentials.from_json_keyfile_name('secrets.json', scope)
        
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
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except:
    pass
if api_key is None:
    api_key = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

st.title("Life Update v3 ✨")

tab1, tab2, tab3, tab4 = st.tabs(["📇 Rolodex", "🧠 Refresher", "🏡 Life", "💼 Work"])

# --- TAB 1: THE ROLODEX (CARD VIEW) ---
with tab1:
    col1, col2 = st.columns([3, 1])
    with col2:
        with st.expander("Import Contacts"):
            uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
            if uploaded_file:
                new_data = pd.read_csv(uploaded_file)
                if "Category" not in new_data.columns:
                    new_data["Category"] = "Uncategorized"
                update_contacts_sheet(new_data)
                st.success("Uploaded!")
                st.rerun()

    try:
        contact_data = load_data("Contacts")
    except:
        contact_data = pd.DataFrame()

    if not contact_data.empty:
        # Filter Logic
        categories = ["All Contacts"] + list(contact_data["Category"].unique())
        selected_category = col1.selectbox("Filter:", categories)
        
        if selected_category == "All Contacts":
            filtered_data = contact_data
        else:
            filtered_data = contact_data[contact_data["Category"] == selected_category]
        
        # METRICS
        m1, m2, m3 = st.columns(3)
        m1.metric("Total", len(contact_data))
        m2.metric("In View", len(filtered_data))
        if st.button("🎲 Random Call", type="primary"):
             if not filtered_data.empty:
                random_person = filtered_data.sample().iloc[0]
                st.balloons()
                st.success(f"**Call: {random_person['Name']}**")
                # Show full details
                st.json(random_person.to_dict())
        
        st.divider()
        
        # CARD GRID VIEW (Instead of Dataframe)
        st.write(f"### {selected_category}")
        
        # Create a grid of cards
        for index, row in filtered_data.iterrows():
            with st.container():
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.write("👤") # Avatar placeholder
                with c2:
                    st.write(f"**{row['Name']}**")
                    st.caption(f"{row['Category']}")
                    # If you have a 'Phone' column, display it
                    if 'Phone' in row:
                        st.write(f"📞 {row['Phone']}")
                st.divider()

    else:
        st.info("Upload a CSV to start.")


# --- TAB 2: THE REFRESHER ---
with tab2:
    st.header("Executive Briefing")
    timeframe = st.selectbox("Period:", ["Last 7 Days", "Last 30 Days"])
    
    if st.button("Generate Briefing", type="primary"):
        with st.spinner("Analyzing databases..."):
            try:
                # Load both journals
                life_df = load_data("Life_Journal")
                work_df = load_data("Work_Journal")
                
                # Convert dates
                today = datetime.date.today()
                cutoff = today - timedelta(days=7 if timeframe == "Last 7 Days" else 30)
                
                # Filter
                life_df['Date'] = pd.to_datetime(life_df['Date']).dt.date
                work_df['Date'] = pd.to_datetime(work_df['Date']).dt.date
                
                recent_life = life_df[life_df['Date'] >= cutoff]
                recent_work = work_df[work_df['Date'] >= cutoff]
                
                prompt = f"""
                Act as my Chief of Staff. Here is my recent data:
                
                LIFE DATA:
                {recent_life.to_string()}
                
                WORK DATA:
                {recent_work.to_string()}
                
                Give me a combined "State of the Union" briefing. 
                Start with "High Level" (Work & Life combined), then specific action items or patterns you notice.
                """
                res = model.generate_content(prompt)
                st.markdown(res.text)
            except Exception as e:
                st.error(f"Error: {e}")

# --- HELPER FOR JOURNALS ---
def render_journal(tab_name, sheet_tab):
    st.header(tab_name)
    with st.form(f"form_{sheet_tab}"):
        date = st.date_input("Date", value=datetime.date.today())
        t1 = st.text_area("Update 1", height=80)
        t2 = st.text_area("Update 2", height=80)
        t3 = st.text_area("Update 3", height=80)
        submitted = st.form_submit_button("Save Entry")
        
        if submitted:
            save_entry(sheet_tab, [str(date), t1, t2, t3])
            st.success("Saved!")
            st.rerun()

with tab3:
    render_journal("Life Journal", "Life_Journal")
with tab4:
    render_journal("Work Updates", "Work_Journal")