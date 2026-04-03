import streamlit as st
import sqlite3
import pandas as pd
import random
import os
import hashlib
import smtplib
import plotly.graph_objects as go
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
from PyPDF2 import PdfReader
from datetime import date

# ============================================================
# 1. CONFIGURATION
# ============================================================
GEMINI_API_KEY = "AIzaSyBQMT4d3cbSSq-6cR-vmStMGzDA7A4vBx4"

# SMTP Config — fill these in for live email
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "your_email@gmail.com"   # ← change
SMTP_PASSWORD = "your_app_password"      # ← change (Gmail App Password)

MAX_RESUME_SIZE_MB = 10

SECTOR_RULES = {
    "IT & Digital Governance": {
        "skills": ["ai", "python", "cloud", "cybersecurity", "data analytics", "machine learning",
                   "deep learning", "nlp", "sql", "javascript", "react", "node", "django", "flask"],
        "certifications": ["aws", "azure", "ceh", "cisa", "docker", "kubernetes", "gcp", "comptia"]
    },
    "Infrastructure & Green Energy": {
        "skills": ["solar", "green hydrogen", "sustainable", "grid", "autocad", "civil",
                   "structural", "electrical", "mechanical", "renewable", "construction"],
        "certifications": ["suryamitra", "bim", "sap", "pmp", "six sigma"]
    },
    "Public Administration": {
        "skills": ["policy", "law", "regulation", "public finance", "data analytics",
                   "governance", "ias", "upsc", "administration", "compliance"],
        "certifications": ["excel", "government", "legal", "ias coaching"]
    },
    "Core Engineering": {
        "skills": ["mechanical", "civil", "electrical", "electronics", "matlab", "solidworks",
                   "catia", "ansys", "plc", "scada", "embedded", "iot", "robotics", "vlsi"],
        "certifications": ["autocad", "solidworks", "plc", "six sigma", "pmp", "iso"]
    },
    "Management & Finance": {
        "skills": ["mba", "finance", "marketing", "sales", "hr", "supply chain", "erp",
                   "excel", "powerpoint", "crm", "accounting", "tally", "sap", "tableau"],
        "certifications": ["ca", "cfa", "cma", "pmp", "google analytics", "salesforce"]
    }
}

SHORTLIST_THRESHOLD = 40

RESUME_STORE = "resumes"
os.makedirs(RESUME_STORE, exist_ok=True)


# ============================================================
# 2. DATABASE  (extended with users + resume_path columns)
# ============================================================
def init_db():
    conn = sqlite3.connect('placement.db')
    c    = conn.cursor()

    # Existing tables
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY, role TEXT, company TEXT, jd TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS applications
                 (id INTEGER PRIMARY KEY, student_name TEXT, job_id INTEGER,
                  resume_text TEXT, ai_score INTEGER, feedback TEXT, status TEXT,
                  sector TEXT, sector_match_score INTEGER,
                  contract_accepted INTEGER DEFAULT 0,
                  placement_probability INTEGER,
                  resume_path TEXT)''')

    # ── NEW: users table (Feature 6)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE,
                  password_hash TEXT, role TEXT)''')

    # ── Safe migration for old applications table
    existing = [row[1] for row in c.execute("PRAGMA table_info(applications)").fetchall()]
    new_cols = {
        "sector":               "TEXT",
        "sector_match_score":   "INTEGER DEFAULT 0",
        "contract_accepted":    "INTEGER DEFAULT 0",
        "placement_probability":"INTEGER DEFAULT 0",
        "resume_path":          "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in existing:
            c.execute(f"ALTER TABLE applications ADD COLUMN {col} {col_type}")

    # Seed one default admin account
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?,?,?)",
              ("admin", admin_hash, "admin"))

    conn.commit()
    conn.close()

init_db()


# ============================================================
# 3. AUTH HELPERS  (Feature 6)
# ============================================================
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def register_user(username: str, password: str, role: str) -> bool:
    try:
        conn = sqlite3.connect('placement.db')
        conn.cursor().execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            (username, hash_password(password), role)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username: str, password: str):
    """Returns (role, username) tuple or None."""
    conn = sqlite3.connect('placement.db')
    row = conn.cursor().execute(
        "SELECT role FROM users WHERE username=? AND password_hash=?",
        (username, hash_password(password))
    ).fetchone()
    conn.close()
    return row[0] if row else None


