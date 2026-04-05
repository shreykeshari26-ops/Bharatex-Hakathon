# 🚀 PlaceMind AI: Smart Placement Management 3.0
**Transforming Campus Recruitment with AI and Real-time Analytics.**

---

## 📌 Problem Statement
Traditional placement processes are fragmented, relying on manual resume screening, scattered spreadsheets, and delayed communication. This leads to:
* **Manual Bottlenecks:** TPOs spend hours manually filtering resumes.
* **Lack of Insights:** Students don't know why they are being rejected or which skills they lack.
* **Communication Gaps:** Manual emailing for every stage update is inefficient and error-prone.

**PlaceMind AI** solves this by providing a unified, AI-driven platform that automates screening, provides visual skill-gap analytics, and manages the entire placement lifecycle in the cloud.

---

## 🛠️ Tech Stack
* **Frontend:** [Streamlit](https://streamlit.io/) (High-end "Xtract" Framer-style UI)
* **Backend:** Python (FastAPI/Streamlit)
* **Database:** [Supabase](https://supabase.com/) (Cloud PostgreSQL)
* **AI/ML:** [Google Gemini 1.5 Flash](https://ai.google.dev/) (Resume Parsing & Interview Prep)
* **Analytics:** [Plotly](https://plotly.com/) (Interactive Radar Charts)
* **DevOps:** GitHub & Git

---

## 🏗️ Architecture & Workflow


1. **Student Portal:** Students upload PDF resumes and provide contact details.
2. **AI Engine:** Gemini parses the PDF, extracts skills, and calculates a match score against job roles.
3. **Cloud Storage:** All data is synced to the Supabase PostgreSQL instance for real-time team collaboration.
4. **TPO Dashboard:** Admins view a glassmorphic dashboard to track applications, view radar charts of student skills, and update hiring stages.
5. **Smart Mailer:** When a candidate is selected, the system auto-fetches their email from the DB for instant communication.

---

## ✨ Core Features (Completed)
* ✅ **Xtract UI:** Midnight black theme with glowing starfield animations and glassmorphism.
* ✅ **Cloud Sync:** Real-time database shared across multiple developer machines via Supabase.
* ✅ **Smart Candidate Selection:** Automatic email fetching from the DB to prevent manual entry errors.
* ✅ **Visual Analytics:** Plotly Radar Charts for real-time skill-gap visualization.
* ✅ **Resume Management:** Automated PDF handling and storage.

---

## 🔮 Upcoming Features (Roadmap)
* 📩 **Automated SMTP Mailer:** Direct email notifications for interview invites.
* 🤖 **AI Mock Interviewer:** Voice-based technical rounds powered by Gemini.
* 📈 **Predictive Analytics:** Predicting placement probability based on historical drive data.
* 📱 **Mobile Dashboard:** A simplified view for students to track status on the go.

---

## 👥 Team Members
* **Shreyansh Keshari** (Lead Developer / UI-UX)
* **Shaurya Verma** (Backend & Database Architect)
* **Shalini Tiwari** (AI Integration & Documentation)

---

## 💻 Developer Quick-Start (Terminal Commands)
To contribute to this project, use the following workflow:

**1. Clone and Sync:**
```bash
git pull origin main