import os
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date
import calendar
import pytz

# --- Config ---
SMTP_HOST  = 'smtp.gmail.com'
SMTP_PORT  = 587
SMTP_USER  = os.environ['SMTP_USERNAME']
SMTP_PASS  = os.environ['SMTP_PASSWORD']
FROM_EMAIL = os.environ.get('REPORT_FROM_EMAIL', SMTP_USER)
FROM_NAME  = os.environ.get('REPORT_FROM_NAME', 'Tempest Weather Station')
# Comma-separated list of recipient emails
RECIPIENTS = [e.strip() for e in os.environ['REPORT_RECIPIENTS'].split(',') if e.strip()]
MASTER_CSV       = 'daily_rainfall.csv'
TIMEZONE         = 'America/Chicago'

tz = pytz.timezone(TIMEZONE)

# --- Determine the previous full month ---
today = datetime.now(tz).date()
first_of_this_month = today.replace(day=1)
last_month_end = first_of_this_month - __import__('datetime').timedelta(days=1)
report_year  = last_month_end.year
report_month = last_month_end.month
month_label  = last_month_end.strftime('%B %Y')  # e.g. "April 2026"

print(f"Generating report for: {month_label}")

# --- Load CSV ---
data = {}
try:
    with open(MASTER_CSV, newline='') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            day_str, precip_str = row[0], row[1]
            try:
                data[day_str] = float(precip_str)
            except ValueError:
                pass
except FileNotFoundError:
    print(f"ERROR: {MASTER_CSV} not found.")
    raise

# --- Filter to report month ---
num_days = calendar.monthrange(report_year, report_month)[1]
daily_rows = []
for day_num in range(1, num_days + 1):
    d = date(report_year, report_month, day_num)
    day_str = d.strftime('%Y-%m-%d')
    precip = data.get(day_str, 0.0)
    daily_rows.append((d, day_str, precip))

total_precip  = sum(r[2] for r in daily_rows)
rain_day_count = sum(1 for r in daily_rows if r[2] > 0)

print(f"  Total: {total_precip:.2f} in  |  Rain days: {rain_day_count}/{num_days}")

# --- Build HTML email ---
table_rows_html = ''
for d, day_str, precip in daily_rows:
    day_label   = d.strftime('%a, %b %-d')  # e.g. "Mon, Apr 1"
    precip_disp = f'{precip:.2f}"'
    row_bg      = '#f0f7ff' if precip > 0 else '#ffffff'
    table_rows_html += f'''
        <tr style="background:{row_bg};">
          <td style="padding:6px 12px; border-bottom:1px solid #e8e8e8; color:#333;">{day_label}</td>
          <td style="padding:6px 12px; border-bottom:1px solid #e8e8e8; color:#333; text-align:right; font-family:monospace;">{precip_disp}</td>
        </tr>'''

html_body = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background:#f5f5f5; font-family:Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5; padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#1a4a7a; padding:28px 32px;">
            <p style="margin:0; color:#a8c8f0; font-size:12px; text-transform:uppercase; letter-spacing:1px;">Monthly Rainfall Report</p>
            <h1 style="margin:6px 0 0; color:#ffffff; font-size:26px;">{month_label}</h1>
          </td>
        </tr>

        <!-- Summary stats -->
        <tr>
          <td style="padding:28px 32px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="48%" style="background:#eef4fb; border-radius:8px; padding:20px 24px; text-align:center;">
                  <p style="margin:0; font-size:12px; color:#666; text-transform:uppercase; letter-spacing:1px;">Total Rainfall</p>
                  <p style="margin:8px 0 0; font-size:36px; font-weight:bold; color:#1a4a7a;">{total_precip:.2f}"</p>
                </td>
                <td width="4%"></td>
                <td width="48%" style="background:#eef4fb; border-radius:8px; padding:20px 24px; text-align:center;">
                  <p style="margin:0; font-size:12px; color:#666; text-transform:uppercase; letter-spacing:1px;">Rain Days</p>
                  <p style="margin:8px 0 0; font-size:36px; font-weight:bold; color:#1a4a7a;">{rain_day_count}<span style="font-size:18px; color:#888;">/{num_days}</span></p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Daily table -->
        <tr>
          <td style="padding:28px 32px;">
            <p style="margin:0 0 12px; font-size:13px; font-weight:bold; color:#444; text-transform:uppercase; letter-spacing:0.5px;">Daily Breakdown</p>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e8e8e8; border-radius:6px; overflow:hidden;">
              <thead>
                <tr style="background:#f8f8f8;">
                  <th style="padding:8px 12px; text-align:left; font-size:12px; color:#666; border-bottom:1px solid #e8e8e8;">Date</th>
                  <th style="padding:8px 12px; text-align:right; font-size:12px; color:#666; border-bottom:1px solid #e8e8e8;">Rainfall</th>
                </tr>
              </thead>
              <tbody>{table_rows_html}
              </tbody>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px 28px; border-top:1px solid #f0f0f0;">
            <p style="margin:0; font-size:11px; color:#aaa;">
              Data sourced from onsite WeatherFlow Tempest station &middot; {month_label} &middot; All measurements in inches
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>'''

# --- Send via Gmail SMTP ---
msg = MIMEMultipart('alternative')
msg['Subject'] = f'Rainfall Report — {month_label}'
msg['From']    = f'{FROM_NAME} <{FROM_EMAIL}>'
msg['To']      = ', '.join(RECIPIENTS)
msg.attach(MIMEText(html_body, 'html'))

with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
    server.ehlo()
    server.starttls()
    server.login(SMTP_USER, SMTP_PASS)
    server.sendmail(FROM_EMAIL, RECIPIENTS, msg.as_string())

print("Report sent successfully.")
