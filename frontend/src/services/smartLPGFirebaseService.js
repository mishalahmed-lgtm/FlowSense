/**
 * SmartLPG Firebase Service
 * Handles saving device dashboards, alerts, FOTA jobs, and device creation to Firebase
 */

import { db } from "../utils/firebase";
import { collection, doc, setDoc, getDoc, getDocs, deleteDoc, query, where, orderBy, Timestamp } from "firebase/firestore";

/**
 * Remove undefined values from an object recursively
 */
function removeUndefined(obj) {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  
  if (Array.isArray(obj)) {
    return obj.map(item => removeUndefined(item)).filter(item => item !== undefined);
  }
  
  const cleaned = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value !== undefined) {
      cleaned[key] = removeUndefined(value);
    }
  }
  return cleaned;
}

/**
 * Save device dashboard configuration to Firebase
 */
export async function saveDeviceDashboardToFirebase(deviceId, config) {
  try {
    // Remove undefined values from config (Firebase doesn't support undefined)
    const cleanedConfig = removeUndefined(config);
    
    const dashboardRef = doc(db, "smartLPG_dashboards", deviceId);
    await setDoc(dashboardRef, {
      device_id: deviceId,
      config: cleanedConfig,
      updated_at: Timestamp.now(),
      created_at: Timestamp.now(),
    }, { merge: true });
    console.log(`✅ Saved dashboard for device ${deviceId} to Firebase`);
    return { success: true };
  } catch (error) {
    console.error("❌ Error saving dashboard to Firebase:", error);
    throw error;
  }
}

/**
 * Get device dashboard configuration from Firebase
 */
export async function getDeviceDashboardFromFirebase(deviceId) {
  try {
    const dashboardRef = doc(db, "smartLPG_dashboards", deviceId);
    const dashboardSnap = await getDoc(dashboardRef);
    if (dashboardSnap.exists()) {
      return dashboardSnap.data();
    }
    return null;
  } catch (error) {
    console.error("❌ Error getting dashboard from Firebase:", error);
    return null;
  }
}

/**
 * Save alert rule to Firebase
 */
export async function saveAlertRuleToFirebase(alertRule) {
  try {
    const alertRuleId = alertRule.id || `alert_rule_${Date.now()}`;
    const alertRuleRef = doc(db, "smartLPG_alert_rules", alertRuleId);
    await setDoc(alertRuleRef, {
      ...alertRule,
      id: alertRuleId,
      created_at: Timestamp.now(),
      updated_at: Timestamp.now(),
    });
    console.log(`✅ Saved alert rule ${alertRuleId} to Firebase`);
    return { success: true, id: alertRuleId };
  } catch (error) {
    console.error("❌ Error saving alert rule to Firebase:", error);
    throw error;
  }
}

/**
 * Save alert to Firebase
 */
export async function saveAlertToFirebase(alert) {
  try {
    const alertId = alert.id || `alert_${Date.now()}`;
    const alertRef = doc(db, "smartLPG_alerts", alertId);
    await setDoc(alertRef, {
      ...alert,
      id: alertId,
      created_at: Timestamp.now(),
      updated_at: Timestamp.now(),
    });
    console.log(`✅ Saved alert ${alertId} to Firebase`);
    return { success: true, id: alertId };
  } catch (error) {
    console.error("❌ Error saving alert to Firebase:", error);
    throw error;
  }
}

/**
 * Get alert rules from Firebase
 */
export async function getAlertRulesFromFirebase(tenantId) {
  try {
    const rulesRef = collection(db, "smartLPG_alert_rules");
    const q = query(
      rulesRef,
      where("tenant_id", "==", tenantId),
      orderBy("created_at", "desc")
    );
    
    const querySnapshot = await getDocs(q);
    const rules = [];
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      rules.push({
        ...data,
        id: docSnap.id,
        created_at: data.created_at?.toDate?.()?.toISOString() || data.created_at,
        updated_at: data.updated_at?.toDate?.()?.toISOString() || data.updated_at,
      });
    });
    
    return rules;
  } catch (error) {
    console.error("❌ Error getting alert rules from Firebase:", error);
    return [];
  }
}

/**
 * Get alerts from Firebase
 */
