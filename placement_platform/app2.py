import streamlit as st
import sqlite3
import pandas as pd
import random
import google.generativeai as genai
from PyPDF2 import PdfReader

# --- 1. CONFIGURATION ---
# Replace with your actual Gemini API Key from Google AI Studio
GEMINI_API_KEY = "AIzaSyBQMT4d3cbSSq-6cR-vmStMGzDA7A4vBx4" 

# 🔴 ADD THIS AT TOP

SECTOR_RULES = {
    "IT & Digital Governance": {
        "skills": ["ai", "python", "cloud", "cybersecurity", "data analytics"],
        "certifications": ["aws", "azure", "ceh", "cisa", "docker", "kubernetes"]
    },
    "Infrastructure & Green Energy": {
        "skills": ["solar", "green hydrogen", "sustainable", "grid", "autocad"],
        "certifications": ["suryamitra", "bim", "sap"]
    },
    "Public Administration": {
        "skills": ["policy", "law", "regulation", "public finance", "data analytics"],
        "certifications": ["excel", "government", "legal"]
    }
}


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
        
# 🔴 ADD BELOW GEMINI FUNCTION

def calculate_govt_score(resume_text, rules):
    resume_text = resume_text.lower()
    score = 0
    found_skills = []
    missing_skills = []

    for skill in rules["skills"]:
        if skill in resume_text:
            score += 10
            found_skills.append(skill)
        else:
            missing_skills.append(skill)

    for cert in rules["certifications"]:
        if cert in resume_text:
            score += 15
            found_skills.append(cert)
        else:
            missing_skills.append(cert)

    return min(score, 100), found_skills, missing_skills


def detect_best_sector(resume_text):
    best_sector = None
    best_score = 0
    best_data = ([], [])

    for sector, rules in SECTOR_RULES.items():
        score, found, missing = calculate_govt_score(resume_text, rules)
        if score > best_score:
            best_score = score
            best_sector = sector
            best_data = (found, missing)

    return best_sector, best_score, best_data

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

                        # 🔥 GOVT ENGINE
                        sector, govt_score, (found, missing) = detect_best_sector(text)

                        # 🤖 GEMINI (keep for demo)
                        result = screen_with_gemini(text, target_jd)

                        # Extract Gemini score
                        try:
                            gemini_score = int(''.join(filter(str.isdigit, result.split('\n')[0])))
                        except:
                            gemini_score = 50

                            # 🧠 FINAL HYBRID SCORE
                        final_score = int((govt_score * 0.7) + (gemini_score * 0.3))

                        c = conn.cursor()
                        c.execute(
                        "INSERT INTO applications (student_name, job_id, resume_text, ai_score, feedback) VALUES (?,?,?,?,?)",
                        (
                            name,
                            job_options[selected_job],
                            text,
                            final_score,
                            f"{result}\n\nSector: {sector}\nSkills Found: {found}\nMissing: {missing}"
                        )
                    )
                    conn.commit()

                    st.balloons()
                    st.success("Application submitted!")

                    st.markdown(f"""
                     ### 🎯 National Readiness Report

                     **🏢 Sector Fit:** {sector}  
                     **📊 Score:** {final_score}/100  

                     **✅ Skills Found:** {', '.join(found) if found else 'None'}  

                     **❌ Missing Skills:** {', '.join(missing) if missing else 'None'}  
                    """)
                    







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
    st.header("📊 Placement Control Center")
    conn = sqlite3.connect('placement.db')

    query = """
        SELECT a.id, a.student_name, j.company, j.role, a.ai_score, a.status, a.feedback
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.ai_score DESC
    """
    apps = pd.read_sql_query(query, conn)

    if not apps.empty:

        # 🔥 FILTER BY SECTOR
        st.subheader("🎯 Filter Candidates by Sector")

        sector_filter = st.selectbox(
            "Select Sector",
            ["All", "IT & Digital Governance", "Infrastructure & Green Energy", "Public Administration"]
        )

        if sector_filter != "All":
            apps = apps[apps['feedback'].str.contains(sector_filter, case=False, na=False)]

        # 📊 MAIN TABLE
        st.dataframe(apps, use_container_width=True)

        st.divider()

        # 🏆 TOP CANDIDATES
        st.subheader("🏆 Top Candidates")
        top_apps = apps.sort_values(by="ai_score", ascending=False).head(5)
        st.dataframe(top_apps, use_container_width=True)

        st.divider()

        # 📉 SKILL GAP ANALYSIS
        st.subheader("📉 Skill Gap Insights")

        missing_skills = []

        for feedback in apps['feedback']:
            if "Missing:" in str(feedback):
                part = feedback.split("Missing:")[-1]
                skills = part.replace("[", "").replace("]", "").replace("'", "").split(",")
                missing_skills.extend([s.strip() for s in skills if s.strip()])

        if missing_skills:
            gap_df = pd.Series(missing_skills).value_counts().head(10)
            st.bar_chart(gap_df)
        else:
            st.info("No missing skill data available.")

        st.divider()

        # 🔧 MANAGEMENT + 📧 MAILER
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🛠️ Management")

            target_id = st.selectbox("Select Student ID", apps['id'].tolist())
            update_to = st.selectbox("Update Stage", ["Applied", "Screened", "Shortlisted", "Interview", "Offered"])

            if st.button("Update Status", type="secondary"):
                db_conn = sqlite3.connect('placement.db')
                db_conn.cursor().execute(
                    "UPDATE applications SET status = ? WHERE id = ?",
                    (update_to, target_id)
                )
                db_conn.commit()
                st.rerun()

        with col2:
            st.subheader("📧 Smart Mailer")

            if st.button("Generate Interview Invite", type="primary"):
                candidate = apps[apps['id'] == target_id].iloc[0]

                prompt = f"""
                Write a professional interview invitation email for {candidate['student_name']}
                for the role of {candidate['role']} at {candidate['company']}.
                Mention their strong screening score.
                """

                with st.spinner("AI is drafting..."):

                    for model_name in ['gemini-1.5-flash']:
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=prompt
                            )
                            email_text = response.text

                            st.text_area("Draft Email", value=email_text, height=200)
                            st.success("Email ready!")
                            break

                        except:
                            st.warning("AI busy, using fallback template")

                            temp = f"""
Dear {candidate['student_name']},

You are shortlisted for the role of {candidate['role']} at {candidate['company']}.

Please attend the interview at [Time].

Regards,
HR Team
"""
                            st.text_area("Template Email", value=temp, height=200)

    else:
        st.info("No applications received yet.")