import os
import csv
import requests
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

# --- Config ---
TEMPEST_API_TOKEN = os.environ['TEMPEST_API_TOKEN']
TEMPEST_STATION_ID = os.environ['TEMPEST_STATION_ID']
MASTER_CSV = 'daily_rainfall.csv'
TIMEZONE = 'America/Chicago'

tz = pytz.timezone(TIMEZONE)

# --- Determine range: previous month + yesterday ---
today = datetime.now(tz)

first_day_last_month = datetime(
    today.year if today.month > 1 else today.year - 1,
    today.month - 1 if today.month > 1 else 12,
    1,
    tzinfo=tz
)

yesterday = today - timedelta(days=1)
# Use end-of-day yesterday so the full day's observations are included
end_date = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=tz)

print(f"DEBUG: today={today.date()}, yesterday={yesterday.date()}")
print(f"DEBUG: Fetching data from {first_day_last_month} to {end_date}")
print(f"DEBUG: UNIX range: {int(first_day_last_month.timestamp())} -> {int(end_date.timestamp())}")

# --- Fetch data from WeatherFlow API ---
url = (
    f'https://swd.weatherflow.com/swd/rest/observations/station/{TEMPEST_STATION_ID}'
    f'?token={TEMPEST_API_TOKEN}&start={int(first_day_last_month.timestamp())}&end={int(end_date.timestamp())}'
)

resp = requests.get(url)
resp.raise_for_status()

data = resp.json()
print(f"DEBUG: API response keys: {list(data.keys())}")

# Determine the correct key for observations
obs_data = data.get('observations') or data.get('obs') or []
if not obs_data:
    print("WARNING: No observations found in API response. Check your station ID and API token.")
    print("DEBUG: Full API response:", data)
else:
    print(f"DEBUG: obs count={len(obs_data)}, first obs type={type(obs_data[0]).__name__}")
    print(f"DEBUG: first obs sample: {obs_data[0]}")

# WeatherFlow station observations arrive as indexed arrays, not dicts.
# Array layout (from API docs):
#   [0]=timestamp, [6]=pressure, [7]=air_temp, [12]=precip(mm in interval),
#   [18]=local_day_rain_accumulation, [19]=rain_accum_final
# Dict-based format (some endpoints) uses 'timestamp' and 'precip_accum' keys.

# --- Aggregate daily rainfall ---
daily_totals = defaultdict(float)
for obs in obs_data:
    if isinstance(obs, dict):
        ts = obs.get('timestamp')
        precip = obs.get('precip_accum') or obs.get('precip', 0.0)
    elif isinstance(obs, (list, tuple)):
        ts = obs[0] if len(obs) > 0 else None
        # Index 12 = per-interval precipitation in mm; convert mm -> inches
        precip_mm = obs[12] if len(obs) > 12 and obs[12] is not None else 0.0
        precip = precip_mm / 25.4
    else:
        print(f"DEBUG: Unexpected obs type: {type(obs)} value: {obs}")
        continue

    if ts is None:
        print(f"DEBUG: Skipping obs with no timestamp: {obs}")
        continue

    dt = datetime.fromtimestamp(ts, tz)
    day_str = dt.strftime('%Y-%m-%d')
    daily_totals[day_str] += precip
    print(f"DEBUG: obs ts={ts} -> {dt.date()}, precip={precip:.4f} in")

# Ensure all days in range exist
current = first_day_last_month
while current <= end_date:
    day_str = current.strftime('%Y-%m-%d')
    daily_totals.setdefault(day_str, 0.0)
    current += timedelta(days=1)

# --- Load existing CSV ---
data_dict = {}
try:
    with open(MASTER_CSV, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            date, precip = row
            data_dict[date] = float(precip)
except FileNotFoundError:
    header = ['date', 'precip_in']

# --- Update dict with debug logging ---
for date, precip in daily_totals.items():
    if date not in data_dict:
        print(f"Added new day: {date} = {precip:.2f} in")
        data_dict[date] = precip
    elif data_dict[date] != precip:
        print(f"Updated day: {date} old={data_dict[date]:.2f} in -> new={precip:.2f} in")
        data_dict[date] = precip
    else:
        print(f"No change: {date} = {precip:.2f} in")

# --- Write updated master CSV ---
with open(MASTER_CSV, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for date in sorted(data_dict.keys()):
        writer.writerow([date, data_dict[date]])
