/**
 * Script to seed SmartLPG Firebase collections with sample alerts and FOTA jobs
 * Run this from the browser console or as a one-time script
 */

import { db } from "../utils/firebase.js";
import { collection, doc, setDoc, getDocs, Timestamp } from "firebase/firestore";

const TENANT_ID = 3; // SmartLPG tenant ID

// Sample device IDs from SmartLPG (using some Tekelek device IDs)
const SAMPLE_DEVICE_IDS = [
  "TEK-00001", "TEK-00002", "TEK-00003", "TEK-00004", "TEK-00005",
  "TEK-00006", "TEK-00007", "TEK-00008", "TEK-00009", "TEK-00010",
  "TEK-00011", "TEK-00012", "TEK-00013", "TEK-00014", "TEK-00015",
];

const SAMPLE_DEVICE_NAMES = [
  "Tekelek Ultrasonic Meter 001",
  "Tekelek Ultrasonic Meter 002",
  "Tekelek Ultrasonic Meter 003",
  "Tekelek Ultrasonic Meter 004",
  "Tekelek Ultrasonic Meter 005",
  "Tekelek Ultrasonic Meter 006",
  "Tekelek Ultrasonic Meter 007",
  "Tekelek Ultrasonic Meter 008",
  "Tekelek Ultrasonic Meter 009",
  "Tekelek Ultrasonic Meter 010",
  "Tekelek Ultrasonic Meter 011",
  "Tekelek Ultrasonic Meter 012",
  "Tekelek Ultrasonic Meter 013",
  "Tekelek Ultrasonic Meter 014",
  "Tekelek Ultrasonic Meter 015",
];

/**
 * Generate sample alerts
 */
