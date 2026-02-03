/**
 * SmartLPG Firebase Service
 * Handles saving device dashboards, alerts, FOTA jobs, and device creation to Firebase
 */

import { db } from "../utils/firebase";
import { collection, doc, setDoc, getDoc, getDocs, deleteDoc, query, where, orderBy, Timestamp } from "firebase/firestore";

/**
 * Remove undefined values from an object recursively and convert to JSON-safe format
 */
function cleanForFirebase(obj) {
  // Handle primitives
  if (obj === null) return null;
  if (obj === undefined) return null; // Convert undefined to null
  if (typeof obj !== 'object') return obj;
  
  // Handle arrays
  if (Array.isArray(obj)) {
    return obj
      .filter(item => item !== undefined) // Remove undefined items
      .map(item => cleanForFirebase(item));
  }
  
  // Handle objects
  const cleaned = {};
  for (const [key, value] of Object.entries(obj)) {
    // Skip undefined values entirely
    if (value === undefined) continue;
    
    // Recursively clean the value
    const cleanedValue = cleanForFirebase(value);
    
    // Only add if the cleaned value isn't undefined
    if (cleanedValue !== undefined) {
      cleaned[key] = cleanedValue;
    }
  }
  return cleaned;
}

/**
 * Save device dashboard configuration to Firebase
 */
