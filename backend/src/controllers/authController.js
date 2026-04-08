// src/controllers/authController.js
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { query } from '../db/index.js';
import { config } from '../config/index.js';
import { httpError } from '../utils/helpers.js';

/**
 * POST /api/auth/login
 * Body: { email, password }
 * Returns: { token, name, role, teacherId }
 */


export async function register(req, res, next) {
    try {
        const { name, email, password } = req.body;

        if (!name || !email || !password) {
            throw httpError(400, 'All fields are required');
        }

        const { rows } = await query('SELECT id FROM teachers WHERE email = $1', [email]);

        if (rows.length > 0) {
            throw httpError(409, 'User already exists');
        }

        const hashedPassword = await bcrypt.hash(password, 12);

        await query(
            'INSERT INTO teachers (name, email, password_hash) VALUES ($1, $2, $3)',
            [name, email, hashedPassword]
        );

        res.status(201).json({ message: 'User created successfully' });
    } catch (err) {
        next(err);
    }
}


export async function login(req, res, next) {
    try {
        const { email, password } = req.body;

        if (!email || !password) {
            throw httpError(400, 'Email and password are required');
        }

        const { rows } = await query(
            'SELECT id, email, name, password_hash, role FROM teachers WHERE email = $1',
            [email]
        );

        if (rows.length === 0) {
            throw httpError(401, 'Invalid email or password');
        }

        const teacher = rows[0];
        const valid = await bcrypt.compare(password, teacher.password_hash);

        if (!valid) {
            throw httpError(401, 'Invalid email or password');
        }

        const token = jwt.sign(
            { userId: teacher.id, email: teacher.email, role: teacher.role },
            config.jwtSecret,
            { expiresIn: config.jwtExpiresIn }
        );

        res.json({
            token,
            name: teacher.name,
            role: teacher.role,
            teacherId: teacher.id,
        });
    } catch (err) {
        next(err);
    }
}

/**
 * POST /api/auth/logout (optional — stateless JWT, so this is mostly a hint)
 */
export async function logout(_req, res) {
    res.clearCookie('token');
    res.json({ message: 'Logged out' });
}