function generateAlerts() {
  const alertTypes = [
    { 
      title: 'Gas Tank Low - Refill Required', 
      message: 'Gas level is at {level}% for device {device}', 
      priority: 'critical', 
      field: 'lpg_tank_level',
      generateLevel: () => (Math.random() * 25).toFixed(1) // 0-25% for low tank
    },
    { 
      title: 'Gas Tank Low - Refill Required', 
      message: 'Gas level is at {level}% for device {device}', 
      priority: 'critical', 
      field: 'lpg_tank_level',
      generateLevel: () => (Math.random() * 25).toFixed(1)
    },
    { 
      title: 'Gas Tank Low - Refill Required', 
      message: 'Gas level is at {level}% for device {device}', 
      priority: 'critical', 
      field: 'lpg_tank_level',
      generateLevel: () => (Math.random() * 25).toFixed(1)
    },
    { 
      title: 'High Tank Level Warning', 
      message: 'LPG tank level is above normal threshold', 
      priority: 'medium', 
      field: 'lpg_tank_level',
      generateLevel: () => (80 + Math.random() * 20).toFixed(1) // 80-100%
    },
    { 
      title: 'Temperature Anomaly', 
      message: 'Tank temperature reading is abnormal', 
      priority: 'high', 
      field: 'temperature',
      generateLevel: () => null
    },
    { 
      title: 'Pressure Alert', 
      message: 'Tank pressure exceeded safe limits', 
      priority: 'critical', 
      field: 'pressure',
      generateLevel: () => null
    },
    { 
      title: 'Connection Lost', 
      message: 'Device has lost connection', 
      priority: 'high', 
      field: 'connectivity',
      generateLevel: () => null
    },
    { 
      title: 'Battery Low', 
      message: 'Device battery is running low', 
      priority: 'medium', 
      field: 'battery',
      generateLevel: () => null
    },
  ];

  const statuses = ['open', 'acknowledged', 'resolved', 'closed'];
  const alerts = [];

  // Generate mostly "Gas Tank Low" alerts to match the dashboard
  for (let i = 0; i < 30; i++) {
    const deviceIndex = Math.floor(Math.random() * SAMPLE_DEVICE_IDS.length);
    const deviceId = SAMPLE_DEVICE_IDS[deviceIndex];
    const deviceName = SAMPLE_DEVICE_NAMES[deviceIndex];
    
    // 70% chance of "Gas Tank Low" alert to match dashboard
    let alertType;
    if (i < 21 || Math.random() < 0.7) {
      alertType = alertTypes[0]; // Gas Tank Low
    } else {
      alertType = alertTypes[Math.floor(Math.random() * (alertTypes.length - 1)) + 1];
    }
    
    const status = i < 15 ? 'open' : statuses[Math.floor(Math.random() * statuses.length)]; // More open alerts
    
    // Create alerts from last 7 days, but more recent ones
    const createdDaysAgo = Math.floor(Math.random() * 3); // Last 3 days
    const createdHoursAgo = Math.floor(Math.random() * 24);
    const createdMinutesAgo = Math.floor(Math.random() * 60);
    const createdAt = new Date();
    createdAt.setDate(createdAt.getDate() - createdDaysAgo);
    createdAt.setHours(createdAt.getHours() - createdHoursAgo);
    createdAt.setMinutes(createdAt.getMinutes() - createdMinutesAgo);
    
    const gasLevel = alertType.generateLevel ? alertType.generateLevel() : null;
    const message = alertType.message
      .replace('{level}', gasLevel || 'N/A')
      .replace('{device}', deviceName);
    
    const alert = {
      id: `alert_${TENANT_ID}_${Date.now()}_${i}_${Math.random().toString(36).substr(2, 9)}`,
      tenant_id: TENANT_ID,
      device_id: deviceId,
      device_name: deviceName,
      rule_id: `rule_${Math.floor(Math.random() * 1000)}`,
      rule_name: alertType.title,
      priority: alertType.priority,
      status: status,
      title: alertType.title,
      message: message,
      trigger_data: {
        field: alertType.field,
        value: gasLevel ? parseFloat(gasLevel) : Math.round(Math.random() * 100),
        threshold: alertType.field === 'lpg_tank_level' ? 25 : Math.round(Math.random() * 80),
        operator: alertType.field === 'lpg_tank_level' ? '<' : '>',
      },
      created_at: Timestamp.fromDate(createdAt),
      updated_at: Timestamp.fromDate(createdAt),
      acknowledged_at: status !== 'open' ? Timestamp.fromDate(new Date(createdAt.getTime() + Math.random() * 60 * 60 * 1000)) : null,
      resolved_at: (status === 'resolved' || status === 'closed') ? Timestamp.fromDate(new Date(createdAt.getTime() + Math.random() * 120 * 60 * 1000)) : null,
    };

    alerts.push(alert);
  }

  return alerts;
}

/**
 * Generate sample FOTA jobs
 */
