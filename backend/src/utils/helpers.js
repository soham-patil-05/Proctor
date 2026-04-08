// src/utils/helpers.js — shared utility functions

/**
 * Wrap an async route handler so thrown errors are forwarded to Express.
 */
export function asyncHandler(fn) {
    return (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
}

/**
 * Create an HTTP error with a status code.
 */
export function httpError(status, message) {
    const err = new Error(message);
    err.status = status;
    return err;
}

/**
 * Pick only the listed keys from an object.
 */
export function pick(obj, keys) {
    return Object.fromEntries(keys.filter((k) => k in obj).map((k) => [k, obj[k]]));
}

/**
 * Snake_case to camelCase mapper for a single row object.
 */
export function toCamel(row) {
    if (!row) return row;
    const out = {};
    for (const [k, v] of Object.entries(row)) {
        const camel = k.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
        out[camel] = v;
    }
    return out;
}

/**
 * Map an array of rows to camelCase.
 */
export function rowsToCamel(rows) {
    return rows.map(toCamel);
}
