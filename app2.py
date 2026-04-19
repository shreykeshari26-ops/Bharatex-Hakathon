import streamlit as st
import pandas as pd
import random
import os
import hashlib
import smtplib
import plotly.graph_objects as go
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

# SQLAlchemy for PostgreSQL
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# ============================================================
# OPTIONAL IMPORTS — wrapped to avoid crash if missing
# ============================================================
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# ============================================================
# 1. CONFIGURATION
# ============================================================
GEMINI_API_KEY     = st.secrets.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
SMTP_HOST          = "smtp.gmail.com"
SMTP_PORT          = 587
SMTP_USER          = st.secrets.get("SMTP_USER", "your_email@gmail.com")
SMTP_PASSWORD      = st.secrets.get("SMTP_PASSWORD", "your_app_password")
MAX_RESUME_SIZE_MB = 10
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
# 2. DATABASE — PostgreSQL via SQLAlchemy
# ============================================================
@st.cache_resource
def get_engine():
    """Create and cache the SQLAlchemy engine using DB_URL from secrets."""
    # Fallback to SQLite for local dev if DB_URL not in secrets
    db_url = st.secrets.get("DB_URL", "sqlite:///placement.db")
    engine = create_engine(db_url, poolclass=NullPool)
    return engine


def init_db():
    """Create tables if they don't exist. PostgreSQL-compatible."""
    engine = get_engine()
    is_postgres = "postgresql" in str(engine.url) or "postgres" in str(engine.url)
    serial = "SERIAL" if is_postgres else "INTEGER"

    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS jobs (
                id      {serial} PRIMARY KEY,
                role    TEXT NOT NULL,
                company TEXT NOT NULL,
                jd      TEXT NOT NULL
            )
        """))

        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS applications (
                id                    {serial} PRIMARY KEY,
                student_name          TEXT    NOT NULL,
                email                 TEXT,
                job_id                INTEGER NOT NULL,
                resume_text           TEXT,
                ai_score              INTEGER DEFAULT 0,
                feedback              TEXT,
                status                TEXT    DEFAULT 'Applied',
                sector                TEXT,
                sector_match_score    INTEGER DEFAULT 0,
                contract_accepted     INTEGER DEFAULT 0,
                placement_probability INTEGER DEFAULT 0,
                resume_path           TEXT
            )
        """))

        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS users (
                id            {serial} PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL
            )
        """))

        # Self-healing: add missing columns
        missing_cols = {
            "email":                 "TEXT",
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
        if is_postgres:
            existing = conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='applications'"
            )).fetchall()
            existing_cols = {r[0] for r in existing}
        else:
            import sqlite3
            sq = sqlite3.connect("placement.db")
            existing_cols = {row[1] for row in sq.execute("PRAGMA table_info(applications)").fetchall()}
            sq.close()

        for col, defn in missing_cols.items():
            if col not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE applications ADD COLUMN {col} {defn}"))
                except Exception:
                    pass

        # Default admin
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        try:
            conn.execute(text(
                "INSERT INTO users (username, password_hash, role) VALUES ('admin', :h, 'admin')"
            ), {"h": admin_hash})
        except Exception:
            pass  # already exists

        conn.commit()


def db_query(sql: str, params: dict = None) -> pd.DataFrame:
    """Run a SELECT query and return a DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        rows = result.fetchall()
        cols = list(result.keys())
    return pd.DataFrame(rows, columns=cols)


