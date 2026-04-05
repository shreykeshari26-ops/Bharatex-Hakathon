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
GEMINI_API_KEY     = "AIzaSyBQMT4d3cbSSq-6cR-vmStMGzDA7A4vBx4"
SMTP_HOST          = "smtp.gmail.com"
SMTP_PORT          = 587
SMTP_USER          = "your_email@gmail.com"
SMTP_PASSWORD      = "your_app_password"
MAX_RESUME_SIZE_MB = 10
DB_PATH            = "placement.db"
RESUME_STORE       = "resumes"

os.makedirs(RESUME_STORE, exist_ok=True)

SECTOR_RULES = {
    "IT & Digital Governance": {
        "skills": ["ai","python","cloud","cybersecurity","data analytics","machine learning",
                   "deep learning","nlp","sql","javascript","react","node","django","flask"],
        "certifications": ["aws","azure","ceh","cisa","docker","kubernetes","gcp","comptia"]
    },
    "Infrastructure & Green Energy": {
        "skills": ["solar","green hydrogen","sustainable","grid","autocad","civil",
                   "structural","electrical","mechanical","renewable","construction"],
        "certifications": ["suryamitra","bim","sap","pmp","six sigma"]
    },
    "Public Administration": {
        "skills": ["policy","law","regulation","public finance","data analytics",
                   "governance","ias","upsc","administration","compliance"],
        "certifications": ["excel","government","legal","ias coaching"]
    },
    "Core Engineering": {
        "skills": ["mechanical","civil","electrical","electronics","matlab","solidworks",
                   "catia","ansys","plc","scada","embedded","iot","robotics","vlsi"],
        "certifications": ["autocad","solidworks","plc","six sigma","pmp","iso"]
    },
    "Management & Finance": {
        "skills": ["mba","finance","marketing","sales","hr","supply chain","erp",
                   "excel","powerpoint","crm","accounting","tally","sap","tableau"],
        "certifications": ["ca","cfa","cma","pmp","google analytics","salesforce"]
    }
}

SHORTLIST_THRESHOLD = 40