function generateFOTAJobs() {
  const firmwareVersions = [
    { id: 'fw_v1.2.3', version: '1.2.3' },
    { id: 'fw_v1.3.0', version: '1.3.0' },
    { id: 'fw_v1.3.1', version: '1.3.1' },
    { id: 'fw_v2.0.0', version: '2.0.0' },
  ];

  const statuses = ['running', 'completed', 'failed', 'scheduled', 'paused'];
  const jobs = [];

  for (let i = 0; i < 15; i++) {
    const fwVersion = firmwareVersions[Math.floor(Math.random() * firmwareVersions.length)];
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    
    // Select random devices (1-5 devices per job)
    const deviceCount = Math.floor(Math.random() * 5) + 1;
    const selectedDevices = [];
    for (let j = 0; j < deviceCount; j++) {
      const deviceId = SAMPLE_DEVICE_IDS[Math.floor(Math.random() * SAMPLE_DEVICE_IDS.length)];
      if (!selectedDevices.includes(deviceId)) {
        selectedDevices.push(deviceId);
      }
    }

    // Create jobs from last 30 days
    const createdDaysAgo = Math.floor(Math.random() * 30);
    const createdAt = new Date();
    createdAt.setDate(createdAt.getDate() - createdDaysAgo);

    const scheduledAt = status === 'scheduled' ? new Date(createdAt.getTime() + Math.random() * 7 * 24 * 60 * 60 * 1000) : null;
    const startedAt = (status === 'running' || status === 'completed' || status === 'failed') 
      ? new Date(createdAt.getTime() + (scheduledAt ? (scheduledAt.getTime() - createdAt.getTime()) : 0) + Math.random() * 60 * 60 * 1000)
      : null;
    const completedAt = (status === 'completed' || status === 'failed')
      ? new Date((startedAt || createdAt).getTime() + Math.random() * 2 * 60 * 60 * 1000)
      : null;

    const job = {
      id: `fota_job_${TENANT_ID}_${Date.now()}_${i}_${Math.random().toString(36).substr(2, 9)}`,
      name: `Firmware Update ${fwVersion.version} - Batch ${i + 1}`,
      tenant_id: TENANT_ID,
      firmware_version_id: fwVersion.id,
      firmware_version: fwVersion.version,
      device_ids: selectedDevices,
      device_count: selectedDevices.length,
      status: status,
      scheduled_at: scheduledAt ? Timestamp.fromDate(scheduledAt) : null,
      started_at: startedAt ? Timestamp.fromDate(startedAt) : null,
      completed_at: completedAt ? Timestamp.fromDate(completedAt) : null,
      created_at: Timestamp.fromDate(createdAt),
      updated_at: Timestamp.fromDate(createdAt),
      created_by_user_id: 'system',
    };

    jobs.push(job);
  }

  return jobs;
}

/**
 * Seed alerts to Firebase
 */
export async function seedAlerts() {
  try {
    console.log('🌱 Seeding alerts to Firebase...');
    const alerts = generateAlerts();
    
    for (const alert of alerts) {
      const alertRef = doc(db, "smartLPG_alerts", alert.id);
      await setDoc(alertRef, alert);
      console.log(`✅ Created alert: ${alert.id} - ${alert.title}`);
    }
    
    console.log(`✅ Successfully seeded ${alerts.length} alerts to Firebase`);
    return { success: true, count: alerts.length };
  } catch (error) {
    console.error('❌ Error seeding alerts:', error);
    throw error;
  }
}

/**
 * Seed FOTA jobs to Firebase
 */
export async function seedFOTAJobs() {
  try {
    console.log('🌱 Seeding FOTA jobs to Firebase...');
    const jobs = generateFOTAJobs();
    console.log(`📦 Generated ${jobs.length} FOTA jobs, saving to Firebase...`);
    
    let successCount = 0;
    for (const job of jobs) {
      try {
        const jobRef = doc(db, "smartLPG_fota_jobs", job.id);
        await setDoc(jobRef, job);
        successCount++;
        console.log(`✅ Saved FOTA job: ${job.id} - ${job.name}`);
      } catch (err) {
        console.error(`❌ Failed to save FOTA job ${job.id}:`, err);
      }
    }
    
    console.log(`✅ Successfully seeded ${successCount} FOTA jobs to Firebase`);
    return { success: true, count: successCount };
  } catch (error) {
    console.error('❌ Error seeding FOTA jobs:', error);
    throw error;
  }
}

/**
 * Generate sample timeseries data for a device
 * @param {string} deviceId - Device ID
 * @param {string} key - Field key (e.g., 'level', 'temperature')
 * @param {number} hours - Number of hours of data to generate
 * @param {number} intervalMinutes - Interval between data points in minutes (default: 5)
 * @returns {Array} Array of {ts, value} objects
 */
