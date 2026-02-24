/**
 * SmartLPG Firebase Service
 * Handles saving device dashboards, alerts, FOTA jobs, and device creation to Firebase
 */

import { db } from "../utils/firebase";
import { collection, doc, setDoc, getDoc, getDocs, deleteDoc, query, where, orderBy, limit as firestoreLimit, Timestamp } from "firebase/firestore";

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
 * Update alert in Firebase (generic update function)
 * @param {string} alertId - Alert ID
 * @param {Object} updates - Object containing fields to update
 */
export async function updateAlertInFirebase(alertId, updates) {
  try {
    const alertRef = doc(db, "smartLPG_alerts", alertId);
    const updateData = cleanForFirebase({
      ...updates,
      updated_at: Timestamp.now(),
    });
    await setDoc(alertRef, updateData, { merge: true });
    console.log(`✅ Updated alert ${alertId} in Firebase:`, updates);
    return { success: true };
  } catch (error) {
    console.error("❌ Error updating alert in Firebase:", error);
    throw error;
  }
}

/**
 * Get a single alert from Firebase by ID
 * @param {string} alertId - Alert ID
 * @returns {Promise<Object|null>} Alert data or null if not found
 */
export async function getAlertFromFirebase(alertId) {
  try {
    const alertRef = doc(db, "smartLPG_alerts", alertId);
    const alertSnap = await getDoc(alertRef);
    
    if (alertSnap.exists()) {
      const data = alertSnap.data();
      
      // Convert Firebase Timestamps to ISO strings
      let created_at = null;
      if (data.created_at) {
        if (data.created_at.toDate) {
          created_at = data.created_at.toDate().toISOString();
        } else if (typeof data.created_at === 'string') {
          created_at = data.created_at;
        } else if (data.created_at instanceof Date) {
          created_at = data.created_at.toISOString();
        }
      }
      
      let updated_at = null;
      if (data.updated_at) {
        if (data.updated_at.toDate) {
          updated_at = data.updated_at.toDate().toISOString();
        } else if (typeof data.updated_at === 'string') {
          updated_at = data.updated_at;
        } else if (data.updated_at instanceof Date) {
          updated_at = data.updated_at.toISOString();
        }
      }
      
      let acknowledged_at = null;
      if (data.acknowledged_at) {
        if (data.acknowledged_at.toDate) {
          acknowledged_at = data.acknowledged_at.toDate().toISOString();
        } else if (typeof data.acknowledged_at === 'string') {
          acknowledged_at = data.acknowledged_at;
        } else if (data.acknowledged_at instanceof Date) {
          acknowledged_at = data.acknowledged_at.toISOString();
        }
      }
      
      let resolved_at = null;
      if (data.resolved_at) {
        if (data.resolved_at.toDate) {
          resolved_at = data.resolved_at.toDate().toISOString();
        } else if (typeof data.resolved_at === 'string') {
          resolved_at = data.resolved_at;
        } else if (data.resolved_at instanceof Date) {
          resolved_at = data.resolved_at.toISOString();
        }
      }
      
      return {
        ...data,
        id: alertSnap.id,
        created_at: created_at,
        updated_at: updated_at,
        acknowledged_at: acknowledged_at,
        resolved_at: resolved_at,
        // Use created_at as triggered_at for SmartLPG alerts (they don't have a separate triggered_at field)
        triggered_at: created_at || updated_at || new Date().toISOString(),
      };
    }
    return null;
  } catch (error) {
    console.error("❌ Error getting alert from Firebase:", error);
    return null;
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
      
      // Convert Firebase Timestamps to ISO strings
      let created_at = null;
      if (data.created_at) {
        if (data.created_at.toDate) {
          created_at = data.created_at.toDate().toISOString();
        } else if (typeof data.created_at === 'string') {
          created_at = data.created_at;
        } else if (data.created_at instanceof Date) {
          created_at = data.created_at.toISOString();
        }
      }
      
      let updated_at = null;
      if (data.updated_at) {
        if (data.updated_at.toDate) {
          updated_at = data.updated_at.toDate().toISOString();
        } else if (typeof data.updated_at === 'string') {
          updated_at = data.updated_at;
        } else if (data.updated_at instanceof Date) {
          updated_at = data.updated_at.toISOString();
        }
      }
      
      let acknowledged_at = null;
      if (data.acknowledged_at) {
        if (data.acknowledged_at.toDate) {
          acknowledged_at = data.acknowledged_at.toDate().toISOString();
        } else if (typeof data.acknowledged_at === 'string') {
          acknowledged_at = data.acknowledged_at;
        } else if (data.acknowledged_at instanceof Date) {
          acknowledged_at = data.acknowledged_at.toISOString();
        }
      }
      
      let resolved_at = null;
      if (data.resolved_at) {
        if (data.resolved_at.toDate) {
          resolved_at = data.resolved_at.toDate().toISOString();
        } else if (typeof data.resolved_at === 'string') {
          resolved_at = data.resolved_at;
        } else if (data.resolved_at instanceof Date) {
          resolved_at = data.resolved_at.toISOString();
        }
      }
      
      alerts.push({
        ...data,
        id: doc.id,
        created_at: created_at,
        updated_at: updated_at,
        acknowledged_at: acknowledged_at,
        resolved_at: resolved_at,
        // Use created_at as triggered_at for SmartLPG alerts (they don't have a separate triggered_at field)
        triggered_at: created_at || updated_at || new Date().toISOString(),
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
    // Fetch all predictions ordered by predicted_at, then filter by tenant_id client-side
    // This avoids the need for a composite index
    const q = query(
      predictionsRef,
      orderBy("predicted_at", "desc"),
      firestoreLimit(1000) // Fetch enough to account for filtering
    );
    const querySnapshot = await getDocs(q);
    
    const predictions = [];
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      // Filter by tenant_id client-side
      if (data.tenant_id === tenantId) {
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
      }
    });
    
    // Sort by predicted_at descending and limit (already sorted by query, but ensure it)
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
    // Fetch all models ordered by created_at, then filter by tenant_id client-side
    // This avoids the need for a composite index
    const q = query(
      modelsRef,
      orderBy("created_at", "desc"),
      firestoreLimit(1000) // Fetch enough to account for filtering
    );
    const querySnapshot = await getDocs(q);
    
    const models = [];
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      // Filter by tenant_id client-side
      if (data.tenant_id === tenantId) {
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
      }
    });
    
    // Sort by created_at descending (already sorted by query, but ensure it)
    models.sort((a, b) => {
      const dateA = new Date(a.created_at || 0);
      const dateB = new Date(b.created_at || 0);
      return dateB - dateA;
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

/**
 * Get timeseries data from Firebase for a device and field key
 * @param {string} deviceId - Device ID
 * @param {string} key - Field key (e.g., 'level', 'temperature')
 * @param {number} minutes - Lookback window in minutes (default: 60)
 * @param {number} limit - Maximum number of points to return (default: 500)
 * @returns {Promise<Array>} Array of {ts, value} objects
 */
export async function getTimeseriesFromFirebase(deviceId, key, minutes = 60, limit = 500) {
  try {
    const timeseriesRef = collection(db, "smartLPG_timeseries");
    
    // Calculate cutoff time
    const now = new Date();
    const cutoff = new Date(now.getTime() - minutes * 60 * 1000);
    
    // Query without filters to avoid composite index requirement
    // We'll filter by device_id, key, and timestamp client-side
    // Fetch more documents to ensure we get enough after filtering
    const fetchLimit = Math.max(limit * 10, 10000); // Fetch more to account for filtering
    const q = query(
      timeseriesRef,
      orderBy("ts", "desc"),
      firestoreLimit(fetchLimit)
    );
    
    const querySnapshot = await getDocs(q);
    let points = [];
    
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      // Filter by device_id, key, and timestamp client-side
      if (data.device_id === deviceId && data.key === key) {
        const ts = data.ts?.toDate ? data.ts.toDate() : new Date(data.ts);
        if (ts >= cutoff) {
          points.push({
            ts: ts.toISOString(),
            value: data.value
          });
        }
      }
    });
    
    // Sort by timestamp ascending and limit
    points.sort((a, b) => new Date(a.ts) - new Date(b.ts));
    points = points.slice(0, limit);
    
    console.log(`✅ Loaded ${points.length} timeseries points for device ${deviceId}, key ${key} (client-side filtered)`);
    return points;
  } catch (error) {
    console.error("❌ Error getting timeseries from Firebase:", error);
    return [];
  }
}

