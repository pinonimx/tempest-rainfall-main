"""
One-time backfill script.
Fetches daily rainfall for the gap: 2025-10-03 through 2026-04-01
using the device observations endpoint (supports historical time ranges).
Delete this file and backfill.yml after the workflow has run successfully.
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

# --- Step 1: Get device ID from station metadata ---
print("Fetching station metadata to get device ID...")
stations_url = f'https://swd.weatherflow.com/swd/rest/stations/{TEMPEST_STATION_ID}?token={TEMPEST_API_TOKEN}'
resp = requests.get(stations_url)
resp.raise_for_status()
station_data = resp.json()

# Find the Tempest device (type=AR for Air+Sky combined, or type=ST for Tempest)
device_id = None
for station in station_data.get('stations', []):
    for device in station.get('devices', []):
        device_type = device.get('device_type', '')
        if device_type in ('ST', 'AR'):  # ST = Tempest, AR = Air+Sky
            device_id = device.get('device_id')
            print(f"Found device: type={device_type} id={device_id}")
            break
    if device_id:
        break

if not device_id:
    print("ERROR: Could not find a Tempest/Air device in station metadata.")
    print("Station response:", station_data)
    raise SystemExit(1)

# --- Step 2: Fetch historical observations from device endpoint ---
start_date = datetime(2025, 10, 3,  0,  0,  0, tzinfo=tz)
end_date   = datetime(2026,  4, 1, 23, 59, 59, tzinfo=tz)

print(f"Fetching device observations: {start_date.date()} → {end_date.date()}")

obs_url = (
    f'https://swd.weatherflow.com/swd/rest/observations/'
    f'?device_id={device_id}'
    f'&time_start={int(start_date.timestamp())}'
    f'&time_end={int(end_date.timestamp())}'
    f'&token={TEMPEST_API_TOKEN}'
)

resp = requests.get(obs_url)
resp.raise_for_status()
obs_data_raw = resp.json()

print(f"DEBUG response keys: {list(obs_data_raw.keys())}")

obs_data = obs_data_raw.get('obs') or obs_data_raw.get('observations') or []
print(f"Observations returned: {len(obs_data)}")

if not obs_data:
    print("ERROR: No observations returned from device endpoint.")
    print("Full response:", obs_data_raw)
    raise SystemExit(1)

# --- Step 3: Print FULL array for Oct 24 (known heavy rain day ~21mm) ---
# and compare against Oct 4 (dry day) to identify precip field
print("\nDEBUG: Full array comparison — dry day vs rainy day:")
target_dates = {'2025-10-04', '2025-10-24', '2025-10-25'}
for obs in obs_data:
    day = obs[0] if isinstance(obs, (list, tuple)) else obs.get('timestamp', '')
    if day in target_dates:
        print(f"\n  [{day}] full array:")
        if isinstance(obs, (list, tuple)):
            for i, val in enumerate(obs):
                print(f"    [{i}] = {val}")

# --- Step 4: Aggregate daily totals ---
# Device endpoint returns array-format obs:
#   [0]=timestamp, [12]=precip mm per interval
# Station endpoint (dict) uses named fields — handled separately below
daily_totals = defaultdict(float)

for obs in obs_data:
    if isinstance(obs, (list, tuple)):
        ts        = obs[0] if len(obs) > 0 else None
        precip_mm = obs[12] if len(obs) > 12 and obs[12] is not None else 0.0
        precip_in = precip_mm / 25.4
    elif isinstance(obs, dict):
        ts        = obs.get('timestamp')
        precip_mm = obs.get('precip_accum_local_day_final') or obs.get('precip', 0.0)
        precip_in = precip_mm / 25.4
    else:
        continue

    if ts is None:
        continue

    # Daily bucket obs return a date string at [0] (e.g. '2025-10-04'),
    # not a Unix timestamp — handle both formats
    if isinstance(ts, str):
        day_str = ts  # already 'YYYY-MM-DD'
    else:
        day_str = datetime.fromtimestamp(ts, tz).strftime('%Y-%m-%d')
    daily_totals[day_str] += precip_in

# Ensure every day in range is present (zero-fill gaps)
current = start_date
while current <= end_date:
    daily_totals.setdefault(current.strftime('%Y-%m-%d'), 0.0)
    current += timedelta(days=1)

# Show any days with rain detected
rain_days = {d: v for d, v in daily_totals.items() if v > 0}
print(f"Rain days found: {len(rain_days)}")
for d, v in sorted(rain_days.items()):
    print(f"  {d}: {v:.4f} in")

# --- Step 5: Load and merge CSV ---
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

added = updated = unchanged = 0
for day_str, precip in daily_totals.items():
    if day_str not in data_dict:
        data_dict[day_str] = precip
        added += 1
    elif round(data_dict[day_str], 4) != round(precip, 4):
        data_dict[day_str] = precip
        updated += 1
    else:
        unchanged += 1

print(f"Days added: {added} | updated: {updated} | unchanged: {unchanged}")

with open(MASTER_CSV, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for day_str in sorted(data_dict.keys()):
        writer.writerow([day_str, f'{data_dict[day_str]:.4f}'])

print("CSV updated successfully.")
