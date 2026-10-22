import os
import sys
import html
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 1. Credentials from environment (GitHub Secrets)
api_key = (os.environ.get("API_KEY") or "").strip()
email_address = (os.environ.get("EMAIL_ADDRESS") or "").strip()
# Gmail App Passwords are shown with spaces; remove them
email_password = (os.environ.get("EMAIL_PASSWORD") or "").replace(" ", "").strip()

missing = [n for n, v in [("API_KEY", api_key),
                          ("EMAIL_ADDRESS", email_address),
                          ("EMAIL_PASSWORD", email_password)] if not v]
if missing:
    print(f"Error: missing secrets: {', '.join(missing)}")
    sys.exit(1)

# 2. Jooble endpoint (in.jooble.org blocks GitHub servers with 403)
base_urls = [f"https://jooble.org/api/{api_key}"]

# 3. Searches: broader keywords x nearby locations
keywords_list = ["procurement manager", "purchase manager", "strategic sourcing", "supply chain manager", "SAP MM"]
locations = ["Ludhiana, Punjab, India", "Chandigarh, India", "Punjab, India", "India"]
search_payloads = [{"keywords": k, "location": l} for k in keywords_list for l in locations]

headers = {"Content-Type": "application/json"}
all_job_results = []
seen_links = set()
api_failures = 0

# 4. Fetch jobs
for payload in search_payloads:
    jobs = []
    ok = False
    for url in base_urls:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"HTTP {response.status_code} for {payload}: {response.text[:100]}")
                continue
            ok = True
            data = response.json()
            jobs = data.get("jobs", [])
            print(f"   totalCount={data.get('totalCount')}")
            if jobs:
                break
        except Exception as e:
            print(f"Exception for {payload}: {e}")
    if not ok:
        api_failures += 1
    print(f"{payload['keywords']} | {payload['location']}: {len(jobs)} jobs")
    for job in jobs:
        title = html.escape(job.get("title") or "Unknown Title")
        company = html.escape(job.get("company") or "Unknown Company")
        location = html.escape(job.get("location") or "")
        link = job.get("link")
        if link and link not in seen_links:
            seen_links.add(link)
            all_job_results.append(
                f"<li><b>{title}</b> at {company} ({location})<br>"
                f"<a href='{html.escape(link, quote=True)}'>View Job &amp; Apply</a></li>"
            )

# Fail the workflow if every search failed (bad key etc.)
if api_failures == len(search_payloads):
    print("All Jooble requests failed. Check API_KEY.")
    sys.exit(1)

# 5. Send email
if not all_job_results:
    print("No jobs found today.")
    sys.exit(0)

print(f"Found {len(all_job_results)} unique jobs. Sending email...")

items = "".join(all_job_results)
html_body = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333;">
    <h2 style="color: #0056b3;">Your Daily Job Alerts</h2>
    <p>Latest procurement and supply chain opportunities in Punjab:</p>
    <ul style="line-height: 1.8;">{items}</ul>
    <p>Good luck!</p>
  </body>
</html>
"""

msg = MIMEMultipart("alternative")
msg["From"] = email_address
msg["To"] = email_address
msg["Subject"] = "Daily Job Scout: Procurement & Supply Chain Roles in Punjab"
msg.attach(MIMEText(html_body, "html"))

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(email_address, email_password)
        server.send_message(msg)
    print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
    sys.exit(1)
