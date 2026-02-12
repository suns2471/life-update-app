import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta
import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("GEMINI_API_KEY not found. Set it in a .env file or as an environment variable.")
    st.stop()
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

st.set_page_config(page_title="Life Update", layout="wide")
st.title("Life Update")

# NOW 4 TABS
tab1, tab2, tab3, tab4 = st.tabs(["The Rolodex", "The Refresher", "Life Journal", "Work Updates"])

# --- HELPER FUNCTION: The Journal Logic ---
# We define this ONCE, and then use it for both Life and Work tabs.
# This saves us from having 200 lines of duplicate code.
def render_journal_tab(tab_name, filename, prompt_context):
    st.header(f"{tab_name}")

    # 1. Missing Entry Warning
    today = datetime.date.today()
    if os.path.exists(filename):
        df_check = pd.read_csv(filename)
        df_check['Date'] = pd.to_datetime(df_check['Date']).dt.date
        existing_dates = df_check['Date'].tolist()
        
        missing_dates = []
        for i in range(1, 8):
            check_date = today - timedelta(days=i)
            if check_date not in existing_dates:
                missing_dates.append(check_date.strftime("%b %d"))
        
        if missing_dates:
            st.warning(f"⚠️ You missed {tab_name} entries on: {', '.join(missing_dates)}")

    # 2. Inspire Me (Unique to each tab)
    session_key = f"inspire_{filename}" # Unique pocket for this tab
    if session_key not in st.session_state:
        st.session_state[session_key] = ""

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("✨ Inspire Me", key=f"btn_{filename}"):
            with st.spinner("Thinking..."):
                try:
                    # tailored prompt based on whether it's work or life
                    prompt = f"Give me 3 short, punchy questions to help me reflect on my {prompt_context}. Just the questions."
                    response = model.generate_content(prompt)
                    st.session_state[session_key] = response.text
                except Exception as e:
                    st.error(f"Could not generate inspiration: {e}")
    
    with col2:
        if st.session_state[session_key]:
            st.info(st.session_state[session_key])

    st.divider()

    # 3. Input Form
    entry_date = st.date_input("Date of Entry", value=datetime.date.today(), key=f"date_{filename}")
    
    default_1 = ""
    default_2 = ""
    default_3 = ""
    
    if os.path.exists(filename):
        df = pd.read_csv(filename)
        df['Date'] = pd.to_datetime(df['Date']).dt.date
        mask = df['Date'] == entry_date
        if mask.any():
            existing_row = df[mask].iloc[0]
            default_1 = existing_row['Entry 1']
            default_2 = existing_row['Entry 2']
            default_3 = existing_row['Entry 3']
            st.caption(f"Editing entry for {entry_date}")

    # CHANGED: st.text_area for bigger boxes!
    thing_1 = st.text_area("1.", value=default_1, height=100, key=f"t1_{filename}_{entry_date}")
    thing_2 = st.text_area("2.", value=default_2, height=100, key=f"t2_{filename}_{entry_date}")
    thing_3 = st.text_area("3.", value=default_3, height=100, key=f"t3_{filename}_{entry_date}")
    
    if st.button("Save Entry", key=f"save_{filename}"):
        if thing_1 or thing_2 or thing_3: # Allow saving even if only 1 box is filled
            new_entry = pd.DataFrame({
                "Date": [entry_date],
                "Entry 1": [thing_1],
                "Entry 2": [thing_2],
                "Entry 3": [thing_3]
            })
            
            if os.path.exists(filename):
                df = pd.read_csv(filename)
                df['Date'] = pd.to_datetime(df['Date']).dt.date
                df = df[df['Date'] != entry_date]
                updated_df = pd.concat([df, new_entry], ignore_index=True)
                updated_df.to_csv(filename, index=False)
            else:
                new_entry.to_csv(filename, index=False)
                
            st.success("Saved!")
            st.rerun()
            
    st.divider()
    
    if os.path.exists(filename):
        st.write("### Past Entries")
        past_entries = pd.read_csv(filename)
        past_entries['Date'] = pd.to_datetime(past_entries['Date'])
        past_entries = past_entries.sort_values(by='Date', ascending=False)
        st.dataframe(past_entries, use_container_width=True)


