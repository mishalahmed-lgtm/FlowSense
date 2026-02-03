/**
 * Script to seed SmartLPG Firebase collections with sample alerts and FOTA jobs
 * Run this from the browser console or as a one-time script
 */

import { db } from "../utils/firebase.js";
import { collection, doc, setDoc, Timestamp } from "firebase/firestore";

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
