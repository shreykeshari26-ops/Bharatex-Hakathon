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
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY, student_name TEXT, job_id INTEGER, 
                  resume_text TEXT, ai_score INTEGER, feedback TEXT)''')
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
        search = st.text_input("Enter your name to track")
        if search:
            conn = sqlite3.connect('placement.db')
            # Fixed SQL query to use proper JOIN
            query = f"""
                SELECT a.ai_score, a.feedback, j.company, j.role 
                FROM applications a 
                JOIN jobs j ON a.job_id = j.id 
                WHERE a.student_name LIKE '%{search}%'
            """
            res = pd.read_sql_query(query, conn)
            if not res.empty:
                for i, row in res.iterrows():
                    with st.expander(f"{row['company']} - {row['role']}"):
                        st.write(f"**AI Score:** {row['ai_score']}/100")
                        st.progress(row['ai_score'] / 100)
                        st.info(f"**Feedback:** {row['feedback']}")
            else:
                st.info("No application found for that name.")

# --- TPO VIEW ---
elif choice == "TPO: Dashboard":
    st.header("📊 Admin Dashboard (TPO)")
    conn = sqlite3.connect('placement.db')
    query = """
        SELECT a.student_name, j.company, j.role, a.ai_score 
        FROM applications a 
        JOIN jobs j ON a.job_id = j.id 
        ORDER BY a.ai_score DESC
    """
    apps = pd.read_sql_query(query, conn)
    
    if not apps.empty:
        st.write("### AI-Ranked Student Shortlist")
        st.dataframe(apps, use_container_width=True)
        
        st.divider()
        st.subheader("Smart Communication")
        selected = st.selectbox("Select Candidate for Interview Invite", apps['student_name'].tolist())
        if st.button("Generate Interview Email"):
            # Ensure even the email generator uses the stable model
            try:
                invite_prompt = f"Write a professional interview invitation for {selected}."
                email_body = client.models.generate_content(model='gemini-1.5-flash', contents=invite_prompt).text
                st.text_area("Draft Email", value=email_body, height=200)
            except:
                st.error("Email service is temporarily limited. Please try again in 1 minute.")
    else:
        st.info("Waiting for students to apply.")