def db_exec(sql: str, params: dict = None):
    """Run an INSERT/UPDATE/DELETE statement."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text(sql), params or {})
        conn.commit()


# ============================================================
# 3. GLOBAL CSS — Xtract / Framer Aesthetic
# ============================================================
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg:        #050507;
        --bg-card:   rgba(12, 12, 18, 0.85);
        --bg-raised: rgba(20, 20, 30, 0.9);
        --border:    rgba(124, 77, 255, 0.18);
        --border-hover: rgba(124, 77, 255, 0.5);
        --purple:    #7c4dff;
        --purple-lt: #a87fff;
        --green:     #00e5a0;
        --orange:    #ff8c42;
        --blue:      #4d9fff;
        --text:      #e8e8f4;
        --muted:     rgba(232,232,244,0.45);
        --glass:     rgba(124, 77, 255, 0.07);
    }

    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif !important;
        background: var(--bg) !important;
        color: var(--text) !important;
    }
    .stApp { background: var(--bg) !important; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding: 2rem 2.5rem 4rem !important; max-width: 1440px; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(8,8,14,0.97) !important;
        border-right: 1px solid var(--border) !important;
        backdrop-filter: blur(20px);
    }
    [data-testid="stSidebar"] * { color: rgba(232,232,244,0.8) !important; }

    /* Typography */
    h1,h2,h3 { font-family:'Outfit',sans-serif !important; letter-spacing:-.03em; }
    h1 { font-size:2.1rem !important; font-weight:900 !important; }
    h2 { font-size:1.4rem !important; font-weight:700 !important; color:var(--purple-lt) !important; }
    h3 { font-size:1.1rem !important; font-weight:600 !important; }

    /* Glass Cards */
    .glass-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 24px 28px;
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        transition: border-color .25s, transform .2s, box-shadow .25s;
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
    }
    .glass-card:hover {
        border-color: var(--border-hover);
        transform: translateY(-2px);
        box-shadow: 0 16px 48px rgba(124,77,255,0.15);
    }
    .glass-card::before {
        content:'';
        position:absolute; top:-60px; right:-60px;
        width:160px; height:160px; border-radius:50%;
        background: radial-gradient(circle, rgba(124,77,255,0.12), transparent 70%);
        pointer-events: none;
    }

    /* Stat Cards */
    .stat-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 22px 24px;
        backdrop-filter: blur(15px);
        position: relative; overflow: hidden;
        transition: transform .2s, box-shadow .2s, border-color .2s;
    }
    .stat-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 50px rgba(124,77,255,0.2);
        border-color: var(--border-hover);
    }
    .stat-card .icon  { font-size:1.8rem; margin-bottom:8px; }
    .stat-card .label { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.1em; margin-bottom:6px; }
    .stat-card .value { font-family:'Outfit',sans-serif; font-size:2.6rem; font-weight:900; line-height:1; }
    .stat-card .sub   { font-size:12px; color:var(--muted); margin-top:5px; }
    .stat-card.purple .value { color:var(--purple-lt); }
    .stat-card.green  .value { color:var(--green); }
    .stat-card.orange .value { color:var(--orange); }
    .stat-card.blue   .value { color:var(--blue); }

    /* Section Title */
    .section-title {
        font-family:'Outfit',sans-serif; font-size:1rem; font-weight:700;
        color:var(--text); margin-bottom:16px;
        display:flex; align-items:center; gap:8px;
    }

    /* Badges */
    .badge { display:inline-block; padding:3px 12px; border-radius:999px; font-size:12px; font-weight:600; }
    .badge-green  { background:rgba(0,229,160,.12);  color:var(--green);  border:1px solid rgba(0,229,160,.3); }
    .badge-blue   { background:rgba(77,159,255,.12); color:var(--blue);   border:1px solid rgba(77,159,255,.3); }
    .badge-orange { background:rgba(255,140,66,.12); color:var(--orange); border:1px solid rgba(255,140,66,.3); }
    .badge-purple { background:rgba(124,77,255,.15); color:var(--purple-lt); border:1px solid rgba(124,77,255,.3); }
    .badge-red    { background:rgba(255,80,80,.12);  color:#ff8080;       border:1px solid rgba(255,80,80,.3); }
    .badge-gray   { background:rgba(255,255,255,.06); color:var(--muted); border:1px solid rgba(255,255,255,.1); }

    /* Progress */
    .prog-wrap { background:rgba(255,255,255,.06); border-radius:999px; height:6px; margin:6px 0; overflow:hidden; }
    .prog-fill  { height:6px; border-radius:999px; background:linear-gradient(90deg,var(--purple),var(--purple-lt)); }

    /* Match Cards */
    .match-card {
        background: var(--bg-raised);
        border: 1px solid var(--border);
        border-radius: 14px; padding: 16px 20px; margin-bottom: 12px;
        transition: border-color .2s, transform .15s;
    }
    .match-card:hover { border-color: var(--border-hover); transform: translateX(4px); }

    /* Inputs */
    .stTextInput input, .stTextArea textarea {
        background: rgba(20,20,30,0.8) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        color: var(--text) !important;
        font-family: 'Outfit', sans-serif !important;
        backdrop-filter: blur(10px);
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--purple) !important;
        box-shadow: 0 0 0 3px rgba(124,77,255,0.18) !important;
    }
    .stTextInput label, .stTextArea label, .stSelectbox label, .stFileUploader label {
        color: var(--muted) !important; font-size:13px !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, var(--purple), var(--purple-lt)) !important;
        color: #fff !important; border: none !important; border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important; font-weight: 700 !important;
        font-size: 14px !important; padding: 10px 24px !important;
        transition: opacity .2s, transform .15s, box-shadow .2s !important;
        box-shadow: 0 4px 20px rgba(124,77,255,0.35) !important;
    }
    .stButton > button:hover {
        opacity: .88 !important; transform: translateY(-2px) !important;
        box-shadow: 0 8px 30px rgba(124,77,255,0.5) !important;
    }
    .stButton > button[kind="secondary"] {
        background: rgba(20,20,30,0.8) !important;
        border: 1px solid var(--border) !important;
        color: var(--purple-lt) !important;
        box-shadow: none !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(12,12,18,0.8) !important;
        border-radius: 14px; padding: 4px; gap: 4px;
        border: 1px solid var(--border);
        backdrop-filter: blur(10px);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important; border-radius: 10px !important;
        color: var(--muted) !important; font-family: 'Outfit', sans-serif !important;
        font-weight: 500 !important; padding: 8px 22px !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--purple), var(--purple-lt)) !important;
        color: #fff !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(20,20,30,0.8) !important;
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        color: var(--purple-lt) !important;
        font-family: 'Outfit', sans-serif !important;
        backdrop-filter: blur(10px);
    }
    .streamlit-expanderContent {
        background: rgba(12,12,18,0.8) !important;
        border: 1px solid var(--border) !important;
        border-top: none !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: rgba(20,20,30,0.8) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px; padding: 16px !important;
        backdrop-filter: blur(10px);
    }
    [data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 12px !important; }
    [data-testid="stMetricValue"] { color: var(--purple-lt) !important; font-family: 'Outfit', sans-serif !important; }

    /* Alerts */
    .stSuccess { background: rgba(0,229,160,.08) !important; border: 1px solid rgba(0,229,160,.25) !important; border-radius: 12px !important; }
    .stError   { background: rgba(255,80,80,.08) !important;  border: 1px solid rgba(255,80,80,.25) !important;  border-radius: 12px !important; }
    .stInfo    { background: rgba(77,159,255,.08) !important; border: 1px solid rgba(77,159,255,.25) !important; border-radius: 12px !important; }
    .stWarning { background: rgba(255,140,66,.08) !important; border: 1px solid rgba(255,140,66,.25) !important; border-radius: 12px !important; }

    hr { border-color: var(--border) !important; margin: 20px 0 !important; }

    /* Welcome Banner */
    .welcome-banner {
        background: linear-gradient(135deg, rgba(124,77,255,0.15) 0%, rgba(12,12,18,0.9) 60%);
        border: 1px solid var(--border);
        border-radius: 22px; padding: 32px 36px; margin-bottom: 28px;
        backdrop-filter: blur(15px);
        position: relative; overflow: hidden;
    }
    .welcome-banner::after {
        content:''; position:absolute; top:-80px; right:-80px;
        width:260px; height:260px; border-radius:50%;
        background: radial-gradient(circle, rgba(124,77,255,0.25), transparent 70%);
        pointer-events: none;
    }
    .welcome-banner h1 { font-size:2rem !important; margin:0 0 6px 0 !important; color:#fff !important; }
    .welcome-banner p  { color:var(--muted); margin:0; font-size:14px; }

    /* Sidebar brand */
    .sidebar-brand {
        background: linear-gradient(135deg, var(--purple), var(--purple-lt));
        border-radius: 16px; padding: 20px; text-align:center; margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(124,77,255,0.4);
    }
    .sidebar-brand h2 { color:#fff !important; font-family:'Outfit',sans-serif !important; font-size:1.4rem !important; margin:0 !important; }
    .sidebar-brand p  { color:rgba(255,255,255,.7); font-size:11px; margin:4px 0 0; }

    .user-pill {
        background: rgba(124,77,255,.12);
        border: 1px solid var(--border);
        border-radius: 999px; padding: 8px 16px;
        font-size:13px; color:var(--purple-lt);
        display:inline-block; margin-bottom:16px;
    }

    /* Stage chips */
    .stage-row  { display:flex; gap:6px; margin:12px 0; }
    .stage-chip { flex:1; text-align:center; padding:6px 4px; border-radius:8px; font-size:11px; font-weight:600; background:rgba(255,255,255,.04); color:var(--muted); border:1px solid var(--border); }
    .stage-chip.active { background:linear-gradient(135deg,var(--purple),var(--purple-lt)); color:#fff; border-color:transparent; }
    .stage-chip.done   { background:rgba(0,229,160,.12); color:var(--green); border-color:rgba(0,229,160,.3); }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background: rgba(20,20,30,0.6) !important;
        border: 2px dashed var(--border) !important;
        border-radius: 14px !important;
        backdrop-filter: blur(10px);
    }

    /* Candidate table */
    .cand-table { width:100%; border-collapse:collapse; font-size:13px; }
    .cand-table th { padding:10px 14px; text-align:left; color:var(--muted); font-weight:500; border-bottom:1px solid var(--border); }
    .cand-table td { padding:10px 14px; border-bottom:1px solid rgba(255,255,255,.04); }
    .cand-table tr:hover td { background:rgba(124,77,255,.05); }

    </style>
    """, unsafe_allow_html=True)






