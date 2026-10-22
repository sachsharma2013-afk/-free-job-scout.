import os
import re
import sys
import time
import html
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---------- Credentials (GitHub Secrets) ----------
app_id = (os.environ.get("ADZUNA_APP_ID") or "").strip()
app_key = (os.environ.get("ADZUNA_APP_KEY") or "").strip()
rapid_key = (os.environ.get("RAPIDAPI_KEY") or "").strip()  # optional (LinkedIn etc. via JSearch)
email_address = (os.environ.get("EMAIL_ADDRESS") or "").strip()
email_password = (os.environ.get("EMAIL_PASSWORD") or "").replace(" ", "").strip()

missing = [n for n, v in [("ADZUNA_APP_ID", app_id), ("ADZUNA_APP_KEY", app_key),
                          ("EMAIL_ADDRESS", email_address), ("EMAIL_PASSWORD", email_password)] if not v]
if missing:
    print(f"Error: missing secrets: {', '.join(missing)}")
    sys.exit(1)

# ---------- Settings (edit these) ----------
# Any ONE of these words in the search matches (one combined query per region)
WHAT_OR = "procurement purchase purchasing sourcing buyer supply chain vendor SAP MM"
LOCATIONS = [
    "",  # empty = whole India
    "Punjab", "Chandigarh", "Ludhiana", "Mohali",
    "Delhi", "Gurgaon", "Noida", "Ghaziabad", "Faridabad",
    "Haryana", "Himachal Pradesh", "Uttarakhand",
    "Gujarat", "Ahmedabad", "Pune",
    "Mumbai", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
    "Jaipur", "Lucknow", "Indore", "Nagpur", "Rajasthan", "Uttar Pradesh",
]
# JSearch (LinkedIn, Indeed, Glassdoor via Google Jobs). Free plan ~200 calls/month: keep this list short.
JSEARCH_QUERIES = [
    "procurement manager in India",
    "purchase manager in Punjab India",
    "strategic sourcing in Delhi NCR India",
    "supply chain manager in India",
    "SAP MM procurement in India",
]
PAGES = [1, 2, 3]            # 50 results per page
MAX_DAYS_OLD = 7          # only jobs posted in the last N days
RESULTS_PER_PAGE = 50
PAUSE_SECONDS = 3         # stay under Adzuna's rate limit

MUST_HAVE = re.compile(r"procure|purchas|sourcing|buyer|supply chain|vendor|category|material|sap mm|scm|logistic|contract", re.I)
MUST_NOT = re.compile(r"sales|marketing|telecall|insurance|loan|recruit|bpo|customer care|business development|driver|teacher", re.I)

API = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"

all_jobs = {}
api_failures = 0
requests_made = 0

for loc in LOCATIONS:
    for page in PAGES:
        params = {
            "app_id": app_id, "app_key": app_key,
            "what_or": WHAT_OR,
            "results_per_page": RESULTS_PER_PAGE,
            "max_days_old": MAX_DAYS_OLD,
            "sort_by": "date",
            "content-type": "application/json",
        }
        if loc:
            params["where"] = loc
        requests_made += 1
        try:
            r = requests.get(API.format(page=page), params=params, timeout=30)
            if r.status_code != 200:
                api_failures += 1
                print(f"HTTP {r.status_code} for {loc} p{page}: {r.text[:150]}")
                time.sleep(PAUSE_SECONDS)
                continue
            results = r.json().get("results", [])
            kept = 0
            for j in results:
                title = j.get("title") or ""
                if not MUST_HAVE.search(title) or MUST_NOT.search(title):
                    continue
                link = j.get("redirect_url")
                if link and link not in all_jobs:
                    all_jobs[link] = {
                        "title": title,
                        "company": (j.get("company") or {}).get("display_name") or "Unknown",
                        "location": (j.get("location") or {}).get("display_name") or "",
                        "posted": (j.get("created") or "")[:10],
                        "source": "Adzuna",
                    }
                    kept += 1
            print(f"{loc or 'All India'} p{page}: {len(results)} found, {kept} new relevant")
            if len(results) < RESULTS_PER_PAGE:
                time.sleep(PAUSE_SECONDS)
                break
        except Exception as e:
            api_failures += 1
            print(f"Exception for {loc} p{page}: {e}")
        time.sleep(PAUSE_SECONDS)

# ---------- JSearch (LinkedIn etc.), optional ----------
if rapid_key:
    for q in JSEARCH_QUERIES:
        try:
            r = requests.get(
                "https://jsearch.p.rapidapi.com/search",
                headers={"X-RapidAPI-Key": rapid_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
                params={"query": q, "page": "1", "num_pages": "1", "country": "in", "date_posted": "week"},
                timeout=40,
            )
            if r.status_code != 200:
                print(f"JSearch HTTP {r.status_code} for '{q}': {r.text[:150]}")
                continue
            results = r.json().get("data", [])
            kept = 0
            for j in results:
                title = j.get("job_title") or ""
                if not MUST_HAVE.search(title) or MUST_NOT.search(title):
                    continue
                link = j.get("job_apply_link")
                if link and link not in all_jobs:
                    place = ", ".join(x for x in [j.get("job_city"), j.get("job_state")] if x)
                    all_jobs[link] = {
                        "title": title,
                        "company": j.get("employer_name") or "Unknown",
                        "location": place,
                        "posted": (j.get("job_posted_at_datetime_utc") or "")[:10],
                        "source": j.get("job_publisher") or "JSearch",
                    }
                    kept += 1
            print(f"JSearch '{q}': {len(results)} found, {kept} new relevant")
        except Exception as e:
            print(f"JSearch exception for '{q}': {e}")
        time.sleep(2)
else:
    print("RAPIDAPI_KEY not set: skipping LinkedIn/JSearch.")

if api_failures == requests_made:
    print("All Adzuna requests failed. Check ADZUNA_APP_ID / ADZUNA_APP_KEY.")
    sys.exit(1)

if not all_jobs:
    print("No relevant jobs found today.")
    sys.exit(0)

print(f"Total unique relevant jobs: {len(all_jobs)}. Sending email...")

# newest first
ordered = sorted(all_jobs.items(), key=lambda kv: kv[1]["posted"], reverse=True)
items = ""
for link, j in ordered:
    items += (f"<li style='margin-bottom:12px'><b>{html.escape(j['title'])}</b><br>"
              f"{html.escape(j['company'])} &middot; {html.escape(j['location'])} &middot; {j['posted']} &middot; <i>{html.escape(j['source'])}</i><br>"
              f"<a href='{html.escape(link, quote=True)}'>View &amp; Apply</a></li>")

html_body = f"""
<html><body style="font-family: Arial, sans-serif; color: #333;">
  <h2 style="color:#0056b3;">Daily Job Scout: {len(ordered)} procurement &amp; supply chain jobs</h2>
  <p>All India (focus North India), posted in the last {MAX_DAYS_OLD} days.</p>
  <ul style="line-height:1.5; padding-left:18px;">{items}</ul>
</body></html>
"""

msg = MIMEMultipart("alternative")
msg["From"] = email_address
msg["To"] = email_address
msg["Subject"] = f"Daily Job Scout: {len(ordered)} procurement jobs"
msg.attach(MIMEText(html_body, "html"))

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(email_address, email_password)
        server.send_message(msg)
    print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
    sys.exit(1)