/**
 * Save timeseries data point to Firebase
 * @param {string} deviceId - Device ID
 * @param {string} key - Field key (e.g., 'level', 'temperature')
 * @param {number} value - Numeric value
 * @param {Date|string|Timestamp} timestamp - Timestamp (defaults to now)
 * @param {number} tenantId - Tenant ID (default: 3 for SmartLPG)
 * @returns {Promise<{success: boolean, id: string}>}
 */
export async function saveTimeseriesToFirebase(deviceId, key, value, timestamp = null, tenantId = 3) {
  try {
    const ts = timestamp 
      ? (timestamp instanceof Timestamp ? timestamp : Timestamp.fromDate(new Date(timestamp)))
      : Timestamp.now();
    
    // Create a unique document ID based on device_id, key, and timestamp
    const docId = `${deviceId}_${key}_${ts.toMillis()}`;
    const timeseriesRef = doc(db, "smartLPG_timeseries", docId);
    
    await setDoc(timeseriesRef, {
      device_id: deviceId,
      key: key,
      value: typeof value === 'number' ? value : parseFloat(value) || 0,
      ts: ts,
      tenant_id: tenantId,
      created_at: Timestamp.now()
    }, { merge: true });
    
    return { success: true, id: docId };
  } catch (error) {
    console.error("❌ Error saving timeseries to Firebase:", error);
    throw error;
  }
}

