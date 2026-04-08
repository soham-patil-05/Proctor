// src/utils/cache.js — simple in-memory TTL cache for snapshot endpoints

const store = new Map();

/**
 * Get or set a cached value.
 * @param {string} key
 * @param {number} ttlMs — time-to-live in milliseconds
 * @param {() => Promise<any>} fetcher — async function to compute the value
 * @returns {Promise<any>}
 */
export async function cached(key, ttlMs, fetcher) {
    const entry = store.get(key);
    if (entry && Date.now() < entry.expiresAt) {
        return entry.value;
    }
    const value = await fetcher();
    store.set(key, { value, expiresAt: Date.now() + ttlMs });
    return value;
}

/**
 * Invalidate a specific cache key.
 */
export function invalidate(key) {
    store.delete(key);
}

/**
 * Clear entire cache.
 */
export function clearCache() {
    store.clear();
}
