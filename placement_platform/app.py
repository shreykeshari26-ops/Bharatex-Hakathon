import streamlit as st
import sqlite3
import pandas as pd
import google.generativeai as genai
from PyPDF2 import PdfReader
import os

# --- REVISED CONFIGURATION ---
genai.configure(api_key="YOUR_GEMINI_API_KEY")

# This helper will find the right model for you
try:
    # Try the newest model first
    model = genai.GenerativeModel('gemini-3-flash')
    # Test it with a tiny call to see if it works
    model.generate_content("test") 
except:
    # Fallback to the stable version if the newest isn't on your plan yet
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# --- END REVISED CONFIGURATION ---

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('placement.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs 
                 (id INTEGER PRIMARY KEY, role TEXT, company TEXT, jd TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY, student_name TEXT, job_id INTEGER, 
                  resume_text TEXT, ai_score INTEGER, feedback TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- AI LOGIC ---
def screen_with_gemini(resume_text, job_description):
    prompt = f"""
    Act as a Technical Recruiter. Compare the Resume and Job Description (JD) below.
    Resume: {resume_text}
    JD: {job_description}
    
    Return the result in this EXACT format:
    SCORE: [0-100]
    REASON: [Short 1 sentence explanation]
    """
    response = model.generate_content(prompt)
    return response.text

# --- UI LAYOUT ---
st.set_page_config(page_title="PlaceMind AI", layout="wide")
st.title("PlaceMind AI: Smart Placement Management")

menu = ["Student: Apply", "HR: Create Drive", "TPO: Dashboard"]
choice = st.sidebar.selectbox("Navigate", menu)

# --- VIEW 1: CREATE DRIVE (HR) ---
if choice == "HR: Create Drive":
    st.header("📢 Create a New Placement Drive")
    company = st.text_input("Company Name")
    role = st.text_input("Job Role")
    jd = st.text_area("Job Description (Paste here)")
    
    if st.button("Post Drive"):
        conn = sqlite3.connect('placement.db')
        c = conn.cursor()
        c.execute("INSERT INTO jobs (role, company, jd) VALUES (?,?,?)", (role, company, jd))
        conn.commit()
        st.success(f"Drive for {company} posted successfully!")

# --- VIEW 2: STUDENT APPLY ---
elif choice == "Student: Apply":
    st.header("📝 Student Application Portal")
    conn = sqlite3.connect('placement.db')
    jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
    
    if jobs_df.empty:
        st.warning("No active drives at the moment.")
    else:
        job_options = {f"{row['company']} - {row['role']}": row['id'] for index, row in jobs_df.iterrows()}
        selected_job = st.selectbox("Select Drive", list(job_options.keys()))
        name = st.text_input("Full Name")
        uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf")
        
        if st.button("Submit Application"):
            # Extract Text from PDF
            reader = PdfReader(uploaded_file)
            resume_text = ""
            for page in reader.pages:
                resume_text += page.extract_text()
            
            # Get Job Description
            target_id = job_options[selected_job]
            jd_text = jobs_df[jobs_df['id'] == target_id]['jd'].values[0]
            
            # AI Screening (The "Magic" Step)
            with st.spinner('AI is screening your resume...'):
                result = screen_with_gemini(resume_text, jd_text)
                # Parse Score (Simple extraction)
                score = 0
                try: score = int([line for line in result.split('\n') if "SCORE" in line][0].split(":")[1].strip())
                except: score = 50 # Fallback
                
            # Save to DB
            c = conn.cursor()
            c.execute("INSERT INTO applications (student_name, job_id, resume_text, ai_score, feedback) VALUES (?,?,?,?,?)",
                      (name, target_id, resume_text, score, result))
            conn.commit()
            st.balloons()
            st.success("Applied Successfully! AI Score: " + str(score))

# --- VIEW 3: TPO DASHBOARD ---
elif choice == "TPO: Dashboard":
    st.header("📊 Placement Control Center")
    conn = sqlite3.connect('placement.db')
    query = """
    SELECT a.student_name, j.company, j.role, a.ai_score, a.feedback 
    FROM applications a 
    JOIN jobs j ON a.job_id = j.id
    ORDER BY a.ai_score DESC
    """
    apps_df = pd.read_sql_query(query, conn)
    
    if apps_df.empty:
        st.info("No applications received yet.")
    else:
        st.write("### All Applications (AI Ranked)")
        st.dataframe(apps_df, use_container_width=True)
        
        # Visualization
        st.bar_chart(apps_df.set_index('student_name')['ai_score'])