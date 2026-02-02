/**
 * Utility script to create dummy alerts and FOTA jobs for SmartLPG tenant
 * Run this from browser console or import and call in a component
 */

import { 
  saveAlertToFirebase, 
  saveFOTAJobToFirebase 
} from "../services/smartLPGFirebaseService.js";

/**
 * Create dummy alerts for SmartLPG tenant
 */
export async function createDummyAlerts() {
  const alerts = [
    {
      title: "Low Tank Level Alert",
      message: "Tank TEK-00001 has dropped below 20% capacity",
      device_id: "TEK-00001",
      device_name: "TEK-00001",
      priority: "high",
      status: "active",
      rule_id: "rule_1",
      created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      updated_at: new Date().toISOString(),
      tenant_id: 3,
    },
    {
      title: "High Temperature Warning",
      message: "Device TEK-00002 temperature exceeds 45°C",
      device_id: "TEK-00002",
      device_name: "TEK-00002",
      priority: "medium",
      status: "active",
      rule_id: "rule_2",
      created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(), // 5 hours ago
      updated_at: new Date().toISOString(),
      tenant_id: 3,
    },
    {
      title: "Battery Low",
      message: "Device TEK-00003 battery level is below 15%",
      device_id: "TEK-00003",
      device_name: "TEK-00003",
      priority: "medium",
      status: "acknowledged",
      rule_id: "rule_3",
      created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
      updated_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), // 12 hours ago
      acknowledged_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
      tenant_id: 3,
    },
    {
      title: "Communication Failure",
      message: "Device TEK-00004 has not reported data in the last 24 hours",
      device_id: "TEK-00004",
      device_name: "TEK-00004",
      priority: "high",
      status: "resolved",
      rule_id: "rule_4",
      created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days ago
      updated_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
      resolved_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
      tenant_id: 3,
    },
    {
      title: "Rapid Consumption Detected",
      message: "Tank TEK-00005 showing unusual consumption rate",
      device_id: "TEK-00005",
      device_name: "TEK-00005",
      priority: "low",
      status: "active",
      rule_id: "rule_5",
      created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 minutes ago
      updated_at: new Date().toISOString(),
      tenant_id: 3,
    },
  ];

  console.log("📢 Creating dummy alerts...");
  const results = [];
  
  for (const alert of alerts) {
    try {
      const result = await saveAlertToFirebase(alert);
      results.push({ success: true, id: result.id, title: alert.title });
      console.log(`✅ Created alert: ${alert.title}`);
    } catch (error) {
      console.error(`❌ Failed to create alert: ${alert.title}`, error);
      results.push({ success: false, title: alert.title, error: error.message });
    }
  }
  
  console.log("📊 Alert creation summary:", results);
  return results;
}

/**
 * Create dummy FOTA jobs for SmartLPG tenant
 */
export async function createDummyFOTAJobs() {
  const jobs = [
    {
      name: "Firmware Update v2.1.0",
      description: "Update all Tekelek devices to firmware version 2.1.0 with improved battery management",
      device_ids: ["TEK-00001", "TEK-00002", "TEK-00003"],
      firmware_version: "2.1.0",
      firmware_url: "https://firmware.example.com/tekelek/v2.1.0.bin",
      status: "pending",
      priority: "high",
      scheduled_at: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days from now
      tenant_id: 3,
      created_by: "smartlpg@flowsense.com",
    },
    {
      name: "Security Patch Update",
      description: "Apply critical security patch to all active devices",
      device_ids: ["TEK-00004", "TEK-00005"],
      firmware_version: "2.0.5",
      firmware_url: "https://firmware.example.com/tekelek/v2.0.5-security.bin",
      status: "in_progress",
      priority: "high",
      scheduled_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
      started_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), // 12 hours ago
      tenant_id: 3,
      created_by: "smartlpg@flowsense.com",
    },
    {
      name: "Battery Optimization Update",
      description: "Update firmware to improve battery life by 30%",
      device_ids: ["TEK-00001"],
      firmware_version: "2.2.0",
      firmware_url: "https://firmware.example.com/tekelek/v2.2.0-battery.bin",
      status: "completed",
      priority: "medium",
      scheduled_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(), // 5 days ago
      started_at: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString(), // 4 days ago
      completed_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days ago
      tenant_id: 3,
      created_by: "smartlpg@flowsense.com",
    },
    {
      name: "Sensor Calibration Update",
      description: "Update sensor calibration algorithms for improved accuracy",
      device_ids: ["TEK-00002", "TEK-00003", "TEK-00004"],
      firmware_version: "2.1.5",
      firmware_url: "https://firmware.example.com/tekelek/v2.1.5-calibration.bin",
      status: "failed",
      priority: "low",
      scheduled_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days ago
      started_at: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString(), // 6 days ago
      error_message: "Network timeout during update",
      tenant_id: 3,
      created_by: "smartlpg@flowsense.com",
    },
    {
      name: "Feature Enhancement Update",
      description: "Add new reporting features and improved data compression",
      device_ids: ["TEK-00005"],
      firmware_version: "2.3.0",
      firmware_url: "https://firmware.example.com/tekelek/v2.3.0-features.bin",
      status: "pending",
      priority: "low",
      scheduled_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days from now
      tenant_id: 3,
      created_by: "smartlpg@flowsense.com",
    },
  ];

  console.log("📦 Creating dummy FOTA jobs...");
  const results = [];
  
  for (const job of jobs) {
    try {
      const result = await saveFOTAJobToFirebase(job);
      results.push({ success: true, id: result.id, name: job.name });
      console.log(`✅ Created FOTA job: ${job.name}`);
    } catch (error) {
      console.error(`❌ Failed to create FOTA job: ${job.name}`, error);
      results.push({ success: false, name: job.name, error: error.message });
    }
  }
  
  console.log("📊 FOTA job creation summary:", results);
  return results;
}

/**
 * Create all dummy data (alerts + FOTA jobs)
 */
export async function createAllDummyData() {
  console.log("🚀 Starting dummy data creation for SmartLPG tenant...");
  
  const alertResults = await createDummyAlerts();
  const fotaResults = await createDummyFOTAJobs();
  
  console.log("✅ Dummy data creation complete!");
  console.log("📊 Summary:");
  console.log(`  - Alerts: ${alertResults.filter(r => r.success).length}/${alertResults.length} created`);
  console.log(`  - FOTA Jobs: ${fotaResults.filter(r => r.success).length}/${fotaResults.length} created`);
  
  return {
    alerts: alertResults,
    fotaJobs: fotaResults,
  };
}
