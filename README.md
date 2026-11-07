# ⚡ AetherApply — Autonomous Job Discovery & Auto-Applier Platform

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-green.svg)](https://playwright.dev/)
[![Gemini MCP](https://img.shields.io/badge/AI-Google%20Gemini%202.5-orange.svg)](https://ai.google.dev/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-Automated%204h%20Cron-purple.svg)](https://github.com/features/actions)
[![Discord Alerts](https://img.shields.io/badge/Discord-Realtime%20Radar-5865F2.svg)](https://discord.com/)

**AetherApply** is an autonomous, cloud-native job search, intelligent matching, and auto-application platform. It is engineered to run unattended in the cloud via **GitHub Actions every 4 hours** (or locally on your workstation).

It parses alert emails and active job portals, extracts deep requirements from job descriptions, scores opportunities against your master resume using semantic NLP, fills out custom application questions using **Gemini Model Context Protocol (MCP)** reasoning, attaches your PDF resume, and submits applications automatically while sending real-time receipts to your **Discord channel**.

---

## Table of Contents

- [Key Capabilities](#key-capabilities)
- [Architecture & Flow](#architecture--flow)
- [Supported Platforms](#supported-platforms)
- [Prerequisites](#prerequisites)
- [Quick Start: Local Setup](#quick-start-local-setup)
- [Candidate Customization](#candidate-customization)
  - [1. Master Resume PDF](#1-master-resume-pdf)
  - [2. Candidate Profile & Application Answers](#2-candidate-profile--application-answers)
  - [3. Target Roles & Search Keywords](#3-target-roles--search-keywords)
- [Setting Up API Keys & Credentials](#setting-up-api-keys--credentials)
  - [1. Google Gemini API (AI Reasoning Engine)](#1-google-gemini-api-ai-reasoning-engine)
  - [2. Discord Webhook (Frontend & Notifications)](#2-discord-webhook-frontend--notifications)
  - [3. Gmail API & 2FA Resolution (OAuth2)](#3-gmail-api--2fa-resolution-oauth2)
  - [4. LinkedIn Authentication](#4-linkedin-authentication)
  - [5. Naukri Authentication](#5-naukri-authentication)
  - [6. Database & Cloud Sync (Optional)](#6-database--cloud-sync-optional)
- [Deploying to GitHub Actions (Unattended Cloud Runner)](#deploying-to-github-actions-unattended-cloud-runner)
- [Directory Structure](#directory-structure)
- [Verification & Testing](#verification--testing)
- [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## Key Capabilities

- **100% Unattended Cloud Execution**: Runs on a scheduled GitHub Actions workflow (`cron: "0 */4 * * *"`) requiring zero manual intervention or daily cookie maintenance.
- **Gemini MCP Reasoning Engine**: Intelligently answers custom recruiter questionnaire prompts, essays ("Why should we hire you?"), and role-specific requirements using your resume as ground truth.
- **Akamai & Bot-Detection Bypass**: Configured with genuine Client Hints (`sec-ch-ua`, mobile, platform) and stealth flags to bypass modern anti-bot protections on job boards like Naukri.
- **Automated 2FA & OTP Resolution**: Automatically reads 6-digit one-time security passcodes from your Gmail via the Gmail API to resolve login security challenges for LinkedIn and Naukri.
- **Round-Robin Fair Queue**: Distributes application slots across platforms (LinkedIn, Naukri, Wellfound, Direct Portals) to prevent single-platform starvation.
- **Zero False-Positive Submission Guarantee**: Verifies DOM confirmation states, button mutations, and confirmation banners. External portal redirects (Workday, Taleo, company SSO) are cleanly routed to a `manual_review` queue with direct links instead of generating fake success receipts.
- **Discord Operations Hub**: Instant rich-embed cards for 100% match roles, submission receipts with details, and warning alerts for captchas or manual review queues.

---

## Architecture & Flow

```mermaid
flowchart TD
    A["⏰ GitHub Actions / Local Cron (Every 4 Hours)"] --> B["🚀 apps.main (Orchestrator)"]
    B --> C["📄 Parser: Extract Master Resume Profile"]
    B --> D["🌐 Launch Playwright Chromium (Stealth Mode)"]
    
    D --> E["Connectors: Job Discovery"]
    E --> E1["📧 Gmail Alert Digest Scraper"]
    E --> E2["💼 LinkedIn Job Search"]
    E --> E3["🇮🇳 Naukri Search (Akamai Bypassed)"]
    E --> E4["🦄 Wellfound / Indeed / Hirist"]

    E1 & E2 & E3 & E4 --> F["🔍 Deduplication & Match Scoring (Matcher)"]
    F -->|Match < 70%| G["📁 Stored / Rejected"]
    F -->|Match >= 70%| H["🎯 High Match Alerts to Discord"]
    H --> I["⚖️ Round-Robin Application Queue"]

    I --> J1["LinkedIn Easy Apply"]
    I --> J2["Naukri 1-Click Apply"]
    I --> J3["Wellfound Applier"]
    I --> J4["Universal ATS (Greenhouse, Lever)"]

    J1 & J2 & J3 & J4 --> K["🧠 Gemini MCP Engine: Custom Form Answering"]
    K --> L["📎 Resume PDF Upload + Form Submission"]
    L --> M{"Verification Check"}
    M -->|Submission Verified| N["✅ Green Discord Receipt + Database Record"]
    M -->|External / Login Wall| O["⚠️ Queued for Manual Review on Discord"]
```

---

## Supported Platforms

| Platform | Discovery Type | Auto-Apply Method | Custom Question Answering |
| :--- | :--- | :--- | :--- |
| **LinkedIn** | Keyword Search + Alerts | Easy Apply (Multi-step modal) | Gemini MCP + Profile Heuristics |
| **Naukri** | Search + Email Digest | 1-Click Apply + Chatbot Modal | Gemini MCP + Profile Heuristics |
| **Wellfound** | Direct API & Search | Direct Candidate Application | Gemini MCP + Profile Heuristics |
| **Gmail Alerts** | IMAP / REST OAuth2 | Link Extraction & Canonicalization | Evaluates individual job links |
| **Universal ATS** | Follow External Links | Greenhouse, Lever, Ashby, Direct | Form Auto-population + Resume |

---

## Prerequisites

Before starting, ensure you have:
1. **Python 3.12+** installed on your system.
2. A **GitHub Account** (if you want to run unattended scheduled jobs in the cloud).
3. A **Discord Server** (to receive alerts and application receipts).
4. A **Google AI Studio API Key** (free tier available at [aistudio.google.com](https://aistudio.google.com/)).

---

## Quick Start: Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/job-apply.git
cd job-apply
```

### 2. Create and Activate a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies & Playwright Browsers
```bash
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

### 4. Setup Environment File
Copy the example environment configuration:
```bash
cp .env.example .env  # or edit .env directly
```

### 5. Run the Test Suite
Ensure all foundation tests pass:
```bash
PYTHONPATH=. pytest -v tests/
```

### 6. Execute a Dry Run
```bash
PYTHONPATH=. python -m apps.main
```

---

## Candidate Customization

To make AetherApply apply on your behalf, you need to customize three files:

### 1. Master Resume PDF
Replace `AT_26_AI.pdf` in the repository root with your own resume PDF:
- Keep the filename `AT_26_AI.pdf` OR update `RESUME_PATH` in `config/settings.py`:
  ```python
  RESUME_PATH = ROOT_DIR / "My_Resume.pdf"
  ```
The resume parser automatically extracts your name, skills, work history, and contact details directly from the PDF text.

### 2. Candidate Profile & Application Answers
Open [`application/answers.py`](file:///home/sudo69/Projects/job-apply/application/answers.py) and update the `ANSWERS` dictionary with your personal details:

```python
ANSWERS = {
    "phone": "9876543210",
    "email": "youremail@example.com",
    "first_name": "Firstname",
    "last_name": "Lastname",
    "full_name": "Firstname Lastname",
    "city": "Your City",
    "location": "City, State, Country",
    "country": "India",
    "years_experience": "4.0",
    "notice_period_days": "15",
    "notice_period_text": "15 Days / Immediate",
    "current_ctc": "1200000",        # In numbers (e.g. 12 LPA)
    "current_ctc_lakhs": "12",
    "expected_ctc": "1800000",       # In numbers (e.g. 18 LPA)
    "expected_ctc_lakhs": "18",
    "degree": "Bachelor of Technology in Computer Science",
    "gender": "Male",                 # or "Female" / "Decline to specify"
    "sponsorship_required": False,
    "authorized_to_work": True,
    "willing_to_relocate": True,
    "current_company": "Your Company",
    "current_role": "Software Engineer",
    "linkedin_url": "https://www.linkedin.com/in/yourprofile",
    "portfolio_url": "https://yourportfolio.dev",
}
```

Also update your contact information in [`config/settings.py`](file:///home/sudo69/Projects/job-apply/config/settings.py):
```python
CANDIDATE_NAME = "Firstname Lastname"
CANDIDATE_EMAIL = "youremail@example.com"
CANDIDATE_PHONE = "9876543210"
CANDIDATE_LOCATION = "City, State, Country"
```

### 3. Target Roles & Search Keywords
Open [`config/platforms.yaml`](file:///home/sudo69/Projects/job-apply/config/platforms.yaml) to customize your desired job titles, locations, and scoring thresholds:

```yaml
global:
  max_jobs_per_run: 50
  auto_apply_min_score: 75.0      # Auto-apply to jobs with >= 75% match
  manual_review_min_score: 50.0   # Send jobs with 50-74% match to review queue

platforms:
  linkedin:
    enabled: true
    search_keywords:
      - "Cloud Engineer"
      - "DevOps Engineer"
      - "Site Reliability Engineer"
    locations:
      - "Remote"
      - "Bangalore, India"

  naukri:
    enabled: true
    search_keywords:
      - "DevOps Engineer"
      - "Cloud Infrastructure"
    locations:
      - "Bangalore"
      - "Remote"
```

---

## Setting Up API Keys & Credentials

### 1. Google Gemini API (AI Reasoning Engine)
1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Create API Key**.
3. Save the key as `GEMINI_API_KEY`.
*(Used by Gemini MCP to answer recruiter questions and write tailored cover letters grounded in your resume).*

---

### 2. Discord Webhook (Frontend & Notifications)
1. In your Discord app, create a private server or channel (e.g., `#job-radar`).
2. Right-click the channel name > **Edit Channel** > **Integrations** > **Webhooks**.
3. Click **New Webhook**, name it `AetherApply`, and click **Copy Webhook URL**.
4. Save the URL as `DISCORD_WEBHOOK_URL`.

---

### 3. Gmail API & 2FA Resolution (OAuth2)
AetherApply uses the Gmail API to:
- Read job alert emails from LinkedIn, Naukri, and Indeed.
- Automatically extract one-time 2FA login verification codes (OTPs) when platforms challenge new cloud runner IPs.

#### How to Generate Gmail OAuth Credentials:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `Job-Apply-Automation`).
3. Enable the **Gmail API**:
   - Go to **APIs & Services** > **Library**.
   - Search for `Gmail API` and click **Enable**.
4. Configure **OAuth Consent Screen**:
   - Choose **External** > Fill in app name and your email.
   - Add scope: `https://www.googleapis.com/auth/gmail.readonly`.
   - Add your Gmail address under **Test Users** and click Save.
5. Create Credentials:
   - Go to **APIs & Services** > **Credentials** > **Create Credentials** > **OAuth client ID**.
   - Select **Desktop App** and click Create.
   - Copy the `Client ID` (`GMAIL_CLIENT_ID`) and `Client Secret` (`GMAIL_CLIENT_SECRET`).
6. Obtain your Refresh Token (`GMAIL_REFRESH_TOKEN`):
   - Run the provided helper script locally:
     ```bash
     python -c "
     from google_auth_oauthlib.flow import InstalledAppFlow
     flow = InstalledAppFlow.from_client_config(
         {'installed': {'client_id': 'YOUR_CLIENT_ID', 'client_secret': 'YOUR_CLIENT_SECRET', 'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token'}},
         scopes=['https://www.googleapis.com/auth/gmail.readonly']
     )
     creds = flow.run_local_server(port=0)
     print('REFRESH_TOKEN:', creds.refresh_token)
     "
     ```
   - Log in and authorize the app. Copy the output `REFRESH_TOKEN`.

---

### 4. LinkedIn Authentication
AetherApply supports automated login with 2FA email code extraction:
- `LINKEDIN_USERNAME`: Your LinkedIn login email.
- `LINKEDIN_PASSWORD`: Your LinkedIn password.
- `LINKEDIN_LI_AT` *(Optional)*: If you prefer using your session cookie:
  - In your browser, log in to LinkedIn.
  - Open Developer Tools (`F12`) > **Application** > **Cookies** > `https://www.linkedin.com`.
  - Copy the value of the `li_at` cookie.

---

### 5. Naukri Authentication
- `NAUKRI_USERNAME`: Your Naukri email ID or username.
- `NAUKRI_PASSWORD`: Your Naukri account password.
- *(Note: AetherApply automatically resolves Naukri login OTPs directly from your Gmail if challenged).*

---

### 6. Database & Cloud Sync (Optional)
By default, AetherApply stores job listings and application logs in a local SQLite file (`data/aetherapply.sqlite3`).
- **PostgreSQL**: To use a persistent remote cloud database (e.g. Neon, Supabase, or AWS RDS), set:
  ```env
  DATABASE_URL=postgresql://user:password@host:5432/dbname
  ```
- **Firebase Firestore**: If you want real-time mobile/web sync, encode your Firebase Service Account JSON as a base64 string and set `FIREBASE_SERVICE_ACCOUNT`.

---

## Deploying to GitHub Actions (Unattended Cloud Runner)

AetherApply is ready for 24/7 cloud automation with zero server costs using GitHub Actions.

### Step 1: Push Your Fork to GitHub
Ensure your repository is private to protect your resume and configuration:
```bash
git remote set-url origin https://github.com/YOUR_USERNAME/job-apply.git
git push origin main
```

### Step 2: Configure GitHub Repository Secrets
Go to your repository on GitHub:
**Settings** > **Secrets and variables** > **Actions** > **New repository secret**.

Add the following secrets:

| Secret Name | Description | Mandatory? |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google AI Studio Gemini API Key | **Yes** |
| `DISCORD_WEBHOOK_URL` | Discord Channel Webhook URL | **Yes** |
| `GMAIL_CLIENT_ID` | Google OAuth Client ID | **Yes** |
| `GMAIL_CLIENT_SECRET` | Google OAuth Client Secret | **Yes** |
| `GMAIL_REFRESH_TOKEN` | Google OAuth Refresh Token | **Yes** |
| `LINKEDIN_USERNAME` | LinkedIn Login Email | Recommended |
| `LINKEDIN_PASSWORD` | LinkedIn Login Password | Recommended |
| `LINKEDIN_LI_AT` | LinkedIn Session Cookie (`li_at`) | Optional |
| `NAUKRI_USERNAME` | Naukri Account Email | Recommended |
| `NAUKRI_PASSWORD` | Naukri Account Password | Recommended |
| `DATABASE_URL` | PostgreSQL connection string | Optional (Uses SQLite) |
| `FIREBASE_SERVICE_ACCOUNT` | Firebase service account base64 | Optional |

### Step 3: Trigger the Pipeline
1. In your GitHub repository, click on the **Actions** tab.
2. Select **AetherApply Pipeline** in the left sidebar.
3. Click **Run workflow** > **Branch: main** > **Run workflow**.
4. The cloud runner will execute the pipeline and report results directly to your Discord channel!

From this point on, the GitHub Actions cron (`0 */4 * * *`) will automatically trigger every 4 hours.

---

## Directory Structure

```text
├── .github/workflows/
│   └── job-apply.yml             # GitHub Actions 4-hour scheduled automation
├── application/
│   ├── answers.py                # Candidate profile & deterministic question rules
│   ├── apply.py                  # AutoApplier orchestrator with round-robin queue
│   ├── linkedin_applier.py       # LinkedIn Easy Apply with Gemini MCP answering
│   ├── naukri_applier.py         # Naukri 1-Click apply, chatbot, in-page login
│   ├── universal_form_applier.py # Greenhouse, Lever, and ATS form applier
│   ├── uploader.py               # File attachment helper for resume PDFs
│   └── wellfound_applier.py      # Wellfound auto-apply module
├── apps/
│   └── main.py                   # Master workflow orchestrator
├── browser/
│   ├── auth.py                   # Automated cloud login & Gmail 2FA resolution
│   ├── manager.py                # Playwright lifecycle & Akamai stealth headers
│   └── utils.py                  # Humanized delays, safe clicks, safe fills
├── config/
│   ├── platforms.yaml            # Platform keywords, locations, score thresholds
│   └── settings.py               # Credentials, paths, and environment loader
├── connectors/
│   ├── base.py                   # BaseConnector interface
│   ├── gmail.py                  # Gmail API alert email ingestion & link extractor
│   ├── linkedin.py               # LinkedIn search connector
│   ├── naukri.py                 # Naukri search connector
│   └── registry.py               # Dynamic connector loader
├── database/
│   ├── db.py                     # SQLAlchemy session & database engine
│   ├── firestore.py              # Firebase Firestore cloud sync
│   └── models.py                 # Job, ApplicationRecord, ProcessedMessage
├── engine/
│   ├── dedup.py                  # Canonical URL normalizer & SHA-256 deduplication
│   ├── matcher.py                # Semantic skill-matching engine
│   └── parser.py                 # pypdf resume extraction engine
├── mcp_server/
│   ├── ai_agent.py               # Gemini 2.5 MCP reasoning & answer engine
│   └── server.py                 # MCP Server tools & resources
├── notifications/
│   └── discord.py                # Discord Webhook UI cards, receipts, and digests
├── tests/
│   └── test_foundation.py        # Complete test suite (15 unit tests)
├── AT_26_AI.pdf                  # Master PDF resume
├── requirements.txt              # Production Python dependencies
└── README.md                     # Documentation
```

---

## Verification & Testing

To verify the installation and test individual modules without applying to real jobs:

```bash
# 1. Run all unit tests
PYTHONPATH=. pytest -v tests/

# 2. Test Resume Parsing
python -c "
from engine.parser import extract_resume_profile
from config.settings import RESUME_PATH
profile = extract_resume_profile(RESUME_PATH)
print('Parsed Name:', profile.name)
print('Skills Found:', len(profile.skills))
"

# 3. Test Gemini MCP AI Question Answering
python -c "
from mcp_server.ai_agent import answer_form_question
print('Years Exp:', answer_form_question('How many years of experience in Kubernetes?', field_type='number'))
print('Notice Period:', answer_form_question('What is your notice period?', field_type='number'))
"

# 4. Test Gmail Connector Authentication
python -c "
from connectors.gmail import GmailConnector
c = GmailConnector({})
print('Gmail Auth OK:', c.authenticate())
"
```

---

## Troubleshooting & FAQs

### Q: Why did Naukri return "Access Denied" previously?
**A:** Naukri uses Akamai Bot Manager, which inspects client hints. Default Playwright headless Chromium sends `"HeadlessChrome"` in the `sec-ch-ua` header. AetherApply includes authentic Chrome Client Hints and stealth parameters in [`browser/manager.py`](file:///home/sudo69/Projects/job-apply/browser/manager.py), allowing clean 200 HTTP responses.

### Q: How does 2FA resolution work without manual input?
**A:** When LinkedIn or Naukri detects a new IP address from the GitHub Actions cloud runner, they email a 6-digit security code. AetherApply detects this challenge, polls your Gmail account via the Gmail API, extracts the code using regex `\b(\d{6})\b`, enters it into the input box, and saves the authenticated session state.

### Q: Does AetherApply apply to jobs that don't match my profile?
**A:** No. Every job description is compared against the skills in your resume. Only jobs matching equal to or higher than `auto_apply_min_score` (default: 75%) in `config/platforms.yaml` are submitted. Lower matching jobs (50–74%) are placed in `manual_review` and sent to Discord for manual decision.

### Q: What happens with external company career portals (Workday, etc.)?
**A:** AetherApply will never submit a fake receipt. If an external company site requires creating an account or manual SSO sign-in, AetherApply marks it as `queued_manual` with the direct application link in Discord so you can finish the final step in seconds.

---

## License

This project is licensed under the MIT License — feel free to customize and automate your job search.
