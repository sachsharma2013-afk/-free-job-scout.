import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 1. Fetch credentials from environment variables
api_key = os.environ.get("API_KEY")
email_address = os.environ.get("EMAIL_ADDRESS")
email_password = os.environ.get("EMAIL_PASSWORD")

if not all([api_key, email_address, email_password]):
    print("Error: Missing one or more environment variables.")
    exit(1)

# 2. Set the Jooble India endpoint
url = f"https://in.jooble.org/api/{api_key}"

# 3. Configure search combinations for procurement operations
search_payloads = [
    {"keywords": "procurement SAP S/4HANA", "location": "Punjab"},
    {"keywords": "purchase manager", "location": "Punjab"},
    {"keywords": "sourcing supply chain", "location": "Punjab"},
    {"keywords": "procurement operations", "location": "Punjab"}
]

headers = {"Content-Type": "application/json"}
all_job_results = []
seen_links = set()

# 4. Loop through searches and fetch jobs
for payload in search_payloads:
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobs", [])
            
            for job in jobs:
                title = job.get("title", "Unknown Title")
                company = job.get("company", "Unknown Company")
                link = job.get("link")
                
                if link and link not in seen_links:
                    seen_links.add(link)
                    # Format as HTML list items
                    all_job_results.append(
                        f"<li><b>{title}</b> at {company}<br><a href='{link}'>View Job & Apply</a></li>"
                    )
        else:
            print(f"Error fetching data for {payload['keywords']}: {response.status_code}")
    except Exception as e:
        print(f"Exception during API call: {e}")

# 5. Format and send the email
if all_job_results:
    print(f"Found {len(all_job_results)} unique jobs. Sending email...")
    
    msg = MIMEMultipart()
    msg['From'] = email_address
    msg['To'] = email_address
    msg['Subject'] = "Daily Job Scout: Procurement & Supply Chain Roles in Punjab"
    
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #0056b3;">Your Daily Job Alerts</h2>
        <p>Here are the latest procurement and supply chain opportunities in Punjab:</p>
        <ul style="line-height: 1.6;">
          {'<br><br>'.join(all_job_results)}
        </ul>
        <p>Good luck!</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        # Connect to Gmail's SMTP server
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(email_address, email_password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")
else:
    print("No new jobs found today.")