# ============================================================
# 4. AI CORE (unchanged)
# ============================================================
def screen_with_gemini(resume_text, job_description):
    prompt = (f"Compare Resume: {resume_text} with JD: {job_description}. "
              f"Return SCORE: [0-100] and REASON: [1 sentence].")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model    = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        st.warning("⚠️ API Rate Limit hit. Using Mock AI.")
        mock_score = random.randint(70, 92)
        return (f"SCORE: {mock_score}\nREASON: [SIMULATED] Strong technical alignment.")


def calculate_govt_score(resume_text, rules):
    resume_lower = resume_text.lower()
    score = 0
    found_skills, missing_skills = [], []
    for skill in rules["skills"]:
        if skill in resume_lower:
            score += 10
            found_skills.append(skill)
        else:
            missing_skills.append(skill)
    for cert in rules["certifications"]:
        if cert in resume_lower:
            score += 15
            found_skills.append(cert)
        else:
            missing_skills.append(cert)
    return min(score, 100), found_skills, missing_skills


def detect_best_sector(resume_text):
    best_sector, best_score, best_data = None, 0, ([], [])
    for sector, rules in SECTOR_RULES.items():
        score, found, missing = calculate_govt_score(resume_text, rules)
        if score > best_score:
            best_score, best_sector, best_data = score, sector, (found, missing)
    return best_sector, best_score, best_data


# ============================================================
# FEATURE 1 — INTELLIGENT JOB RECOMMENDATIONS
# ============================================================
def get_job_recommendations(resume_text: str, top_n: int = 5) -> list[dict]:
    """
    Score every open job against the resume using keyword overlap
    between resume and JD, then return top_n matches.
    """
    conn    = sqlite3.connect('placement.db')
    jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
    conn.close()

    if jobs_df.empty:
        return []

    resume_lower = resume_text.lower()
    results      = []

    for _, job in jobs_df.iterrows():
        jd_words    = set(job['jd'].lower().split())
        resume_words= set(resume_lower.split())
        overlap     = len(jd_words & resume_words)
        max_possible= max(len(jd_words), 1)
        match_pct   = min(int((overlap / max_possible) * 100 * 3), 100)  # amplify small matches
        results.append({
            "job_id":    job['id'],
            "role":      job['role'],
            "company":   job['company'],
            "match_pct": match_pct,
        })

    results.sort(key=lambda x: x['match_pct'], reverse=True)
    return results[:top_n]


# ============================================================
# FEATURE 2 — SMART MAILER
# ============================================================
EMAIL_TEMPLATES = {
    "Interview Invite": {
        "subject": "Interview Invitation – {role} at {company}",
        "body": (
            "Dear {name},\n\n"
            "Congratulations! You have been shortlisted for the role of {role} at {company}.\n\n"
            "Please attend the interview on the date communicated by the HR team.\n"
            "Carry a copy of your resume and relevant documents.\n\n"
            "Best regards,\nPlaceMind AI | HR Team"
        ),
    },
    "Selection Offer": {
        "subject": "Offer Letter – {role} at {company}",
        "body": (
            "Dear {name},\n\n"
            "We are delighted to inform you that you have been selected for the position of "
            "{role} at {company}.\n\n"
            "Your joining details will be shared shortly. Kindly confirm your acceptance.\n\n"
            "Warm regards,\nPlaceMind AI | HR Team"
        ),
    },
    "Rejection Mail": {
        "subject": "Application Status – {role} at {company}",
        "body": (
            "Dear {name},\n\n"
            "Thank you for applying for the role of {role} at {company}.\n\n"
            "After careful review, we regret to inform you that we will not be moving forward "
            "with your application at this time. We encourage you to apply for future openings.\n\n"
            "Best wishes,\nPlaceMind AI | HR Team"
        ),
    },
}

