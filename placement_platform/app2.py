import streamlit as st
import sqlite3
import pandas as pd
import random
import google.generativeai as genai
from PyPDF2 import PdfReader
from datetime import date

# ============================================================
# 1. CONFIGURATION
# ============================================================
GEMINI_API_KEY = "AIzaSyBQMT4d3cbSSq-6cR-vmStMGzDA7A4vBx4"

# ── Expanded Sector Rules (Feature 1 extends original 3 sectors + adds new ones)
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

# Shortlisting threshold (auto-shortlist if sector_match_score >= this)
SHORTLIST_THRESHOLD = 40


# ============================================================
# 2. DATABASE ENGINE  (new columns added safely)
# ============================================================
def init_db():
    conn = sqlite3.connect('placement.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY, role TEXT, company TEXT, jd TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS applications
                 (id INTEGER PRIMARY KEY, student_name TEXT, job_id INTEGER,
                  resume_text TEXT, ai_score INTEGER, feedback TEXT, status TEXT,
                  sector TEXT, sector_match_score INTEGER,
                  contract_accepted INTEGER DEFAULT 0,
                  placement_probability INTEGER)''')

    # ── Safe migration: add new columns if they don't exist yet ──
    existing = [row[1] for row in c.execute("PRAGMA table_info(applications)").fetchall()]
    new_cols = {
        "sector": "TEXT",
        "sector_match_score": "INTEGER DEFAULT 0",
        "contract_accepted": "INTEGER DEFAULT 0",
        "placement_probability": "INTEGER DEFAULT 0",
    }
    for col, col_type in new_cols.items():
        if col not in existing:
            c.execute(f"ALTER TABLE applications ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()

init_db()


# ============================================================
# 3. AI CORE LOGIC  (unchanged from original)
# ============================================================
def screen_with_gemini(resume_text, job_description):
    prompt = (f"Compare Resume: {resume_text} with JD: {job_description}. "
              f"Return SCORE: [0-100] and REASON: [1 sentence].")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        st.warning("⚠️ API Rate Limit hit. Using 'Mock AI' for this demo.")
        mock_score = random.randint(70, 92)
        return (f"SCORE: {mock_score}\n"
                f"REASON: [SIMULATED] Candidate shows strong technical alignment.")


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
# FEATURE 1 — SMART SECTOR-BASED SHORTLISTING
# ============================================================
def get_sector_match_score(resume_text, sector_name):
    """Return numeric sector match score for a specific sector."""
    if sector_name not in SECTOR_RULES:
        return 0
    score, _, _ = calculate_govt_score(resume_text, SECTOR_RULES[sector_name])
    return score


def auto_shortlist_by_sector(threshold=SHORTLIST_THRESHOLD):
    """
    Auto-update status to 'Shortlisted' for candidates whose
    sector_match_score >= threshold and are still in 'Applied' stage.
    """
    conn = sqlite3.connect('placement.db')
    c = conn.cursor()
    c.execute(
        "UPDATE applications SET status = 'Shortlisted' "
        "WHERE sector_match_score >= ? AND (status = 'Applied' OR status IS NULL)",
        (threshold,)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected


# ============================================================
# FEATURE 2 — SMART CONTRACT COMMITMENT BOND
# ============================================================
def generate_contract(candidate_name, company, role):
    """Generate a text-based digital commitment contract."""
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

  1. I have been offered the position of {role} at {company}.
  2. I accept this offer in good faith and commit to joining
     on the date communicated by the company.
  3. I will not renege on this offer after acceptance.
  4. I understand that backing out may affect my institute's
     future placement relations with {company}.

ACCEPTANCE
──────────
By clicking "Accept Contract", I digitally sign and agree
to all the above terms.

                    Powered by PlaceMind AI
"""


def accept_contract(application_id):
    """Mark contract as accepted in the database."""
    conn = sqlite3.connect('placement.db')
    conn.cursor().execute(
        "UPDATE applications SET contract_accepted = 1 WHERE id = ?",
        (application_id,)
    )
    conn.commit()
    conn.close()


# ============================================================
# FEATURE 3 — PLACEMENT PROBABILITY PREDICTION
# ============================================================
def calculate_placement_probability(ai_score, sector_match_score):
    """
    Weighted rule-based placement probability.
    Weights: AI Score 60% + Sector Match 40%
    """
    ai_score = ai_score or 0
    sector_match_score = sector_match_score or 0
    probability = int((ai_score * 0.60) + (sector_match_score * 0.40))
    return min(probability, 100)


def get_probability_label(prob):
    if prob >= 75:
        return "🟢 High"
    elif prob >= 50:
        return "🟡 Medium"
    else:
        return "🔴 Low"


def get_improvement_suggestions(missing_skills, sector):
    """Return actionable suggestions based on missing skills."""
    suggestions = []

    # Generic suggestions per sector
    sector_tips = {
        "IT & Digital Governance": [
            "🔧 Build a project on GitHub to showcase your code",
            "📚 Complete a free AWS / Azure certification",
            "💻 Practice DSA on LeetCode (aim for 100+ problems)",
        ],
        "Core Engineering": [
            "🛠 Add a CAD design project to your portfolio",
            "📐 Get a SolidWorks or AutoCAD certification",
            "🔌 Work on an IoT / embedded systems mini-project",
        ],
        "Infrastructure & Green Energy": [
            "☀️ Complete the Suryamitra certification",
            "🏗 Add a BIM modelling project to your resume",
            "📊 Learn SAP basics through free online courses",
        ],
        "Public Administration": [
            "📜 Add relevant policy or governance internships",
            "🏛 Mention UPSC / state service exam preparation",
            "📊 Learn Excel / data tools for public finance analysis",
        ],
        "Management & Finance": [
            "📈 Learn Tableau or Power BI for data storytelling",
            "💼 Add an internship in sales, marketing or HR",
            "🧾 Complete a Tally / SAP basics certification",
        ],
    }

    if sector in sector_tips:
        suggestions.extend(sector_tips[sector])

    # Skill-specific nudges
    for skill in (missing_skills or [])[:3]:
        suggestions.append(f"➕ Add '{skill}' to your skill set or projects")

    return suggestions[:5]  # Return max 5 suggestions


# ============================================================
# 4. UI LAYOUT
# ============================================================
st.set_page_config(page_title="PlaceMind AI", layout="wide")

st.sidebar.markdown("""
    <div style="background-color:#FF4B4B;padding:15px;border-radius:10px;margin-bottom:20px">
    <h2 style="color:white;text-align:center;margin:0;">BHARAT-TECH X</h2>
    <p style="color:white;text-align:center;font-size:12px;">Placement Management 3.0</p>
    </div>
""", unsafe_allow_html=True)

menu = ["Student: Apply & Track", "HR: Create Drive", "TPO: Dashboard"]
choice = st.sidebar.selectbox("Navigate System", menu)


# ────────────────────────────────────────────────────────────
# HR VIEW  (unchanged)
# ────────────────────────────────────────────────────────────
if choice == "HR: Create Drive":
    st.header("📢 Create a New Placement Drive")
    company = st.text_input("Company Name")
    role    = st.text_input("Job Role")
    jd      = st.text_area("Job Description")

    if st.button("Post Drive", type="primary"):
        if company and role and jd:
            conn = sqlite3.connect('placement.db')
            conn.cursor().execute(
                "INSERT INTO jobs (role, company, jd) VALUES (?,?,?)", (role, company, jd)
            )
            conn.commit()
            st.success(f"Drive for {company} Posted!")
        else:
            st.error("Please fill all fields.")


# ────────────────────────────────────────────────────────────
# STUDENT VIEW
# ────────────────────────────────────────────────────────────
elif choice == "Student: Apply & Track":
    st.header("📝 Student Portal")
    tab1, tab2 = st.tabs(["Apply Now", "Track My Status"])

    # ── Tab 1: Apply ──
    with tab1:
        conn     = sqlite3.connect('placement.db')
        jobs_df  = pd.read_sql_query("SELECT * FROM jobs", conn)
        conn.close()

        if not jobs_df.empty:
            job_options  = {f"{r['company']} - {r['role']}": r['id']
                            for _, r in jobs_df.iterrows()}
            selected_job = st.selectbox("Select Drive", list(job_options.keys()))
            name         = st.text_input("Your Full Name")
            file         = st.file_uploader("Upload Resume (PDF)", type="pdf")

            if st.button("Submit Application", type="primary"):
                if file and name:
                    reader = PdfReader(file)
                    text   = "".join([p.extract_text() or "" for p in reader.pages])

                    target_jd = jobs_df[
                        jobs_df['id'] == job_options[selected_job]
                    ]['jd'].values[0]

                    with st.spinner("AI analysing your profile..."):
                        # ── Sector detection
                        sector, govt_score, (found, missing) = detect_best_sector(text)

                        # ── Gemini scoring
                        result = screen_with_gemini(text, target_jd)
                        try:
                            gemini_score = int(
                                ''.join(filter(str.isdigit, result.split('\n')[0]))
                            )
                        except Exception:
                            gemini_score = 50

                        # ── Hybrid final score
                        final_score = int((govt_score * 0.7) + (gemini_score * 0.3))

                        # ── Feature 3: Placement Probability
                        prob  = calculate_placement_probability(final_score, govt_score)
                        label = get_probability_label(prob)
                        tips  = get_improvement_suggestions(missing, sector)

                        feedback_text = (
                            f"{result}\n\n"
                            f"Sector: {sector}\n"
                            f"Skills Found: {found}\n"
                            f"Missing: {missing}"
                        )

                        conn = sqlite3.connect('placement.db')
                        conn.cursor().execute(
                            """INSERT INTO applications
                               (student_name, job_id, resume_text, ai_score, feedback,
                                sector, sector_match_score, placement_probability)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (name, job_options[selected_job], text,
                             final_score, feedback_text,
                             sector, govt_score, prob)
                        )
                        conn.commit()
                        conn.close()

                    st.balloons()
                    st.success("Application submitted!")

                    # ── National Readiness Report
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

                    # ── Feature 3 UI: Improvement Suggestions
                    if tips:
                        st.subheader("📌 How to Improve Your Probability")
                        for tip in tips:
                            st.markdown(f"- {tip}")
                else:
                    st.error("Upload resume and enter your name.")
        else:
            st.warning("No active drives yet.")

    # ── Tab 2: Track ──
    with tab2:
        st.subheader("🔍 Your Application Journey")
        search = st.text_input("Enter your name to track")

        if search:
            conn = sqlite3.connect('placement.db')
            query = f"""
                SELECT a.id, a.ai_score, a.feedback, j.company, j.role,
                       a.status, a.sector, a.sector_match_score,
                       a.placement_probability, a.contract_accepted
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                WHERE a.student_name LIKE '%{search}%'
            """
            res = pd.read_sql_query(query, conn)
            conn.close()

            if not res.empty:
                for _, row in res.iterrows():
                    with st.expander(f"📌 {row['company']} - {row['role']}", expanded=True):

                        # ── Journey progress
                        stages       = ["Applied", "Screened", "Shortlisted", "Interview", "Offered"]
                        current_status = row['status'] if row['status'] else "Applied"
                        current_idx    = stages.index(current_status) if current_status in stages else 0

                        st.write(f"**Current Stage:** `{current_status}`")
                        st.progress((current_idx + 1) / len(stages))

                        if current_status == "Applied":
                            st.info("Your resume is in the queue for AI Screening.")
                        elif current_status == "Screened":
                            st.success(f"AI Score: {row['ai_score']}/100. TPO is reviewing your profile.")

                        # ── Feature 3: Probability badge
                        prob  = row['placement_probability'] or 0
                        label = get_probability_label(prob)
                        st.metric("📊 Placement Probability", f"{prob}%", label)

                        # ── Sector info
                        st.write(
                            f"**🏢 Sector:** {row['sector']}  |  "
                            f"**Sector Match Score:** {row['sector_match_score']}/100"
                        )

                        # ── Feature 2: Contract Bond (shown only when Offered)
                        if current_status == "Offered":
                            st.divider()
                            st.subheader("📄 Your Placement Contract")

                            if row['contract_accepted']:
                                st.success("✅ You have already accepted this contract.")
                            else:
                                contract_text = generate_contract(
                                    search, row['company'], row['role']
                                )
                                st.code(contract_text, language=None)
                                if st.button(
                                    f"✅ Accept Contract (ID: {row['id']})",
                                    key=f"accept_{row['id']}"
                                ):
                                    accept_contract(row['id'])
                                    st.success("🎉 Contract accepted! Welcome aboard.")
                                    st.balloons()
                                    st.rerun()

                        st.write(f"**AI Insights:** {row['feedback']}")
            else:
                st.info("No application found.")


# ────────────────────────────────────────────────────────────
# TPO DASHBOARD
# ────────────────────────────────────────────────────────────
elif choice == "TPO: Dashboard":
    st.header("📊 Placement Control Center")
    conn = sqlite3.connect('placement.db')

    query = """
        SELECT a.id, a.student_name, j.company, j.role,
               a.ai_score, a.status, a.feedback,
               a.sector, a.sector_match_score,
               a.placement_probability, a.contract_accepted
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.ai_score DESC
    """
    apps = pd.read_sql_query(query, conn)
    conn.close()

    if not apps.empty:

        # ── Feature 1 UI: Sector Filter ──
        st.subheader("🎯 Filter Candidates by Sector")
        all_sectors  = ["All"] + list(SECTOR_RULES.keys())
        sector_filter = st.selectbox("Select Sector", all_sectors)

        filtered_apps = apps.copy()
        if sector_filter != "All":
            filtered_apps = filtered_apps[
                filtered_apps['sector'].str.contains(sector_filter, case=False, na=False)
            ]

        # ── Feature 1 UI: Auto-Shortlist Button ──
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

        # ── Main candidate table ──
        display_cols = ["id", "student_name", "company", "role",
                        "sector", "sector_match_score", "ai_score",
                        "placement_probability", "status", "contract_accepted"]
        st.dataframe(filtered_apps[display_cols], use_container_width=True)

        st.divider()

        # ── Feature 3 UI: Probability Distribution ──
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

        # ── Skill Gap Analysis ──
        st.subheader("📉 Skill Gap Insights")
        missing_skills = []
        for feedback in apps['feedback']:
            if "Missing:" in str(feedback):
                part   = feedback.split("Missing:")[-1]
                skills = part.replace("[","").replace("]","").replace("'","").split(",")
                missing_skills.extend([s.strip() for s in skills if s.strip()])

        if missing_skills:
            gap_df = pd.Series(missing_skills).value_counts().head(10)
            st.bar_chart(gap_df)
        else:
            st.info("No missing skill data available.")

        st.divider()

        # ── Management + Mailer ──
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🛠️ Management")
            target_id = st.selectbox("Select Student ID", apps['id'].tolist())
            update_to = st.selectbox(
                "Update Stage", ["Applied", "Screened", "Shortlisted", "Interview", "Offered"]
            )
            if st.button("Update Status", type="secondary"):
                db_conn = sqlite3.connect('placement.db')
                db_conn.cursor().execute(
                    "UPDATE applications SET status = ? WHERE id = ?", (update_to, target_id)
                )
                db_conn.commit()
                db_conn.close()
                st.rerun()

        with col2:
            st.subheader("📧 Smart Mailer")
            if st.button("Generate Interview Invite", type="primary"):
                candidate = apps[apps['id'] == target_id].iloc[0]
                prompt    = (
                    f"Write a professional interview invitation email for "
                    f"{candidate['student_name']} for the role of {candidate['role']} "
                    f"at {candidate['company']}. Mention their strong screening score."
                )
                with st.spinner("AI is drafting..."):
                    try:
                        genai.configure(api_key=GEMINI_API_KEY)
                        model     = genai.GenerativeModel('gemini-1.5-flash')
                        response  = model.generate_content(prompt)
                        email_text = response.text
                        st.text_area("Draft Email", value=email_text, height=200)
                        st.success("Email ready!")
                    except Exception:
                        st.warning("AI busy, using fallback template")
                        temp = (
                            f"Dear {candidate['student_name']},\n\n"
                            f"You are shortlisted for the role of {candidate['role']} "
                            f"at {candidate['company']}.\n\n"
                            f"Please attend the interview at [Time].\n\nRegards,\nHR Team"
                        )
                        st.text_area("Template Email", value=temp, height=200)

        # ── Feature 2 TPO View: Contract Status ──
        st.divider()
        st.subheader("📄 Contract Acceptance Tracker")
        offered = apps[apps['status'] == "Offered"][
            ["id", "student_name", "company", "role", "contract_accepted"]
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