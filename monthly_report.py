import os
import csv
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, date, timedelta
import calendar
import pytz

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.platypus import KeepTogether

# --- Config ---
SMTP_HOST  = 'smtp.gmail.com'
SMTP_PORT  = 587
SMTP_USER  = os.environ['SMTP_USERNAME']
SMTP_PASS  = os.environ['SMTP_PASSWORD']
FROM_EMAIL = os.environ.get('REPORT_FROM_EMAIL', SMTP_USER)
FROM_NAME  = os.environ.get('REPORT_FROM_NAME', 'Tempest Weather Station')
RECIPIENTS = [e.strip() for e in os.environ['REPORT_RECIPIENTS'].split(',') if e.strip()]
MASTER_CSV = 'daily_rainfall.csv'
TIMEZONE   = 'America/Chicago'

tz = pytz.timezone(TIMEZONE)

# --- Determine the previous full month ---
today            = datetime.now(tz).date()
first_of_this_month = today.replace(day=1)
last_month_end   = first_of_this_month - timedelta(days=1)
report_year      = last_month_end.year
report_month     = last_month_end.month
month_label      = last_month_end.strftime('%B %Y')

print(f"Generating report for: {month_label}")

# --- Load CSV ---
data = {}
try:
    with open(MASTER_CSV, newline='') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                data[row[0]] = float(row[1])
            except ValueError:
                pass
except FileNotFoundError:
    print(f"ERROR: {MASTER_CSV} not found.")
    raise

# --- Filter to report month ---
num_days = calendar.monthrange(report_year, report_month)[1]
daily_rows = []
for day_num in range(1, num_days + 1):
    d       = date(report_year, report_month, day_num)
    day_str = d.strftime('%Y-%m-%d')
    precip  = data.get(day_str, 0.0)
    daily_rows.append((d, day_str, precip))

total_precip   = sum(r[2] for r in daily_rows)
rain_day_count = sum(1 for r in daily_rows if r[2] > 0)

print(f"  Total: {total_precip:.2f} in  |  Rain days: {rain_day_count}/{num_days}")

# =============================================================================
# BUILD HTML EMAIL BODY
# =============================================================================
table_rows_html = ''
for d, day_str, precip in daily_rows:
    day_label   = d.strftime('%a, %b %-d')
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
        <tr>
          <td style="background:#1a4a7a; padding:28px 32px;">
            <p style="margin:0; color:#a8c8f0; font-size:12px; text-transform:uppercase; letter-spacing:1px;">Monthly Rainfall Report</p>
            <h1 style="margin:6px 0 0; color:#ffffff; font-size:26px;">{month_label}</h1>
          </td>
        </tr>
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

# =============================================================================
# BUILD PDF ATTACHMENT
# =============================================================================
NAVY   = colors.HexColor('#1a4a7a')
BLUE_L = colors.HexColor('#eef4fb')
GRAY   = colors.HexColor('#666666')
WHITE  = colors.white
BLACK  = colors.HexColor('#333333')

