"""
One-time backfill script.
Fetches daily rainfall for the gap: 2025-10-03 through 2026-04-01
and merges it into daily_rainfall.csv.
Delete this file after the backfill workflow has run successfully.
"""

import os
import csv
import requests
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

# --- Config ---
TEMPEST_API_TOKEN  = os.environ['TEMPEST_API_TOKEN']
TEMPEST_STATION_ID = os.environ['TEMPEST_STATION_ID']
MASTER_CSV         = 'daily_rainfall.csv'
TIMEZONE           = 'America/Chicago'

tz = pytz.timezone(TIMEZONE)

# --- Hardcoded backfill range ---
start_date = datetime(2025, 10, 3,  0,  0,  0, tzinfo=tz)
end_date   = datetime(2026,  4, 1, 23, 59, 59, tzinfo=tz)

print(f"Backfilling: {start_date.date()} → {end_date.date()}")

# --- Fetch from WeatherFlow API ---
url = (
    f'https://swd.weatherflow.com/swd/rest/observations/station/{TEMPEST_STATION_ID}'
    f'?token={TEMPEST_API_TOKEN}'
    f'&start={int(start_date.timestamp())}'
    f'&end={int(end_date.timestamp())}'
)

resp = requests.get(url)
resp.raise_for_status()
data = resp.json()

obs_data = data.get('observations') or data.get('obs') or []
print(f"Observations returned: {len(obs_data)}")

if not obs_data:
    print("WARNING: No observations returned. Check API token and station ID.")
    raise SystemExit(1)

# --- Debug: print first observation to verify field layout ---
first_obs = obs_data[0]
print(f"DEBUG first obs type: {type(first_obs).__name__}")
print(f"DEBUG first obs: {first_obs}")
if isinstance(first_obs, (list, tuple)):
    for i, val in enumerate(first_obs):
        print(f"  [{i}] = {val}")

# --- Debug: print any obs where index 12 or 18/19 is non-zero ---
nonzero_found = False
for obs in obs_data[:500]:
    if isinstance(obs, (list, tuple)) and len(obs) > 19:
        if (obs[12] and obs[12] > 0) or (obs[18] and obs[18] > 0) or (obs[19] and obs[19] > 0):
            print(f"DEBUG non-zero precip obs: idx12={obs[12]} idx18={obs[18]} idx19={obs[19]} ts={obs[0]}")
            nonzero_found = True
if not nonzero_found:
    print("DEBUG: No non-zero precip found in first 500 obs (indices 12, 18, 19)")

# --- Aggregate daily totals ---
daily_totals = defaultdict(float)

for obs in obs_data:
    if isinstance(obs, dict):
        ts     = obs.get('timestamp')
        precip = obs.get('precip_accum') or obs.get('precip', 0.0)
    elif isinstance(obs, (list, tuple)):
        ts         = obs[0] if len(obs) > 0 else None
        precip_mm  = obs[12] if len(obs) > 12 and obs[12] is not None else 0.0
        precip     = precip_mm / 25.4  # mm → inches
    else:
        continue

    if ts is None:
        continue

    day_str = datetime.fromtimestamp(ts, tz).strftime('%Y-%m-%d')
    daily_totals[day_str] += precip

# Ensure every day in range exists (fill zeros for days with no obs)
current = start_date
while current <= end_date:
    daily_totals.setdefault(current.strftime('%Y-%m-%d'), 0.0)
    current += timedelta(days=1)

# --- Load existing CSV ---
data_dict = {}
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
    header = ['Date', 'Rainfall (inches)']

# --- Merge ---
added = updated = unchanged = 0
for day_str, precip in daily_totals.items():
    if day_str not in data_dict:
        data_dict[day_str] = precip
        added += 1
    elif data_dict[day_str] != precip:
        data_dict[day_str] = precip
        updated += 1
    else:
        unchanged += 1

print(f"Days added: {added} | updated: {updated} | unchanged: {unchanged}")

# --- Write updated CSV ---
with open(MASTER_CSV, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for day_str in sorted(data_dict.keys()):
        writer.writerow([day_str, f'{data_dict[day_str]:.4f}'])

print("CSV updated successfully.")
