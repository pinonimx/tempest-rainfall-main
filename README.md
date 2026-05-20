# Tempest Rainfall

Automated rainfall data collection and monthly reporting from an onsite WeatherFlow Tempest weather station. Runs entirely on GitHub Actions — no servers required.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Setup & Configuration](#setup--configuration)
- [Schedules](#schedules)
- [Troubleshooting](#troubleshooting)

---

## System Overview

This system does two things automatically:

1. **Collects daily rainfall data** from a WeatherFlow Tempest station via the WeatherFlow REST API and stores it in a CSV file committed to this repository.
2. **Sends a monthly rainfall report** on the first Monday of each month — an HTML email with a PDF attachment — to a configured list of recipients.

### Components

| File | Purpose |
|---|---|
| `rainfall_logger.py` | Fetches yesterday's finalized rainfall from the WeatherFlow API and updates `daily_rainfall.csv` |
| `monthly_report.py` | Reads the CSV, generates an HTML email + PDF report, and sends it via Gmail SMTP |
| `daily_rainfall.csv` | Master data file — one row per day, rainfall in inches |
| `.github/workflows/rainfall.yml` | Runs `rainfall_logger.py` daily at 6 AM Central |
| `.github/workflows/monthly_report.yml` | Runs `monthly_report.py` on the first Monday of each month at 7 AM Central |

---

## Architecture

```
┌─────────────────────────┐
│  WeatherFlow Tempest     │
│  Station (onsite)        │
└──────────┬──────────────┘
           │ REST API
           ▼
┌─────────────────────────┐        ┌──────────────────────┐
│  rainfall_logger.py      │──────▶ │  daily_rainfall.csv  │
│  (runs daily, 6 AM CST)  │ commit │  (stored in GitHub)  │
└─────────────────────────┘        └──────────┬───────────┘
                                              │ reads
                                              ▼
                                   ┌──────────────────────┐
                                   │  monthly_report.py   │
                                   │  (1st Monday/month)  │
                                   └──────────┬───────────┘
                                              │ sends
                                              ▼
                                   ┌──────────────────────┐
                                   │  Recipients          │
                                   │  HTML email + PDF    │
                                   └──────────────────────┘
```

### Data Flow

**Daily (6 AM Central):**
1. GitHub Actions triggers `rainfall.yml`
2. `rainfall_logger.py` calls the WeatherFlow station API
3. Reads `precip_accum_local_yesterday_final` — the QC-corrected daily rainfall total for yesterday (mm), converts to inches
4. Updates `daily_rainfall.csv` with yesterday's entry
5. Commits and pushes the updated CSV back to the repository

**Monthly (first Monday, 7 AM Central):**
1. GitHub Actions triggers `monthly_report.yml`
2. `monthly_report.py` reads `daily_rainfall.csv`
3. Filters to the previous full month, computes total rainfall and rain day count
4. Builds an HTML email (inline, rendered in the inbox)
5. Builds a PDF report (via ReportLab) with the same data, suitable for archiving
6. Sends via Gmail SMTP with the PDF as an attachment

---

## Setup & Configuration

### Prerequisites

- A GitHub account with this repository forked or cloned
- A **WeatherFlow Tempest** weather station with a personal API token
  - Get your token at: [tempestwx.com](https://tempestwx.com) → Settings → Data Authorizations → Create Token
  - Get your station ID from the same settings page or the WeatherFlow API
- A **Gmail account** with 2-Step Verification enabled and an App Password created
  - App Passwords: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

### Step-by-Step Deployment

**1. Add GitHub Secrets**

Go to your repository → **Settings → Secrets and variables → Actions → New repository secret** and add each of the following:

| Secret | Description | Example |
|---|---|---|
| `TEMPEST_API_TOKEN` | WeatherFlow personal access token | `a1b2c3d4-...` |
| `TEMPEST_STATION_ID` | WeatherFlow station ID (numeric) | `123456` |
| `SMTP_USERNAME` | Gmail address used to send | `reports@gmail.com` |
| `SMTP_PASSWORD` | Gmail App Password (16 characters, no spaces) | `abcdabcdabcdabcd` |
| `REPORT_FROM_EMAIL` | Sender address shown in the email | `reports@gmail.com` |
| `REPORT_FROM_NAME` | Display name shown in the email | `Tempest Weather Station` |
| `REPORT_RECIPIENTS` | Comma-separated recipient email addresses | `a@example.com,b@example.com` |

**2. Enable GitHub Actions**

If Actions are not already enabled, go to the **Actions** tab in your repository and click **Enable Actions**.

**3. Run the Daily Logger for the First Time**

Go to **Actions → Daily Rainfall → Run workflow** to manually trigger an initial run. This populates the CSV with yesterday's data and confirms the API connection is working.

Check the workflow run logs — you should see:
```
Running logger for: YYYY-MM-DD
Yesterday (YYYY-MM-DD): X.XXXX mm = X.XXXX in
Done.
```

**4. Verify the CSV**

After the run completes, check `daily_rainfall.csv` in the repository. It should have a new or updated entry for yesterday.

**5. Test the Monthly Report**

Go to **Actions → Monthly Rainfall Report → Run workflow** to send a test report. Check the workflow logs for:
```
Generating report for: [Month] [Year]
  Total: X.XX in  |  Rain days: X/XX
PDF generated: XXXXX bytes
Report sent successfully.
```

---

## Schedules

Both workflows run automatically on GitHub's infrastructure. No manual intervention is needed during normal operation.

| Workflow | Schedule | Cron | What it does |
|---|---|---|---|
| Daily Rainfall | Every day at 6 AM Central | `0 11 * * *` | Logs yesterday's rainfall to CSV |
| Monthly Rainfall Report | First Monday of each month at 7 AM Central | `0 12 1-7 * 1` | Sends monthly report email with PDF |

> **Note:** GitHub Actions cron runs in UTC. `0 11 * * *` = 6 AM CDT (UTC−5) and 5 AM CST (UTC−6). The one-hour shift in winter is expected and does not affect functionality.

The monthly report always covers the **previous full calendar month**. Since it runs the first Monday of the month (days 1–7), the prior month's data is always complete in the CSV before the report fires.

---

## Troubleshooting

### Daily Logger

**Workflow fails — API error or no data returned**
- Verify `TEMPEST_API_TOKEN` and `TEMPEST_STATION_ID` are correct in GitHub Secrets
- Check that your Tempest station is online at [tempestwx.com](https://tempestwx.com)
- The API endpoint used: `GET /swd/rest/observations/station/{station_id}`

**CSV not updated after a successful run**
- Check the "Commit & push updated CSV" step in the workflow logs
- Confirm the workflow has `permissions: contents: write` in `rainfall.yml`
- If the push is rejected with "fetch first", add `git pull --rebase origin main` before `git push`

**Yesterday's rainfall shows 0.0000 but it rained**
- The station may have been offline or lost connectivity during the day
- WeatherFlow's `precip_accum_local_yesterday_final` reflects finalized QC data — occasional station dropouts result in 0
- No manual correction is needed; future days are unaffected

**CSV has a gap of several days or weeks**
- The daily logger only writes one day per run (yesterday)
- For gaps, use the device observations API endpoint (`/swd/rest/observations/?device_id=...`) with a custom date range to backfill missing dates
- Refer to the archived `backfill.py` approach if needed

### Monthly Report

**SMTPAuthenticationError (535)**
- The Gmail App Password may be incorrect or expired
- Regenerate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) and update the `SMTP_PASSWORD` secret
- Confirm 2-Step Verification is still enabled on the Gmail account

**Report shows the wrong month**
- The script targets the previous full calendar month based on `datetime.now()` in the `America/Chicago` timezone
- If triggered manually mid-month, it will correctly report the prior month
- Do not change the `TIMEZONE` constant unless the station has moved

**PDF not attached or email not received**
- Check the full workflow log for any Python tracebacks
- Confirm `reportlab` is listed in the `pip install` step of `monthly_report.yml`
- Verify all five email secrets are set correctly (`SMTP_USERNAME`, `SMTP_PASSWORD`, `REPORT_FROM_EMAIL`, `REPORT_FROM_NAME`, `REPORT_RECIPIENTS`)

**Report fires but recipients don't receive it**
- Check spam/junk folders — Gmail-sourced automated emails occasionally get filtered
- Verify `REPORT_RECIPIENTS` contains valid, comma-separated email addresses with no extra spaces
- Check the Gmail account's sent folder to confirm the message was sent

### General

**Workflow does not trigger on schedule**
- GitHub may delay scheduled workflows by up to 15–30 minutes during high load periods
- Scheduled workflows in repositories with no recent activity may be disabled by GitHub — push any commit to re-enable them
- Manually trigger via the Actions tab to confirm the workflow itself is functional

**How to re-enable a disabled scheduled workflow**
- GitHub disables scheduled workflows in repositories with no activity for 60 days
- Simply push a commit (e.g., update README) to reactivate the schedule
