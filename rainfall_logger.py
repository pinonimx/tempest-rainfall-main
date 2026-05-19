import os
import csv
import requests
from datetime import datetime, timedelta
import pytz

# --- Config ---
TEMPEST_API_TOKEN  = os.environ['TEMPEST_API_TOKEN']
TEMPEST_STATION_ID = os.environ['TEMPEST_STATION_ID']
MASTER_CSV         = 'daily_rainfall.csv'
TIMEZONE           = 'America/Chicago'

tz = pytz.timezone(TIMEZONE)

today     = datetime.now(tz)
yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')

print(f"Running logger for: {yesterday}")

# --- Fetch latest station observation (dict format) ---
# The station endpoint returns the current observation as a named-field dict.
# It includes precip_accum_local_yesterday_final: the finalized daily total
# for yesterday in mm, which is exactly what we need.
url = (
    f'https://swd.weatherflow.com/swd/rest/observations/station/{TEMPEST_STATION_ID}'
    f'?token={TEMPEST_API_TOKEN}'
)

resp = requests.get(url)
resp.raise_for_status()
data = resp.json()

obs_list = data.get('obs') or data.get('observations') or []
if not obs_list:
    print("ERROR: No observation returned from API.")
    print("Full response:", data)
    raise SystemExit(1)

obs = obs_list[0]
print(f"DEBUG obs keys: {list(obs.keys())}")

# Extract yesterday's finalized rainfall total (mm) and convert to inches
yesterday_mm = obs.get('precip_accum_local_yesterday_final') or 0.0
yesterday_in = round(yesterday_mm / 25.4, 4)

print(f"Yesterday ({yesterday}): {yesterday_mm:.4f} mm = {yesterday_in:.4f} in")

# --- Load existing CSV ---
data_dict = {}
header    = ['Date', 'Rainfall (inches)']
try:
    with open(MASTER_CSV, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) >= 2:
                try:
                    data_dict[row[0]] = float(row[1])
                except ValueError:
                    pass
except FileNotFoundError:
    pass

# --- Update yesterday's entry ---
if yesterday not in data_dict:
    print(f"Added:   {yesterday} = {yesterday_in:.4f} in")
elif data_dict[yesterday] != yesterday_in:
    print(f"Updated: {yesterday} was {data_dict[yesterday]:.4f} in -> {yesterday_in:.4f} in")
else:
    print(f"No change: {yesterday} = {yesterday_in:.4f} in")

data_dict[yesterday] = yesterday_in

# --- Write updated CSV ---
with open(MASTER_CSV, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for date in sorted(data_dict.keys()):
        writer.writerow([date, f'{data_dict[date]:.4f}'])

print("Done.")
