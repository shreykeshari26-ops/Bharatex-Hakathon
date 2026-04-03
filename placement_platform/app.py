import streamlit as st
import sqlite3
import pandas as pd
import random
from google import genai
from PyPDF2 import PdfReader

# --- 1. CONFIGURATION ---
# Replace with your actual Gemini API Key from Google AI Studio
GEMINI_API_KEY = "AIzaSyBQMT4d3cbSSq-6cR-vmStMGzDA7A4vBx4" 
client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('placement.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs 
                 (id INTEGER PRIMARY KEY, role TEXT, company TEXT, jd TEXT)''')
    # ADDED 'status' COLUMN HERE
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY, student_name TEXT, job_id INTEGER, 
                  resume_text TEXT, ai_score INTEGER, feedback TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. AI CORE LOGIC (Rate-Limit Proof) ---
def screen_with_gemini(resume_text, job_description):
    prompt = f"Compare Resume: {resume_text} with JD: {job_description}. Return SCORE: [0-100] and REASON: [1 sentence]."
    
    try:
        # Using 1.5-flash: Most stable for free-tier keys
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=prompt
        )
        return response.text
    except Exception as e:
        # Fallback: If API hits a limit, generate a mock result so the app keeps running
        st.warning("⚠️ API Rate Limit hit. Using 'Mock AI' for this demo.")
        mock_score = random.randint(70, 92)
        return f"SCORE: {mock_score}\nREASON: [SIMULATED] Candidate shows strong technical alignment with job requirements."

# --- 4. UI LAYOUT ---
st.set_page_config(page_title="PlaceMind AI", layout="wide")

# Stylish Sidebar
st.sidebar.markdown("""
    <div style="background-color:#FF4B4B;padding:15px;border-radius:10px;margin-bottom:20px">
    <h2 style="color:white;text-align:center;margin:0;">BHARAT-TECH X</h2>
    <p style="color:white;text-align:center;font-size:12px;">Placement Management 3.0</p>
    </div>
""", unsafe_allow_html=True)

menu = ["Student: Apply & Track", "HR: Create Drive", "TPO: Dashboard"]
choice = st.sidebar.selectbox("Navigate System", menu)

# --- HR VIEW ---
if choice == "HR: Create Drive":
    st.header("📢 Create a New Placement Drive")
    company = st.text_input("Company Name")
    role = st.text_input("Job Role")
    jd = st.text_area("Job Description")
    if st.button("Post Drive", type="primary"):
        if company and role and jd:
            conn = sqlite3.connect('placement.db')
            c = conn.cursor()
            c.execute("INSERT INTO jobs (role, company, jd) VALUES (?,?,?)", (role, company, jd))
            conn.commit()
            st.success(f"Drive for {company} Posted!")
        else:
            st.error("Please fill all fields.")

# --- STUDENT VIEW ---
elif choice == "Student: Apply & Track":
    st.header("📝 Student Portal")
    tab1, tab2 = st.tabs(["Apply Now", "Track My Status"])
    
    with tab1:
        conn = sqlite3.connect('placement.db')
        jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
        
        if not jobs_df.empty:
            job_options = {f"{row['company']} - {row['role']}": row['id'] for i, row in jobs_df.iterrows()}
            selected_job = st.selectbox("Select Drive", list(job_options.keys()))
            name = st.text_input("Your Full Name")
            file = st.file_uploader("Upload Resume (PDF)", type="pdf")
            
            if st.button("Submit Application", type="primary"):
                if file and name:
                    reader = PdfReader(file)
                    text = "".join([p.extract_text() for p in reader.pages])
                    target_jd = jobs_df[jobs_df['id'] == job_options[selected_job]]['jd'].values[0]
                    
                    with st.spinner('AI analyzing your profile...'):
                        result = screen_with_gemini(text, target_jd)
                        # Extract the score number safely
                        try:
                            score = int(''.join(filter(str.isdigit, result.split('\n')[0])))
                        except:
                            score = 50
                            
                        c = conn.cursor()
                        c.execute("INSERT INTO applications (student_name, job_id, resume_text, ai_score, feedback) VALUES (?,?,?,?,?)",
                                  (name, job_options[selected_job], text, score, result))
                        conn.commit()
                        st.balloons()
                        st.success(f"Application submitted! AI Score: {score}/100")
                else:
                    st.error("Upload resume and enter your name.")
        else:
            st.warning("No active drives yet.")

    with tab2:
        st.subheader("🔍 Your Application Journey")
        search = st.text_input("Enter your name to track")
        if search:
            conn = sqlite3.connect('placement.db')
            query = f"""
                SELECT a.ai_score, a.feedback, j.company, j.role, a.status 
                FROM applications a 
                JOIN jobs j ON a.job_id = j.id 
                WHERE a.student_name LIKE '%{search}%'
            """
            res = pd.read_sql_query(query, conn)
            if not res.empty:
                for i, row in res.iterrows():
                    with st.expander(f"📌 {row['company']} - {row['role']}", expanded=True):
                        # Journey Progress Bar
                        stages = ["Applied", "Screened", "Shortlisted", "Interview", "Offered"]
                        current_status = row['status'] if row['status'] else "Applied"
                        current_idx = stages.index(current_status) if current_status in stages else 0
                        
                        # Visual Progress
                        st.write(f"**Current Stage:** `{current_status}`")
                        st.progress((current_idx + 1) / len(stages))
                        
                        # Status-specific Tips
                        if current_status == "Applied":
                            st.info("Your resume is in the queue for AI Screening.")
                        elif current_status == "Screened":
                            st.success(f"AI Score: {row['ai_score']}/100. The TPO is reviewing your profile.")
                        
                        st.write(f"**AI Insights:** {row['feedback']}")
            else:
                st.info("No application found.")

# --- TPO VIEW ---
elif choice == "TPO: Dashboard":
    st.header("📊 Admin Dashboard (TPO)")
    conn = sqlite3.connect('placement.db')
    query = """
        SELECT a.id, a.student_name, j.company, j.role, a.ai_score, a.status 
        FROM applications a 
        JOIN jobs j ON a.job_id = j.id 
        ORDER BY a.ai_score DESC
    """
    apps = pd.read_sql_query(query, conn)
    
    if not apps.empty:
        st.dataframe(apps, use_container_width=True)
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🛠️ Management")
            selected_id = st.selectbox("Select Student ID to Update", apps['id'].tolist())
            new_status = st.selectbox("Update Status", ["Applied", "Screened", "Shortlisted", "Interview", "Offered"])
            if st.button("Update Status"):
                c = conn.cursor()
                c.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, selected_id))
                conn.commit()
                st.rerun() # Refresh to show new status

        with col2:
            st.subheader("📧 Smart Mailer")
            if st.button("Generate Interview Invite"):
                candidate = apps[apps['id'] == selected_id].iloc[0]
                
                # Prompt for a high-quality email
                invite_prompt = (
                    f"Write a professional interview invitation email for {candidate['student_name']} "
                    f"for the role of {candidate['role']} at {candidate['company']}. "
                    "Mention their impressive resume screening score. Keep placeholders for [Time] and [Link]."
                )
                
                with st.spinner("AI is drafting the email..."):
                    email_body = client.models.generate_content(
                        model='gemini-1.5-flash', 
                        contents=invite_prompt
                    ).text
                    st.text_area("Draft Email", value=email_body, height=250)
                    st.caption("Copy this to your email client.")
    else:
        st.info("Waiting for applications.")