/**
 * Analyze patterns for SmartLPG devices from Firebase timeseries data
 * @param {string} deviceId - Device ID
 * @param {string} deviceName - Device name
 * @param {string} analysisType - Type of analysis (occupancy, traffic, energy_consumption)
 * @param {string|null} fieldKey - Optional field key to filter by
 * @param {number} days - Number of days to analyze
 * @returns {Promise<Object|null>} Pattern analysis result
 */
export async function analyzePatternsFromFirebase(deviceId, deviceName, analysisType = "occupancy", fieldKey = null, days = 7) {
  try {
    // Calculate time range
    const now = new Date();
    const startDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    
    // Get timeseries data for the device
    const timeseriesRef = collection(db, "smartLPG_timeseries");
    const fetchLimit = 10000; // Fetch enough to account for filtering
    const q = query(
      timeseriesRef,
      orderBy("ts", "desc"),
      firestoreLimit(fetchLimit)
    );
    
    const querySnapshot = await getDocs(q);
    const data = [];
    
    querySnapshot.forEach((docSnap) => {
      const docData = docSnap.data();
      // Filter by device_id, field key (if specified), and timestamp
      if (docData.device_id === deviceId) {
        if (!fieldKey || docData.key === fieldKey) {
          const ts = docData.ts?.toDate ? docData.ts.toDate() : new Date(docData.ts);
          if (ts >= startDate && ts <= now && docData.value != null) {
            data.push({
              timestamp: ts,
              key: docData.key,
              value: typeof docData.value === 'number' ? docData.value : parseFloat(docData.value) || 0
            });
          }
        }
      }
    });
    
    if (data.length === 0) {
      return null;
    }
    
    // Sort by timestamp
    data.sort((a, b) => a.timestamp - b.timestamp);
    
    // Calculate hourly and daily averages
    const hourlyData = {};
    const dailyData = {};
    
    data.forEach(point => {
      const hour = point.timestamp.getHours();
      const dayOfWeek = point.timestamp.getDay();
      
      if (!hourlyData[hour]) {
        hourlyData[hour] = { sum: 0, count: 0 };
      }
      hourlyData[hour].sum += point.value;
      hourlyData[hour].count += 1;
      
      if (!dailyData[dayOfWeek]) {
        dailyData[dayOfWeek] = { sum: 0, count: 0 };
      }
      dailyData[dayOfWeek].sum += point.value;
      dailyData[dayOfWeek].count += 1;
    });
    
    // Calculate averages
    const hourlyAvg = {};
    const dailyAvg = {};
    
    Object.keys(hourlyData).forEach(hour => {
      hourlyAvg[parseInt(hour)] = hourlyData[hour].sum / hourlyData[hour].count;
    });
    
    Object.keys(dailyData).forEach(day => {
      dailyAvg[parseInt(day)] = dailyData[day].sum / dailyData[day].count;
    });
    
    // Find peak hour and day
    let peakHour = null;
    let peakDay = null;
    let maxHourlyAvg = -Infinity;
    let maxDailyAvg = -Infinity;
    
    Object.keys(hourlyAvg).forEach(hour => {
      if (hourlyAvg[parseInt(hour)] > maxHourlyAvg) {
        maxHourlyAvg = hourlyAvg[parseInt(hour)];
        peakHour = parseInt(hour);
      }
    });
    
    Object.keys(dailyAvg).forEach(day => {
      if (dailyAvg[parseInt(day)] > maxDailyAvg) {
        maxDailyAvg = dailyAvg[parseInt(day)];
        peakDay = parseInt(day);
      }
    });
    
    // Calculate trend
    let trend = "stable";
    if (data.length > 1) {
      const midPoint = Math.floor(data.length / 2);
      const firstHalf = data.slice(0, midPoint);
      const secondHalf = data.slice(midPoint);
      
      const firstHalfAvg = firstHalf.reduce((sum, p) => sum + p.value, 0) / firstHalf.length;
      const secondHalfAvg = secondHalf.reduce((sum, p) => sum + p.value, 0) / secondHalf.length;
      
      if (secondHalfAvg > firstHalfAvg * 1.1) {
        trend = "increasing";
      } else if (secondHalfAvg < firstHalfAvg * 0.9) {
        trend = "decreasing";
      }
    }
    
    return {
      device_id: deviceId,
      device_name: deviceName,
      analysis_type: analysisType,
      field_key: fieldKey,
      peak_times: {
        hour: peakHour,
        day: peakDay
      },
      trends: {
        overall: trend
      },
      summary: `Analyzed ${data.length} data points. ${peakHour !== null ? `Peak usage at hour ${peakHour}.` : 'No clear peak time detected.'}`,
      insights: {
        trend: trend,
        peak_hour: peakHour
      }
    };
  } catch (error) {
    console.error("❌ Error analyzing patterns from Firebase:", error);
    return null;
  }
}

