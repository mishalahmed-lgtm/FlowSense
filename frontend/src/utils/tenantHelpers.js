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
 * Check if tenant uses SmartLPG collection (tenant_id = "0078")
 */
export function isSmartLPGTenant(tenantId) {
  return tenantId === "0078" || tenantId === 78 || tenantId === "78";
}

/**
 * Check if tenant uses any Firebase collection
 */
export function usesFirebase(tenantId) {
  return isFirebaseTenant(tenantId) || isSmartLPGTenant(tenantId);
}