def fill_template(template_key: str, name: str, company: str, role: str) -> tuple[str, str]:
    """Returns (subject, body) with placeholders filled."""
    t       = EMAIL_TEMPLATES[template_key]
    subject = t["subject"].format(name=name, company=company, role=role)
    body    = t["body"].format(name=name, company=company, role=role)
    return subject, body

def send_email(to_addr: str, subject: str, body: str) -> bool:
    """Send email via SMTP. Returns True on success."""
    try:
        msg              = MIMEMultipart()
        msg['From']      = SMTP_USER
        msg['To']        = to_addr
        msg['Subject']   = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_addr, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"SMTP Error: {e}")
        return False


# ============================================================
# FEATURE 3 — FILE UPLOAD VALIDATION
# ============================================================
def validate_resume(file) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    if file is None:
        return False, "No file uploaded."
    if not file.name.lower().endswith(".pdf"):
        return False, "❌ Only PDF files are allowed."
    size_mb = file.size / (1024 * 1024)
    if size_mb > MAX_RESUME_SIZE_MB:
        return False, f"❌ File size {size_mb:.1f} MB exceeds the {MAX_RESUME_SIZE_MB} MB limit."
    return True, ""


# ============================================================
# FEATURE 4 — RESUME STORAGE HELPERS
# ============================================================
def save_resume_file(file, student_name: str) -> str:
    """Save uploaded PDF bytes to disk; return file path."""
    safe_name = student_name.replace(" ", "_")
    filename  = f"{safe_name}_{date.today()}.pdf"
    path      = os.path.join(RESUME_STORE, filename)
    with open(path, "wb") as f:
        f.write(file.getbuffer())
    return path

def get_resume_bytes(path: str) -> bytes | None:
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


# ============================================================
# EXISTING HELPERS (unchanged)
# ============================================================
def get_sector_match_score(resume_text, sector_name):
    if sector_name not in SECTOR_RULES:
        return 0
    score, _, _ = calculate_govt_score(resume_text, SECTOR_RULES[sector_name])
    return score

def auto_shortlist_by_sector(threshold=SHORTLIST_THRESHOLD):
    conn = sqlite3.connect('placement.db')
    c    = conn.cursor()
    c.execute(
        "UPDATE applications SET status='Shortlisted' "
        "WHERE sector_match_score >= ? AND (status='Applied' OR status IS NULL)",
        (threshold,)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected

def generate_contract(candidate_name, company, role):
    today = date.today().strftime("%d %B %Y")
    return f"""
╔══════════════════════════════════════════════════════════╗
       PLACEMENT COMMITMENT BOND — PLACEMIND AI
╚══════════════════════════════════════════════════════════╝

Date  : {today}
Ref # : PCB-{abs(hash(candidate_name + company)) % 100000:05d}

CANDIDATE  : {candidate_name}
COMPANY    : {company}
ROLE       : {role}

DECLARATION
───────────
I, {candidate_name}, hereby confirm that:
  1. I accept this offer in good faith and commit to joining.
  2. I will not renege on this offer after acceptance.
  3. I understand backing out may affect institute–company relations.

By clicking "Accept Contract", I digitally sign these terms.

                    Powered by PlaceMind AI
"""

def accept_contract(application_id):
    conn = sqlite3.connect('placement.db')
    conn.cursor().execute(
        "UPDATE applications SET contract_accepted=1 WHERE id=?", (application_id,)
    )
    conn.commit()
    conn.close()

def calculate_placement_probability(ai_score, sector_match_score):
    ai_score           = ai_score or 0
    sector_match_score = sector_match_score or 0
    return min(int((ai_score * 0.60) + (sector_match_score * 0.40)), 100)

def get_probability_label(prob):
    if prob >= 75:  return "🟢 High"
    elif prob >= 50: return "🟡 Medium"
    else:            return "🔴 Low"

def get_improvement_suggestions(missing_skills, sector):
    sector_tips = {
        "IT & Digital Governance": [
            "🔧 Build a GitHub project to showcase code",
            "📚 Complete a free AWS / Azure certification",
            "💻 Practice DSA on LeetCode (100+ problems)",
        ],
        "Core Engineering": [
            "🛠 Add a CAD design project to your portfolio",
            "📐 Get SolidWorks or AutoCAD certified",
            "🔌 Work on an IoT / embedded systems project",
        ],
        "Infrastructure & Green Energy": [
            "☀️ Complete the Suryamitra certification",
            "🏗 Add a BIM modelling project",
            "📊 Learn SAP basics online",
        ],
        "Public Administration": [
            "📜 Add policy or governance internships",
            "🏛 Mention UPSC / state service preparation",
            "📊 Learn Excel / data tools for public finance",
        ],
        "Management & Finance": [
            "📈 Learn Tableau or Power BI",
            "💼 Add a sales, marketing or HR internship",
            "🧾 Complete Tally / SAP basics",
        ],
    }
    suggestions = list(sector_tips.get(sector, []))
    for skill in (missing_skills or [])[:3]:
        suggestions.append(f"➕ Add '{skill}' to your skill set")
    return suggestions[:5]


# ============================================================
# FEATURE 7 — PLOTLY DOUGHNUT CHARTS
# ============================================================
def doughnut_chart(labels, values, title):
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.5,
        textinfo="label+percent",
        marker=dict(colors=["#FF4B4B","#4CAF50","#2196F3","#FF9800","#9C27B0"])
    ))
    fig.update_layout(
        title_text=title, showlegend=True,
        margin=dict(t=50, b=20, l=20, r=20),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )
    return fig