# ============================================================
# 4. HELPERS
# ============================================================
def stat_card(icon, label, value, sub, variant=""):
    return f"""<div class="stat-card {variant}">
        <div class="icon">{icon}</div>
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        <div class="sub">{sub}</div>
    </div>"""


def status_badge(s):
    m = {
        "Applied":     ("badge-gray",   "Applied"),
        "Screened":    ("badge-blue",   "Screened"),
        "Shortlisted": ("badge-purple", "Shortlisted"),
        "Interview":   ("badge-orange", "Interview"),
        "Offered":     ("badge-green",  "✅ Offered"),
        "Rejected":    ("badge-red",    "Rejected"),
    }
    cls, lbl = m.get(s, ("badge-gray", s or "—"))
    return f'<span class="badge {cls}">{lbl}</span>'


# ============================================================
# 5. AUTH
# ============================================================
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def register_user(username: str, password: str, role: str) -> bool:
    try:
        db_exec(
            "INSERT INTO users (username, password_hash, role) VALUES (:u, :h, :r)",
            {"u": username.strip(), "h": hash_pw(password), "r": role}
        )
        return True
    except Exception:
        return False


def login_user(username: str, password: str):
    df = db_query(
        "SELECT role FROM users WHERE username=:u AND password_hash=:h",
        {"u": username.strip(), "h": hash_pw(password)}
    )
    return df.iloc[0]["role"] if not df.empty else None


# ============================================================
# 6. AI CORE
# ============================================================
def screen_with_gemini(resume_text: str, jd: str) -> str:
    try:
        if GEMINI_AVAILABLE:
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
        raise Exception("Gemini not available")
    except Exception:
        s = random.randint(65, 92)
        return f"SCORE: {s}\nREASON: [SIMULATED] Strong technical alignment with the job requirements."


def calc_govt_score(resume_text: str, rules: dict):
    rl = resume_text.lower()
    score = 0
    found, missing = [], []
    for s in rules["skills"]:
        if s in rl: found.append(s); score += 10
        else: missing.append(s)
    for c in rules["certifications"]:
        if c in rl: found.append(c); score += 15
        else: missing.append(c)
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
    df = db_query("SELECT * FROM jobs")
    if df.empty: return []
    rl = resume_text.lower()
    results = []
    for _, job in df.iterrows():
        jw = set(str(job["jd"]).lower().split())
        rw = set(rl.split())
        pct = min(int((len(jw & rw) / max(len(jw), 1)) * 300), 100)
        results.append({"job_id": job["id"], "role": job["role"], "company": job["company"], "match_pct": pct})
    return sorted(results, key=lambda x: x["match_pct"], reverse=True)[:top_n]


def parse_ai_score(text: str) -> int:
    try:
        for line in text.splitlines():
            if "SCORE" in line.upper():
                digits = "".join(filter(str.isdigit, line))
                if digits: return min(int(digits), 100)
    except Exception:
        pass
    return 50


# ============================================================
# 7. EMAIL & RESUME HELPERS
# ============================================================
EMAIL_TEMPLATES = {
    "Interview Invite": {
        "subject": "Interview Invitation – {role} at {company}",
        "body": (
            "Dear {name},\n\nCongratulations! You have been shortlisted for {role} at {company}.\n\n"
            "Please attend the interview on the date communicated by HR. Carry a copy of your resume.\n\n"
            "Best regards,\nPlaceMind AI | HR Team"
        ),
    },
    "Selection Offer": {
        "subject": "Offer Letter – {role} at {company}",
        "body": (
            "Dear {name},\n\nWe are delighted to inform you that you have been selected for {role} at {company}.\n\n"
            "Your joining details will be shared shortly.\n\nWarm regards,\nPlaceMind AI | HR Team"
        ),
    },
    "Rejection Mail": {
        "subject": "Application Update – {role} at {company}",
        "body": (
            "Dear {name},\n\nThank you for applying for {role} at {company}. "
            "After careful review we will not be moving forward at this time.\n\n"
            "We encourage you to apply for future openings.\n\nBest wishes,\nPlaceMind AI | HR Team"
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
    if not f: return False, "No file uploaded."
    if not f.name.lower().endswith(".pdf"): return False, "❌ Only PDF files are allowed."
    if f.size / 1024 / 1024 > MAX_RESUME_SIZE_MB: return False, f"❌ File too large. Limit is {MAX_RESUME_SIZE_MB} MB."
    return True, ""


def save_resume(f, name: str) -> str:
    safe_name = name.replace(" ", "_").replace("/", "_")
    path = os.path.join(RESUME_STORE, f"{safe_name}_{date.today()}.pdf")
    with open(path, "wb") as fp:
        fp.write(f.getbuffer())
    return path


def get_resume_bytes(path: str):
    if path and os.path.exists(path):
        with open(path, "rb") as f: return f.read()
    return None


def extract_pdf_text(uploaded_file) -> str:
    if not PDF_AVAILABLE: return ""
    try:
        reader = PdfReader(uploaded_file)
        return "".join([page.extract_text() or "" for page in reader.pages])
    except Exception: return ""


def auto_shortlist(threshold: int = SHORTLIST_THRESHOLD) -> int:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(
            "UPDATE applications SET status='Shortlisted' WHERE sector_match_score >= :t AND (status='Applied' OR status IS NULL)"
        ), {"t": threshold})
        n = result.rowcount
        conn.commit()
    return n


def gen_contract(name: str, company: str, role: str) -> str:
    ref = abs(hash(name + company + role)) % 100000
    return (
        f"PLACEMENT COMMITMENT BOND — PLACEMIND AI\n"
        f"Date      : {date.today().strftime('%d %B %Y')}   Ref # : PCB-{ref:05d}\n"
        f"Candidate : {name}   Company : {company}   Role : {role}\n\n"
        f"I, {name}, hereby confirm that:\n"
        f"  1. I accept this offer in good faith and commit to joining.\n"
        f"  2. I will not renege after acceptance.\n"
        f"  3. Backing out may affect institute–company relations.\n\n"
        f"By clicking 'Accept Contract' I digitally sign these terms.\n"
        f"                    Powered by PlaceMind AI"
    )


def accept_contract(app_id: int):
    db_exec("UPDATE applications SET contract_accepted=1 WHERE id=:id", {"id": app_id})


def calc_prob(ai_score, sec_score) -> int:
    return min(int((ai_score or 0) * 0.6 + (sec_score or 0) * 0.4), 100)


def prob_lbl(p) -> str:
    p = p or 0
    return "🟢 High" if p >= 75 else "🟡 Medium" if p >= 50 else "🔴 Low"


def tips(missing: list, sector: str) -> list:
    sector_tips = {
        "IT & Digital Governance": ["🔧 Build a GitHub project","📚 Get AWS/Azure certified","💻 Practice DSA on LeetCode"],
        "Core Engineering": ["🛠 Add a CAD portfolio project","📐 Get SolidWorks certified","🔌 Build an IoT project"],
        "Infrastructure & Green Energy": ["☀️ Complete Suryamitra certification","🏗 Add a BIM project","📊 Learn SAP basics"],
        "Public Administration": ["📜 Add governance internships","🏛 Note UPSC preparation experience","📊 Learn Excel for public finance"],
        "Management & Finance": ["📈 Learn Tableau or Power BI","💼 Add an HR/sales internship","🧾 Complete Tally/SAP basics"],
    }
    out = list(sector_tips.get(sector, []))
    for sk in (missing or [])[:3]: out.append(f"➕ Add '{sk}' to your skill set")
    return out[:5]


# ============================================================
# 8. CHARTS
# ============================================================
CHART_COLORS = ["#7c4dff","#a87fff","#00e5a0","#ff8c42","#4d9fff","#ec4899","#f59e0b"]


def doughnut(labels, values, title):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.58,
        textinfo="label+percent",
        marker=dict(colors=CHART_COLORS, line=dict(color="#050507", width=3))
    ))
    fig.update_layout(
        title_text=title,
        title_font=dict(color="#a87fff", family="Outfit", size=14),
        showlegend=False,
        margin=dict(t=40, b=10, l=10, r=10), height=260,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#888", family="Outfit"),
    )
    return fig


