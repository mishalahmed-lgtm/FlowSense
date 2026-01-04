# Setting Up Render Cron Job for Device Sync

## Overview
The device sync is now handled by a Render Cron Job that runs hourly. This fetches:
- Installations data (locations) from API A
- Telemetry data from SmartTive API B
- Sends complete device data to FlowSense

## Option 1: Manual Setup on Render Dashboard

### Step 1: Create Cron Job
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Cron Job"**
3. Fill in:
   - **Name**: `flowsense-device-sync`
   - **Environment**: Python 3
   - **Region**: Same as your web service
   - **Branch**: `master`
   - **Schedule**: `0 * * * *` (every hour)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python scripts/sync_devices_complete.py`

### Step 2: Add Environment Variables
In the cron job settings, add these environment variables:

| Key | Value |
|-----|-------|
| `FLOWSENSE_API_URL` | `https://flowsense-772d.onrender.com` |
| `FLOWSENSE_API_KEY` | `ext_DOxMY4SinUXk1kgud1LZTBh06QRQvIgPSTJzx4hIO6k` |
| `API_A_URL` | `https://flooddemo-qr2x.onrender.com/api/installations` |
| `API_B_URL` | `https://op1.smarttive.com/device/{}` |
| `API_B_KEY` | `M2nJ5vKt8QwR3pLxT0yZ7aDbU1sH6cYe` |

### Step 3: Deploy
Click **"Create Cron Job"** and it will start running hourly.

## Option 2: Infrastructure as Code (render.yaml)

Create a `render.yaml` in your repo:

```yaml
services:
  # Existing web service
  - type: web
    name: flowsense
    env: python
    # ... your existing config ...

  # NEW: Hourly device sync
  - type: cron
    name: flowsense-device-sync
    env: python
    repo: https://github.com/mishalahmed-lgtm/FlowSense
    schedule: "0 * * * *"
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python scripts/sync_devices_complete.py"
    envVars:
      - key: FLOWSENSE_API_URL
        value: https://flowsense-772d.onrender.com
      - key: FLOWSENSE_API_KEY
        value: ext_DOxMY4SinUXk1kgud1LZTBh06QRQvIgPSTJzx4hIO6k
      - key: API_A_URL
        value: https://flooddemo-qr2x.onrender.com/api/installations
      - key: API_B_URL
        value: https://op1.smarttive.com/device/{}
      - key: API_B_KEY
        value: M2nJ5vKt8QwR3pLxT0yZ7aDbU1sH6cYe
```

Then push to GitHub and Render will auto-detect and create the cron job.

## What Happens Now?

✅ **Every hour** at minute 0:
1. Cron job starts
2. Fetches all installations (with locations)
3. Fetches telemetry for each device (200 concurrent)
4. Builds complete device JSON with:
   - Location
   - Telemetry
   - History (3 data points)
   - Dashboard widgets
   - Health metrics
   - Randomized fallback data
5. Sends to `/api/v1/external/devices/complete`
6. All pages populate: Map, Health, Analytics, Dashboard

✅ **Background service**: Now just runs idle (device sync disabled)

✅ **Performance**: ~10,000 devices synced in ~30 seconds

## Testing Manually

Run once to test:
```bash
cd /home/mishal/my-iot-project
python scripts/sync_devices_complete.py
```

Check the output for success/failure counts.

## Monitoring

View cron job logs on Render Dashboard → Cron Jobs → flowsense-device-sync → Logs

## Schedule Options

- Every hour: `0 * * * *`
- Every 30 minutes: `*/30 * * * *`
- Every 2 hours: `0 */2 * * *`
- Every day at 2am: `0 2 * * *`