function generateTimeseriesData(deviceId, key, hours = 72, intervalMinutes = 5) {
  const points = [];
  const now = new Date();
  const startTime = new Date(now.getTime() - hours * 60 * 60 * 1000);
  
  // Base values and ranges for different field types
  const fieldConfig = {
    'level': { base: 60, range: 40, trend: 'stable' }, // 20-100%
    'level_cm': { base: 120, range: 80, trend: 'stable' }, // 40-200 cm (typical tank height)
    'lpg_tank_level': { base: 60, range: 40, trend: 'stable' }, // 20-100%
    'temperature': { base: 25, range: 10, trend: 'cyclic' }, // 15-35°C with daily cycle
    'pressure': { base: 150, range: 30, trend: 'stable' }, // 120-180 PSI
    'battery': { base: 85, range: 15, trend: 'decreasing' }, // 70-100%, slowly decreasing
    'flow_rate': { base: 2.5, range: 1.5, trend: 'variable' }, // 1-4 L/min
    'total_consumption': { base: 0, range: 0, trend: 'increasing' }, // Cumulative, always increasing
  };
  
  const config = fieldConfig[key] || { base: 50, range: 20, trend: 'stable' };
  let currentValue = config.base + (Math.random() - 0.5) * config.range;
  
  // For cumulative fields, start from a random base
  if (key === 'total_consumption') {
    currentValue = Math.random() * 1000; // Start from 0-1000 L
  }
  
  const totalPoints = Math.floor((hours * 60) / intervalMinutes);
  
  for (let i = 0; i < totalPoints; i++) {
    const timestamp = new Date(startTime.getTime() + i * intervalMinutes * 60 * 1000);
    
    // Apply trend
    switch (config.trend) {
      case 'cyclic':
        // Daily temperature cycle (cooler at night, warmer during day)
        const hourOfDay = timestamp.getHours();
        const cycleOffset = Math.sin((hourOfDay / 24) * 2 * Math.PI) * 5;
        currentValue = config.base + cycleOffset + (Math.random() - 0.5) * config.range;
        break;
      case 'decreasing':
        // Slowly decreasing (battery)
        const decreaseRate = config.range / totalPoints;
        currentValue = Math.max(config.base - config.range / 2, currentValue - decreaseRate + (Math.random() - 0.5) * 2);
        break;
      case 'increasing':
        // Cumulative consumption (always increasing)
        const increaseRate = (Math.random() * 0.1) + 0.05; // 0.05-0.15 per interval
        currentValue += increaseRate;
        break;
      case 'variable':
        // Variable flow rate
        currentValue = config.base + (Math.random() - 0.5) * config.range;
        break;
      default: // 'stable'
        // Stable with small random variation
        currentValue = config.base + (Math.random() - 0.5) * config.range;
    }
    
    // Ensure value stays within reasonable bounds
    if (key === 'level' || key === 'lpg_tank_level' || key === 'battery') {
      currentValue = Math.max(0, Math.min(100, currentValue));
    } else if (key === 'level_cm') {
      currentValue = Math.max(0, Math.min(250, currentValue)); // 0-250 cm
    } else if (key === 'temperature') {
      currentValue = Math.max(10, Math.min(50, currentValue));
    } else if (key === 'pressure') {
      currentValue = Math.max(100, Math.min(200, currentValue));
    } else if (key === 'flow_rate') {
      currentValue = Math.max(0, Math.min(10, currentValue));
    }
    
    points.push({
      ts: timestamp.toISOString(),
      value: parseFloat(currentValue.toFixed(2))
    });
  }
  
  return points;
}

/**
 * Seed timeseries data to Firebase
 */
