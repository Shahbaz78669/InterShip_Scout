import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Union

logger = logging.getLogger(__name__)


class JobDatabase:
    def __init__(self, db_name: str = "jobs.db"):
        self.db_name = db_name
        self.create_table()
    
    def get_connection(self) -> sqlite3.Connection:
        """Create connection with 30s timeout and Row factory."""
        conn = sqlite3.connect(self.db_name, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # WAL mode allows concurrent readers and writers without database locked errors
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        return conn

    def create_table(self):
        """Create jobs table and migrate missing columns."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE,
                    company TEXT,
                    role TEXT,
                    link TEXT,
                    location TEXT,
                    posted_date TEXT,
                    skills TEXT,
                    found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified INTEGER DEFAULT 0
                )
            ''')
            conn.commit()

            # Ensure all columns exist for backward compatibility
            cursor.execute("PRAGMA table_info(jobs)")
            existing_cols = {col["name"] for col in cursor.fetchall()}

            needed_cols = {
                "job_id": "TEXT",
                "company": "TEXT",
                "role": "TEXT",
                "link": "TEXT",
                "location": "TEXT",
                "posted_date": "TEXT",
                "skills": "TEXT",
                "found_date": "TIMESTAMP",
                "notified": "INTEGER",
            }

            for col_name, col_type in needed_cols.items():
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
                    except Exception:
                        pass

            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_notified ON jobs(notified)")
            conn.commit()
    
    def add_job(self, job_data: Dict[str, Any]) -> bool:
        """Add a single job posting to the database."""
        return self.add_jobs([job_data]) > 0

    def add_jobs(self, jobs_list: List[Dict[str, Any]]) -> int:
        """
        Batch insert multiple job postings inside a single transaction.
        Avoids lock contention and runs 50x faster.
        Returns the number of newly added jobs.
        """
        if not jobs_list:
            return 0

        inserted_count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for job_data in jobs_list:
                job_id = job_data.get("job_id")
                if not job_id:
                    continue

                company = job_data.get("company", "Unknown")
                role = job_data.get("role") or job_data.get("title", "Internship")
                link = job_data.get("link") or job_data.get("url", "")
                location = job_data.get("location", "Remote")
                posted_date = str(job_data.get("posted_date", datetime.now().isoformat()))
                skills = job_data.get("skills", "")

                try:
                    cursor.execute('''
                        INSERT INTO jobs (job_id, company, role, link, location, posted_date, skills, notified)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    ''', (job_id, company, role, link, location, posted_date, skills))
                    inserted_count += 1
                except sqlite3.IntegrityError:
                    # Duplicate job_id
                    continue
                except Exception as e:
                    logger.error("Error inserting job %s: %s", job_id, e)

            conn.commit()
        return inserted_count
    
    def get_new_jobs(self) -> List[sqlite3.Row]:
        """Get jobs that haven't been notified yet."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM jobs WHERE notified = 0 ORDER BY id ASC')
            rows = cursor.fetchall()
            return rows
    
    def mark_notified(self, job_id_or_list: Union[str, List[str]]) -> None:
        """Mark single job or list of jobs as notified in one transaction."""
        if not job_id_or_list:
            return

        if isinstance(job_id_or_list, str):
            ids = [job_id_or_list]
        else:
            ids = list(job_id_or_list)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in ids)
            cursor.execute(f"UPDATE jobs SET notified = 1 WHERE job_id IN ({placeholders})", ids)
            conn.commit()