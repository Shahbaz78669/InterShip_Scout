# 🎯 Internship Scout

An automated scout that searches for fresh internship postings across multiple platforms, deduplicates them in a local SQLite database (`jobs.db`), and dispatches instant alerts via **Email** and **WhatsApp**.

---

## 📁 Project Structure

```
internship-scout/
├── scraper.py              # Main scraper (RemoteOK, WeWorkRemotely, custom boards)
├── notifier.py             # Email (SMTP/HTML) + WhatsApp (Twilio/CallMeBot) sender
├── database.py             # SQLite handler with automatic deduplication
├── main.py                 # Orchestrator pipeline
├── .env                    # Store API keys and configs (DO NOT commit)
├── .env.example            # Safe template for version control
├── jobs.db                 # Database (auto-created on first run)
├── requirements.txt        # Python package dependencies
└── .github/workflows/
    └── daily-scout.yml     # GitHub Actions automated daily cron scheduler
```

---

## 🚀 Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Copy `.env.example` to `.env` (or edit the created `.env`):
```ini
# Search keywords
SCRAPE_KEYWORDS=intern,internship,software intern,junior developer

# Email Notifications (e.g. Gmail with App Password)
ENABLE_EMAIL_NOTIFICATION=true
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_gmail_app_password
NOTIFY_EMAIL=your_email@gmail.com

# WhatsApp Notifications (Twilio or CallMeBot)
ENABLE_WHATSAPP_NOTIFICATION=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+1234567890
```

### 3. Run Locally
Test in dry-run mode (scrapes and checks database without sending messages):
```bash
python main.py --dry-run
```

Run live:
```bash
python main.py
```

---

## ⏰ Automated Scheduling (GitHub Actions)

The repository includes a workflow in `.github/workflows/daily-scout.yml` that runs every day at 08:00 UTC.

To enable it:
1. Push this project to your GitHub repository.
2. Go to **Settings > Secrets and variables > Actions > Repository secrets**.
3. Add your secrets:
   - `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASS`, `NOTIFY_EMAIL`
   - `ENABLE_EMAIL_NOTIFICATION` (`true`)
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_WHATSAPP_TO` (if using WhatsApp)
   - `ENABLE_WHATSAPP_NOTIFICATION`
4. The workflow automatically updates and commits `jobs.db` back to the repository so you don't receive duplicate alerts on subsequent runs!
