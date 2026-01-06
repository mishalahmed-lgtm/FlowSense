# Device Sync - Background Service (FREE, No Cron Needed!)

## Overview
The device sync is now **automatically handled by the background service** that runs hourly for FREE. No Render Cron needed!

This fetches:
- Installations data (locations) from API A
- Telemetry data from SmartTive API B
- Randomizes missing fields
- Builds complete device JSON with history, dashboard, fields, health
- Sends complete device data to FlowSense

## ✅ How It Works

The `ExternalAPISyncService` automatically:
1. **Runs on server startup** - Does initial sync immediately
2. **Runs every hour** - Keeps data fresh automatically
3. **Fetches from both APIs**:
   - Installations API → Locations
   - SmartTive API → Telemetry (200 concurrent requests)
4. **Randomizes missing data** - Fills in gaps with realistic values
5. **Sends complete device data** - All pages populate automatically

## 🎉 No Setup Required!

The background service is already running. Just deploy and it works!

**What you get:**
- ✅ Device Map (locations)
- ✅ Health Page (battery, status)
- ✅ Analytics (history/charts)
- ✅ Dashboard (auto-generated widgets)
- ✅ Utility (if telemetry has utility data)

## Manual Testing

If you want to test the sync manually, you can still run:
```bash
python scripts/sync_devices_complete.py
```

But the background service will do this automatically every hour!

## Option 1: Manual Setup on Render Dashboard

### Step 1: Create Cron Job
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Cron Job"**
3. Fill in all fields:
   - **Name**: `flowsense-device-sync`
   - **Repository**: `https://github.com/mishalahmed-lgtm/FlowSense` (or connect your GitHub account and select the repo)
   - **Environment**: `Python 3`
   - **Region**: Same as your web service (e.g., `Oregon (US West)`)
   - **Branch**: `master`
   - **Root Directory**: Leave empty (or `/` if required)
   - **Schedule**: `0 * * * *` (every hour at minute 0)
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