export async function getAlertsFromFirebase(tenantId, filters = {}) {
  try {
    const alertsRef = collection(db, "smartLPG_alerts");
    let q = query(alertsRef, where("tenant_id", "==", tenantId));
    
    if (filters.status && filters.status !== "all") {
      q = query(q, where("status", "==", filters.status));
    }
    if (filters.priority && filters.priority !== "all") {
      q = query(q, where("priority", "==", filters.priority));
    }
    
    q = query(q, orderBy("created_at", "desc"));
    
    const querySnapshot = await getDocs(q);
    const alerts = [];
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      alerts.push({
        ...data,
        id: docSnap.id,
        created_at: data.created_at?.toDate?.()?.toISOString() || data.created_at,
        updated_at: data.updated_at?.toDate?.()?.toISOString() || data.updated_at,
      });
    });
    
    return alerts;
  } catch (error) {
    console.error("❌ Error getting alerts from Firebase:", error);
    return [];
  }
}

/**
 * Update alert in Firebase
 */
export async function updateAlertInFirebase(alertId, updates) {
  try {
    const alertRef = doc(db, "smartLPG_alerts", alertId);
    await setDoc(alertRef, {
      ...updates,
      updated_at: Timestamp.now(),
    }, { merge: true });
    console.log(`✅ Updated alert ${alertId} in Firebase`);
    return { success: true };
  } catch (error) {
    console.error("❌ Error updating alert in Firebase:", error);
    throw error;
  }
}

/**
 * Delete alert rule from Firebase
 */
export async function deleteAlertRuleFromFirebase(ruleId) {
  try {
    const ruleRef = doc(db, "smartLPG_alert_rules", ruleId);
    await deleteDoc(ruleRef);
    console.log(`✅ Deleted alert rule ${ruleId} from Firebase`);
    return { success: true };
  } catch (error) {
    console.error("❌ Error deleting alert rule from Firebase:", error);
    throw error;
  }
}

/**
 * Save FOTA job to Firebase
 */
export async function saveFOTAJobToFirebase(fotaJob) {
  try {
    const jobId = fotaJob.id || `fota_job_${Date.now()}`;
    const jobRef = doc(db, "smartLPG_fota_jobs", jobId);
    await setDoc(jobRef, {
      ...fotaJob,
      id: jobId,
      created_at: Timestamp.now(),
      updated_at: Timestamp.now(),
    });
    console.log(`✅ Saved FOTA job ${jobId} to Firebase`);
    return { success: true, id: jobId };
  } catch (error) {
    console.error("❌ Error saving FOTA job to Firebase:", error);
    throw error;
  }
}

/**
 * Get FOTA jobs from Firebase
 */
export async function getFOTAJobsFromFirebase(tenantId) {
  try {
    const jobsRef = collection(db, "smartLPG_fota_jobs");
    const q = query(
      jobsRef,
      where("tenant_id", "==", tenantId),
      orderBy("created_at", "desc")
    );
    
    const querySnapshot = await getDocs(q);
    const jobs = [];
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      jobs.push({
        ...data,
        id: docSnap.id,
        created_at: data.created_at?.toDate?.()?.toISOString() || data.created_at,
        updated_at: data.updated_at?.toDate?.()?.toISOString() || data.updated_at,
        scheduled_at: data.scheduled_at?.toDate?.()?.toISOString() || data.scheduled_at,
        started_at: data.started_at?.toDate?.()?.toISOString() || data.started_at,
        completed_at: data.completed_at?.toDate?.()?.toISOString() || data.completed_at,
      });
    });
    
    return jobs;
  } catch (error) {
    console.error("❌ Error getting FOTA jobs from Firebase:", error);
    return [];
  }
}

/**
 * Save device to Firebase (for SmartLPG tenant)
 */
export async function saveDeviceToFirebase(device) {
  try {
    const deviceId = device.device_id;
    const deviceRef = doc(db, "smartLPG", deviceId);
    
    // Get existing device data if it exists
    const existingSnap = await getDoc(deviceRef);
    const existingData = existingSnap.exists() ? existingSnap.data() : {};
    
    // Merge new device data with existing
    const deviceData = {
      ...existingData,
      device_id: deviceId,
      name: device.name || existingData.name,
      device_type: device.device_type || existingData.device_type,
      protocol: device.protocol || existingData.protocol || "NB-IoT/CAT-M1",
      is_active: device.is_active !== undefined ? device.is_active : (existingData.is_active !== undefined ? existingData.is_active : true),
      tenant_id: device.tenant_id || existingData.tenant_id || 3,
      metadata: device.metadata || existingData.metadata || {},
      updated_at: Timestamp.now(),
    };
    
    // Set created_at only if device is new
    if (!existingSnap.exists()) {
      deviceData.created_at = Timestamp.now();
    }
    
    await setDoc(deviceRef, deviceData);
    console.log(`✅ Saved device ${deviceId} to Firebase`);
    return { success: true, device_id: deviceId };
  } catch (error) {
    console.error("❌ Error saving device to Firebase:", error);
    throw error;
  }
}
