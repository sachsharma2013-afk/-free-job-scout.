# Free Job Scout (India) — email digest

A small Python + GitHub Actions workflow that searches Adzuna's job ads API daily, prioritizes Punjab, scores job text against procurement/purchasing/sourcing keywords, removes duplicates, and emails a digest. It does **not** scrape logged-in LinkedIn/Naukri pages or submit applications.

## What is and isn't automated
- Automated: daily Adzuna searches, keyword-based relevance score, within-run duplicate removal, persistent seen-job IDs, email digest.
- Separate setup recommended: create native daily email alerts directly on LinkedIn and Naukri. This tool cannot guarantee every portal's listings.
- Review workflow: open the job link yourself; paste the selected job description and your master resume into ChatGPT to tailor the resume. No resume is sent to this script.
- Score is a transparent **keyword relevance estimate**, not a verified resume-to-job AI score. Tune keywords in `config.json`.

## Requirements (free tiers; provider terms/limits may change)
1. A GitHub account and a **private** repository.
2. Adzuna API `app_id` and `app_key` from https://developer.adzuna.com/ (access is subject to Adzuna's terms and quota).
3. A dedicated email sender account. For Gmail SMTP, turn on 2-Step Verification and create an App Password if your account offers it. Never use your normal Gmail password. Google recommends Sign in with Google where supported; this starter uses SMTP App Passwords.
4. GitHub repository Actions enabled.

## Install on Android
1. Download and extract this ZIP on your phone.
2. In GitHub, create a **new private repository** named `free-job-scout`.
3. Upload the extracted files and folders to the repository root. GitHub mobile may not upload folders cleanly; if so, use GitHub in Chrome with **Desktop site**, or upload the ZIP only if you then extract it locally and upload the files (GitHub does not run a ZIP as source).
4. In the repo, open **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `ADZUNA_APP_ID`
   - `ADZUNA_APP_KEY`
   - `MAIL_USERNAME` (sender Gmail address)
   - `MAIL_APP_PASSWORD` (16-character Google App Password; remove spaces)
   - `MAIL_TO` (destination email address)
5. Go to **Settings → Actions → General → Workflow permissions**. Choose **Read and write permissions** so the workflow can save seen-job IDs. Keep the repository private.
6. Open **Actions** and enable workflows if prompted. Choose **Daily Job Scout**, then **Run workflow** to test.
7. Open the run and inspect the log. If successful, check inbox and Spam. Daily schedule is 03:30 UTC = 09:00 India time; scheduled runs can be delayed by GitHub.

## Security
- Never place API keys, email passwords, your resume, phone number, or other private data in source files or commits.
- Add only the secrets above through GitHub Secrets. GitHub masks secrets in logs, but no secret system is perfect; do not print environment variables.
- This workflow sends only job listings to your email. It never uploads your resume to Adzuna.
- The repo needs write permission only to update `seen_jobs.json`. If you don't want that, remove the commit step; duplicate suppression across days will then be less reliable.
- Prefer a separate sender account and revoke its App Password if you stop using the workflow.
- Do not publish the repository. A private repo is not a substitute for careful secret handling.

## Limitations
- Adzuna coverage varies by location and job title. It does not guarantee coverage of LinkedIn, Naukri, every company career site, or every fresh listing.
- API free-tier access/quotas can change. If API access is denied or the quota is exhausted, inspect the Actions log.
- This tool deliberately does not automate logged-in website scraping, bypass access controls, or apply to jobs.