export async function seedTimeseries() {
  try {
    console.log('🌱 Seeding timeseries data to Firebase...');
    
    // Fetch all devices from Firebase (not just hardcoded ones)
    const devicesRef = collection(db, "smartLPG");
    const devicesSnap = await getDocs(devicesRef);
    const deviceIds = [];
    
    devicesSnap.forEach((docSnap) => {
      const data = docSnap.data();
      const deviceId = data.device_id || docSnap.id;
      if (deviceId) {
        deviceIds.push(deviceId);
      }
    });
    
    // If no devices found in Firebase, fall back to sample device IDs
    const devicesToSeed = deviceIds.length > 0 ? deviceIds : SAMPLE_DEVICE_IDS;
    
    console.log(`📊 Found ${devicesToSeed.length} devices to seed timeseries data for:`, devicesToSeed);
    
    // Common field keys for SmartLPG devices
    const fieldKeys = ['level', 'level_cm', 'lpg_tank_level', 'temperature', 'pressure', 'battery', 'flow_rate', 'total_consumption'];
    
    let totalPoints = 0;
    const batchSize = 100; // Write in batches to avoid overwhelming Firebase
    
    for (const deviceId of devicesToSeed) {
      for (const key of fieldKeys) {
        // Generate 72 hours of data (5-minute intervals = ~864 points per field)
        const points = generateTimeseriesData(deviceId, key, 72, 5);
        
        console.log(`📊 Generated ${points.length} points for device ${deviceId}, field ${key}`);
        
        // Write points in batches
        for (let i = 0; i < points.length; i += batchSize) {
          const batch = points.slice(i, i + batchSize);
          const batchPromises = batch.map(point => {
            const docId = `${deviceId}_${key}_${new Date(point.ts).getTime()}`;
            const timeseriesRef = doc(db, "smartLPG_timeseries", docId);
            return setDoc(timeseriesRef, {
              device_id: deviceId,
              key: key,
              value: point.value,
              ts: Timestamp.fromDate(new Date(point.ts)),
              tenant_id: TENANT_ID,
              created_at: Timestamp.now()
            }, { merge: true });
          });
          
          await Promise.all(batchPromises);
          totalPoints += batch.length;
        }
        
        console.log(`✅ Saved ${points.length} timeseries points for ${deviceId}/${key}`);
      }
    }
    
    console.log(`✅ Successfully seeded ${totalPoints} timeseries points to Firebase`);
    return { success: true, count: totalPoints };
  } catch (error) {
    console.error('❌ Error seeding timeseries:', error);
    throw error;
  }
}

/**
 * Seed firmware versions for SmartLPG devices
 */
export async function seedFirmwareVersions() {
  try {
    console.log('🌱 Seeding firmware versions to Firebase...');
    
    const firmwareVersions = [
      {
        device_type: "Tekelek Ultrasonic Meter",
        name: "Tekelek LPG Meter Firmware",
        version: "2.1.0",
        file_path: "/data/firmware/tekelek_lpg_meter_v2.1.0.bin",
        checksum: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        file_size_bytes: 524288, // 512 KB
        release_notes: "Improved gas level accuracy, battery optimization, bug fixes",
        min_hw_version: "1.0",
        is_recommended: true,
        is_mandatory: false,
      },
      {
        device_type: "Tekelek Ultrasonic Meter",
        name: "Tekelek LPG Meter Firmware",
        version: "2.0.5",
        file_path: "/data/firmware/tekelek_lpg_meter_v2.0.5.bin",
        checksum: "b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7",
        file_size_bytes: 516096,
        release_notes: "Stable release with enhanced connectivity",
        min_hw_version: "1.0",
        is_recommended: false,
        is_mandatory: false,
      },
      {
        device_type: "Tekelek Ultrasonic Meter",
        name: "Tekelek LPG Meter Firmware",
        version: "1.9.2",
        file_path: "/data/firmware/tekelek_lpg_meter_v1.9.2.bin",
        checksum: "c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8",
        file_size_bytes: 507904,
        release_notes: "Legacy stable version",
        min_hw_version: "1.0",
        is_recommended: false,
        is_mandatory: false,
      },
      {
        device_type: "ASCO Valve Controller",
        name: "ASCO Valve Firmware",
        version: "1.5.0",
        file_path: "/data/firmware/asco_valve_v1.5.0.bin",
        checksum: "d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9",
        file_size_bytes: 262144, // 256 KB
        release_notes: "Improved valve control precision and safety features",
        min_hw_version: "1.0",
        is_recommended: true,
        is_mandatory: false,
      },
      {
        device_type: "ASCO Valve Controller",
        name: "ASCO Valve Firmware",
        version: "1.4.3",
        file_path: "/data/firmware/asco_valve_v1.4.3.bin",
        checksum: "e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
        file_size_bytes: 258048,
        release_notes: "Previous stable release",
        min_hw_version: "1.0",
        is_recommended: false,
        is_mandatory: false,
      },
    ];
    
    const firmwareVersionsRef = collection(db, "smartLPG_firmware_versions");
    let count = 0;
    
    for (const fw of firmwareVersions) {
      const fwRef = doc(firmwareVersionsRef);
      await setDoc(fwRef, {
        ...fw,
        tenant_id: TENANT_ID,
        created_at: Timestamp.now(),
      });
      count++;
      console.log(`✅ Seeded firmware version: ${fw.name} v${fw.version}`);
    }
    
    console.log(`✅ Successfully seeded ${count} firmware versions to Firebase`);
    return { success: true, count };
  } catch (error) {
    console.error('❌ Error seeding firmware versions:', error);
    throw error;
  }
}

