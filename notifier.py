import os
import smtplib
import sqlite3
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Union
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class Notifier:
    """Handles dispatching job alerts via Email and WhatsApp."""

    def __init__(self):
        # Email configuration (supports both EMAIL/EMAIL_PASSWORD and EMAIL_USER/EMAIL_PASS)
        host_val = (os.getenv("EMAIL_HOST") or "smtp.gmail.com").strip()
        self.email_host = host_val if host_val else "smtp.gmail.com"

        email_port_str = (os.getenv("EMAIL_PORT") or "587").strip()
        self.email_port = int(email_port_str) if email_port_str.isdigit() else 587

        self.email_user = (os.getenv("EMAIL_USER") or os.getenv("EMAIL", "")).strip()
        raw_pass = os.getenv("EMAIL_PASS") or os.getenv("EMAIL_PASSWORD", "")
        self.email_pass = raw_pass.replace(" ", "").strip()
        self.notify_email = (os.getenv("NOTIFY_EMAIL") or self.email_user).strip()

        enable_email_env = os.getenv("ENABLE_EMAIL_NOTIFICATION")
        if enable_email_env is not None:
            self.enable_email = enable_email_env.lower() in ("true", "1", "yes")
        else:
            self.enable_email = bool(self.email_user and self.email_pass)

        # Twilio WhatsApp configuration (supports TWILIO_WHATSAPP_FROM/TO and TWILIO_PHONE/RECIPIENT_PHONE)
        self.twilio_sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
        self.twilio_token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
        self.twilio_from = (os.getenv("TWILIO_WHATSAPP_FROM") or os.getenv("TWILIO_PHONE") or "whatsapp:+14155238886").strip()
        self.twilio_to = (os.getenv("TWILIO_WHATSAPP_TO") or os.getenv("RECIPIENT_PHONE") or "").strip()

        enable_whatsapp_env = os.getenv("ENABLE_WHATSAPP_NOTIFICATION")
        if enable_whatsapp_env is not None:
            self.enable_whatsapp = enable_whatsapp_env.lower() in ("true", "1", "yes")
        else:
            self.enable_whatsapp = bool(
                self.twilio_sid
                and self.twilio_token
                and self.twilio_to
                and self.twilio_sid != "your-sid"
            )

        # Optional CallMeBot WhatsApp API (free alternative)
        self.callmebot_phone = os.getenv("CALLMEBOT_PHONE", "")
        self.callmebot_apikey = os.getenv("CALLMEBOT_APIKEY", "")

    def _normalize_job(self, j: Any) -> Dict[str, str]:
        """Convert tuple, sqlite3.Row, or dict to standard format."""
        if isinstance(j, (dict, sqlite3.Row)):
            # Support both role/title and link/url
            keys = j.keys() if hasattr(j, "keys") else []
            role = j["role"] if "role" in keys else j.get("title", "Internship Opportunity")
            link = j["link"] if "link" in keys else j.get("url", "#")
            company = j["company"] if "company" in keys else "Company"
            location = j["location"] if "location" in keys else "Remote"
            skills = j["skills"] if "skills" in keys else ""
            return {
                "role": str(role),
                "company": str(company),
                "link": str(link),
                "location": str(location),
                "skills": str(skills),
            }
        elif isinstance(j, (tuple, list)):
            # Tuple indices: (id, job_id, company, role, link, location, posted_date, skills, found_date, notified)
            return {
                "company": str(j[2]) if len(j) > 2 else "Company",
                "role": str(j[3]) if len(j) > 3 else "Internship",
                "link": str(j[4]) if len(j) > 4 else "#",
                "location": str(j[5]) if len(j) > 5 else "Remote",
                "skills": str(j[7]) if len(j) > 7 else "",
            }
        return {
            "role": "Internship Opportunity",
            "company": "Company",
            "link": "#",
            "location": "Remote",
            "skills": "",
        }

    # ==========================
    # EMAIL SENDER
    # ==========================
    def format_email_body(self, raw_jobs: List[Any]) -> tuple[str, str]:
        """Generate both plain-text and HTML versions of the internship alert."""
        jobs = [self._normalize_job(j) for j in raw_jobs]
        text_lines = [f"🎯 Internship Scout found {len(jobs)} new opportunity/opportunities:\n"]
        for i, j in enumerate(jobs, 1):
            text_lines.append(
                f"{i}. {j['role']} at {j['company']}\n"
                f"   📍 Location: {j['location']}\n"
                f"   🛠️ Skills: {j['skills'][:100]}\n"
                f"   🔗 Apply: {j['link']}\n"
            )
        plain_text = "\n".join(text_lines)

        html_cards = ""
        for j in jobs:
            skills_html = f"<div style='margin-top:6px; font-size:12px; color:#64748b;'><strong>Skills / Tags:</strong> {j['skills']}</div>" if j['skills'] else ""
            html_cards += f"""
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px; margin-bottom:12px; font-family:sans-serif;">
                <h3 style="margin:0 0 6px 0; color:#1e293b; font-size:18px;">{j['role']}</h3>
                <p style="margin:0 0 8px 0; color:#475569; font-size:14px;">
                    <strong>🏢 Company:</strong> {j['company']} &nbsp;|&nbsp;
                    <strong>📍 Location:</strong> {j['location']}
                </p>
                {skills_html}
                <div style="margin-top:12px;">
                    <a href="{j['link']}" style="display:inline-block; background-color:#2563eb; color:#ffffff; padding:8px 16px; text-decoration:none; border-radius:4px; font-weight:bold; font-size:13px;" target="_blank">View & Apply &rarr;</a>
                </div>
            </div>
            """

        html_body = f"""
        <html>
        <body style="font-family:sans-serif; background-color:#ffffff; color:#334155; padding:20px; max-width:650px; margin:auto;">
            <div style="border-bottom:2px solid #2563eb; padding-bottom:12px; margin-bottom:20px;">
                <h2 style="color:#0f172a; margin:0;">🎯 New Internship Scout Digest</h2>
                <p style="color:#64748b; margin:4px 0 0 0;">Here are the latest internship postings discovered for you.</p>
            </div>
            {html_cards}
            <div style="margin-top:24px; font-size:12px; color:#94a3b8; text-align:center;">
                Generated automatically by Internship Scout.
            </div>
        </body>
        </html>
        """
        return plain_text, html_body

    def send_email(self, jobs: List[Any]) -> bool:
        """Send email alert with internship listings."""
        if not self.enable_email:
            print("ℹ️ Email notifications are disabled in .env (ENABLE_EMAIL_NOTIFICATION=false).")
            return False

        if not self.email_user or not self.email_pass:
            print("⚠️ Email credentials (EMAIL_USER / EMAIL_PASS) not configured in .env. Skipping email.")
            return False

        subject = f"🎯 Internship Scout: {len(jobs)} New Opportunities Found!"
        plain_text, html_body = self.format_email_body(jobs)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Internship Scout <{self.email_user}>"
        msg["To"] = self.notify_email

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            print(f"📧 Connecting to SMTP server {self.email_host}:{self.email_port}...")
            server = smtplib.SMTP(self.email_host, self.email_port)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.email_user, self.email_pass)
            server.sendmail(self.email_user, self.notify_email, msg.as_string())
            server.quit()
            print(f"✅ Email alert successfully sent to {self.notify_email}.")
            return True
        except Exception as err:
            print(f"❌ Failed to send email alert: {err}")
            return False

    # ==========================
    # WHATSAPP SENDER
    # ==========================
    def format_whatsapp_message(self, raw_jobs: List[Any]) -> str:
        """Format a WhatsApp message digest with emojis and direct links."""
        jobs = [self._normalize_job(j) for j in raw_jobs]
        lines = [f"🎯 *Internship Scout Alert*\nFound *{len(jobs)}* new opportunities:\n"]
        for i, j in enumerate(jobs[:10], 1):
            lines.append(
                f"*{i}. {j['role']}*\n"
                f"🏢 {j['company']} | 📍 {j['location']}\n"
                f"🔗 {j['link']}\n"
            )
        if len(jobs) > 10:
            lines.append(f"_...and {len(jobs) - 10} more in your database._")
        return "\n".join(lines)

    def send_whatsapp(self, jobs: List[Any]) -> bool:
        """Send WhatsApp alert via Twilio or CallMeBot API."""
        if not self.enable_whatsapp:
            # WhatsApp disabled by default
            return False

        message_body = self.format_whatsapp_message(jobs)

        # 1. Try CallMeBot if configured
        if self.callmebot_phone and self.callmebot_apikey:
            try:
                print("📱 Sending WhatsApp message via CallMeBot...")
                url = "https://api.callmebot.com/whatsapp.php"
                params = {
                    "phone": self.callmebot_phone,
                    "text": message_body,
                    "apikey": self.callmebot_apikey,
                }
                res = requests.get(url, params=params, timeout=15)
                if res.status_code == 200:
                    print("✅ CallMeBot WhatsApp notification sent successfully.")
                    return True
                else:
                    print(f"⚠️ CallMeBot error {res.status_code}: {res.text}")
            except Exception as err:
                print(f"❌ CallMeBot dispatch error: {err}")

        # 2. Try Twilio WhatsApp API
        if self.twilio_sid and self.twilio_token and self.twilio_to:
            if self.twilio_token in ("your_twilio_auth_token_here", "your-token", "") or self.twilio_token.startswith("your_"):
                print("ℹ️ Twilio Auth Token not configured in .env yet. Skipping WhatsApp.")
                return False
            try:
                print("📱 Sending WhatsApp message via Twilio...")
                to_num = self.twilio_to if self.twilio_to.startswith("whatsapp:") else f"whatsapp:{self.twilio_to}"
                from_num = self.twilio_from if self.twilio_from.startswith("whatsapp:") else f"whatsapp:{self.twilio_from}"

                twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
                data = {
                    "From": from_num,
                    "To": to_num,
                    "Body": message_body,
                }
                res = requests.post(twilio_url, data=data, auth=(self.twilio_sid, self.twilio_token), timeout=15)
                if res.status_code in (200, 201):
                    print("✅ Twilio WhatsApp message sent successfully.")
                    return True
                else:
                    print(f"⚠️ Twilio API error {res.status_code}: {res.text}")
            except Exception as err:
                print(f"❌ Twilio dispatch error: {err}")

        return False
