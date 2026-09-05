import sys
import os
from dotenv import load_dotenv

# Ensure UTF-8 output encoding across platforms (especially Windows CP1252)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from scraper import JobScraper
from database import JobDatabase
from notifier import Notifier


def main():
    print("🚀 Starting Internship Scout...")

    # Initialize
    scraper = JobScraper()
    db = JobDatabase()
    notifier = Notifier()

    # Scrape
    print("📡 Scraping LinkedIn (JSearch), Indeed, and Remote job boards...")
    scraper.scrape_linkedin()
    scraper.scrape_indeed()
    scraper.scrape_remote()

    # Store new jobs in batch
    new_jobs_count = db.add_jobs(scraper.jobs)
    print(f"✅ Found {new_jobs_count} new opportunities (Scraped: {len(scraper.jobs)} total)")

    # Get unnotified jobs
    unnotified = db.get_new_jobs()

    if unnotified:
        print(f"📬 Dispatching alerts for {len(unnotified)} unnotified jobs...")
        email_sent = notifier.send_email(unnotified)
        whatsapp_sent = notifier.send_whatsapp(unnotified)

        if email_sent or whatsapp_sent:
            notified_ids = [
                job["job_id"] if "job_id" in job.keys() else job[1]
                for job in unnotified
            ]
            db.mark_notified(notified_ids)
            print(f"💾 Database updated: {len(notified_ids)} jobs marked as notified.")
        else:
            print("⚠️ Notification was not dispatched (check credentials). Jobs remain pending for next run.")
    else:
        print("💤 No pending jobs to notify.")

    print("✨ Done!")


if __name__ == "__main__":
    main()