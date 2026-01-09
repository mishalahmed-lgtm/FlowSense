/**
 * Page-level caching utility
 * Stores data in localStorage with TTL to prevent unnecessary reloads
 */

const CACHE_PREFIX = 'page_cache_';
const DEFAULT_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours

/**
 * Save data to cache
 * @param {string} key - Cache key
 * @param {any} data - Data to cache
 * @param {number} ttlMs - Time to live in milliseconds (default: 5 minutes)
 */
export function saveToCache(key, data, ttlMs = DEFAULT_TTL_MS) {
  try {
    const cacheEntry = {
      data: data,
      timestamp: Date.now(),
      expires: Date.now() + ttlMs,
    };
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(cacheEntry));
    console.log(`💾 Cached: ${key} (expires in ${Math.round(ttlMs / 1000)}s)`);
  } catch (error) {
    console.warn('Failed to save to cache:', error);
  }
}

/**
 * Load data from cache
 * @param {string} key - Cache key
 * @returns {any|null} - Cached data or null if not found/expired
 */
export function loadFromCache(key) {
  try {
    const cached = localStorage.getItem(CACHE_PREFIX + key);
    if (!cached) {
      return null;
    }

    const cacheEntry = JSON.parse(cached);
    const now = Date.now();

    // Check if expired
    if (now > cacheEntry.expires) {
      console.log(`🗑️ Cache expired: ${key} (age: ${Math.round((now - cacheEntry.timestamp) / 1000)}s)`);
      localStorage.removeItem(CACHE_PREFIX + key);
      return null;
    }

    const age = Math.round((now - cacheEntry.timestamp) / 1000);
    console.log(`📦 Cache hit: ${key} (age: ${age}s)`);
    return cacheEntry.data;
  } catch (error) {
    console.warn('Failed to load from cache:', error);
    return null;
  }
}

/**
 * Clear specific cache key
 * @param {string} key - Cache key to clear
 */
export function clearCache(key) {
  try {
    localStorage.removeItem(CACHE_PREFIX + key);
    console.log(`🗑️ Cache cleared: ${key}`);
  } catch (error) {
    console.warn('Failed to clear cache:', error);
  }
}

/**
 * Clear all page caches
 */
export function clearAllCaches() {
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(CACHE_PREFIX)) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
    console.log(`🗑️ Cleared ${keysToRemove.length} cache entries`);
  } catch (error) {
    console.warn('Failed to clear all caches:', error);
  }
}

/**
 * Get cache key with filters
 * @param {string} baseName - Base name for the cache key
 * @param {object} filters - Filter object to include in cache key
 * @returns {string} - Cache key
 */
export function getCacheKey(baseName, filters = {}) {
  const filterStr = Object.entries(filters)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join('&');
  return filterStr ? `${baseName}_${filterStr}` : baseName;
}
