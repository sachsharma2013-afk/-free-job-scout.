#!/usr/bin/env python3
"""Daily job search digest. Uses only Python standard library."""
import json
import os
import re
import smtplib
import sys
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SEEN_PATH = ROOT / "seen_jobs.json"
API_ID = os.environ.get("ADZUNA_APP_ID", "").strip()
API_KEY = os.environ.get("ADZUNA_APP_KEY", "").strip()
MAIL_USER = os.environ.get("MAIL_USERNAME", "").strip()
MAIL_PASS = os.environ.get("MAIL_APP_PASSWORD", "").replace(" ", "").strip()
MAIL_TO = os.environ.get("MAIL_TO", "").strip()

def fail(message):
    print("ERROR:", message)
    sys.exit(1)

if not all([API_ID, API_KEY, MAIL_USER, MAIL_PASS, MAIL_TO]):
    fail("Missing one or more GitHub Secrets: ADZUNA_APP_ID, ADZUNA_APP_KEY, MAIL_USERNAME, MAIL_APP_PASSWORD, MAIL_TO.")

def clean(value):
    value = unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def fetch(search):
    country = CONFIG.get("country_code", "in")
    params = {
        "app_id": API_ID,
        "app_key": API_KEY,
        "results_per_page": int(CONFIG.get("results_per_query", 30)),
        "what": search["what"],
        "where": search["where"],
        "content-type": "application/json",
    }
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "FreeJobScout/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("results", [])
    except Exception as exc:
        print(f"Search failed for {search['what']} / {search['where']}: {type(exc).__name__}: {exc}")
        return []

def score(job):
    title = clean(job.get("title")).lower()
    description = clean(job.get("description")).lower()
    combined = title + " " + description
    terms = CONFIG["keywords"]
    if any(word in title for word in terms.get("exclude_title", [])):
        return 0
    core = terms.get("core", [])
    skills = terms.get("skills", [])
    core_hits = sum(1 for word in core if word in combined)
    skill_hits = sum(1 for word in skills if word in combined)
    # Weighted keyword heuristic: core role fit is worth 70%, skills 30%.
    core_part = min(1.0, core_hits / 4) * 70
    skill_part = min(1.0, skill_hits / 5) * 30
    return round(core_part + skill_part)

def job_id(job):
    return str(job.get("id") or job.get("redirect_url") or (clean(job.get("title")) + clean(job.get("company", {}).get("display_name"))))

def main():
    try:
        seen = set(json.loads(SEEN_PATH.read_text(encoding="utf-8"))) if SEEN_PATH.exists() else set()
    except Exception:
        seen = set()

    all_jobs = {}
    for search in CONFIG["searches"]:
        results = fetch(search)
        print(f"{search['what']} / {search['where']}: {len(results)} results")
        for job in results:
            jid = job_id(job)
            if jid and jid not in all_jobs:
                job["_scout_score"] = score(job)
                job["_scout_search"] = search["where"]
                all_jobs[jid] = job
        time.sleep(0.25)

    minimum = int(CONFIG.get("minimum_score", 60))
    eligible = [(jid, job) for jid, job in all_jobs.items() if job.get("_scout_score", 0) >= minimum]
    new_jobs = [(jid, job) for jid, job in eligible if jid not in seen]

    # Punjab-first, then score, then title.
    def rank(item):
        jid, job = item
        loc = clean(job.get("location", {}).get("display_name")).lower()
        punjab = any(x in loc for x in ["punjab", "ludhiana", "mohali", "chandigarh", "amritsar", "jalandhar", "patiala"])
        return (not punjab, -job.get("_scout_score", 0), clean(job.get("title")).lower())
    new_jobs.sort(key=rank)

    print(f"Unique jobs: {len(all_jobs)}; score >= {minimum}: {len(eligible)}; new qualifying: {len(new_jobs)}")
    if not new_jobs:
        body = (
            f"Free Job Scout daily digest\n\n"
            f"No new jobs scored {minimum}% or higher today from the configured Adzuna searches.\n"
            f"Searches run: {len(CONFIG['searches'])}\n\n"
            "This score is a keyword relevance estimate, not an AI resume match. "
            "Try broadening keywords in config.json if results are too limited."
        )
    else:
        lines = [
            "FREE JOB SCOUT — DAILY DIGEST",
            f"New qualifying vacancies: {len(new_jobs)} | Minimum keyword score: {minimum}%",
            "Punjab-first ranking. Please verify that each vacancy is still active.",
            "",
        ]
        for idx, (jid, job) in enumerate(new_jobs[:60], 1):
            title = clean(job.get("title")) or "Untitled role"
            company = clean(job.get("company", {}).get("display_name")) or "Company not listed"
            location = clean(job.get("location", {}).get("display_name")) or "Location not listed"
            link = clean(job.get("redirect_url")) or clean(job.get("url"))
            created = clean(job.get("created")) or "Posting date not provided"
            salary = ""
            if job.get("salary_min") or job.get("salary_max"):
                salary = f" | Salary: {job.get('salary_min', '?')}–{job.get('salary_max', '?')}"
            lines.extend([
                f"{idx}. {title}",
                f"   Company: {company}",
                f"   Location: {location}{salary}",
                f"   Keyword relevance score: {job.get('_scout_score', 0)}%",
                f"   Listed: {created}",
                f"   Apply / view: {link}",
                "",
            ])
        lines.extend([
            "NEXT STEP",
            "Open a job you like. Copy its job description and ask ChatGPT to tailor your master resume truthfully.",
            "No resume was sent to this job-search script.",
        ])
        body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = f"Daily Job Scout: {len(new_jobs)} new matches (threshold {minimum}%)"
    msg["From"] = MAIL_USER
    msg["To"] = MAIL_TO
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25) as server:
            server.login(MAIL_USER, MAIL_PASS)
            server.send_message(msg)
    except Exception as exc:
        fail(f"Email send failed: {type(exc).__name__}: {exc}")

    # Save only the IDs we have emailed. Keep a rolling cap to bound file growth.
    for jid, _ in new_jobs:
        seen.add(jid)
    seen_list = list(seen)[-10000:]
    SEEN_PATH.write_text(json.dumps(seen_list, indent=2), encoding="utf-8")
    print("Email sent successfully. Seen IDs updated.")

if __name__ == "__main__":
    main()
