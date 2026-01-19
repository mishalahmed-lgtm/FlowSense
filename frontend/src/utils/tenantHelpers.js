/**
 * Tenant helper functions
 */

/**
 * Check if tenant uses Firebase installations collection (tenant_id = 2)
 */
export function isFirebaseTenant(tenantId) {
  return tenantId === 2 || tenantId === "2";
}

/**
 * Check if tenant uses SmartLPG collection (tenant_id = 3, "0078", or 78)
 */
export function isSmartLPGTenant(tenantId) {
  // Handle various formats: 3, "0078", 78, "78", "smartlpg", etc.
  const normalized = String(tenantId).trim();
  const asNumber = Number(tenantId);
  
  const isMatch = 
    asNumber === 3 ||           // SmartLPG tenant in database
    normalized === "3" ||
    normalized === "0078" || 
    normalized === "78" ||
    asNumber === 78 ||
    normalized === "smartlpg" ||
    normalized.toLowerCase() === "smartlpg";
  
  if (isMatch) {
    console.log(`✅ SmartLPG tenant detected: tenant_id = ${tenantId} (normalized: ${normalized})`);
  }
  
  return isMatch;
}

/**
 * Check if tenant uses any Firebase collection
 */
export function usesFirebase(tenantId) {
  return isFirebaseTenant(tenantId) || isSmartLPGTenant(tenantId);
}