def skill_gap_radar(skill_counts: dict):
    """Radar / Spider chart for skill gap insights."""
    if not skill_counts:
        return None
    skills = list(skill_counts.keys())[:10]
    counts = [skill_counts[s] for s in skills]
    # Close the polygon
    skills_closed = skills + [skills[0]]
    counts_closed = counts + [counts[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=counts_closed, theta=skills_closed,
        fill='toself',
        fillcolor='rgba(124,77,255,0.15)',
        line=dict(color='#7c4dff', width=2),
        marker=dict(color='#a87fff', size=7),
        name='Skill Gap'
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(visible=True, color='rgba(255,255,255,0.2)', gridcolor='rgba(255,255,255,0.08)'),
            angularaxis=dict(color='rgba(255,255,255,0.5)', gridcolor='rgba(255,255,255,0.08)')
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=20, b=20, l=30, r=30),
        height=320,
        showlegend=False,
        font=dict(color='#a87fff', family='Outfit', size=11),
    )
    return fig


def skill_gap_bars(skill_counts: dict):
    """Horizontal progress bars as an alternative to bar chart."""
    if not skill_counts: return ""
    items = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    max_v = max(v for _, v in items) or 1
    html = ""
    for skill, count in items:
        pct = int((count / max_v) * 100)
        html += f"""
        <div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span style="font-size:13px;color:var(--text);">{skill}</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--purple-lt);">{count}</span>
          </div>
          <div class="prog-wrap" style="height:8px;">
            <div class="prog-fill" style="width:{pct}%;background:linear-gradient(90deg,var(--purple),var(--purple-lt));"></div>
          </div>
        </div>"""
    return html


# ============================================================
# 9. SESSION + PAGE CONFIG
# ============================================================
def init_session():
    for key, default in [("logged_in", False), ("role", None), ("username", None), ("show_login", False)]:
        if key not in st.session_state:
            st.session_state[key] = default


