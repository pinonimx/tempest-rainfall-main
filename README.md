# Tempest Rainfall

Automated rainfall data collection and monthly reporting from an onsite WeatherFlow Tempest weather station.

## How it works

Two GitHub Actions workflows run automatically:

**1. Daily logger** (`.github/workflows/rainfall.yml`)
Runs every day at 6 AM Central. Pulls the previous day's observations from the WeatherFlow API and appends daily rainfall totals (in inches) to `daily_rainfall.csv`.

**2. Monthly report** (`.github/workflows/monthly_report.yml`)
Runs on the first Monday of every month. Reads `daily_rainfall.csv`, generates an HTML email summarizing the prior month's rainfall (total inches, rain day count, and a full day-by-day table), and sends it to the configured recipient list via SendGrid.

## Repository secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `TEMPEST_API_TOKEN` | WeatherFlow API token |
| `TEMPEST_STATION_ID` | WeatherFlow station ID |
| `RESEND_API_KEY` | Resend API key (resend.com) |
| `REPORT_FROM_EMAIL` | Verified sender address in Resend (e.g. `reports@yourdomain.com`) |
| `REPORT_FROM_NAME` | Sender display name (e.g. `Tempest Weather Station`) |
| `REPORT_RECIPIENTS` | Comma-separated list of recipient emails |

## Data

`daily_rainfall.csv` is the master data file. It is updated automatically each day and committed back to the repo by the daily logger workflow.

## Manual runs

Both workflows support `workflow_dispatch` — you can trigger either one manually from the **Actions** tab in GitHub.