def build_pdf(daily_rows, total_precip, rain_day_count, num_days, month_label):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()

    s_label = ParagraphStyle('label', fontSize=8,  textColor=GRAY,  spaceAfter=2,  alignment=TA_CENTER, fontName='Helvetica')
    s_stat  = ParagraphStyle('stat',  fontSize=28, textColor=NAVY,  spaceAfter=0,  alignment=TA_CENTER, fontName='Helvetica-Bold')
    s_sub   = ParagraphStyle('sub',   fontSize=11, textColor=GRAY,  spaceAfter=0,  alignment=TA_CENTER, fontName='Helvetica')
    s_title = ParagraphStyle('title', fontSize=9,  textColor=GRAY,  spaceAfter=4,  fontName='Helvetica', leading=11)
    s_head  = ParagraphStyle('head',  fontSize=20, textColor=NAVY,  spaceAfter=6,  fontName='Helvetica-Bold')
    s_foot  = ParagraphStyle('foot',  fontSize=8,  textColor=GRAY,  alignment=TA_CENTER, fontName='Helvetica')
    s_th    = ParagraphStyle('th',    fontSize=8,  textColor=GRAY,  fontName='Helvetica-Bold')
    s_td    = ParagraphStyle('td',    fontSize=9,  textColor=BLACK, fontName='Helvetica')
    s_td_r  = ParagraphStyle('td_r',  fontSize=9,  textColor=BLACK, fontName='Helvetica', alignment=TA_RIGHT)

    story = []

    # Header block
    story.append(Paragraph('MONTHLY RAINFALL REPORT', s_title))
    story.append(Paragraph(month_label, s_head))
    story.append(HRFlowable(width='100%', thickness=1, color=NAVY, spaceAfter=16))

    # Stats row
    stat_data = [[
        [Paragraph('TOTAL RAINFALL', s_label), Paragraph(f'{total_precip:.2f}"', s_stat)],
        [Paragraph('RAIN DAYS',      s_label), Paragraph(f'{rain_day_count}', s_stat), Paragraph(f'out of {num_days}', s_sub)],
    ]]
    stat_table = Table([[
        Table([[Paragraph('TOTAL RAINFALL', s_label)], [Paragraph(f'{total_precip:.2f}"', s_stat)]], colWidths=[3*inch]),
        Table([[Paragraph('RAIN DAYS', s_label)], [Paragraph(f'{rain_day_count} / {num_days}', s_stat)]], colWidths=[3*inch]),
    ]], colWidths=[3.5*inch, 3.5*inch])
    stat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), BLUE_L),
        ('BACKGROUND', (1,0), (1,0), BLUE_L),
        ('ROUNDEDCORNERS', [6]),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING',   (0,0), (-1,-1), 12),
        ('RIGHTPADDING',  (0,0), (-1,-1), 12),
        ('LEFTPADDING',   (1,0), (1,0),   24),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 20))

    # Daily breakdown table
    table_data = [[
        Paragraph('DATE', s_th),
        Paragraph('RAINFALL', s_th),
    ]]
    for d, day_str, precip in daily_rows:
        row = [
            Paragraph(d.strftime('%a, %b %-d'), s_td),
            Paragraph(f'{precip:.4f}"', s_td_r),
        ]
        table_data.append(row)

    col_widths = [4.5*inch, 2.5*inch]
    daily_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    row_styles = [
        ('BACKGROUND',    (0,0),  (-1,0),  colors.HexColor('#f8f8f8')),
        ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),  (-1,0),  8),
        ('TEXTCOLOR',     (0,0),  (-1,0),  GRAY),
        ('BOTTOMPADDING', (0,0),  (-1,0),  6),
        ('TOPPADDING',    (0,0),  (-1,0),  6),
        ('LINEBELOW',     (0,0),  (-1,0),  0.5, colors.HexColor('#e8e8e8')),
        ('ALIGN',         (1,0),  (1,-1),  'RIGHT'),
        ('TOPPADDING',    (0,1),  (-1,-1), 5),
        ('BOTTOMPADDING', (0,1),  (-1,-1), 5),
        ('LINEBELOW',     (0,1),  (-1,-1), 0.25, colors.HexColor('#eeeeee')),
        ('BOX',           (0,0),  (-1,-1), 0.5, colors.HexColor('#e8e8e8')),
    ]
    # Highlight rainy days
    for i, (d, day_str, precip) in enumerate(daily_rows, start=1):
        if precip > 0:
            row_styles.append(('BACKGROUND', (0,i), (-1,i), BLUE_L))

    daily_table.setStyle(TableStyle(row_styles))
    story.append(daily_table)
    story.append(Spacer(1, 16))

    # Footer
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e0e0e0'), spaceAfter=8))
    story.append(Paragraph(
        f'Data sourced from onsite WeatherFlow Tempest station  ·  {month_label}  ·  All measurements in inches',
        s_foot
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()

pdf_bytes = build_pdf(daily_rows, total_precip, rain_day_count, num_days, month_label)
pdf_filename = f'Rainfall_Report_{month_label.replace(" ", "_")}.pdf'
print(f"PDF generated: {len(pdf_bytes)} bytes")

# =============================================================================
# SEND EMAIL WITH HTML BODY + PDF ATTACHMENT
# =============================================================================
msg = MIMEMultipart('mixed')
msg['Subject'] = f'Rainfall Report — {month_label}'
msg['From']    = f'{FROM_NAME} <{FROM_EMAIL}>'
msg['To']      = ', '.join(RECIPIENTS)

# HTML body
msg.attach(MIMEText(html_body, 'html'))

# PDF attachment
pdf_part = MIMEBase('application', 'pdf')
pdf_part.set_payload(pdf_bytes)
encoders.encode_base64(pdf_part)
pdf_part.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
msg.attach(pdf_part)

with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
    server.ehlo()
    server.starttls()
    server.login(SMTP_USER, SMTP_PASS)
    server.sendmail(FROM_EMAIL, RECIPIENTS, msg.as_string())

print("Report sent successfully.")
