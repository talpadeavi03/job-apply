# AetherApply — Autonomous Job Application Platform

AetherApply is an autonomous, cloud-native job discovery and application platform built to run unattended on **GitHub Actions** every 4 hours.

---

## Architecture Overview

```text
               GitHub Actions Workflow (Every 4 Hours)
                                │
                                ▼
                       apps.main (Orchestrator)
                                │
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
  Browser Manager        Resume & Scorer          Database Layer
(Headless Chromium)    (pypdf + JobMatcher)    (PostgreSQL / SQLite)
        │                       │                        │
        └───────────────────────┼────────────────────────┘
                                │
                   Active Platform Connectors
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
      Gmail API              LinkedIn               Naukri
   (Job Alert Emails)   (Keyword Discovery)   (Location Discovery)
```

---

## Key Features

- **Automated Scheduling**: Scheduled every 4 hours via `.github/workflows/job-apply.yml`.
- **Central Browser Lifecycle**: Single persistent Chromium instance with anti-detection headers, viewport simulation, and automatic screenshotting on failure.
- **Master Resume Profile**: Directly extracts skills, targets, and credentials from `AT_26_AI.pdf`.
- **Intelligent Job Matcher**: Scores opportunities against target cloud/DevOps roles (Azure, AWS, Kubernetes, Terraform, CI/CD, Python, Linux) and categorizes into `queued_apply`, `manual_review`, or `rejected`.
- **Deduplication Engine**: Deterministic SHA-256 identity hashing across alert emails and multi-keyword searches.
- **Dual Database Support**: Fully supports PostgreSQL (Neon / Supabase) via `DATABASE_URL` with automatic local SQLite fallback (`data/aetherapply.sqlite3`).

---

## Directory Structure

```text
├── .github/workflows/
│   └── job-apply.yml         # 4-hour scheduled runner & secret bindings
├── apps/
│   └── main.py               # Main pipeline orchestrator
├── browser/
│   ├── manager.py            # Playwright browser context & lifecycle
│   └── utils.py              # Humanized delays & safe DOM interaction
├── config/
│   ├── platforms.yaml        # Enabled platforms & search parameters
│   └── settings.py           # Paths, credentials, and environment loader
├── connectors/
│   ├── base.py               # BaseConnector abstract contract
│   ├── gmail.py              # Gmail API alert email ingestion
│   ├── linkedin.py           # LinkedIn job search & Easy Apply
│   ├── naukri.py             # Naukri search & discovery
│   └── registry.py           # Connector factory & dynamic loading
├── database/
│   ├── db.py                 # Engine initialization & session management
│   └── models.py             # SQLAlchemy models (Job, Application, ProcessedMessage)
├── engine/
│   ├── dedup.py              # SHA-256 deduplication
│   ├── matcher.py            # Profile & skill matching engine
│   └── parser.py             # PDF resume parser
├── tests/
│   └── test_foundation.py    # Unit tests for database, dedup, and parser
├── AT_26_AI.pdf              # Master candidate resume
└── requirements.txt          # Production dependencies
```

---

## Local Development & Testing

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Run the test suite**:
   ```bash
   PYTHONPATH=. pytest -v tests/
   ```

3. **Execute a single pipeline run**:
   ```bash
   PYTHONPATH=. python -m apps.main
   ```

---

## GitHub Actions Secrets

Configure the following secrets under **Repository Settings > Secrets and variables > Actions**:
- `GMAIL_CLIENT_ID`: Google OAuth Desktop Client ID
- `GMAIL_CLIENT_SECRET`: Google OAuth Client Secret
- `GMAIL_REFRESH_TOKEN`: Authorized OAuth refresh token
- `DATABASE_URL` *(Optional)*: Neon / Supabase PostgreSQL connection string