/**
 * Analyze correlations between two devices/fields from Firebase timeseries data
 * @param {string} device1Id - First device ID
 * @param {string} device2Id - Second device ID
 * @param {string} field1Key - First field key
 * @param {string} field2Key - Second field key
 * @param {number} days - Number of days to analyze
 * @returns {Promise<Object|null>} Correlation result
 */
export async function analyzeCorrelationFromFirebase(device1Id, device2Id, field1Key, field2Key, days = 7) {
  try {
    // Calculate time range
    const now = new Date();
    const startDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    
    // Get timeseries data for both devices
    const timeseriesRef = collection(db, "smartLPG_timeseries");
    const fetchLimit = 10000;
    const q = query(
      timeseriesRef,
      orderBy("ts", "desc"),
      firestoreLimit(fetchLimit)
    );
    
    const querySnapshot = await getDocs(q);
    const device1Data = [];
    const device2Data = [];
    
    querySnapshot.forEach((docSnap) => {
      const docData = docSnap.data();
      const ts = docData.ts?.toDate ? docData.ts.toDate() : new Date(docData.ts);
      
      if (ts >= startDate && ts <= now && docData.value != null) {
        if (docData.device_id === device1Id && docData.key === field1Key) {
          device1Data.push({
            timestamp: ts,
            value: typeof docData.value === 'number' ? docData.value : parseFloat(docData.value) || 0
          });
        } else if (docData.device_id === device2Id && docData.key === field2Key) {
          device2Data.push({
            timestamp: ts,
            value: typeof docData.value === 'number' ? docData.value : parseFloat(docData.value) || 0
          });
        }
      }
    });
    
    if (device1Data.length === 0 || device2Data.length === 0) {
      return null;
    }
    
    // Align timestamps (find closest match within 5 minutes)
    const alignedValues = [];
    const fiveMinutes = 5 * 60 * 1000; // 5 minutes in milliseconds
    
    device1Data.forEach(point1 => {
      let closest = null;
      let minDiff = Infinity;
      
      device2Data.forEach(point2 => {
        const diff = Math.abs(point2.timestamp - point1.timestamp);
        if (diff < minDiff && diff < fiveMinutes) {
          minDiff = diff;
          closest = point2;
        }
      });
      
      if (closest) {
        alignedValues.push([point1.value, closest.value]);
      }
    });
    
    if (alignedValues.length < 10) {
      return null; // Need at least 10 aligned points
    }
    
    // Calculate correlation coefficient
    const values1 = alignedValues.map(v => v[0]);
    const values2 = alignedValues.map(v => v[1]);
    
    const mean1 = values1.reduce((sum, v) => sum + v, 0) / values1.length;
    const mean2 = values2.reduce((sum, v) => sum + v, 0) / values2.length;
    
    let numerator = 0;
    let denom1 = 0;
    let denom2 = 0;
    
    for (let i = 0; i < values1.length; i++) {
      const diff1 = values1[i] - mean1;
      const diff2 = values2[i] - mean2;
      numerator += diff1 * diff2;
      denom1 += diff1 * diff1;
      denom2 += diff2 * diff2;
    }
    
    const denominator = Math.sqrt(denom1 * denom2);
    const correlation = denominator > 0 ? numerator / denominator : 0;
    
    // Check for NaN
    if (correlation !== correlation) {
      return null;
    }
    
    // Determine correlation type
    let correlationType = "none";
    if (correlation > 0.5) {
      correlationType = "positive";
    } else if (correlation < -0.5) {
      correlationType = "negative";
    }
    
    return {
      device1_id: device1Id,
      device2_id: device2Id,
      field1_key: field1Key,
      field2_key: field2Key,
      correlation_coefficient: correlation,
      correlation_type: correlationType,
      insights: `Correlation coefficient: ${correlation.toFixed(3)}. ${correlationType === 'positive' ? 'Strong positive correlation' : correlationType === 'negative' ? 'Strong negative correlation' : 'Weak correlation'}.`
    };
  } catch (error) {
    console.error("❌ Error analyzing correlation from Firebase:", error);
    return null;
  }
}