export async function saveDeviceDashboardToFirebase(deviceId, config) {
  try {
    console.log("🔧 Original config:", config);
    
    // Convert to JSON and back to remove any undefined values and functions
    const jsonSafe = JSON.parse(JSON.stringify(config, (key, value) => {
      // Replace undefined with null in JSON
      return value === undefined ? null : value;
    }));
    
    // Then clean any remaining issues
    const cleanedConfig = cleanForFirebase(jsonSafe);
    
    console.log("✨ Cleaned config:", cleanedConfig);
    
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
    console.error("❌ Config that failed:", config);
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
export async function saveAlertRuleToFirebase(rule) {
  try {
    const ruleId = rule.id || `alert_rule_${Date.now()}`;
    const ruleRef = doc(db, "smartLPG_alert_rules", ruleId);
    await setDoc(ruleRef, {
      ...rule,
      id: ruleId,
      updated_at: Timestamp.now(),
      created_at: rule.created_at || Timestamp.now(),
    }, { merge: true });
    console.log(`✅ Saved alert rule ${ruleId} to Firebase`);
    return { success: true, id: ruleId };
  } catch (error) {
    console.error("❌ Error saving alert rule to Firebase:", error);
    throw error;
  }
}

/**
 * Get alert rules from Firebase
 */
export async function getAlertRulesFromFirebase() {
  try {
    const rulesRef = collection(db, "smartLPG_alert_rules");
    const rulesSnap = await getDocs(rulesRef);
    const rules = [];
    rulesSnap.forEach((doc) => {
      rules.push({ ...doc.data(), id: doc.id });
    });
    console.log(`✅ Loaded ${rules.length} alert rules from Firebase`);
    return rules;
  } catch (error) {
    console.error("❌ Error getting alert rules from Firebase:", error);
    return [];
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
 * Save alert to Firebase
 */
export async function saveAlertToFirebase(alert) {
  try {
    const alertId = alert.id || `alert_${Date.now()}`;
    const alertRef = doc(db, "smartLPG_alerts", alertId);
    await setDoc(alertRef, {
      ...alert,
      id: alertId,
      created_at: alert.created_at || Timestamp.now(),
      updated_at: Timestamp.now(),
    }, { merge: true });
    console.log(`✅ Saved alert ${alertId} to Firebase`);
    return { success: true, id: alertId };
  } catch (error) {
    console.error("❌ Error saving alert to Firebase:", error);
    throw error;
  }
}

/**
 * Update alert status in Firebase
 */
export async function updateAlertStatusInFirebase(alertId, status) {
  try {
    const alertRef = doc(db, "smartLPG_alerts", alertId);
    await setDoc(alertRef, {
      status: status,
      updated_at: Timestamp.now(),
    }, { merge: true });
    console.log(`✅ Updated alert ${alertId} status to ${status}`);
    return { success: true };
  } catch (error) {
    console.error("❌ Error updating alert status in Firebase:", error);
    throw error;
  }
}

/**
 * Get alerts from Firebase with optional filtering
 */
export async function getAlertsFromFirebase(tenantId = null, options = {}) {
  try {
    const { status: filterStatus = null, priority: filterPriority = null } = options;
    const alertsRef = collection(db, "smartLPG_alerts");
    let q;
    
    // Build query - filter by status if provided, otherwise just order by created_at
    // Note: We filter tenant_id and priority client-side to avoid composite index requirements
    if (filterStatus) {
      q = query(alertsRef, where("status", "==", filterStatus), orderBy("created_at", "desc"));
    } else {
      q = query(alertsRef, orderBy("created_at", "desc"));
    }
    
    const alertsSnap = await getDocs(q);
    let alerts = [];
    alertsSnap.forEach((doc) => {
      const data = doc.data();
      alerts.push({
        ...data,
        id: doc.id,
        created_at: data.created_at?.toDate?.()?.toISOString() || data.created_at,
        updated_at: data.updated_at?.toDate?.()?.toISOString() || data.updated_at,
      });
    });
    
    // Apply tenant_id filter client-side (to avoid composite index requirement)
    if (tenantId) {
      alerts = alerts.filter(alert => alert.tenant_id === tenantId);
    }
    
    // Apply priority filter client-side
    if (filterPriority) {
      alerts = alerts.filter(alert => alert.priority === filterPriority);
    }
    
    console.log(`✅ Loaded ${alerts.length} alerts from Firebase`);
    return alerts;
  } catch (error) {
    console.error("❌ Error getting alerts from Firebase:", error);
    return [];
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
    // Query without tenant_id filter to avoid composite index requirement
    // We'll filter tenant_id client-side
    const q = query(
      jobsRef,
      orderBy("created_at", "desc")
    );
    
    const querySnapshot = await getDocs(q);
    let jobs = [];
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
    
    // Filter by tenant_id client-side (to avoid composite index requirement)
    if (tenantId) {
      jobs = jobs.filter(job => job.tenant_id === tenantId);
    }
    
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

/**
 * Update device in Firebase
 */
export async function updateDeviceInFirebase(device) {
  return saveDeviceToFirebase(device); // Same as save, uses merge
}

/**
 * Get analytics predictions from Firebase (for SmartLPG tenant)
 */
export async function getAnalyticsPredictionsFromFirebase(tenantId, limit = 20) {
  try {
    const predictionsRef = collection(db, "smartLPG_analytics_predictions");
    const q = query(
      predictionsRef,
      where("tenant_id", "==", tenantId),
      orderBy("predicted_at", "desc")
    );
    const querySnapshot = await getDocs(q);
    
    const predictions = [];
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      predictions.push({
        id: docSnap.id,
        device_id: data.device_id,
        device_name: data.device_name,
        prediction_type: data.prediction_type,
        predicted_value: data.predicted_value,
        confidence: data.confidence,
        predicted_at: data.predicted_at?.toDate?.()?.toISOString() || data.predicted_at,
        ...data
      });
    });
    
    // Sort by predicted_at descending and limit
    predictions.sort((a, b) => {
      const dateA = new Date(a.predicted_at || 0);
      const dateB = new Date(b.predicted_at || 0);
      return dateB - dateA;
    });
    
    return predictions.slice(0, limit);
  } catch (error) {
    console.error("❌ Error getting analytics predictions from Firebase:", error);
    return [];
  }
}

/**
 * Save analytics prediction to Firebase (for SmartLPG tenant)
 */
export async function saveAnalyticsPredictionToFirebase(prediction) {
  try {
    const predictionData = cleanForFirebase({
      device_id: prediction.device_id,
      device_name: prediction.device_name,
      prediction_type: prediction.prediction_type,
      predicted_value: prediction.predicted_value,
      confidence: prediction.confidence || 0.8,
      tenant_id: prediction.tenant_id || 3,
      predicted_at: Timestamp.now(),
      created_at: Timestamp.now(),
      updated_at: Timestamp.now(),
      ...prediction
    });
    
    const predictionRef = doc(collection(db, "smartLPG_analytics_predictions"));
    await setDoc(predictionRef, predictionData);
    console.log(`✅ Saved analytics prediction to Firebase`);
    return { success: true, id: predictionRef.id };
  } catch (error) {
    console.error("❌ Error saving analytics prediction to Firebase:", error);
    throw error;
  }
}

/**
 * Get analytics models from Firebase (for SmartLPG tenant)
 */
export async function getAnalyticsModelsFromFirebase(tenantId) {
  try {
    const modelsRef = collection(db, "smartLPG_analytics_models");
    const q = query(
      modelsRef,
      where("tenant_id", "==", tenantId),
      orderBy("created_at", "desc")
    );
    const querySnapshot = await getDocs(q);
    
    const models = [];
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      models.push({
        id: docSnap.id,
        name: data.name,
        model_type: data.model_type,
        algorithm: data.algorithm,
        is_trained: data.is_trained || false,
        training_accuracy: data.training_accuracy,
        trained_at: data.trained_at?.toDate?.()?.toISOString() || data.trained_at,
        created_at: data.created_at?.toDate?.()?.toISOString() || data.created_at,
        ...data
      });
    });
    
    return models;
  } catch (error) {
    console.error("❌ Error getting analytics models from Firebase:", error);
    return [];
  }
}

/**
 * Save analytics model to Firebase (for SmartLPG tenant)
 */
export async function saveAnalyticsModelToFirebase(model) {
  try {
    const modelData = cleanForFirebase({
      name: model.name,
      model_type: model.model_type,
      algorithm: model.algorithm,
      is_trained: model.is_trained || false,
      training_accuracy: model.training_accuracy,
      device_ids: model.device_ids || [],
      days: model.days || 30,
      tenant_id: model.tenant_id || 3,
      trained_at: model.trained_at ? Timestamp.fromDate(new Date(model.trained_at)) : null,
      created_at: Timestamp.now(),
      updated_at: Timestamp.now(),
      ...model
    });
    
    const modelRef = doc(collection(db, "smartLPG_analytics_models"));
    await setDoc(modelRef, modelData);
    console.log(`✅ Saved analytics model to Firebase`);
    return { success: true, id: modelRef.id };
  } catch (error) {
    console.error("❌ Error saving analytics model to Firebase:", error);
    throw error;
  }
}

/**
 * Delete device from Firebase
 */
export async function deleteDeviceFromFirebase(deviceId) {
  try {
    const deviceRef = doc(db, "smartLPG", deviceId);
    await deleteDoc(deviceRef);
    console.log(`✅ Deleted device ${deviceId} from Firebase`);
    return { success: true };
  } catch (error) {
    console.error("❌ Error deleting device from Firebase:", error);
    throw error;
  }
}

/**
 * Save device rule to Firebase
 */
export async function saveDeviceRuleToFirebase(rule) {
  try {
    // Convert to JSON and back to remove undefined
    const jsonSafe = JSON.parse(JSON.stringify(rule, (key, value) => {
      return value === undefined ? null : value;
    }));
    
    const cleanedRule = cleanForFirebase(jsonSafe);
    
    const ruleId = rule.id || `rule_${Date.now()}`;
    const ruleRef = doc(db, "smartLPG_device_rules", ruleId);
    await setDoc(ruleRef, {
      ...cleanedRule,
      id: ruleId,
      updated_at: Timestamp.now(),
      created_at: cleanedRule.created_at || Timestamp.now(),
    }, { merge: true });
    console.log(`✅ Saved device rule ${ruleId} to Firebase`);
    return { success: true, id: ruleId };
  } catch (error) {
    console.error("❌ Error saving device rule to Firebase:", error);
    throw error;
  }
}

/**
 * Get device rules from Firebase
 */
export async function getDeviceRulesFromFirebase() {
  try {
    const rulesRef = collection(db, "smartLPG_device_rules");
    const rulesSnap = await getDocs(rulesRef);
    const rules = [];
    rulesSnap.forEach((doc) => {
      rules.push({ ...doc.data(), id: doc.id });
    });
    console.log(`✅ Loaded ${rules.length} device rules from Firebase`);
    return rules;
  } catch (error) {
    console.error("❌ Error getting device rules from Firebase:", error);
    return [];
  }
}

/**
 * Delete device rule from Firebase
 */
export async function deleteDeviceRuleFromFirebase(ruleId) {
  try {
    const ruleRef = doc(db, "smartLPG_device_rules", ruleId);
    await deleteDoc(ruleRef);
    console.log(`✅ Deleted device rule ${ruleId} from Firebase`);
    return { success: true };
  } catch (error) {
    console.error("❌ Error deleting device rule from Firebase:", error);
    throw error;
  }
}
