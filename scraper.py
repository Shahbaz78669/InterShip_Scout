import os
import re
import json
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class JobScraper:
    def __init__(self, query: Optional[str] = None):
        self.jobs: List[Dict[str, Any]] = []
        self._seen_ids = set()
        self.query = query or os.getenv("SEARCH_QUERY", "AI ML internship Flask")
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY", os.getenv("X_RAPIDAPI_KEY", ""))

    def _add_job(self, job: Dict[str, Any]) -> None:
        """Safely append a unique job posting to self.jobs."""
        job_id = job.get("job_id")
        if not job_id:
            # Fallback hash
            raw = f"{job.get('role', '')}|{job.get('company', '')}|{job.get('link', '')}"
            job_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            job["job_id"] = job_id

        if job_id not in self._seen_ids:
            self._seen_ids.add(job_id)
            self.jobs.append(job)

    def scrape_linkedin(self) -> List[Dict[str, Any]]:
        """
        LinkedIn scraping via JSearch API on RapidAPI.
        Reads RAPIDAPI_KEY from environment.
        """
        if not self.rapidapi_key or self.rapidapi_key.strip().lower() in ("", "your-key", "your_rapidapi_key"):
            print("ℹ️ RAPIDAPI_KEY not configured or using placeholder. Skipping LinkedIn (JSearch) API.")
            return []

        try:
            url = "https://jsearch.p.rapidapi.com/search"
            headers = {
                "X-RapidAPI-Key": self.rapidapi_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            querystring = {
                "query": self.query,
                "page": "1",
                "num_pages": "1"
            }

            response = requests.get(url, headers=headers, params=querystring, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ JSearch API returned status {response.status_code}: {response.text[:200]}")
                return []

            data = response.json()
            keywords = [k.strip().lower() for k in self.query.split() if len(k.strip()) > 2]

            for job in data.get("data", []):
                description = job.get("job_description", "")
                title = job.get("job_title", "")
                content = f"{title} {description}".lower()

                # Match relevant keywords
                matches = [k for k in keywords if k in content]
                if "intern" in content or "internship" in content or matches:
                    location_city = job.get("job_city") or "Remote"
                    location_country = job.get("job_country") or ""
                    location = f"{location_city}, {location_country}".strip(", ")

                    self._add_job({
                        "job_id": job.get("job_id", f"jsearch_{len(self.jobs)}"),
                        "company": job.get("employer_name", "Unknown"),
                        "role": title,
                        "link": job.get("job_apply_link") or job.get("job_google_link", ""),
                        "location": location or "Remote",
                        "posted_date": job.get("job_posted_at_datetime_utc", datetime.now().isoformat()),
                        "skills": description[:250] if description else "AI / ML / Python",
                    })

            return self.jobs

        except Exception as e:
            print(f"❌ Error scraping LinkedIn (JSearch): {e}")
            return []

    def scrape_indeed(self) -> List[Dict[str, Any]]:
        """
        Indeed scraping with defensive parsing and fallback selectors.
        """
        try:
            formatted_query = "+".join(self.query.split())
            url = f"https://www.indeed.com/jobs?q={formatted_query}&l=remote"
            
            response = requests.get(url, headers=HEADERS, timeout=12)
            if response.status_code != 200:
                print(f"ℹ️ Indeed returned HTTP status {response.status_code} (anti-scraping protection).")
                return self.jobs

            soup = BeautifulSoup(response.content, "html.parser")
            job_cards = soup.select(".job_seen_beacon, .cardOutline, [data-jk]")

            for card in job_cards:
                try:
                    title_el = card.select_one("h2.jobTitle, a[data-jk]")
                    company_el = card.select_one(".companyName, [data-testid='company-name']")
                    link_el = card.select_one("a[href*='/rc/clk'], a[href*='/pagead/clk'], a[data-jk]")

                    if not title_el or not link_el:
                        continue

                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    href = link_el.get("href", "")
                    
                    full_link = f"https://www.indeed.com{href}" if href.startswith("/") else href
                    
                    # Extract job_id from jk parameter or attribute
                    job_id = card.get("data-jk")
                    if not job_id and "jk=" in full_link:
                        job_id = full_link.split("jk=")[1].split("&")[0]
                    if not job_id:
                        job_id = hashlib.sha256(full_link.encode()).hexdigest()[:16]

                    self._add_job({
                        "job_id": f"indeed_{job_id}",
                        "company": company,
                        "role": title,
                        "link": full_link,
                        "location": "Remote",
                        "posted_date": datetime.now().isoformat(),
                        "skills": "Python, Flask, AI/ML",
                    })
                except Exception:
                    continue

            return self.jobs
        except Exception as e:
            print(f"❌ Indeed error: {e}")
            return self.jobs

    def scrape_remote(self) -> List[Dict[str, Any]]:
        """
        Reliable public tech internships fallback (RemoteOK API).
        No API key required; ensures immediate working results.
        """
        try:
            url = "https://remoteok.com/api?tag=intern"
            res = requests.get(url, headers=HEADERS, timeout=12)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    if not isinstance(item, dict) or "position" not in item:
                        continue
                    title = item.get("position", "")
                    company = item.get("company", "Unknown")
                    link = item.get("url") or item.get("apply_url", "")
                    tags = item.get("tags", [])
                    skills = ", ".join(tags) if isinstance(tags, list) else str(tags)
                    
                    self._add_job({
                        "job_id": f"remoteok_{item.get('id', hashlib.md5(link.encode()).hexdigest()[:10])}",
                        "company": company,
                        "role": title,
                        "link": link,
                        "location": item.get("location") or "Remote",
                        "posted_date": item.get("date") or datetime.now().isoformat(),
                        "skills": skills[:200] if skills else "Python, Intern",
                    })
            return self.jobs
        except Exception as e:
            logger.debug("RemoteOK fallback error: %s", e)
            return self.jobs

    def scrape_wellfound(self) -> List[Dict[str, Any]]:
        """AngelList / Wellfound placeholder."""
        # Wellfound requires authentication cookies or headless browser
        return self.jobs


if __name__ == "__main__":
    scraper = JobScraper()
    print("Testing scrapers...")
    scraper.scrape_linkedin()
    scraper.scrape_indeed()
    scraper.scrape_remote()
    print(f"Total jobs collected: {len(scraper.jobs)}")
    for j in scraper.jobs[:3]:
        print(f" - {j['role']} at {j['company']} ({j['location']}) -> {j['link']}")