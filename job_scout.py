import os
import re
import sys
import html
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---------- Credentials (GitHub Secrets) ----------
app_id = (os.environ.get("ADZUNA_APP_ID") or "").strip()
app_key = (os.environ.get("ADZUNA_APP_KEY") or "").strip()
email_address = (os.environ.get("EMAIL_ADDRESS") or "").strip()
email_password = (os.environ.get("EMAIL_PASSWORD") or "").replace(" ", "").strip()

missing = [n for n, v in [("ADZUNA_APP_ID", app_id), ("ADZUNA_APP_KEY", app_key),
                          ("EMAIL_ADDRESS", email_address), ("EMAIL_PASSWORD", email_password)] if not v]
if missing:
    print(f"Error: missing secrets: {', '.join(missing)}")
    sys.exit(1)

# ---------- Settings (edit these) ----------
SEARCH_TERMS = ["procurement", "purchase manager", "strategic sourcing",
                "supply chain", "SAP MM", "category manager", "buyer"]
LOCATIONS = ["Punjab", "Chandigarh", "Ludhiana", "Mohali"]
MAX_DAYS_OLD = 7
RESULTS_PER_PAGE = 50

MUST_HAVE = re.compile(r"procure|purchas|sourcing|buyer|supply chain|vendor|category|material|sap mm|scm|logistic|contract", re.I)
MUST_NOT = re.compile(r"sales|marketing|telecall|insurance|loan|recruit|bpo|customer care|business development|driver|teacher", re.I)

API = "https://api.adzuna.com/v1/api/jobs/in/search/1"

all_jobs = {}
api_failures = 0
requests_made = 0

for term in SEARCH_TERMS:
    for loc in LOCATIONS:
        params = {
            "app_id": app_id, "app_key": app_key,
            "what": term, "where": loc,
            "results_per_page": RESULTS_PER_PAGE,
            "max_days_old": MAX_DAYS_OLD,
            "sort_by": "date",
            "content-type": "application/json",
        }
        requests_made += 1
        try:
            r = requests.get(API, params=params, timeout=30)
            if r.status_code != 200:
                api_failures += 1
                print(f"HTTP {r.status_code} for '{term}' in {loc}: {r.text[:150]}")
                continue
            data = r.json()
            results = data.get("results", [])
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
                    }
                    kept += 1
            print(f"'{term}' | {loc}: {len(results)} found, {kept} new relevant")
        except Exception as e:
            api_failures += 1
            print(f"Exception for '{term}' in {loc}: {e}")

if api_failures == requests_made:
    print("All Adzuna requests failed. Check ADZUNA_APP_ID / ADZUNA_APP_KEY.")
    sys.exit(1)

if not all_jobs:
    print("No relevant jobs found today.")
    sys.exit(0)

print(f"Total unique relevant jobs: {len(all_jobs)}. Sending email...")

ordered = sorted(all_jobs.items(), key=lambda kv: kv[1]["posted"], reverse=True)
items = ""
for link, j in ordered:
    items += (f"<li style='margin-bottom:12px'><b>{html.escape(j['title'])}</b><br>"
              f"{html.escape(j['company'])} &middot; {html.escape(j['location'])} &middot; {j['posted']}<br>"
              f"<a href='{html.escape(link, quote=True)}'>View &amp; Apply</a></li>")

html_body = f"""
<html><body style="font-family: Arial, sans-serif; color: #333;">
  <h2 style="color:#0056b3;">Daily Job Scout: {len(ordered)} procurement &amp; supply chain jobs</h2>
  <p>Punjab / Chandigarh region, posted in the last {MAX_DAYS_OLD} days.</p>
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
