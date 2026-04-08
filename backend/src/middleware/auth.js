// src/middleware/auth.js — JWT authentication middleware
import jwt from 'jsonwebtoken';
import { config } from '../config/index.js';

/**
 * Express middleware that validates a Bearer JWT token.
 * On success, attaches `req.user = { userId, email, role }`.
 * On failure, returns 401.
 */
export function authenticate(req, res, next) {
    const header = req.headers.authorization;
    const token = header?.startsWith('Bearer ')
        ? header.slice(7)
        : req.query.token;  // fallback for WebSocket upgrade requests

    if (!token) {
        return res.status(401).json({ error: 'Authentication required' });
    }

    try {
        const decoded = jwt.verify(token, config.jwtSecret);
        req.user = {
            userId: decoded.userId,
            email: decoded.email,
            role: decoded.role,
        };
        next();
    } catch (err) {
        return res.status(401).json({ error: 'Invalid or expired token' });
    }
}

/**
 * Verify a JWT string and return the payload (used by WS server).
 * Throws on invalid/expired token.
 */
export function verifyToken(token) {
    return jwt.verify(token, config.jwtSecret);
}
