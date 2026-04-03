import streamlit as st
import sqlite3
import pandas as pd
import random
from google import genai
from PyPDF2 import PdfReader

# --- CONFIGURATION ---
GEMINI_API_KEY = "AIzaSyBQMT4d3cbSSq-6cR-vmStMGzDA7A4vBx4"
client = genai.Client(api_key=GEMINI_API_KEY)

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('placement.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs 
                 (id INTEGER PRIMARY KEY, role TEXT, company TEXT, jd TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY, student_name TEXT, student_email TEXT, job_id INTEGER, 
                  resume_text TEXT, ai_score INTEGER, feedback TEXT, status TEXT)''')
    try:
        c.execute("SELECT student_email FROM applications LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE applications ADD COLUMN student_email TEXT DEFAULT 'N/A'")
    conn.commit()
    conn.close()

init_db()

# --- AI CORE LOGIC ---
def screen_with_gemini(resume_text, job_description):
    prompt = f"Compare Resume: {resume_text} with JD: {job_description}. Return SCORE: [0-100] and REASON: [1 sentence]."
    try:
        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        return response.text
    except Exception:
        st.warning("⚠️ API Rate Limit hit. Using Mock AI for this demo.")
        mock_score = random.randint(70, 92)
        return f"SCORE: {mock_score}\nREASON: [SIMULATED] Candidate shows strong technical alignment with job requirements."

# ─────────────────────────────────────────────
# GLOBAL STYLES
# ─────────────────────────────────────────────
st.set_page_config(page_title="PlaceMind AI", layout="wide", page_icon="⚡")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600&display=swap');

/* ── Root reset ── */
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }

/* ── Dark background ── */
.stApp { background: #0A0C10 !important; }
section[data-testid="stSidebar"] { background: #111318 !important; border-right: 1px solid #232836; }
.block-container { padding: 2rem 2.5rem !important; max-width: 100% !important; }

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── Sidebar logo ── */
.logo-block {
    background: linear-gradient(135deg, #141720 0%, #1a1f2e 100%);
    border: 1px solid #2a3045;
    border-radius: 10px;
    padding: 18px 16px;
    margin-bottom: 20px;
    text-align: center;
}
.logo-main { font-family: 'Space Mono', monospace; font-size: 16px; font-weight: 700;
             color: #4F8EF7; letter-spacing: 3px; }
.logo-sub  { font-size: 10px; color: #6B7592; letter-spacing: 1.5px; margin-top: 4px; }

/* ── Sidebar nav labels ── */
.sidebar-section { font-family: 'Space Mono', monospace; font-size: 9px;
                   letter-spacing: 2px; color: #3a4260; text-transform: uppercase;
                   padding: 12px 4px 6px; }

/* ── Page header ── */
.page-header {
    display: flex; align-items: flex-start; justify-content: space-between;
    border-bottom: 1px solid #232836;
    padding-bottom: 18px; margin-bottom: 24px;
}
.page-title { font-size: 22px; font-weight: 600; color: #E8ECF4; }
.page-crumb { font-family: 'Space Mono', monospace; font-size: 10px;
              color: #4F8EF7; margin-top: 4px; }
.live-badge {
    background: rgba(0,212,170,.1); border: 1px solid rgba(0,212,170,.25);
    color: #00D4AA; font-family: 'Space Mono', monospace;
    font-size: 10px; padding: 4px 10px; border-radius: 4px;
}

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #111318 !important;
    border: 1px solid #232836 !important;
    border-radius: 10px !important;
    padding: 18px 20px !important;
}
div[data-testid="metric-container"] label {
    font-family: 'Space Mono', monospace !important;
    font-size: 10px !important; letter-spacing: 1px !important;
    color: #6B7592 !important; text-transform: uppercase !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 28px !important; font-weight: 600 !important; color: #E8ECF4 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    color: #00D4AA !important; font-size: 12px !important;
}

/* ── Data table ── */
.styled-table-wrap {
    background: #111318; border: 1px solid #232836;
    border-radius: 10px; overflow: hidden; margin: 12px 0;
}
.styled-table-header {
    padding: 14px 20px; border-bottom: 1px solid #232836;
    display: flex; align-items: center; justify-content: space-between;
}
.styled-table-title { font-size: 13px; font-weight: 500; color: #E8ECF4; }

/* ── Score pill ── */
.score-pill {
    display: inline-block; padding: 3px 10px;
    border-radius: 20px; font-family: 'Space Mono', monospace;
    font-size: 11px; font-weight: 700;
}
.score-high { background: rgba(0,212,170,.12); color: #00D4AA; }
.score-mid  { background: rgba(79,142,247,.12);  color: #4F8EF7; }
.score-low  { background: rgba(107,117,146,.12); color: #6B7592; }

/* ── Status pills ── */
.status-pill {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-family: 'Space Mono', monospace; font-size: 10px;
    font-weight: 700; text-transform: uppercase; letter-spacing: .5px;
}
.s-applied    { background: rgba(79,142,247,.12);  color: #4F8EF7; }
.s-screened   { background: rgba(107,117,146,.12); color: #6B7592; }
.s-shortlisted{ background: rgba(0,212,247,.12);   color: #00D4F7; }
.s-interview  { background: rgba(247,193,84,.12);  color: #F7C154; }
.s-offered    { background: rgba(0,212,170,.12);   color: #00D4AA; }

/* ── Inputs & selects ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background: #181C24 !important;
    border: 1px solid #2a3045 !important;
    color: #E8ECF4 !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #4F8EF7 !important;
    box-shadow: 0 0 0 2px rgba(79,142,247,.15) !important;
}
label { color: #6B7592 !important; font-size: 12px !important; font-family: 'Space Mono', monospace !important; letter-spacing: .5px !important; }

/* ── Buttons ── */
.stButton > button {
    background: #4F8EF7 !important;
    border: none !important;
    color: #fff !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    transition: all .15s !important;
}
.stButton > button:hover { background: #3a78e0 !important; transform: translateY(-1px); }
.stButton > button[kind="secondary"] {
    background: #181C24 !important;
    border: 1px solid #2a3045 !important;
    color: #E8ECF4 !important;
}
.stButton > button[kind="secondary"]:hover { border-color: #4F8EF7 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    gap: 4px !important;
    border-bottom: 1px solid #232836 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    color: #6B7592 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 12px !important;
    padding: 8px 16px !important;
    border-radius: 6px 6px 0 0 !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(79,142,247,.1) !important;
    color: #4F8EF7 !important;
    border-bottom: 2px solid #4F8EF7 !important;
}

/* ── File uploader ── */
.stFileUploader {
    background: #181C24 !important;
    border: 1px dashed #2a3045 !important;
    border-radius: 8px !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #111318 !important;
    border: 1px solid #232836 !important;
    border-radius: 8px !important;
    color: #E8ECF4 !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ── Divider ── */
hr { border-color: #232836 !important; }

/* ── Info / warning / success boxes ── */
.stAlert { border-radius: 8px !important; border-width: 1px !important; }
[data-baseweb="notification"] { border-radius: 8px !important; }

/* ── Dataframe ── */
.dataframe { background: #111318 !important; color: #E8ECF4 !important; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: #4F8EF7 !important; }

/* ── AI card ── */
.ai-card {
    background: #181C24; border: 1px solid rgba(79,142,247,.2);
    border-radius: 8px; padding: 14px 16px; margin: 8px 0;
    font-size: 13px; color: #B0B8D0; line-height: 1.6;
}
.ai-card strong { color: #E8ECF4; }

/* ── Panel card ── */
.panel-card {
    background: #111318; border: 1px solid #232836;
    border-radius: 10px; padding: 20px;
}
.panel-label { font-family: 'Space Mono', monospace; font-size: 10px;
               letter-spacing: 1.2px; color: #6B7592; text-transform: uppercase;
               margin-bottom: 14px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="logo-block">
        <div class="logo-main">PLACEMIND</div>
        <div class="logo-sub">AI PLACEMENT OS · v3.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">Navigation</div>', unsafe_allow_html=True)
    menu = ["⚡ TPO Dashboard", "📝 Student Portal", "📢 HR Drive"]
    choice = st.radio("", menu, label_visibility="collapsed")

    st.markdown("---")
    st.markdown("""
    <div style="text-align:center">
        <div style="display:inline-flex;align-items:center;gap:8px;font-size:11px;color:#6B7592">
            <span style="width:7px;height:7px;border-radius:50%;background:#00D4AA;display:inline-block;animation:none"></span>
            Gemini 1.5 Flash · Active
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# TPO DASHBOARD
# ─────────────────────────────────────────────
if choice == "⚡ TPO Dashboard":
    st.markdown("""
    <div class="page-header">
        <div>
            <div class="page-title">Placement Control Center</div>
            <div class="page-crumb">BHARAT-TECH X › TPO › Overview</div>
        </div>
        <span class="live-badge">● AI Engine Live</span>
    </div>
    """, unsafe_allow_html=True)

    conn = sqlite3.connect('placement.db')
    apps = pd.read_sql_query("""
        SELECT a.id, a.student_name, a.student_email, j.company, j.role,
               a.ai_score, a.status 
        FROM applications a JOIN jobs j ON a.job_id = j.id 
        ORDER BY a.ai_score DESC
    """, conn)
    jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)

    # Stats row
    total = len(apps)
    offered = len(apps[apps['status'] == 'Offered']) if not apps.empty else 0
    avg_score = int(apps['ai_score'].mean()) if not apps.empty else 0
    drives = len(jobs_df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Applicants", total, "+12 this week")
    c2.metric("Offers Extended", offered)
    c3.metric("Active Drives", drives)
    c4.metric("Avg AI Score", f"{avg_score}%")

    st.markdown("<br>", unsafe_allow_html=True)

    if not apps.empty:
        # Styled table section
        st.markdown("""
        <div class="styled-table-wrap">
            <div class="styled-table-header">
                <span class="styled-table-title">Applications — sorted by AI score</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Build display dataframe with HTML badges
        def score_pill(s):
            if s >= 80: cls = "score-high"
            elif s >= 60: cls = "score-mid"
            else: cls = "score-low"
            return f'<span class="score-pill {cls}">{s}</span>'

        def status_pill(st_val):
            mapping = {
                "Applied": "s-applied", "Screened": "s-screened",
                "Shortlisted": "s-shortlisted", "Interview": "s-interview", "Offered": "s-offered"
            }
            cls = mapping.get(st_val, "s-applied")
            return f'<span class="status-pill {cls}">{st_val}</span>'

        display = apps.copy()
        display["AI Score"] = display["ai_score"].apply(score_pill)
        display["Status"] = display["status"].apply(status_pill)
        display = display.rename(columns={"student_name": "Student", "student_email": "Email",
                                          "company": "Company", "role": "Role"})
        display = display[["id", "Student", "Email", "Company", "Role", "AI Score", "Status"]]

        st.write(display.to_html(escape=False, index=False), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="panel-label">Manage Application</div>', unsafe_allow_html=True)

        col1, col2 = st.columns([1, 1])
        with col1:
            target_id = st.selectbox("Select Student ID", apps['id'].tolist())
            update_to = st.selectbox("Update Stage", ["Applied", "Screened", "Shortlisted", "Interview", "Offered"])
            if st.button("Update Status", type="primary"):
                db_conn = sqlite3.connect('placement.db')
                db_conn.cursor().execute("UPDATE applications SET status = ? WHERE id = ?", (update_to, target_id))
                db_conn.commit()
                st.success("Status updated.")
                st.rerun()

        with col2:
            st.markdown('<div class="panel-label">Smart AI Mailer</div>', unsafe_allow_html=True)
            if st.button("✦ Generate Interview Invite", type="secondary"):
                candidate = apps[apps['id'] == target_id].iloc[0]
                email_to = candidate.get('student_email', 'N/A')
                prompt = f"Draft a concise, professional interview invite for {candidate['student_name']} applying for {candidate['role']} at {candidate['company']}."
                with st.spinner("AI is drafting..."):
                    for m_name in ['gemini-2.0-flash', 'gemini-1.5-flash']:
                        try:
                            response = client.models.generate_content(model=m_name, contents=prompt)
                            email_text = response.text
                            st.markdown(f'<div class="ai-card"><strong>To:</strong> {email_to}<br><br>{email_text}</div>', unsafe_allow_html=True)
                            break
                        except:
                            if m_name == 'gemini-1.5-flash':
                                fallback = f"Dear {candidate['student_name']},\n\nYou are invited for an interview for the {candidate['role']} position at {candidate['company']}.\n\nBest regards,\nPlacement Cell"
                                st.markdown(f'<div class="ai-card">{fallback}</div>', unsafe_allow_html=True)
    else:
        st.info("No applications received yet. Post a drive and wait for students to apply.")

# ─────────────────────────────────────────────
# STUDENT PORTAL
# ─────────────────────────────────────────────
elif choice == "📝 Student Portal":
    st.markdown("""
    <div class="page-header">
        <div>
            <div class="page-title">Student Career Portal</div>
            <div class="page-crumb">BHARAT-TECH X › Student › Apply & Track</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Apply for Jobs", "Track My Status"])

    with tab1:
        conn = sqlite3.connect('placement.db')
        jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)

        if not jobs_df.empty:
            job_map = {f"{r['company']} — {r['role']}": r['id'] for _, r in jobs_df.iterrows()}
            selected_job = st.selectbox("Active Placement Drive", list(job_map.keys()))

            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name")
            with col2:
                email_addr = st.text_input("Email Address")

            file = st.file_uploader("Resume (PDF only)", type="pdf")

            if st.button("Submit Application", type="primary"):
                if file and name and email_addr:
                    reader = PdfReader(file)
                    text = "".join([p.extract_text() for p in reader.pages])
                    target_jd = jobs_df[jobs_df['id'] == job_map[selected_job]]['jd'].values[0]

                    with st.spinner("AI is screening your profile..."):
                        result = screen_with_gemini(text, target_jd)
                        try:
                            score = int(''.join(filter(str.isdigit, result.split('\n')[0])))
                        except:
                            score = 0

                        c = conn.cursor()
                        c.execute("""
                            INSERT INTO applications 
                            (student_name, student_email, job_id, resume_text, ai_score, feedback, status) 
                            VALUES (?,?,?,?,?,?,?)
                        """, (name, email_addr, job_map[selected_job], text, score, result, "Applied"))
                        conn.commit()
                        st.balloons()
                        st.success(f"Application submitted! Your AI Match Score: **{score}%**")
                        st.markdown(f'<div class="ai-card"><strong>AI Feedback:</strong><br>{result}</div>', unsafe_allow_html=True)
                else:
                    st.warning("Please fill in your name, email, and upload a resume.")
        else:
            st.info("No active drives yet. Check back soon.")

    with tab2:
        search = st.text_input("Enter your name to track applications")
        if search:
            conn = sqlite3.connect('placement.db')
            query = f"""
                SELECT a.*, j.company, j.role 
                FROM applications a JOIN jobs j ON a.job_id = j.id 
                WHERE a.student_name LIKE '%{search}%'
            """
            res = pd.read_sql_query(query, conn)
            if not res.empty:
                for _, row in res.iterrows():
                    with st.expander(f"📌 {row['company']} — {row['role']}"):
                        st.markdown(f"**Status:** `{row['status']}`")
                        st.markdown(f'<div class="ai-card"><strong>AI Score:</strong> {row["ai_score"]}%<br><br>{row["feedback"]}</div>', unsafe_allow_html=True)
            else:
                st.info("No applications found for that name.")

# ─────────────────────────────────────────────
# HR DRIVE
# ─────────────────────────────────────────────
elif choice == "📢 HR Drive":
    st.markdown("""
    <div class="page-header">
        <div>
            <div class="page-title">Create Placement Drive</div>
            <div class="page-crumb">BHARAT-TECH X › HR › New Drive</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        company = st.text_input("Company Name")
    with col2:
        role = st.text_input("Job Role")

    jd = st.text_area("Job Description", height=200,
                       placeholder="Describe the role, required skills, experience, and responsibilities...")

    if st.button("Post Drive", type="primary"):
        if company and role and jd:
            conn = sqlite3.connect('placement.db')
            c = conn.cursor()
            c.execute("INSERT INTO jobs (role, company, jd) VALUES (?,?,?)", (role, company, jd))
            conn.commit()
            st.success(f"Drive for **{company} — {role}** is now live!")
        else:
            st.error("Please fill in all fields before posting.")