# ============================================================
# 5. SESSION STATE INITIALISATION
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role      = None
    st.session_state.username  = None


# ============================================================
# 6. PAGE CONFIG + SIDEBAR
# ============================================================
st.set_page_config(page_title="PlaceMind AI", layout="wide")

st.sidebar.markdown("""
    <div style="background-color:#FF4B4B;padding:15px;border-radius:10px;margin-bottom:20px">
    <h2 style="color:white;text-align:center;margin:0;">BHARAT-TECH X</h2>
    <p style="color:white;text-align:center;font-size:12px;">Placement Management 3.0</p>
    </div>
""", unsafe_allow_html=True)


# ============================================================
# 7. LOGIN / REGISTER PAGE
# ============================================================
def show_auth_page():
    st.title("🎓 PlaceMind AI — Secure Login")
    tab_login, tab_reg = st.tabs(["Login", "Register"])

    with tab_login:
        uname = st.text_input("Username", key="l_uname")
        pwd   = st.text_input("Password", type="password", key="l_pwd")
        if st.button("Login", type="primary"):
            role = login_user(uname, pwd)
            if role:
                st.session_state.logged_in = True
                st.session_state.role      = role
                st.session_state.username  = uname
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")

    with tab_reg:
        new_uname = st.text_input("Choose Username", key="r_uname")
        new_pwd   = st.text_input("Choose Password", type="password", key="r_pwd")

        st.markdown("**Register as:**")
        reg_col1, reg_col2 = st.columns(2)

        def _do_register(reg_role: str):
            if len(new_pwd) < 6:
                st.error("Password must be at least 6 characters.")
            elif not new_uname.strip():
                st.error("Username cannot be empty.")
            elif register_user(new_uname.strip(), new_pwd, reg_role):
                st.success(f"✅ Registered as **{reg_role}**! Please login.")
            else:
                st.error("Username already exists.")

        with reg_col1:
            if st.button("🎓 Register as Student", type="primary", use_container_width=True):
                _do_register("student")

        with reg_col2:
            if st.button("🛡️ Register as Admin", type="secondary", use_container_width=True):
                _do_register("admin")