/**
 * Seed all data
 */
export async function seedAll() {
  try {
    console.log('🌱 Starting SmartLPG data seeding...');
    const alertsResult = await seedAlerts();
    const jobsResult = await seedFOTAJobs();
    
    console.log(`✅ Seeding complete! Created ${alertsResult.count} alerts and ${jobsResult.count} FOTA jobs`);
    return { 
      success: true, 
      alerts: alertsResult.count, 
      fotaJobs: jobsResult.count 
    };
  } catch (error) {
    console.error('❌ Error during seeding:', error);
    throw error;
  }
}

/**
 * Seed all data including timeseries
 */
export async function seedAllWithTimeseries() {
  try {
    console.log('🌱 Starting SmartLPG data seeding (including timeseries)...');
    const alertsResult = await seedAlerts();
    const jobsResult = await seedFOTAJobs();
    const timeseriesResult = await seedTimeseries();
    
    console.log(`✅ Seeding complete! Created ${alertsResult.count} alerts, ${jobsResult.count} FOTA jobs, and ${timeseriesResult.count} timeseries points`);
    return { 
      success: true, 
      alerts: alertsResult.count, 
      fotaJobs: jobsResult.count,
      timeseries: timeseriesResult.count
    };
  } catch (error) {
    console.error('❌ Error during seeding:', error);
    throw error;
  }
}

/**
 * Seed alert rules to Firebase (for SmartLPG tenant)
 */