# --- TAB 1: THE ROLODEX ---
with tab1:
    header_col, upload_col = st.columns([2, 1])
    with upload_col:
        uploaded_file = st.file_uploader("Import Contacts (CSV)", type=["csv"])
    with header_col:
        st.header("My Network")

    if uploaded_file is not None:
        if os.path.exists("master_contacts.csv"):
            contact_data = pd.read_csv("master_contacts.csv")
        else:
            contact_data = pd.read_csv(uploaded_file)
        
        if "Category" not in contact_data.columns:
            contact_data["Category"] = "Uncategorized"
        
        categories = ["All Contacts"] + list(contact_data["Category"].unique())
        if "Uncategorized" not in categories: categories.append("Uncategorized")
            
        selected_category = st.selectbox("Filter View:", categories)
        
        if selected_category == "All Contacts":
            filtered_data = contact_data
        else:
            filtered_data = contact_data[contact_data["Category"] == selected_category]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"Showing {len(filtered_data)} contacts")
            edited_data = st.data_editor(
                filtered_data,
                column_config={
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        width="medium",
                        options=["Close Friends", "Work", "Network / Acquaintances", "Family", "Uncategorized"],
                        required=True,
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="contact_editor"
            )

        with col2:
            st.write("### Actions")
            if st.button("💾 Save Changes"):
                contact_data.update(edited_data)
                contact_data.to_csv("master_contacts.csv", index=False)
                st.success("Saved!")
                st.rerun()

            st.divider()
            if st.button("🎲 Pick someone to call!", type="primary"):
                if not filtered_data.empty:
                    random_person = filtered_data.sample().iloc[0]
                    st.success(f"**Call: {random_person['Name']}**")
                    st.dataframe(random_person.to_frame().T, hide_index=True)
                else:
                    st.warning("No contacts found!")
    else:
        st.info("👆 Upload your contact list to get started.")


# --- TAB 2: THE REFRESHER (SPLIT BRAIN) ---
with tab2:
    st.header("The Executive Briefing")
    
    timeframe = st.selectbox("Look back period:", ["Last 7 Days", "Last 30 Days", "All Time"])
    
    # Create two big columns for the two different generators
    col_life, col_work = st.columns(2)
    
    # --- LIFE GENERATOR ---
    with col_life:
        st.subheader("🏡 Life Update")
        if st.button("Generate Life Summary", type="primary"):
            if os.path.exists("life_journal.csv"):
                journal_data = pd.read_csv("life_journal.csv")
                journal_data['Date'] = pd.to_datetime(journal_data['Date']).dt.date
                today = datetime.date.today()
                
                if timeframe == "Last 7 Days":
                    cutoff = today - timedelta(days=7)
                    journal_data = journal_data[journal_data['Date'] >= cutoff]
                elif timeframe == "Last 30 Days":
                    cutoff = today - timedelta(days=30)
                    journal_data = journal_data[journal_data['Date'] >= cutoff]
                
                if not journal_data.empty:
                    prompt = f"""
                    Here are my PERSONAL life journal entries ({timeframe}):
                    {journal_data.to_string()}
                    
                    Summarize my recent personal life. Focus on fun, relationships, health, and memorable moments.
                    """
                    with st.spinner("Analyzing life..."):
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                else:
                    st.warning("No recent life entries found.")
            else:
                st.warning("No life journal found.")

    # --- WORK GENERATOR ---
    with col_work:
        st.subheader("💼 Work Update")
        if st.button("Generate Work Summary", type="primary"):
            if os.path.exists("work_journal.csv"):
                journal_data = pd.read_csv("work_journal.csv")
                journal_data['Date'] = pd.to_datetime(journal_data['Date']).dt.date
                today = datetime.date.today()
                
                if timeframe == "Last 7 Days":
                    cutoff = today - timedelta(days=7)
                    journal_data = journal_data[journal_data['Date'] >= cutoff]
                elif timeframe == "Last 30 Days":
                    cutoff = today - timedelta(days=30)
                    journal_data = journal_data[journal_data['Date'] >= cutoff]
                
                if not journal_data.empty:
                    prompt = f"""
                    Here are my WORK journal entries ({timeframe}):
                    {journal_data.to_string()}
                    
                    Summarize my recent professional progress. Focus on deals, project milestones, and key decisions.
                    """
                    with st.spinner("Analyzing work..."):
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                else:
                    st.warning("No recent work entries found.")
            else:
                st.warning("No work journal found.")


# --- TABS 3 & 4: THE JOURNALS ---
# Here is where we use that helper function we wrote at the top!
with tab3:
    render_journal_tab("Life Journal", "life_journal.csv", "personal life")

with tab4:
    render_journal_tab("Work Updates", "work_journal.csv", "professional career")