// src/middleware/errorHandler.js — centralised error handler
/**
 * Express error-handling middleware.
 * Must have four arguments so Express recognises it as an error handler.
 */
export function errorHandler(err, _req, res, _next) {
    console.error('[Error]', err.stack || err.message || err);

    const status = err.status || err.statusCode || 500;
    const message = status === 500 ? 'Server error' : (err.message || 'Server error');

    res.status(status).json({ error: message });
}