# ============================================================
# MAIN APP  (shown only after login)
# ============================================================
def show_main_app():
    role     = st.session_state.role
    username = st.session_state.username

    # Sidebar nav
    if role == "admin":
        menu_options = ["HR: Create Drive", "TPO: Dashboard"]
    else:
        menu_options = ["Student: Apply & Track"]

    menu_options.append("Logout")
    st.sidebar.markdown(f"👤 **{username}** `({role})`")
    choice = st.sidebar.selectbox("Navigate System", menu_options)

    if choice == "Logout":
        st.session_state.logged_in = False
        st.session_state.role      = None
        st.session_state.username  = None
        st.rerun()

    # ──────────────────────────────────────────────────────
    # HR VIEW
    # ──────────────────────────────────────────────────────
    if choice == "HR: Create Drive":
        st.header("📢 Create a New Placement Drive")
        company = st.text_input("Company Name")
        role_in = st.text_input("Job Role")
        jd      = st.text_area("Job Description")

        if st.button("Post Drive", type="primary"):
            if company and role_in and jd:
                conn = sqlite3.connect('placement.db')
                conn.cursor().execute(
                    "INSERT INTO jobs (role, company, jd) VALUES (?,?,?)",
                    (role_in, company, jd)
                )
                conn.commit()
                conn.close()
                st.success(f"Drive for {company} posted!")
            else:
                st.error("Please fill all fields.")

    # ──────────────────────────────────────────────────────
    # STUDENT VIEW
    # ──────────────────────────────────────────────────────
    elif choice == "Student: Apply & Track":
        st.header("📝 Student Portal")
        tab1, tab2, tab3 = st.tabs(["Apply Now", "Track My Status", "💡 Job Recommendations"])

        # ── Tab 1: Apply ──
        with tab1:
            conn    = sqlite3.connect('placement.db')
            jobs_df = pd.read_sql_query("SELECT * FROM jobs", conn)
            conn.close()

            if not jobs_df.empty:
                job_options  = {f"{r['company']} - {r['role']}": r['id']
                                for _, r in jobs_df.iterrows()}
                selected_job = st.selectbox("Select Drive", list(job_options.keys()))
                name         = st.text_input("Your Full Name")

                # FEATURE 3: validated uploader
                file = st.file_uploader("Upload Resume (PDF, max 10 MB)", type=["pdf"])

                if st.button("Submit Application", type="primary"):
                    is_valid, err_msg = validate_resume(file)
                    if not is_valid:
                        st.error(err_msg)
                    elif not name:
                        st.error("Please enter your name.")
                    else:
                        reader = PdfReader(file)
                        text   = "".join([p.extract_text() or "" for p in reader.pages])

                        # FEATURE 4: save file to disk
                        resume_path = save_resume_file(file, name)

                        target_jd   = jobs_df[
                            jobs_df['id'] == job_options[selected_job]
                        ]['jd'].values[0]

                        with st.spinner("AI analysing your profile..."):
                            sector, govt_score, (found, missing) = detect_best_sector(text)
                            result = screen_with_gemini(text, target_jd)
                            try:
                                gemini_score = int(
                                    ''.join(filter(str.isdigit, result.split('\n')[0]))
                                )
                            except Exception:
                                gemini_score = 50

                            final_score = int((govt_score * 0.7) + (gemini_score * 0.3))
                            prob        = calculate_placement_probability(final_score, govt_score)
                            label       = get_probability_label(prob)
                            tips        = get_improvement_suggestions(missing, sector)

                            feedback_text = (
                                f"{result}\n\nSector: {sector}\n"
                                f"Skills Found: {found}\nMissing: {missing}"
                            )

                            conn = sqlite3.connect('placement.db')
                            conn.cursor().execute(
                                """INSERT INTO applications
                                   (student_name, job_id, resume_text, ai_score, feedback,
                                    sector, sector_match_score, placement_probability, resume_path)
                                   VALUES (?,?,?,?,?,?,?,?,?)""",
                                (name, job_options[selected_job], text,
                                 final_score, feedback_text,
                                 sector, govt_score, prob, resume_path)
                            )
                            conn.commit()
                            conn.close()

                        st.balloons()
                        st.success("Application submitted!")

                        st.markdown(f"""
### 🎯 National Readiness Report

| Metric | Value |
|---|---|
| **Sector Fit** | {sector} |
| **Hybrid Score** | {final_score}/100 |
| **Sector Match Score** | {govt_score}/100 |
| **Placement Probability** | {prob}% — **{label}** |

**✅ Skills Found:** {', '.join(found) if found else 'None'}

**❌ Missing Skills:** {', '.join(missing) if missing else 'None'}
""")
                        if tips:
                            st.subheader("📌 How to Improve Your Probability")
                            for tip in tips:
                                st.markdown(f"- {tip}")
            else:
                st.warning("No active drives yet.")

        # ── Tab 2: Track ──
        with tab2:
            st.subheader("🔍 Your Application Journey")
            search = st.text_input("Enter your name to track")

            if search:
                conn = sqlite3.connect('placement.db')
                res  = pd.read_sql_query(f"""
                    SELECT a.id, a.ai_score, a.feedback, j.company, j.role,
                           a.status, a.sector, a.sector_match_score,
                           a.placement_probability, a.contract_accepted
                    FROM applications a
                    JOIN jobs j ON a.job_id = j.id
                    WHERE a.student_name LIKE '%{search}%'
                """, conn)
                conn.close()

                if not res.empty:
                    for _, row in res.iterrows():
                        with st.expander(f"📌 {row['company']} - {row['role']}", expanded=True):
                            stages         = ["Applied","Screened","Shortlisted","Interview","Offered"]
                            current_status = row['status'] if row['status'] else "Applied"
                            current_idx    = stages.index(current_status) if current_status in stages else 0

                            st.write(f"**Current Stage:** `{current_status}`")
                            st.progress((current_idx + 1) / len(stages))

                            if current_status == "Applied":
                                st.info("Your resume is in the queue for AI Screening.")
                            elif current_status == "Screened":
                                st.success(f"AI Score: {row['ai_score']}/100. TPO is reviewing.")

                            prob  = row['placement_probability'] or 0
                            label = get_probability_label(prob)
                            st.metric("📊 Placement Probability", f"{prob}%", label)
                            st.write(
                                f"**🏢 Sector:** {row['sector']}  |  "
                                f"**Sector Match:** {row['sector_match_score']}/100"
                            )

                            if current_status == "Offered":
                                st.divider()
                                st.subheader("📄 Your Placement Contract")
                                if row['contract_accepted']:
                                    st.success("✅ Contract already accepted.")
                                else:
                                    st.code(generate_contract(search, row['company'], row['role']),
                                            language=None)
                                    if st.button(f"✅ Accept Contract (ID: {row['id']})",
                                                 key=f"accept_{row['id']}"):
                                        accept_contract(row['id'])
                                        st.success("🎉 Contract accepted! Welcome aboard.")
                                        st.balloons()
                                        st.rerun()

                            st.write(f"**AI Insights:** {row['feedback']}")
                else:
                    st.info("No application found.")

        # ── Tab 3: Job Recommendations (Feature 1) ──
        with tab3:
            st.subheader("💡 Recommended Jobs for You")
            st.info("Upload your resume once so we can match you to the best open roles.")

            rec_file = st.file_uploader("Upload Resume for Recommendations (PDF)",
                                        type=["pdf"], key="rec_file")

            if rec_file:
                is_valid, err_msg = validate_resume(rec_file)
                if not is_valid:
                    st.error(err_msg)
                else:
                    rec_reader = PdfReader(rec_file)
                    rec_text   = "".join([p.extract_text() or "" for p in rec_reader.pages])
                    recs       = get_job_recommendations(rec_text)

                    if recs:
                        for r in recs:
                            bar_color = "#4CAF50" if r['match_pct'] >= 60 else \
                                        "#FF9800" if r['match_pct'] >= 30 else "#F44336"
                            st.markdown(f"""
<div style="border:1px solid #444;border-radius:8px;padding:12px;margin-bottom:10px;">
<b>🏢 {r['company']}</b> &nbsp;|&nbsp; 🎯 <b>{r['role']}</b><br>
<div style="background:#222;border-radius:4px;height:14px;margin-top:8px;">
  <div style="background:{bar_color};width:{r['match_pct']}%;height:14px;border-radius:4px;"></div>
</div>
<small>Match Score: <b>{r['match_pct']}%</b></small>
</div>
""", unsafe_allow_html=True)
                    else:
                        st.warning("No open drives found. Ask your TPO to post drives first.")

    # ──────────────────────────────────────────────────────
    # TPO / ADMIN DASHBOARD
    # ──────────────────────────────────────────────────────
    elif choice == "TPO: Dashboard":
        st.header("📊 Placement Control Center")

        conn = sqlite3.connect('placement.db')
        apps = pd.read_sql_query("""
            SELECT a.id, a.student_name, j.company, j.role,
                   a.ai_score, a.status, a.feedback,
                   a.sector, a.sector_match_score,
                   a.placement_probability, a.contract_accepted, a.resume_path
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            ORDER BY a.ai_score DESC
        """, conn)
        conn.close()

        if not apps.empty:

            # ── Feature 7: Doughnut Charts ──
            st.subheader("📊 Visual Analytics")
            chart_col1, chart_col2, chart_col3 = st.columns(3)

            with chart_col1:
                placed     = len(apps[apps['status'] == 'Offered'])
                not_placed = len(apps) - placed
                st.plotly_chart(
                    doughnut_chart(["Placed","Not Placed"], [placed, not_placed],
                                   "Placement Status"),
                    use_container_width=True
                )

            with chart_col2:
                sec_dist   = apps['sector'].value_counts()
                st.plotly_chart(
                    doughnut_chart(sec_dist.index.tolist(), sec_dist.values.tolist(),
                                   "Sector Distribution"),
                    use_container_width=True
                )

            with chart_col3:
                status_dist = apps['status'].fillna("Applied").value_counts()
                st.plotly_chart(
                    doughnut_chart(status_dist.index.tolist(), status_dist.values.tolist(),
                                   "Application Stages"),
                    use_container_width=True
                )

            st.divider()

            # ── Feature 1 UI: Sector Filter + Auto-Shortlist ──
            st.subheader("🎯 Filter Candidates by Sector")
            all_sectors   = ["All"] + list(SECTOR_RULES.keys())
            sector_filter = st.selectbox("Select Sector", all_sectors)

            filtered_apps = apps.copy()
            if sector_filter != "All":
                filtered_apps = filtered_apps[
                    filtered_apps['sector'].str.contains(sector_filter, case=False, na=False)
                ]

            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(
                    f"Showing **{len(filtered_apps)}** candidates"
                    + (f" in *{sector_filter}*" if sector_filter != "All" else "")
                )
            with col_b:
                if st.button("⚡ Auto Shortlist by Sector", type="primary"):
                    n = auto_shortlist_by_sector(SHORTLIST_THRESHOLD)
                    st.success(f"✅ {n} candidates auto-shortlisted (score ≥ {SHORTLIST_THRESHOLD})")
                    st.rerun()

            display_cols = ["id","student_name","company","role",
                            "sector","sector_match_score","ai_score",
                            "placement_probability","status","contract_accepted"]
            st.dataframe(filtered_apps[display_cols], use_container_width=True)

            st.divider()

            # ── Feature 4: Resume Access ──
            st.subheader("📂 Student Resume Access")
            resume_apps = apps[apps['resume_path'].notna() & (apps['resume_path'] != '')]

            if not resume_apps.empty:
                for _, row in resume_apps.iterrows():
                    r_col1, r_col2, r_col3 = st.columns([3, 1, 1])
                    with r_col1:
                        st.write(f"**{row['student_name']}** — {row['company']} / {row['role']}")
                    with r_col2:
                        resume_bytes = get_resume_bytes(row['resume_path'])
                        if resume_bytes:
                            st.download_button(
                                "⬇️ Download",
                                data=resume_bytes,
                                file_name=os.path.basename(row['resume_path']),
                                mime="application/pdf",
                                key=f"dl_{row['id']}"
                            )
                    with r_col3:
                        st.write(f"`{os.path.basename(row['resume_path']) if row['resume_path'] else 'N/A'}`")
            else:
                st.info("No resumes stored yet.")

            st.divider()

            # ── Probability Distribution ──
            st.subheader("📈 Placement Probability Distribution")
            def label_prob(p):
                if p >= 75: return "High"
                elif p >= 50: return "Medium"
                else: return "Low"

            if 'placement_probability' in apps.columns:
                prob_dist = apps['placement_probability'].dropna().apply(label_prob).value_counts()
                st.bar_chart(prob_dist)

            st.divider()

            # ── Top Candidates ──
            st.subheader("🏆 Top Candidates")
            st.dataframe(
                filtered_apps.sort_values("ai_score", ascending=False).head(5)[display_cols],
                use_container_width=True
            )

            st.divider()

            # ── Skill Gap ──
            st.subheader("📉 Skill Gap Insights")
            missing_skills = []
            for feedback in apps['feedback']:
                if "Missing:" in str(feedback):
                    part   = feedback.split("Missing:")[-1]
                    skills = part.replace("[","").replace("]","").replace("'","").split(",")
                    missing_skills.extend([s.strip() for s in skills if s.strip()])
            if missing_skills:
                st.bar_chart(pd.Series(missing_skills).value_counts().head(10))
            else:
                st.info("No missing skill data yet.")

            st.divider()

            # ── Management ──
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("🛠️ Update Stage")
                target_id = st.selectbox("Select Student ID", apps['id'].tolist())
                update_to = st.selectbox(
                    "Update Stage",
                    ["Applied","Screened","Shortlisted","Interview","Offered"]
                )
                if st.button("Update Status", type="secondary"):
                    db_conn = sqlite3.connect('placement.db')
                    db_conn.cursor().execute(
                        "UPDATE applications SET status=? WHERE id=?", (update_to, target_id)
                    )
                    db_conn.commit()
                    db_conn.close()
                    st.rerun()

            # ── Feature 2: Smart Mailer ──
            with col2:
                st.subheader("📧 Smart Mailer")

                candidate_row = apps[apps['id'] == target_id].iloc[0]

                template_choice = st.selectbox(
                    "Select Email Template",
                    list(EMAIL_TEMPLATES.keys())
                )
                to_email = st.text_input("Recipient Email Address")

                subj, body = fill_template(
                    template_choice,
                    name=candidate_row['student_name'],
                    company=candidate_row['company'],
                    role=candidate_row['role']
                )

                st.text_input("Subject (auto-filled)", value=subj, key="email_subject")
                edited_body = st.text_area("Email Body (editable)", value=body, height=200)

                send_col1, send_col2 = st.columns(2)

                with send_col1:
                    if st.button("📤 Send Mail", type="primary"):
                        if to_email:
                            ok = send_email(to_email, subj, edited_body)
                            if ok:
                                st.success(f"✅ Email sent to {to_email}")
                        else:
                            st.error("Enter recipient email.")

                with send_col2:
                    if st.button("🤖 AI Draft", type="secondary"):
                        prompt = (
                            f"Write a professional {template_choice} email for "
                            f"{candidate_row['student_name']} for the role of "
                            f"{candidate_row['role']} at {candidate_row['company']}."
                        )
                        with st.spinner("AI drafting..."):
                            try:
                                genai.configure(api_key=GEMINI_API_KEY)
                                model     = genai.GenerativeModel('gemini-1.5-flash')
                                response  = model.generate_content(prompt)
                                st.text_area("AI Draft", value=response.text, height=200)
                            except Exception:
                                st.warning("AI busy — use the template above.")

            # ── Contract Tracker ──
            st.divider()
            st.subheader("📄 Contract Acceptance Tracker")
            offered = apps[apps['status'] == "Offered"][
                ["id","student_name","company","role","contract_accepted"]
            ].copy()

            if not offered.empty:
                offered['contract_accepted'] = offered['contract_accepted'].map(
                    {1: "✅ Accepted", 0: "⏳ Pending"}
                )
                st.dataframe(offered, use_container_width=True)
            else:
                st.info("No candidates at 'Offered' stage yet.")

        else:
            st.info("No applications received yet.")


# ============================================================
# 8. ENTRY POINT
# ============================================================
if not st.session_state.logged_in:
    show_auth_page()
else:
    show_main_app()