# ============================================================
# 2. GLOBAL CSS
# ============================================================
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif !important;
        background-color: #0f0f13 !important;
        color: #e8e8f0 !important;
    }
    .stApp { background: #0f0f13 !important; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding: 2rem 2.5rem 3rem !important; max-width: 1400px; }

    [data-testid="stSidebar"] {
        background: #16161e !important;
        border-right: 1px solid #2a2a38 !important;
    }
    [data-testid="stSidebar"] * { color: #c8c8d8 !important; }

    h1,h2,h3 { font-family:'Syne',sans-serif !important; letter-spacing:-.02em; }
    h1 { font-size:2rem !important; font-weight:800 !important; }
    h2 { font-size:1.35rem !important; font-weight:700 !important; color:#c8b8ff !important; }
    h3 { font-size:1.05rem !important; font-weight:600 !important; }

    .stat-card {
        background:linear-gradient(135deg,#1e1e2e 0%,#1a1a28 100%);
        border:1px solid #2e2e45; border-radius:16px; padding:22px 24px;
        position:relative; overflow:hidden; transition:transform .2s, box-shadow .2s;
    }
    .stat-card:hover { transform:translateY(-3px); box-shadow:0 12px 40px rgba(120,80,255,.18); }
    .stat-card::before {
        content:''; position:absolute; top:-40px; right:-40px; width:120px; height:120px;
        border-radius:50%; background:radial-gradient(circle,rgba(120,80,255,.25),transparent 70%);
    }
    .stat-card .label { font-size:12px; color:#888; text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px; }
    .stat-card .value { font-family:'Syne',sans-serif; font-size:2.4rem; font-weight:800; color:#fff; line-height:1; }
    .stat-card .sub   { font-size:12px; color:#666; margin-top:6px; }
    .stat-card .icon  { font-size:2rem; margin-bottom:10px; }
    .stat-card.purple { border-color:#7850ff44; background:linear-gradient(135deg,#2a1f5e,#1e1e2e); }
    .stat-card.purple .value { color:#c8b8ff; }
    .stat-card.green  { border-color:#22c55e44; }
    .stat-card.green  .value { color:#86efac; }
    .stat-card.orange { border-color:#f9731644; }
    .stat-card.orange .value { color:#fdba74; }
    .stat-card.blue   { border-color:#3b82f644; }
    .stat-card.blue   .value { color:#93c5fd; }

    .section-card { background:#16161e; border:1px solid #2a2a38; border-radius:16px; padding:24px; margin-bottom:20px; }
    .section-title { font-family:'Syne',sans-serif; font-size:1rem; font-weight:700; color:#e8e8f0; margin-bottom:16px; display:flex; align-items:center; gap:8px; }

    .badge { display:inline-block; padding:3px 12px; border-radius:999px; font-size:12px; font-weight:600; }
    .badge-green  { background:#14532d; color:#86efac; border:1px solid #22c55e44; }
    .badge-blue   { background:#1e3a5f; color:#93c5fd; border:1px solid #3b82f644; }
    .badge-orange { background:#431407; color:#fdba74; border:1px solid #f9731644; }
    .badge-purple { background:#2e1065; color:#c084fc; border:1px solid #a855f744; }
    .badge-red    { background:#450a0a; color:#fca5a5; border:1px solid #ef444444; }
    .badge-gray   { background:#1f1f2e; color:#94a3b8; border:1px solid #33334a; }

    .prog-wrap { background:#1e1e2e; border-radius:999px; height:8px; margin:8px 0; overflow:hidden; }
    .prog-fill  { height:8px; border-radius:999px; background:linear-gradient(90deg,#7850ff,#a855f7); }

    .match-card { background:#1a1a28; border:1px solid #2a2a38; border-radius:12px; padding:16px 20px; margin-bottom:12px; transition:border-color .2s; }
    .match-card:hover { border-color:#7850ff88; }
    .match-bar-bg   { background:#0f0f13; border-radius:999px; height:6px; margin-top:10px; }
    .match-bar-fill { height:6px; border-radius:999px; }

    .stTextInput input, .stTextArea textarea {
        background:#1e1e2e !important; border:1px solid #2e2e45 !important;
        border-radius:10px !important; color:#e8e8f0 !important;
        font-family:'DM Sans',sans-serif !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color:#7850ff !important; box-shadow:0 0 0 3px rgba(120,80,255,.15) !important;
    }
    .stTextInput label, .stTextArea label, .stSelectbox label, .stFileUploader label {
        color:#888 !important; font-size:13px !important;
    }

    .stButton > button {
        background:linear-gradient(135deg,#7850ff,#a855f7) !important;
        color:#fff !important; border:none !important; border-radius:10px !important;
        font-family:'Syne',sans-serif !important; font-weight:600 !important;
        font-size:14px !important; padding:10px 22px !important;
        transition:opacity .2s, transform .15s !important;
    }
    .stButton > button:hover { opacity:.85 !important; transform:translateY(-1px) !important; }
    .stButton > button[kind="secondary"] {
        background:#1e1e2e !important; border:1px solid #2e2e45 !important; color:#c8b8ff !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        background:#16161e !important; border-radius:12px; padding:4px; gap:4px; border:1px solid #2a2a38;
    }
    .stTabs [data-baseweb="tab"] {
        background:transparent !important; border-radius:8px !important;
        color:#888 !important; font-family:'DM Sans',sans-serif !important;
        font-weight:500 !important; padding:8px 20px !important;
    }
    .stTabs [aria-selected="true"] {
        background:linear-gradient(135deg,#7850ff,#a855f7) !important; color:#fff !important;
    }

    .streamlit-expanderHeader {
        background:#1a1a28 !important; border-radius:10px !important;
        border:1px solid #2a2a38 !important; color:#c8b8ff !important;
        font-family:'Syne',sans-serif !important;
    }
    .streamlit-expanderContent {
        background:#16161e !important; border:1px solid #2a2a38 !important; border-top:none !important;
    }

    [data-testid="stMetric"] { background:#1a1a28; border:1px solid #2a2a38; border-radius:12px; padding:16px !important; }
    [data-testid="stMetricLabel"] { color:#888 !important; font-size:12px !important; }
    [data-testid="stMetricValue"] { color:#c8b8ff !important; font-family:'Syne',sans-serif !important; font-size:1.8rem !important; }

    .stSuccess { background:#14532d22 !important; border:1px solid #22c55e44 !important; border-radius:10px !important; }
    .stError   { background:#450a0a22 !important; border:1px solid #ef444444 !important; border-radius:10px !important; }
    .stInfo    { background:#1e3a5f22 !important; border:1px solid #3b82f644 !important; border-radius:10px !important; }
    .stWarning { background:#43140722 !important; border:1px solid #f9731644 !important; border-radius:10px !important; }

    hr { border-color:#2a2a38 !important; margin:20px 0 !important; }

    .welcome-banner {
        background:linear-gradient(135deg,#2a1f5e 0%,#1e1e2e 60%,#16161e 100%);
        border:1px solid #7850ff44; border-radius:20px; padding:28px 32px; margin-bottom:28px;
        position:relative; overflow:hidden;
    }
    .welcome-banner::after {
        content:''; position:absolute; top:-60px; right:-60px; width:220px; height:220px;
        border-radius:50%; background:radial-gradient(circle,rgba(120,80,255,.3),transparent 70%);
    }
    .welcome-banner h1 { font-size:1.8rem !important; margin:0 0 4px 0 !important; color:#fff !important; }
    .welcome-banner p  { color:#888; margin:0; font-size:14px; }

    .sidebar-brand {
        background:linear-gradient(135deg,#7850ff,#a855f7);
        border-radius:14px; padding:18px; text-align:center; margin-bottom:24px;
    }
    .sidebar-brand h2 { color:#fff !important; font-family:'Syne',sans-serif !important; font-size:1.3rem !important; margin:0 !important; }
    .sidebar-brand p  { color:rgba(255,255,255,.7); font-size:11px; margin:4px 0 0; }

    .user-pill {
        background:#1e1e2e; border:1px solid #2e2e45; border-radius:999px;
        padding:8px 16px; font-size:13px; color:#c8b8ff; display:inline-block; margin-bottom:16px;
    }

    .stage-row { display:flex; gap:6px; margin:12px 0; }
    .stage-chip { flex:1; text-align:center; padding:6px 4px; border-radius:8px; font-size:11px; font-weight:600; background:#1e1e2e; color:#555; border:1px solid #2a2a38; }
    .stage-chip.active { background:linear-gradient(135deg,#7850ff,#a855f7); color:#fff; border-color:transparent; }
    .stage-chip.done   { background:#14532d; color:#86efac; border-color:#22c55e44; }

    [data-testid="stFileUploader"] { background:#1a1a28 !important; border:2px dashed #2e2e45 !important; border-radius:12px !important; }

    .cand-table { width:100%; border-collapse:collapse; font-size:13px; }
    .cand-table th { padding:10px 14px; text-align:left; color:#555; font-weight:500; border-bottom:1px solid #2a2a38; }
    .cand-table td { padding:10px 14px; border-bottom:1px solid #1e1e2e; }
    .cand-table tr:hover td { background:#1e1e2e; }
    </style>
    """, unsafe_allow_html=True)


def stat_card(icon, label, value, sub, variant=""):
    return f"""<div class="stat-card {variant}">
        <div class="icon">{icon}</div>
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        <div class="sub">{sub}</div>
    </div>"""

def status_badge(s):
    m = {
        "Applied":    ("badge-gray",   "Applied"),
        "Screened":   ("badge-blue",   "Screened"),
        "Shortlisted":("badge-purple", "Shortlisted"),
        "Interview":  ("badge-orange", "Interview"),
        "Offered":    ("badge-green",  "✅ Offered"),
        "Rejected":   ("badge-red",    "Rejected"),
    }
    cls, lbl = m.get(s, ("badge-gray", s or "—"))
    return f'<span class="badge {cls}">{lbl}</span>'


# ============================================================
# 3. DATABASE  — single source of truth, self-healing
# ============================================================
def get_conn():
    """Return a thread-safe connection with WAL mode for reliability."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """
    Create tables if they don't exist, then add any missing columns
    (self-healing migration). Always safe to call on startup.
    """
    conn = get_conn()
    c = conn.cursor()

    # ── jobs ────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            role    TEXT NOT NULL,
            company TEXT NOT NULL,
            jd      TEXT NOT NULL
        )
    """)

    # ── applications (full authoritative schema) ────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name         TEXT    NOT NULL,
            job_id               INTEGER NOT NULL,
            resume_text          TEXT,
            ai_score             INTEGER DEFAULT 0,
            feedback             TEXT,
            status               TEXT    DEFAULT 'Applied',
            sector               TEXT,
            sector_match_score   INTEGER DEFAULT 0,
            contract_accepted    INTEGER DEFAULT 0,
            placement_probability INTEGER DEFAULT 0,
            resume_path          TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    # ── users ────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL
        )
    """)

    # ── Self-healing: add any missing columns to applications ─
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(applications)").fetchall()}
    migrations = {
        "status":                "TEXT DEFAULT 'Applied'",
        "sector":                "TEXT",
        "sector_match_score":    "INTEGER DEFAULT 0",
        "contract_accepted":     "INTEGER DEFAULT 0",
        "placement_probability": "INTEGER DEFAULT 0",
        "resume_path":           "TEXT",
        "feedback":              "TEXT",
        "ai_score":              "INTEGER DEFAULT 0",
        "resume_text":           "TEXT",
    }
    for col, defn in migrations.items():
        if col not in existing_cols:
            try:
                c.execute(f"ALTER TABLE applications ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass  # already added by a concurrent call

    # ── Default admin account ────────────────────────────────
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute(
        "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?,?,?)",
        ("admin", admin_hash, "admin")
    )

    conn.commit()
    conn.close()


# ============================================================
# 4. AUTH
# ============================================================
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def register_user(username: str, password: str, role: str) -> bool:
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
            (username.strip(), hash_pw(password), role)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def login_user(username: str, password: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT role FROM users WHERE username=? AND password_hash=?",
        (username.strip(), hash_pw(password))
    ).fetchone()
    conn.close()
    return row[0] if row else None


# ============================================================
# 5. AI CORE
# ============================================================
def screen_with_gemini(resume_text: str, jd: str) -> str:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        result = model.generate_content(
            f"Compare this Resume:\n{resume_text}\n\n"
            f"With this Job Description:\n{jd}\n\n"
            "Return exactly two lines:\n"
            "SCORE: [integer 0-100]\n"
            "REASON: [one sentence]"
        )
        return result.text
    except Exception:
        s = random.randint(65, 92)
        return f"SCORE: {s}\nREASON: [SIMULATED] Strong technical alignment with the job requirements."


def calc_govt_score(resume_text: str, rules: dict):
    rl = resume_text.lower()
    score = 0
    found, missing = [], []
    for s in rules["skills"]:
        if s in rl:
            found.append(s)
            score += 10
        else:
            missing.append(s)
    for c in rules["certifications"]:
        if c in rl:
            found.append(c)
            score += 15
        else:
            missing.append(c)
    return min(score, 100), found, missing


def detect_best_sector(resume_text: str):
    best_sector, best_score, best_fm = None, 0, ([], [])
    for sector, rules in SECTOR_RULES.items():
        sc, f, m = calc_govt_score(resume_text, rules)
        if sc > best_score:
            best_sector, best_score, best_fm = sector, sc, (f, m)
    if best_sector is None:
        best_sector = "IT & Digital Governance"
        best_fm = ([], [])
    return best_sector, best_score, best_fm


def get_recs(resume_text: str, top_n: int = 5):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM jobs", conn)
    conn.close()
    if df.empty:
        return []
    rl = resume_text.lower()
    results = []
    for _, job in df.iterrows():
        jw = set(job["jd"].lower().split())
        rw = set(rl.split())
        pct = min(int((len(jw & rw) / max(len(jw), 1)) * 300), 100)
        results.append({
            "job_id":    job["id"],
            "role":      job["role"],
            "company":   job["company"],
            "match_pct": pct,
        })
    return sorted(results, key=lambda x: x["match_pct"], reverse=True)[:top_n]


def parse_ai_score(text: str) -> int:
    """Safely extract integer score from Gemini response."""
    try:
        for line in text.splitlines():
            if "SCORE" in line.upper():
                digits = "".join(filter(str.isdigit, line))
                if digits:
                    return min(int(digits), 100)
    except Exception:
        pass
    return 50


# ============================================================
# 6. FEATURES
# ============================================================
EMAIL_TEMPLATES = {
    "Interview Invite": {
        "subject": "Interview Invitation – {role} at {company}",
        "body": (
            "Dear {name},\n\n"
            "Congratulations! You have been shortlisted for {role} at {company}.\n\n"
            "Please attend the interview on the date communicated by HR. "
            "Carry a copy of your resume.\n\n"
            "Best regards,\nPlaceMind AI | HR Team"
        ),
    },
    "Selection Offer": {
        "subject": "Offer Letter – {role} at {company}",
        "body": (
            "Dear {name},\n\n"
            "We are delighted to inform you that you have been selected for {role} at {company}.\n\n"
            "Your joining details will be shared shortly.\n\n"
            "Warm regards,\nPlaceMind AI | HR Team"
        ),
    },
    "Rejection Mail": {
        "subject": "Application Update – {role} at {company}",
        "body": (
            "Dear {name},\n\n"
            "Thank you for applying for {role} at {company}. "
            "After careful review we will not be moving forward at this time.\n\n"
            "We encourage you to apply for future openings.\n\n"
            "Best wishes,\nPlaceMind AI | HR Team"
        ),
    },
}


def fill_template(key: str, name: str, company: str, role: str):
    t = EMAIL_TEMPLATES[key]
    return (
        t["subject"].format(name=name, company=company, role=role),
        t["body"].format(name=name, company=company, role=role),
    )


def send_email(to: str, subj: str, body: str) -> bool:
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to
        msg["Subject"] = subj
        msg.attach(MIMEText(body, "plain"))
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, to, msg.as_string())
        s.quit()
        return True
    except Exception as e:
        st.error(f"SMTP Error: {e}")
        return False


def validate_resume(f) -> tuple:
    if not f:
        return False, "No file uploaded."
    if not f.name.lower().endswith(".pdf"):
        return False, "❌ Only PDF files are allowed."
    if f.size / 1024 / 1024 > MAX_RESUME_SIZE_MB:
        return False, f"❌ File too large. Limit is {MAX_RESUME_SIZE_MB} MB."
    return True, ""


def save_resume(f, name: str) -> str:
    safe_name = name.replace(" ", "_").replace("/", "_")
    path = os.path.join(RESUME_STORE, f"{safe_name}_{date.today()}.pdf")
    with open(path, "wb") as fp:
        fp.write(f.getbuffer())
    return path


def get_resume_bytes(path: str):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def extract_pdf_text(uploaded_file) -> str:
    try:
        reader = PdfReader(uploaded_file)
        return "".join([page.extract_text() or "" for page in reader.pages])
    except Exception:
        return ""


def auto_shortlist(threshold: int = SHORTLIST_THRESHOLD) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """UPDATE applications
           SET status='Shortlisted'
           WHERE sector_match_score >= ?
             AND (status='Applied' OR status IS NULL)""",
        (threshold,)
    )
    n = c.rowcount
    conn.commit()
    conn.close()
    return n


def gen_contract(name: str, company: str, role: str) -> str:
    ref = abs(hash(name + company + role)) % 100000
    return (
        f"PLACEMENT COMMITMENT BOND — PLACEMIND AI\n"
        f"Date      : {date.today().strftime('%d %B %Y')}   "
        f"Ref #     : PCB-{ref:05d}\n"
        f"Candidate : {name}   Company : {company}   Role : {role}\n\n"
        f"I, {name}, hereby confirm that:\n"
        f"  1. I accept this offer in good faith and commit to joining.\n"
        f"  2. I will not renege after acceptance.\n"
        f"  3. Backing out may affect institute–company relations.\n\n"
        f"By clicking 'Accept Contract' I digitally sign these terms.\n"
        f"                    Powered by PlaceMind AI"
    )


def accept_contract(app_id: int):
    conn = get_conn()
    conn.execute("UPDATE applications SET contract_accepted=1 WHERE id=?", (app_id,))
    conn.commit()
    conn.close()


def calc_prob(ai_score, sec_score) -> int:
    return min(int((ai_score or 0) * 0.6 + (sec_score or 0) * 0.4), 100)


def prob_lbl(p) -> str:
    p = p or 0
    return "🟢 High" if p >= 75 else "🟡 Medium" if p >= 50 else "🔴 Low"


def tips(missing: list, sector: str) -> list:
    sector_tips = {
        "IT & Digital Governance": [
            "🔧 Build a GitHub project",
            "📚 Get AWS/Azure certified",
            "💻 Practice DSA on LeetCode",
        ],
        "Core Engineering": [
            "🛠 Add a CAD portfolio project",
            "📐 Get SolidWorks certified",
            "🔌 Build an IoT project",
        ],
        "Infrastructure & Green Energy": [
            "☀️ Complete Suryamitra certification",
            "🏗 Add a BIM project",
            "📊 Learn SAP basics",
        ],
        "Public Administration": [
            "📜 Add governance internships",
            "🏛 Note UPSC preparation experience",
            "📊 Learn Excel for public finance",
        ],
        "Management & Finance": [
            "📈 Learn Tableau or Power BI",
            "💼 Add an HR/sales internship",
            "🧾 Complete Tally/SAP basics",
        ],
    }
    out = list(sector_tips.get(sector, []))
    for sk in (missing or [])[:3]:
        out.append(f"➕ Add '{sk}' to your skill set")
    return out[:5]


# ============================================================
# 7. CHARTS
# ============================================================
CHART_COLORS = ["#7850ff", "#a855f7", "#22c55e", "#f59e0b", "#3b82f6", "#ec4899"]

def doughnut(labels, values, title):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        textinfo="label+percent",
        marker=dict(colors=CHART_COLORS, line=dict(color="#0f0f13", width=2))
    ))
    fig.update_layout(
        title_text=title,
        title_font=dict(color="#c8b8ff", family="Syne", size=14),
        showlegend=False,
        margin=dict(t=40, b=10, l=10, r=10),
        height=260,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#888", family="DM Sans"),
    )
    return fig


# ============================================================
# 8. SESSION STATE + PAGE CONFIG
# ============================================================
def init_session():
    for key, default in [("logged_in", False), ("role", None), ("username", None)]:
        if key not in st.session_state:
            st.session_state[key] = default


# ============================================================
# 9. AUTH PAGE
# ============================================================
def show_auth():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:40px 0 32px;">
          <div style="font-family:'Syne',sans-serif;font-size:2.4rem;font-weight:800;
                      background:linear-gradient(135deg,#c8b8ff,#7850ff);
                      -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            PlaceMind AI
          </div>
          <div style="color:#444;font-size:14px;margin-top:8px;">India's Smartest Placement Platform</div>
        </div>""", unsafe_allow_html=True)

        tab_l, tab_r = st.tabs(["🔐  Login", "✨  Register"])

        with tab_l:
            st.markdown("<br>", unsafe_allow_html=True)
            uname = st.text_input("Username", placeholder="Enter username", key="lu")
            pwd   = st.text_input("Password", type="password", placeholder="••••••••", key="lp")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Login →", type="primary", use_container_width=True):
                role = login_user(uname, pwd)
                if role:
                    st.session_state.logged_in = True
                    st.session_state.role      = role
                    st.session_state.username  = uname
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials.")
            st.markdown(
                '<div style="text-align:center;margin-top:10px;font-size:12px;color:#333;">'
                'Default admin: <code style="color:#c8b8ff">admin / admin123</code></div>',
                unsafe_allow_html=True
            )

        with tab_r:
            st.markdown("<br>", unsafe_allow_html=True)
            nu = st.text_input("Choose Username", placeholder="e.g. rahul_sharma", key="ru")
            np_ = st.text_input("Choose Password", type="password", placeholder="Min 6 characters", key="rp")
            st.markdown("<br>**Register as:**")
            rc1, rc2 = st.columns(2)

            def _reg(rl):
                if len(np_) < 6:
                    st.error("Password must be ≥ 6 characters.")
                elif not nu.strip():
                    st.error("Username cannot be empty.")
                elif register_user(nu.strip(), np_, rl):
                    st.success(f"✅ Registered as **{rl}**! Please login.")
                else:
                    st.error("Username already taken.")

            with rc1:
                if st.button("🎓 Student", use_container_width=True):
                    _reg("student")
            with rc2:
                if st.button("🛡️ Admin", type="secondary", use_container_width=True):
                    _reg("admin")


# ============================================================
# 10. MAIN APP
# ============================================================
def show_app():
    role     = st.session_state.role
    username = st.session_state.username

    nav = (
        ["HR: Create Drive", "TPO: Dashboard"] if role == "admin"
        else ["Student: Apply & Track"]
    ) + ["Logout"]

    st.sidebar.markdown(
        f'<div class="user-pill">👤 {username} · {role}</div>',
        unsafe_allow_html=True
    )
    choice = st.sidebar.selectbox("Navigation", nav)

    # ── LOGOUT ──────────────────────────────────────────────
    if choice == "Logout":
        st.session_state.logged_in = False
        st.session_state.role      = None
        st.session_state.username  = None
        st.rerun()

    # ── HR: CREATE DRIVE ────────────────────────────────────
    elif choice == "HR: Create Drive":
        st.markdown(
            '<div class="welcome-banner"><h1>📢 Post a Placement Drive</h1>'
            '<p>Create new job openings for students to apply and get AI-matched.</p></div>',
            unsafe_allow_html=True
        )
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        company = st.text_input("Company Name", placeholder="e.g. Infosys, DRDO, BHEL")
        role_in = st.text_input("Job Role",     placeholder="e.g. Software Engineer")
        jd      = st.text_area("Job Description", height=180,
                               placeholder="Describe required skills and responsibilities...")
        if st.button("🚀 Post Drive", type="primary"):
            if company and role_in and jd:
                conn = get_conn()
                conn.execute(
                    "INSERT INTO jobs (role, company, jd) VALUES (?,?,?)",
                    (role_in.strip(), company.strip(), jd.strip())
                )
                conn.commit()
                conn.close()
                st.success(f"✅ Drive posted for **{company}**!")
            else:
                st.error("Please fill all fields.")
        st.divider()
        st.markdown("#### 📋 Active Drives")
        conn = get_conn()
        df = pd.read_sql_query("SELECT id, company, role, jd FROM jobs", conn)
        conn.close()
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No drives posted yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── STUDENT PORTAL ───────────────────────────────────────
    elif choice == "Student: Apply & Track":
        conn = get_conn()
        my_apps = pd.read_sql_query(
            """SELECT a.id, a.student_name, a.ai_score, a.feedback,
                      a.status, a.sector, a.sector_match_score,
                      a.placement_probability, a.contract_accepted,
                      j.company, j.role
               FROM applications a
               JOIN jobs j ON a.job_id = j.id
               WHERE a.student_name LIKE ?""",
            conn, params=(f"%{username}%",)
        )
        conn.close()

        # Ensure status column always exists and has sane values
        if "status" not in my_apps.columns:
            my_apps["status"] = "Applied"
        my_apps["status"] = my_apps["status"].fillna("Applied")

        total     = len(my_apps)
        active    = len(my_apps[~my_apps["status"].isin(["Offered", "Rejected"])])
        interview = len(my_apps[my_apps["status"] == "Interview"])
        offered   = len(my_apps[my_apps["status"] == "Offered"])

        st.markdown(
            f'<div class="welcome-banner"><h1>Welcome Back, {username.title()}! 👋</h1>'
            f'<p>Your career journey starts here. Track and manage your applications seamlessly.</p></div>',
            unsafe_allow_html=True
        )

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(stat_card("📤", "Total Applications", total,    "All submitted",  "purple"), unsafe_allow_html=True)
        with c2: st.markdown(stat_card("🔄", "Active Applications", active,  "In progress",    "blue"),   unsafe_allow_html=True)
        with c3: st.markdown(stat_card("🗓️", "Waiting Interview",  interview,"In queue",       "orange"), unsafe_allow_html=True)
        with c4: st.markdown(stat_card("🎉", "Offers Received",    offered,  "From employers", "green"),  unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        t1, t2, t3 = st.tabs(["📤  Apply Now", "🔍  Track Status", "💡  Job Matches"])

        # ── Apply Now ──────────────────────────────────────
        with t1:
            conn = get_conn()
            jdf = pd.read_sql_query("SELECT id, company, role, jd FROM jobs", conn)
            conn.close()

            if not jdf.empty:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                jopts = {f"{r['company']} — {r['role']}": r['id'] for _, r in jdf.iterrows()}
                sel   = st.selectbox("Select Drive", list(jopts.keys()))
                name  = st.text_input("Your Full Name", placeholder="e.g. Priya Sharma")
                file  = st.file_uploader("Upload Resume (PDF · Max 10 MB)", type=["pdf"])

                if st.button("🚀 Submit Application", type="primary"):
                    ok, err = validate_resume(file)
                    if not ok:
                        st.error(err)
                    elif not name.strip():
                        st.error("Enter your full name.")
                    else:
                        resume_text = extract_pdf_text(file)
                        rpath       = save_resume(file, name.strip())
                        tjd         = jdf[jdf["id"] == jopts[sel]]["jd"].values[0]

                        with st.spinner("🤖 AI is analysing your profile..."):
                            sector, gscore, (found, missing) = detect_best_sector(resume_text)
                            ai_result  = screen_with_gemini(resume_text, tjd)
                            gscore_ai  = parse_ai_score(ai_result)
                            final      = int(gscore * 0.7 + gscore_ai * 0.3)
                            prob       = calc_prob(final, gscore)
                            lbl        = prob_lbl(prob)
                            suggestion = tips(missing, sector)
                            feedback   = (
                                f"{ai_result}\n\n"
                                f"Sector: {sector}\n"
                                f"Found: {found}\n"
                                f"Missing: {missing}"
                            )

                        # ── Insert with ALL columns ──────
                        conn = get_conn()
                        conn.execute(
                            """INSERT INTO applications
                               (student_name, job_id, resume_text, ai_score, feedback,
                                status, sector, sector_match_score,
                                placement_probability, resume_path)
                               VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (
                                name.strip(), jopts[sel], resume_text,
                                final, feedback, "Applied",
                                sector, gscore, prob, rpath
                            )
                        )
                        conn.commit()
                        conn.close()

                        st.balloons()
                        st.success("✅ Application submitted successfully!")

                        # Report card
                        prob_color  = "#86efac" if prob >= 75 else "#fdba74" if prob >= 50 else "#fca5a5"
                        found_badges = "".join(
                            [f'<span class="badge badge-green">{s}</span> ' for s in found[:8]]
                        ) or '<span style="color:#444">None detected</span>'

                        st.markdown(f"""
                        <div style="background:#1a1a28;border:1px solid #2a2a38;border-radius:14px;padding:24px;margin-top:16px;">
                          <div style="font-family:'Syne',sans-serif;font-size:1.05rem;font-weight:700;color:#c8b8ff;margin-bottom:16px;">🎯 National Readiness Report</div>
                          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
                            <div style="background:#0f0f13;border-radius:10px;padding:14px;">
                              <div style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Sector Fit</div>
                              <div style="color:#c8b8ff;font-weight:600;">{sector}</div>
                            </div>
                            <div style="background:#0f0f13;border-radius:10px;padding:14px;">
                              <div style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Hybrid Score</div>
                              <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;color:#fff;">{final}<span style="font-size:.85rem;color:#555">/100</span></div>
                            </div>
                            <div style="background:#0f0f13;border-radius:10px;padding:14px;">
                              <div style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Sector Match</div>
                              <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;color:#86efac;">{gscore}<span style="font-size:.85rem;color:#555">/100</span></div>
                            </div>
                            <div style="background:#0f0f13;border-radius:10px;padding:14px;">
                              <div style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Placement Probability</div>
                              <div style="font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;color:{prob_color};">{prob}%</div>
                              <div style="font-size:12px;color:#666;margin-top:2px;">{lbl}</div>
                            </div>
                          </div>
                          <div style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">Skills Found</div>
                          <div>{found_badges}</div>
                        </div>""", unsafe_allow_html=True)

                        if suggestion:
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.markdown(
                                '<div class="section-card">'
                                '<div class="section-title">📌 How to Improve Your Probability</div>',
                                unsafe_allow_html=True
                            )
                            for tip in suggestion:
                                st.markdown(f"- {tip}")
                            st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("No active placement drives yet. Please check back later.")

        # ── Track Status ───────────────────────────────────
        with t2:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            search = st.text_input("🔍 Search by name", placeholder="Enter your full name...", key="trk")
            if search:
                conn = get_conn()
                res = pd.read_sql_query(
                    """SELECT a.id, a.ai_score, a.feedback, j.company, j.role,
                              a.status, a.sector, a.sector_match_score,
                              a.placement_probability, a.contract_accepted
                       FROM applications a
                       JOIN jobs j ON a.job_id = j.id
                       WHERE a.student_name LIKE ?""",
                    conn, params=(f"%{search}%",)
                )
                conn.close()

                if not res.empty:
                    res["status"] = res["status"].fillna("Applied")
                    for _, row in res.iterrows():
                        with st.expander(f"🏢 {row['company']}  ·  {row['role']}", expanded=True):
                            stages = ["Applied", "Screened", "Shortlisted", "Interview", "Offered"]
                            cur    = row["status"] if row["status"] in stages else "Applied"
                            idx    = stages.index(cur)
                            chips  = "".join([
                                f'<div class="stage-chip {"done" if i < idx else "active" if i == idx else ""}">{s}</div>'
                                for i, s in enumerate(stages)
                            ])
                            st.markdown(f'<div class="stage-row">{chips}</div>', unsafe_allow_html=True)

                            m1, m2, m3 = st.columns(3)
                            with m1: st.metric("AI Score",            f"{row['ai_score'] or 0}/100")
                            with m2: st.metric("Sector Match",        f"{row['sector_match_score'] or 0}/100")
                            with m3: st.metric("Placement Probability",
                                               f"{row['placement_probability'] or 0}%",
                                               prob_lbl(row['placement_probability'] or 0))

                            st.markdown(
                                f"**Sector:** {row['sector'] or '—'}  "
                                f"**Status:** {status_badge(cur)}",
                                unsafe_allow_html=True
                            )

                            if cur == "Offered":
                                st.divider()
                                if row["contract_accepted"]:
                                    st.success("✅ Contract already accepted. Welcome aboard!")
                                else:
                                    st.subheader("📄 Placement Contract")
                                    st.code(gen_contract(search, row["company"], row["role"]), language=None)
                                    if st.button("✅ Accept Contract", key=f"acc_{row['id']}"):
                                        accept_contract(row["id"])
                                        st.success("🎉 Contract accepted!")
                                        st.balloons()
                                        st.rerun()

                            with st.expander("📊 AI Feedback"):
                                st.write(row["feedback"] or "No feedback available.")
                else:
                    st.info("No applications found for that name.")
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Job Matches ────────────────────────────────────
        with t3:
            st.markdown(
                '<div class="section-card">'
                '<div class="section-title">💡 Jobs Matched to Your Profile</div>',
                unsafe_allow_html=True
            )
            st.caption("Upload your resume to see personalised job matches ranked by compatibility.")
            rf = st.file_uploader("Upload Resume (PDF)", type=["pdf"], key="rec")
            if rf:
                ok, err = validate_resume(rf)
                if not ok:
                    st.error(err)
                else:
                    rt   = extract_pdf_text(rf)
                    recs = get_recs(rt)
                    if recs:
                        for r in recs:
                            color = "#7850ff" if r["match_pct"] >= 60 else "#f59e0b" if r["match_pct"] >= 30 else "#ef4444"
                            badge = "badge-purple" if r["match_pct"] >= 60 else "badge-orange" if r["match_pct"] >= 30 else "badge-red"
                            st.markdown(f"""<div class="match-card">
                              <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div>
                                  <div style="font-family:'Syne',sans-serif;font-weight:700;color:#e8e8f0;">{r['role']}</div>
                                  <div style="color:#888;font-size:13px;margin-top:2px;">🏢 {r['company']}</div>
                                </div>
                                <span class="badge {badge}">{r['match_pct']}% match</span>
                              </div>
                              <div class="match-bar-bg">
                                <div class="match-bar-fill" style="width:{r['match_pct']}%;background:{color};"></div>
                              </div>
                            </div>""", unsafe_allow_html=True)
                    else:
                        st.warning("No active drives found. Ask your TPO to post drives first.")
            st.markdown('</div>', unsafe_allow_html=True)

    # ── TPO DASHBOARD ────────────────────────────────────────
    elif choice == "TPO: Dashboard":
        st.markdown(
            '<div class="welcome-banner"><h1>📊 Placement Control Center</h1>'
            '<p>Manage candidates, track pipeline, send communications and analyse placements.</p></div>',
            unsafe_allow_html=True
        )

        conn = get_conn()
        try:
            apps = pd.read_sql_query(
                """SELECT a.id, a.student_name, j.company, j.role,
                          a.ai_score, a.status, a.feedback,
                          a.sector, a.sector_match_score,
                          a.placement_probability, a.contract_accepted,
                          a.resume_path
                   FROM applications a
                   JOIN jobs j ON a.job_id = j.id
                   ORDER BY a.ai_score DESC""",
                conn
            )
        except Exception:
            apps = pd.read_sql_query(
                "SELECT a.*, j.company, j.role FROM applications a JOIN jobs j ON a.job_id = j.id",
                conn
            )
        finally:
            conn.close()

        # Ensure all required columns exist in the DataFrame
        default_cols = {
            "status":                "Applied",
            "sector":                "",
            "sector_match_score":    0,
            "placement_probability": 0,
            "contract_accepted":     0,
            "resume_path":           "",
            "feedback":              "",
            "ai_score":              0,
        }
        for col, default in default_cols.items():
            if col not in apps.columns:
                apps[col] = default

        apps["status"] = apps["status"].fillna("Applied")

        if not apps.empty:
            total       = len(apps)
            offered     = len(apps[apps["status"] == "Offered"])
            pending     = len(apps[apps["status"].isin(["Applied", "Screened"])])
            shortlisted = len(apps[apps["status"] == "Shortlisted"])

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(stat_card("👥", "Total Candidates", total,       "All applications",  "purple"), unsafe_allow_html=True)
            with c2: st.markdown(stat_card("✅", "Offers Extended",  offered,     "Placed candidates", "green"),  unsafe_allow_html=True)
            with c3: st.markdown(stat_card("⏳", "Pending Review",   pending,     "Awaiting screening","orange"), unsafe_allow_html=True)
            with c4: st.markdown(stat_card("⚡", "Shortlisted",      shortlisted, "Ready for interview","blue"),  unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Charts ──────────────────────────────────────
            st.markdown(
                '<div class="section-card"><div class="section-title">📊 Visual Analytics</div>',
                unsafe_allow_html=True
            )
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                st.plotly_chart(
                    doughnut(["Placed", "Not Placed"], [offered, max(total - offered, 0)], "Placement Status"),
                    use_container_width=True
                )
            with cc2:
                sd = apps["sector"].replace("", pd.NA).dropna().value_counts()
                if not sd.empty:
                    st.plotly_chart(doughnut(sd.index.tolist(), sd.values.tolist(), "Sector Distribution"), use_container_width=True)
                else:
                    st.info("No sector data yet.")
            with cc3:
                stds = apps["status"].value_counts()
                st.plotly_chart(doughnut(stds.index.tolist(), stds.values.tolist(), "Pipeline Stages"), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Candidate Table ──────────────────────────────
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-title">🎯 Candidate Pipeline</div>', unsafe_allow_html=True)

            fc1, fc2 = st.columns([2, 1])
            with fc1:
                sf = st.selectbox("Filter by Sector", ["All"] + list(SECTOR_RULES.keys()))
            with fc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("⚡ Auto-Shortlist", type="primary"):
                    n = auto_shortlist()
                    st.success(f"✅ {n} candidates shortlisted!")
                    st.rerun()

            filtered = apps.copy()
            if sf != "All":
                filtered = filtered[filtered["sector"].str.contains(sf, case=False, na=False)]

            tbl = (
                '<table class="cand-table"><thead><tr>'
                '<th>ID</th><th>Candidate</th><th>Company / Role</th>'
                '<th>Sector</th><th>AI Score</th><th>Probability</th><th>Status</th>'
                '</tr></thead><tbody>'
            )
            for _, row in filtered.iterrows():
                prob_val = int(row["placement_probability"] or 0)
                pc = "#86efac" if prob_val >= 75 else "#fdba74" if prob_val >= 50 else "#fca5a5"
                score_val = int(row["ai_score"] or 0)
                tbl += (
                    f'<tr>'
                    f'<td style="color:#555;">#{row["id"]}</td>'
                    f'<td style="font-weight:600;color:#e8e8f0;">{row["student_name"]}</td>'
                    f'<td><div style="color:#c8b8ff;font-weight:500;">{row["company"]}</div>'
                    f'<div style="color:#555;font-size:12px;">{row["role"]}</div></td>'
                    f'<td style="color:#888;font-size:12px;">{row["sector"] or "—"}</td>'
                    f'<td><span style="font-family:Syne,sans-serif;font-weight:700;color:#fff;">{score_val}</span>'
                    f'<div class="prog-wrap" style="width:80px;">'
                    f'<div class="prog-fill" style="width:{score_val}%;"></div></div></td>'
                    f'<td style="font-weight:700;color:{pc};">{prob_val}%</td>'
                    f'<td>{status_badge(row["status"])}</td>'
                    f'</tr>'
                )
            tbl += "</tbody></table>"
            st.markdown(tbl, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Resume Access ────────────────────────────────
            st.markdown(
                '<div class="section-card"><div class="section-title">📂 Student Resume Access</div>',
                unsafe_allow_html=True
            )
            ra = apps[apps["resume_path"].notna() & (apps["resume_path"] != "")]
            if not ra.empty:
                for _, row in ra.iterrows():
                    rc1, rc2, rc3 = st.columns([4, 1, 2])
                    with rc1:
                        st.markdown(
                            f'<div style="padding:8px 0;">'
                            f'<span style="font-weight:600;color:#e8e8f0;">{row["student_name"]}</span> '
                            f'<span style="color:#555;font-size:12px;">{row["company"]} · {row["role"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    with rc2:
                        rb = get_resume_bytes(row["resume_path"])
                        if rb:
                            st.download_button(
                                "⬇️", data=rb,
                                file_name=os.path.basename(row["resume_path"]),
                                mime="application/pdf",
                                key=f"dl_{row['id']}"
                            )
                    with rc3:
                        st.markdown(
                            f'<small style="color:#333">`{os.path.basename(row["resume_path"])}`</small>',
                            unsafe_allow_html=True
                        )
            else:
                st.info("No resumes stored yet.")
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Skill Gap ────────────────────────────────────
            st.markdown(
                '<div class="section-card"><div class="section-title">📉 Skill Gap Insights</div>',
                unsafe_allow_html=True
            )
            mg = []
            for fb in apps["feedback"].dropna():
                if "Missing:" in str(fb):
                    parts = str(fb).split("Missing:")[-1]
                    mg.extend([
                        s.strip()
                        for s in parts.replace("[", "").replace("]", "").replace("'", "").split(",")
                        if s.strip()
                    ])
            if mg:
                st.bar_chart(pd.Series(mg).value_counts().head(10))
            else:
                st.info("No skill gap data yet.")
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Stage Update + Mailer ────────────────────────
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(
                    '<div class="section-card"><div class="section-title">🛠️ Update Stage</div>',
                    unsafe_allow_html=True
                )
                cand_options = [f"#{r['id']} — {r['student_name']}" for _, r in apps.iterrows()]
                tid_str      = st.selectbox("Candidate", cand_options)
                tid          = int(tid_str.split("#")[1].split(" ")[0])
                update_to    = st.selectbox("Move to Stage",
                                            ["Applied", "Screened", "Shortlisted", "Interview", "Offered", "Rejected"])
                if st.button("💾 Update Status", type="primary"):
                    conn = get_conn()
                    conn.execute("UPDATE applications SET status=? WHERE id=?", (update_to, tid))
                    conn.commit()
                    conn.close()
                    st.success("✅ Status updated!")
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            with col2:
                st.markdown(
                    '<div class="section-card"><div class="section-title">📧 Smart Mailer</div>',
                    unsafe_allow_html=True
                )
                cand_row = apps[apps["id"] == tid].iloc[0]
                tmpl     = st.selectbox("Template", list(EMAIL_TEMPLATES.keys()))
                to_email = st.text_input("Recipient Email", placeholder="student@email.com")
                subj, body = fill_template(tmpl, cand_row["student_name"], cand_row["company"], cand_row["role"])
                st.text_input("Subject", value=subj, key="subj_disp")
                edit_body = st.text_area("Body", value=body, height=140)

                mc1, mc2 = st.columns(2)
                with mc1:
                    if st.button("📤 Send Mail", type="primary"):
                        if to_email:
                            if send_email(to_email, subj, edit_body):
                                st.success("✅ Email sent!")
                        else:
                            st.error("Enter recipient email.")
                with mc2:
                    if st.button("🤖 AI Draft", type="secondary"):
                        with st.spinner("Drafting..."):
                            try:
                                genai.configure(api_key=GEMINI_API_KEY)
                                r = genai.GenerativeModel("gemini-1.5-flash").generate_content(
                                    f"Write a professional {tmpl} email for {cand_row['student_name']} "
                                    f"applying for {cand_row['role']} at {cand_row['company']}. "
                                    f"Keep it concise and warm."
                                )
                                st.text_area("AI Draft", value=r.text, height=140, key="ai_draft_out")
                            except Exception:
                                st.warning("AI unavailable. Check your API key.")
                st.markdown('</div>', unsafe_allow_html=True)

            # ── Contract Tracker ─────────────────────────────
            st.markdown(
                '<div class="section-card"><div class="section-title">📄 Contract Tracker</div>',
                unsafe_allow_html=True
            )
            odf = apps[apps["status"] == "Offered"][
                ["id", "student_name", "company", "role", "contract_accepted"]
            ].copy()
            if not odf.empty:
                odf["contract_accepted"] = odf["contract_accepted"].map(
                    {1: "✅ Accepted", 0: "⏳ Pending"}
                ).fillna("⏳ Pending")
                st.dataframe(odf, use_container_width=True, hide_index=True)
            else:
                st.info("No candidates at 'Offered' stage yet.")
            st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.markdown(
                '<div style="text-align:center;padding:60px;color:#333;">'
                '<div style="font-size:3rem">📭</div>'
                '<div style="font-family:Syne,sans-serif;font-size:1.2rem;color:#444;margin-top:12px;">'
                'No applications yet</div></div>',
                unsafe_allow_html=True
            )


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__" or True:
    # Always initialise DB first — creates tables + heals missing columns
    init_db()
    init_session()

    st.set_page_config(page_title="PlaceMind AI", page_icon="⚡", layout="wide")
    inject_css()

    st.sidebar.markdown("""
    <div class="sidebar-brand">
      <h2>⚡ PlaceMind AI</h2>
      <p>Placement Management 3.0</p>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.logged_in:
        show_auth()
    else:
        show_app()