# ============================================================
# 10. LANDING PAGE
# ============================================================
def show_landing():
    st.markdown("""
    <style>
    /* Hide sidebar and top header on landing page */
    [data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    
    /* Splash Animations */
    @keyframes glowPulse {
        0% { text-shadow: 0 0 20px rgba(168,127,255,0.3); }
        50% { text-shadow: 0 0 40px rgba(168,127,255,0.7); }
        100% { text-shadow: 0 0 20px rgba(168,127,255,0.3); }
    }
    @keyframes slideUpFade {
        0% { opacity: 0; transform: translateY(40px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    .landing-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding-bottom: 80px;
    }
    
    .landing-hero {
        text-align: center;
        padding: 5vh 20px 40px;
        max-width: 900px;
        animation: slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    
    .hero-badge {
        display: inline-block;
        background: rgba(124,77,255,0.15);
        color: var(--purple-lt);
        padding: 8px 18px;
        border-radius: 999px;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 24px;
        border: 1px solid rgba(124,77,255,0.3);
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    
    .landing-title {
        font-size: 5.5rem !important;
        font-weight: 900 !important;
        line-height: 1.1;
        margin-bottom: 24px !important;
        background: linear-gradient(135deg, #fff 0%, #a87fff 50%, #00e5a0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: glowPulse 4s infinite, slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    
    @media (max-width: 768px) {
        .landing-title { font-size: 3.5rem !important; }
    }
    
    .landing-subtitle {
        font-size: 1.35rem;
        color: var(--muted);
        line-height: 1.7;
        margin-bottom: 48px;
        animation: slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) 0.1s forwards;
        opacity: 0;
    }
    
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 20px;
        width: 100%;
        max-width: 1100px;
        margin-top: 40px;
        padding: 0 20px;
    }
    
    .f-card {
        background: rgba(20,20,30,0.5);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 32px 28px;
        text-align: left;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        animation: slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        opacity: 0;
        position: relative;
        overflow: hidden;
    }
    .f-card:nth-child(1) { animation-delay: 0.2s; }
    .f-card:nth-child(2) { animation-delay: 0.3s; }
    .f-card:nth-child(3) { animation-delay: 0.4s; }
    .f-card:nth-child(4) { animation-delay: 0.5s; }
    
    .f-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 4px;
        background: linear-gradient(90deg, var(--purple), var(--purple-lt));
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .f-card:hover {
        transform: translateY(-8px);
        border-color: var(--purple-lt);
        box-shadow: 0 24px 48px rgba(124,77,255,0.15);
        background: rgba(25,25,35,0.8);
    }
    .f-card:hover::before { opacity: 1; }
    
    .f-icon {
        font-size: 2.2rem;
        margin-bottom: 20px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 56px; height: 56px;
        background: rgba(124,77,255,0.1);
        border-radius: 14px;
        color: var(--purple-lt);
        border: 1px solid rgba(124,77,255,0.2);
    }
    
    .f-card:nth-child(2) .f-icon { color: var(--green); background: rgba(0,229,160,0.1); border-color: rgba(0,229,160,0.2); }
    .f-card:nth-child(3) .f-icon { color: var(--blue); background: rgba(77,159,255,0.1); border-color: rgba(77,159,255,0.2); }
    .f-card:nth-child(4) .f-icon { color: var(--orange); background: rgba(255,140,66,0.1); border-color: rgba(255,140,66,0.2); }
    
    .f-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #fff;
        margin-bottom: 12px;
        font-family: 'Outfit', sans-serif;
    }
    
    .f-desc {
        color: var(--muted);
        font-size: 1rem;
        line-height: 1.5;
    }
    </style>
    
    <div class="landing-wrapper">
        <div class="landing-hero">
            <div class="hero-badge">Placement Management 3.0</div>
            <h1 class="landing-title">PlaceMind AI</h1>
            <p class="landing-subtitle">The next-generation hiring ecosystem supercharged by Artificial Intelligence. Streamline workflows, auto-shortlist top talent, and eliminate skill gaps instantly.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown('<div style="animation: slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) 0.2s forwards; opacity: 0; padding: 0 10px;">', unsafe_allow_html=True)
        if st.button("🚀 Sign In / Register", type="primary", use_container_width=True):
            st.session_state.show_login = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="landing-wrapper" style="padding-top: 0;">
        <div class="feature-grid">
            <div class="f-card">
                <div class="f-icon">🧠</div>
                <div class="f-title">AI Resume Screening</div>
                <div class="f-desc">Powered by generative AI, accurately analyze structure, experience, and parse insights dynamically—no pre-labeled data needed.</div>
            </div>
            <div class="f-card">
                <div class="f-icon">⚡</div>
                <div class="f-title">Smart Shortlisting</div>
                <div class="f-desc">Set custom AI match thresholds. Our engine automatically tags top candidates for interviews in real-time.</div>
            </div>
            <div class="f-card">
                <div class="f-icon">📊</div>
                <div class="f-title">Advanced Analytics</div>
                <div class="f-desc">Deep-dive into skill gap radars, placement probability forecasts, and cohort benchmarking on the fly.</div>
            </div>
            <div class="f-card">
                <div class="f-icon">📧</div>
                <div class="f-title">Automated Workflows</div>
                <div class="f-desc">Generate offer letters instantly, dispatch automated AI-penned emails, and seal digital contracts with a click.</div>
            </div>
        </div>
<<<<<<< HEAD
        <div class="feature-grid" style="margin-top: 30px; gap: 16px;">
            <div class="f-card" style="padding:24px 24px;">
                <div class="f-title">Institution-ready placement intelligence</div>
                <div class="f-desc">Designed for TPOs, HR teams, and students to collaborate in one platform, with role-specific analytics, smart matching, and placement readiness scores.</div>
            </div>
            <div class="f-card" style="padding:24px 24px;">
                <div class="f-title">Reliable candidate visibility</div>
                <div class="f-desc">Track every student application from resume upload to contract acceptance, while reducing manual screening and follow-ups.</div>
            </div>
            <div class="f-card" style="padding:24px 24px;">
                <div class="f-title">Actionable improvement guidance</div>
                <div class="f-desc">Receive targeted suggestions for missing skills, certifications, and sector alignment to boost placement probability instantly.</div>
            </div>
        </div>
        <div style="margin-top: 60px; font-size: 13px; color: var(--muted); opacity: 0.85; animation: slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) 0.6s forwards;">
=======
        
        <div style="margin-top: 60px; font-size: 13px; color: var(--muted); opacity: 0.7; animation: slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) 0.6s forwards; opacity: 0;">
>>>>>>> 1feb0e5ac997127442b1f39ad66fb985fe50df4a
            © 2026 PlaceMind AI. All rights reserved.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# 10.5 AUTH PAGE
# ============================================================
def show_auth():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:48px 0 36px;">
          <div style="font-family:'Outfit',sans-serif;font-size:2.8rem;font-weight:900;
                      background:linear-gradient(135deg,#a87fff,#7c4dff);
                      -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            PlaceMind AI
          </div>
          <div style="color:rgba(232,232,244,0.4);font-size:14px;margin-top:8px;letter-spacing:.05em;">
            PLACEMENT MANAGEMENT 3.0
          </div>
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
                    st.session_state.role = role
                    st.session_state.username = uname
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials.")
            st.markdown(
                '<div style="text-align:center;margin-top:10px;font-size:12px;color:#333;">'
                'Default admin: <code style="color:#a87fff">admin / admin123</code></div>',
                unsafe_allow_html=True
            )

        with tab_r:
            st.markdown("<br>", unsafe_allow_html=True)
            nu  = st.text_input("Choose Username", placeholder="e.g. rahul_sharma", key="ru")
            np_ = st.text_input("Choose Password", type="password", placeholder="Min 6 characters", key="rp")
            st.markdown("<br>**Register as:**")
            rc1, rc2 = st.columns(2)

            def _reg(rl):
                if len(np_) < 6: st.error("Password must be ≥ 6 characters.")
                elif not nu.strip(): st.error("Username cannot be empty.")
                elif register_user(nu.strip(), np_, rl): st.success(f"✅ Registered as **{rl}**! Please login.")
                else: st.error("Username already taken.")

            with rc1:
                if st.button("🎓 Student", use_container_width=True): _reg("student")
            with rc2:
                if st.button("🛡️ Admin", type="secondary", use_container_width=True): _reg("admin")


# ============================================================
# 11. MAIN APP
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

    # ── LOGOUT ───────────────────────────────────────────────
    if choice == "Logout":
        for k in ["logged_in", "role", "username"]:
            st.session_state[k] = None if k != "logged_in" else False
        st.rerun()

    # ── HR: CREATE DRIVE ─────────────────────────────────────
    elif choice == "HR: Create Drive":
        st.markdown(
            '<div class="welcome-banner"><h1>📢 Post a Placement Drive</h1>'
            '<p>Create new job openings for students to apply and get AI-matched.</p></div>',
            unsafe_allow_html=True
        )
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        company = st.text_input("Company Name", placeholder="e.g. Infosys, DRDO, BHEL")
        role_in = st.text_input("Job Role", placeholder="e.g. Software Engineer")
        jd      = st.text_area("Job Description", height=180, placeholder="Describe required skills and responsibilities...")
        if st.button("🚀 Post Drive", type="primary"):
            if company and role_in and jd:
                db_exec("INSERT INTO jobs (role, company, jd) VALUES (:r, :c, :j)",
                        {"r": role_in.strip(), "c": company.strip(), "j": jd.strip()})
                st.success(f"✅ Drive posted for **{company}**!")
            else:
                st.error("Please fill all fields.")
        st.divider()
        st.markdown("#### 📋 Active Drives")
        df = db_query("SELECT id, company, role, jd FROM jobs")
        if not df.empty: st.dataframe(df, use_container_width=True, hide_index=True)
        else: st.info("No drives posted yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── STUDENT PORTAL ────────────────────────────────────────
    elif choice == "Student: Apply & Track":
        my_apps = db_query(
            """SELECT a.id, a.student_name, a.email, a.ai_score, a.feedback,
                      a.status, a.sector, a.sector_match_score,
                      a.placement_probability, a.contract_accepted,
                      j.company, j.role
               FROM applications a
               JOIN jobs j ON a.job_id = j.id
               WHERE a.student_name LIKE :u""",
            {"u": f"%{username}%"}
        )
        if "status" not in my_apps.columns: my_apps["status"] = "Applied"
        my_apps["status"] = my_apps["status"].fillna("Applied")

        total     = len(my_apps)
        active    = len(my_apps[~my_apps["status"].isin(["Offered", "Rejected"])])
        interview = len(my_apps[my_apps["status"] == "Interview"])
        offered   = len(my_apps[my_apps["status"] == "Offered"])

        st.markdown(
            f'<div class="welcome-banner"><h1>Welcome Back, {username.title()}! 👋</h1>'
            '<p>Your career journey starts here. Track and manage your applications seamlessly.</p></div>',
            unsafe_allow_html=True
        )

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(stat_card("📤", "Total Applications", total,    "All submitted",  "purple"), unsafe_allow_html=True)
        with c2: st.markdown(stat_card("🔄", "Active Applications", active,  "In progress",    "blue"),   unsafe_allow_html=True)
        with c3: st.markdown(stat_card("🗓️", "Waiting Interview",  interview,"In queue",       "orange"), unsafe_allow_html=True)
        with c4: st.markdown(stat_card("🎉", "Offers Received",    offered,  "From employers", "green"),  unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        t1, t2, t3 = st.tabs(["📤  Apply Now", "🔍  Track Status", "💡  Job Matches"])

        # ── Apply Now ─────────────────────────────────────────
        with t1:
            jdf = db_query("SELECT id, company, role, jd FROM jobs")
            if not jdf.empty:
                st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                jopts = {f"{r['company']} — {r['role']}": r['id'] for _, r in jdf.iterrows()}
                sel   = st.selectbox("Select Drive", list(jopts.keys()))
                name  = st.text_input("Your Full Name", placeholder="e.g. Priya Sharma")
                email = st.text_input("Your Email Address ✱", placeholder="e.g. priya@email.com")
                file  = st.file_uploader("Upload Resume (PDF · Max 10 MB)", type=["pdf"])

                if st.button("🚀 Submit Application", type="primary"):
                    ok, err = validate_resume(file)
                    if not ok: st.error(err)
                    elif not name.strip(): st.error("Enter your full name.")
                    elif not email.strip() or "@" not in email: st.error("Enter a valid email address.")
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

                        db_exec(
                            """INSERT INTO applications
                               (student_name, email, job_id, resume_text, ai_score, feedback,
                                status, sector, sector_match_score, placement_probability, resume_path)
                               VALUES (:name, :email, :job_id, :resume_text, :ai_score, :feedback,
                                       :status, :sector, :sector_match_score, :prob, :resume_path)""",
                            {
                                "name": name.strip(), "email": email.strip(),
                                "job_id": jopts[sel], "resume_text": resume_text,
                                "ai_score": final, "feedback": feedback,
                                "status": "Applied", "sector": sector,
                                "sector_match_score": gscore, "prob": prob,
                                "resume_path": rpath
                            }
                        )

                        st.balloons()
                        st.success("✅ Application submitted successfully!")

                        prob_color   = "#00e5a0" if prob >= 75 else "#ff8c42" if prob >= 50 else "#ff8080"
                        found_badges = "".join(
                            [f'<span class="badge badge-green">{s}</span> ' for s in found[:8]]
                        ) or '<span style="color:#444">None detected</span>'

                        st.markdown(f"""
                        <div class="glass-card" style="margin-top:16px;">
                          <div style="font-family:'Outfit',sans-serif;font-size:1.05rem;font-weight:700;color:#a87fff;margin-bottom:16px;">🎯 National Readiness Report</div>
                          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
                            <div style="background:rgba(5,5,7,0.7);border:1px solid var(--border);border-radius:10px;padding:14px;">
                              <div style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Sector Fit</div>
                              <div style="color:#a87fff;font-weight:600;">{sector}</div>
                            </div>
                            <div style="background:rgba(5,5,7,0.7);border:1px solid var(--border);border-radius:10px;padding:14px;">
                              <div style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Hybrid Score</div>
                              <div style="font-family:'Outfit',sans-serif;font-size:1.8rem;font-weight:900;color:#fff;">{final}<span style="font-size:.85rem;color:var(--muted)">/100</span></div>
                            </div>
                            <div style="background:rgba(5,5,7,0.7);border:1px solid var(--border);border-radius:10px;padding:14px;">
                              <div style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Sector Match</div>
                              <div style="font-family:'Outfit',sans-serif;font-size:1.8rem;font-weight:900;color:#00e5a0;">{gscore}<span style="font-size:.85rem;color:var(--muted)">/100</span></div>
                            </div>
                            <div style="background:rgba(5,5,7,0.7);border:1px solid var(--border);border-radius:10px;padding:14px;">
                              <div style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;">Placement Probability</div>
                              <div style="font-family:'Outfit',sans-serif;font-size:1.8rem;font-weight:900;color:{prob_color};">{prob}%</div>
                              <div style="font-size:12px;color:var(--muted);margin-top:2px;">{lbl}</div>
                            </div>
                          </div>
                          <div style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">Skills Found</div>
                          <div>{found_badges}</div>
                        </div>""", unsafe_allow_html=True)

                        if suggestion:
                            st.markdown('<div class="glass-card"><div class="section-title">📌 How to Improve Your Probability</div>', unsafe_allow_html=True)
                            for tip in suggestion: st.markdown(f"- {tip}")
                            st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("No active placement drives yet. Please check back later.")

        # ── Track Status ──────────────────────────────────────
        with t2:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            search = st.text_input("🔍 Search by name", placeholder="Enter your full name...", key="trk")
            if search:
                res = db_query(
                    """SELECT a.id, a.ai_score, a.feedback, j.company, j.role,
                              a.status, a.sector, a.sector_match_score,
                              a.placement_probability, a.contract_accepted
                       FROM applications a
                       JOIN jobs j ON a.job_id = j.id
                       WHERE a.student_name LIKE :s""",
                    {"s": f"%{search}%"}
                )
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
                            with m1: st.metric("AI Score", f"{row['ai_score'] or 0}/100")
                            with m2: st.metric("Sector Match", f"{row['sector_match_score'] or 0}/100")
                            with m3: st.metric("Placement Probability", f"{row['placement_probability'] or 0}%", prob_lbl(row['placement_probability'] or 0))
                            st.markdown(f"**Sector:** {row['sector'] or '—'}  **Status:** {status_badge(cur)}", unsafe_allow_html=True)

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

        # ── Job Matches ───────────────────────────────────────
        with t3:
            st.markdown('<div class="glass-card"><div class="section-title">💡 Jobs Matched to Your Profile</div>', unsafe_allow_html=True)
            st.caption("Upload your resume to see personalised job matches ranked by compatibility.")
            rf = st.file_uploader("Upload Resume (PDF)", type=["pdf"], key="rec")
            if rf:
                ok, err = validate_resume(rf)
                if not ok: st.error(err)
                else:
                    rt   = extract_pdf_text(rf)
                    recs = get_recs(rt)
                    if recs:
                        for r in recs:
                            color = "#7c4dff" if r["match_pct"] >= 60 else "#ff8c42" if r["match_pct"] >= 30 else "#ff8080"
                            badge = "badge-purple" if r["match_pct"] >= 60 else "badge-orange" if r["match_pct"] >= 30 else "badge-red"
                            st.markdown(f"""<div class="match-card">
                              <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div>
                                  <div style="font-family:'Outfit',sans-serif;font-weight:700;color:var(--text);">{r['role']}</div>
                                  <div style="color:var(--muted);font-size:13px;margin-top:2px;">🏢 {r['company']}</div>
                                </div>
                                <span class="badge {badge}">{r['match_pct']}% match</span>
                              </div>
                              <div class="prog-wrap"><div class="prog-fill" style="width:{r['match_pct']}%;background:{color};"></div></div>
                            </div>""", unsafe_allow_html=True)
                    else:
                        st.warning("No active drives found. Ask your TPO to post drives first.")
            st.markdown('</div>', unsafe_allow_html=True)

    # ── TPO DASHBOARD ─────────────────────────────────────────
    elif choice == "TPO: Dashboard":
        st.markdown(
            '<div class="welcome-banner"><h1>📊 Placement Control Center</h1>'
            '<p>Manage candidates, track pipeline, send communications and analyse placements.</p></div>',
            unsafe_allow_html=True
        )

        try:
            apps = db_query(
                """SELECT a.id, a.student_name, a.email, j.company, j.role,
                          a.ai_score, a.status, a.feedback,
                          a.sector, a.sector_match_score,
                          a.placement_probability, a.contract_accepted, a.resume_path
                   FROM applications a
                   JOIN jobs j ON a.job_id = j.id
                   ORDER BY a.ai_score DESC"""
            )
        except Exception:
            apps = pd.DataFrame()

        default_cols = {"status": "Applied", "sector": "", "sector_match_score": 0,
                        "placement_probability": 0, "contract_accepted": 0,
                        "resume_path": "", "feedback": "", "ai_score": 0, "email": ""}
        for col, default in default_cols.items():
            if col not in apps.columns: apps[col] = default
        apps["status"] = apps["status"].fillna("Applied")
        apps["email"]  = apps["email"].fillna("")

        if not apps.empty:
            total       = len(apps)
            offered     = len(apps[apps["status"] == "Offered"])
            pending     = len(apps[apps["status"].isin(["Applied", "Screened"])])
            shortlisted = len(apps[apps["status"] == "Shortlisted"])

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(stat_card("👥", "Total Candidates", total,       "All applications",   "purple"), unsafe_allow_html=True)
            with c2: st.markdown(stat_card("✅", "Offers Extended",  offered,     "Placed candidates",  "green"),  unsafe_allow_html=True)
            with c3: st.markdown(stat_card("⏳", "Pending Review",   pending,     "Awaiting screening", "orange"), unsafe_allow_html=True)
            with c4: st.markdown(stat_card("⚡", "Shortlisted",      shortlisted, "Ready for interview","blue"),   unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Charts ────────────────────────────────────────
            st.markdown('<div class="section-title" style="margin-top:8px;">📊 Visual Analytics</div>', unsafe_allow_html=True)
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                st.plotly_chart(doughnut(["Placed","Not Placed"],[offered, max(total-offered,0)], "Placement Status"), use_container_width=True)
            with cc2:
                sd = apps["sector"].replace("", pd.NA).dropna().value_counts()
                if not sd.empty: st.plotly_chart(doughnut(sd.index.tolist(), sd.values.tolist(), "Sector Distribution"), use_container_width=True)
                else: st.info("No sector data yet.")
            with cc3:
                stds = apps["status"].value_counts()
                st.plotly_chart(doughnut(stds.index.tolist(), stds.values.tolist(), "Pipeline Stages"), use_container_width=True)

            # ── Candidate Table ───────────────────────────────
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
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
            if sf != "All": filtered = filtered[filtered["sector"].str.contains(sf, case=False, na=False)]

            tbl = (
                '<table class="cand-table"><thead><tr>'
                '<th>ID</th><th>Candidate</th><th>Email</th><th>Company / Role</th>'
                '<th>Sector</th><th>AI Score</th><th>Probability</th><th>Status</th>'
                '</tr></thead><tbody>'
            )
            for _, row in filtered.iterrows():
                prob_val  = int(row["placement_probability"] or 0)
                pc = "#00e5a0" if prob_val >= 75 else "#ff8c42" if prob_val >= 50 else "#ff8080"
                score_val = int(row["ai_score"] or 0)
                tbl += (
                    f'<tr>'
                    f'<td style="color:var(--muted);">#{row["id"]}</td>'
                    f'<td style="font-weight:600;color:var(--text);">{row["student_name"]}</td>'
                    f'<td style="color:var(--muted);font-size:12px;">{row["email"] or "—"}</td>'
                    f'<td><div style="color:#a87fff;font-weight:500;">{row["company"]}</div>'
                    f'<div style="color:var(--muted);font-size:12px;">{row["role"]}</div></td>'
                    f'<td style="color:var(--muted);font-size:12px;">{row["sector"] or "—"}</td>'
                    f'<td><span style="font-family:Outfit,sans-serif;font-weight:700;color:#fff;">{score_val}</span>'
                    f'<div class="prog-wrap" style="width:80px;"><div class="prog-fill" style="width:{score_val}%;"></div></div></td>'
                    f'<td style="font-weight:700;color:{pc};">{prob_val}%</td>'
                    f'<td>{status_badge(row["status"])}</td>'
                    f'</tr>'
                )
            tbl += "</tbody></table>"
            st.markdown(tbl, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Resume Access ─────────────────────────────────
            st.markdown('<div class="glass-card"><div class="section-title">📂 Student Resume Access</div>', unsafe_allow_html=True)
            ra = apps[apps["resume_path"].notna() & (apps["resume_path"] != "")]
            if not ra.empty:
                for _, row in ra.iterrows():
                    rc1, rc2, rc3 = st.columns([4, 1, 2])
                    with rc1:
                        st.markdown(
                            f'<div style="padding:8px 0;">'
                            f'<span style="font-weight:600;color:var(--text);">{row["student_name"]}</span> '
                            f'<span style="color:var(--muted);font-size:12px;">{row["company"]} · {row["role"]}</span>'
                            f'</div>', unsafe_allow_html=True
                        )
                    with rc2:
                        rb = get_resume_bytes(row["resume_path"])
                        if rb:
                            st.download_button("⬇️", data=rb, file_name=os.path.basename(row["resume_path"]),
                                               mime="application/pdf", key=f"dl_{row['id']}")
                    with rc3:
                        st.markdown(f'<small style="color:rgba(255,255,255,0.2)">`{os.path.basename(row["resume_path"])}`</small>', unsafe_allow_html=True)
            else:
                st.info("No resumes stored yet.")
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Skill Gap — Radar + Bars ──────────────────────
            st.markdown('<div class="glass-card"><div class="section-title">📉 Skill Gap Insights</div>', unsafe_allow_html=True)
            mg = []
            for fb in apps["feedback"].dropna():
                if "Missing:" in str(fb):
                    parts = str(fb).split("Missing:")[-1]
                    mg.extend([
                        s.strip()
                        for s in parts.replace("[","").replace("]","").replace("'","").split(",")
                        if s.strip()
                    ])
            if mg:
                skill_counts = pd.Series(mg).value_counts().head(10).to_dict()
                col_r, col_b = st.columns([1, 1])
                with col_r:
                    fig = skill_gap_radar(skill_counts)
                    if fig: st.plotly_chart(fig, use_container_width=True)
                with col_b:
                    st.markdown(skill_gap_bars(skill_counts), unsafe_allow_html=True)
            else:
                st.info("No skill gap data yet.")
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Stage Update + Smart Mailer ───────────────────
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<div class="glass-card"><div class="section-title">🛠️ Update Stage</div>', unsafe_allow_html=True)
                cand_options = [f"#{r['id']} — {r['student_name']}" for _, r in apps.iterrows()]
                tid_str      = st.selectbox("Candidate", cand_options)
                tid          = int(tid_str.split("#")[1].split(" ")[0])
                update_to    = st.selectbox("Move to Stage", ["Applied","Screened","Shortlisted","Interview","Offered","Rejected"])
                if st.button("💾 Update Status", type="primary"):
                    db_exec("UPDATE applications SET status=:s WHERE id=:id", {"s": update_to, "id": tid})
                    st.success("✅ Status updated!")
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            with col2:
                st.markdown('<div class="glass-card"><div class="section-title">📧 Smart Mailer</div>', unsafe_allow_html=True)
                cand_row = apps[apps["id"] == tid].iloc[0]

                # ── Auto-fetch student email from DB ─────────
                fetched_email = str(cand_row.get("email", "") or "")
                tmpl     = st.selectbox("Template", list(EMAIL_TEMPLATES.keys()))
                subj, body = fill_template(tmpl, cand_row["student_name"], cand_row["company"], cand_row["role"])

                # Read-only email display (disabled input trick)
                if fetched_email:
                    st.markdown(
                        f'<div style="background:rgba(5,5,7,0.7);border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin-bottom:12px;">'
                        f'<div style="font-size:11px;color:var(--muted);margin-bottom:4px;">RECIPIENT EMAIL (auto-fetched)</div>'
                        f'<div style="color:#a87fff;font-family:\'JetBrains Mono\',monospace;font-size:13px;">{fetched_email}</div>'
                        f'</div>', unsafe_allow_html=True
                    )
                else:
                    fetched_email = st.text_input("Recipient Email (not on file)", placeholder="student@email.com")

                st.text_input("Subject", value=subj, key="subj_disp")
                edit_body = st.text_area("Body", value=body, height=140)

                mc1, mc2 = st.columns(2)
                with mc1:
                    if st.button("📤 Send Mail", type="primary"):
                        if fetched_email:
                            try:
                                if send_email(fetched_email, subj, edit_body):
                                    st.success("✅ Email sent!")
                            except Exception as e:
                                st.warning(f"Mail not sent (check SMTP config): {e}")
                        else:
                            st.error("No email address found for this candidate.")
                with mc2:
                    if st.button("🤖 AI Draft", type="secondary"):
                        with st.spinner("Drafting..."):
                            try:
                                if GEMINI_AVAILABLE:
                                    genai.configure(api_key=GEMINI_API_KEY)
                                    r = genai.GenerativeModel("gemini-1.5-flash").generate_content(
                                        f"Write a professional {tmpl} email for {cand_row['student_name']} "
                                        f"applying for {cand_row['role']} at {cand_row['company']}. "
                                        f"Keep it concise and warm."
                                    )
                                    st.text_area("AI Draft", value=r.text, height=140, key="ai_draft_out")
                                else:
                                    st.warning("Gemini not installed. Run: pip install google-generativeai")
                            except Exception as e:
                                st.warning(f"AI unavailable: {e}")
                st.markdown('</div>', unsafe_allow_html=True)

            # ── Contract Tracker ──────────────────────────────
            st.markdown('<div class="glass-card"><div class="section-title">📄 Contract Tracker</div>', unsafe_allow_html=True)
            odf = apps[apps["status"] == "Offered"][["id","student_name","company","role","contract_accepted"]].copy()
            if not odf.empty:
                odf["contract_accepted"] = odf["contract_accepted"].map({1:"✅ Accepted",0:"⏳ Pending"}).fillna("⏳ Pending")
                st.dataframe(odf, use_container_width=True, hide_index=True)
            else:
                st.info("No candidates at 'Offered' stage yet.")
            st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.markdown(
                '<div style="text-align:center;padding:60px;color:var(--muted);">'
                '<div style="font-size:3rem">📭</div>'
                '<div style="font-family:Outfit,sans-serif;font-size:1.2rem;margin-top:12px;">No applications yet</div></div>',
                unsafe_allow_html=True
            )


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__" or True:
    init_db()
    init_session()

    st.set_page_config(page_title="PlaceMind AI", page_icon="⚡", layout="wide")
    inject_css()

    if not st.session_state.logged_in:
        if not st.session_state.show_login:
            show_landing()
        else:
            st.sidebar.markdown("""
            <div class="sidebar-brand">
              <h2>⚡ PlaceMind AI</h2>
              <p>Placement Management 3.0</p>
            </div>""", unsafe_allow_html=True)
            
            _, bc, _ = st.columns([1, 2, 1])
            with bc:
                if st.button("← Back to Home", key="back_home_btn"):
                    st.session_state.show_login = False
                    st.rerun()
            show_auth()
    else:
        st.sidebar.markdown("""
        <div class="sidebar-brand">
          <h2>⚡ PlaceMind AI</h2>
          <p>Placement Management 3.0</p>
        </div>""", unsafe_allow_html=True)
        show_app()