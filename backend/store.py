"""Small, transactional SQLite document store for a single-user workstation."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "clipforge.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL)")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def projects(self):
        with self.connect() as db:
            rows = [json.loads(r[0]) for r in db.execute("SELECT body FROM projects")]
        return sorted(rows, key=lambda x: x["created_at"], reverse=True)

    def get(self, id):
        with self.connect() as db:
            row = db.execute("SELECT body FROM projects WHERE id=?", (id,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, project):
        with self.lock, self.connect() as db:
            db.execute("INSERT OR REPLACE INTO projects VALUES (?,?)", (project["id"], json.dumps(project)))

    def mutate(self, id, callback):
        with self.lock:
            project = self.get(id)
            if project is None:
                raise ValueError("Project no longer exists")
            callback(project)
            self.put(project)
            return project

    def delete(self, id):
        with self.lock, self.connect() as db:
            db.execute("DELETE FROM projects WHERE id=?", (id,))
            db.execute("DELETE FROM jobs WHERE project_id=?", (id,))

    def job(self, id):
        with self.connect() as db:
            row = db.execute("SELECT body FROM jobs WHERE id=?", (id,)).fetchone()
        return json.loads(row[0]) if row else None

    def put_job(self, job):
        with self.lock, self.connect() as db:
            db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?)", (job["id"], job["project_id"], json.dumps(job)))

    def jobs(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT body FROM jobs")]

    def busy(self, id):
        return any(j["project_id"] == id and j["status"] in ("queued", "running") for j in self.jobs())

    def recover_jobs(self):
        for job in self.jobs():
            if job["status"] in ("queued", "running"):
                job.update(status="failed", error="The server stopped during this job. Please retry.", message="Interrupted by server restart")
                self.put_job(job)