export async function seedAlertRules() {
  try {
    console.log('🌱 Seeding alert rules to Firebase...');
    
    const alertRules = [
      {
        name: "Gas Tank Low Alert",
        description: "Alert when LPG tank level drops below 25%",
        device_id: null, // Tenant-wide rule
        tenant_id: TENANT_ID,
        condition: {
          field: "lpg_tank_level",
          operator: "<",
          value: "25"
        },
        priority: "critical",
        title_template: "Gas Tank Low - Refill Required",
        message_template: "Gas level is at {level}% for device {device}",
        notify_email: true,
        notify_sms: false,
        notify_webhook: false,
        escalation_enabled: false,
        aggregation_enabled: true,
        aggregation_window_minutes: 5,
        max_alerts_per_window: 10,
        is_active: true,
      },
      {
        name: "High Temperature Alert",
        description: "Alert when temperature exceeds 40°C",
        device_id: null, // Tenant-wide rule
        tenant_id: TENANT_ID,
        condition: {
          field: "temperature",
          operator: ">",
          value: "40"
        },
        priority: "high",
        title_template: "High Temperature Warning",
        message_template: "Temperature is {temp}°C for device {device}",
        notify_email: true,
        notify_sms: false,
        notify_webhook: false,
        escalation_enabled: false,
        aggregation_enabled: true,
        aggregation_window_minutes: 10,
        max_alerts_per_window: 5,
        is_active: true,
      },
      {
        name: "Temperature Alert (tmp > 89)",
        description: "Alert when temperature exceeds 89 (using tmp field)",
        device_id: null, // Tenant-wide rule
        tenant_id: TENANT_ID,
        condition: {
          field: "tmp",
          operator: ">",
          value: "89"
        },
        priority: "medium",
        title_template: "Temperature Alert",
        message_template: "Temperature (tmp) is {value} for device {device}",
        notify_email: true,
        notify_sms: false,
        notify_webhook: false,
        escalation_enabled: false,
        aggregation_enabled: true,
        aggregation_window_minutes: 5,
        max_alerts_per_window: 10,
        is_active: true,
      },
      {
        name: "Low Battery Alert",
        description: "Alert when device battery drops below 20%",
        device_id: null, // Tenant-wide rule
        tenant_id: TENANT_ID,
        condition: {
          field: "battery",
          operator: "<",
          value: "20"
        },
        priority: "medium",
        title_template: "Battery Low",
        message_template: "Device battery is running low for device {device}",
        notify_email: true,
        notify_sms: false,
        notify_webhook: false,
        escalation_enabled: false,
        aggregation_enabled: true,
        aggregation_window_minutes: 15,
        max_alerts_per_window: 3,
        is_active: true,
      },
      {
        name: "High Pressure Alert",
        description: "Alert when pressure exceeds 180 PSI",
        device_id: null, // Tenant-wide rule
        tenant_id: TENANT_ID,
        condition: {
          field: "pressure",
          operator: ">",
          value: "180"
        },
        priority: "critical",
        title_template: "High Pressure Warning",
        message_template: "Tank pressure exceeded safe limits for device {device}",
        notify_email: true,
        notify_sms: true,
        notify_webhook: false,
        escalation_enabled: true,
        escalation_delay_minutes: 30,
        escalation_priority: "critical",
        aggregation_enabled: true,
        aggregation_window_minutes: 5,
        max_alerts_per_window: 5,
        is_active: true,
      },
    ];
    
    const rulesRef = collection(db, "smartLPG_alert_rules");
    let count = 0;
    
    for (const rule of alertRules) {
      const ruleId = `alert_rule_${Date.now()}_${count}`;
      const ruleRef = doc(rulesRef, ruleId);
      await setDoc(ruleRef, {
        ...rule,
        id: ruleId,
        created_at: Timestamp.now(),
        updated_at: Timestamp.now(),
      });
      count++;
      console.log(`✅ Seeded alert rule: ${rule.name} (${ruleId})`);
    }
    
    console.log(`✅ Successfully seeded ${count} alert rules to Firebase`);
    return { success: true, count };
  } catch (error) {
    console.error('❌ Error seeding alert rules:', error);
    throw error;
  }
}

/**
 * Seed all data including firmware versions
 */
export async function seedAllWithFirmware() {
  try {
    console.log('🌱 Starting SmartLPG data seeding (including firmware versions)...');
    const alertsResult = await seedAlerts();
    const jobsResult = await seedFOTAJobs();
    const firmwareResult = await seedFirmwareVersions();
    
    console.log(`✅ Seeding complete! Created ${alertsResult.count} alerts, ${jobsResult.count} FOTA jobs, and ${firmwareResult.count} firmware versions`);
    return { 
      success: true, 
      alerts: alertsResult.count, 
      fotaJobs: jobsResult.count,
      firmwareVersions: firmwareResult.count
    };
  } catch (error) {
    console.error('❌ Error during seeding:', error);
    throw error;
  }
}
