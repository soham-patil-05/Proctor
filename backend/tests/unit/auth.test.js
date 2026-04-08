// tests/unit/auth.test.js — Unit tests for auth controller and middleware
import { jest } from '@jest/globals';

// ── Mock modules before imports ──────────────────────────────────
// We need to mock bcrypt, jsonwebtoken, and db/index before loading controllers.

const mockQuery = jest.fn();
jest.unstable_mockModule('../../src/db/index.js', () => ({
    query: mockQuery,
    pool: { end: jest.fn() },
}));

const mockBcryptCompare = jest.fn();
jest.unstable_mockModule('bcrypt', () => ({
    default: { compare: mockBcryptCompare },
    compare: mockBcryptCompare,
}));

const mockJwtSign = jest.fn();
const mockJwtVerify = jest.fn();
jest.unstable_mockModule('jsonwebtoken', () => ({
    default: { sign: mockJwtSign, verify: mockJwtVerify },
    sign: mockJwtSign,
    verify: mockJwtVerify,
}));

// Now import modules under test
const { login } = await import('../../src/controllers/authController.js');
const { authenticate } = await import('../../src/middleware/auth.js');

/* ─── login tests ───────────────────────────────────────────────── */
describe('authController.login', () => {
    let req, res, next;

    beforeEach(() => {
        req = { body: {} };
        res = { json: jest.fn(), status: jest.fn().mockReturnThis() };
        next = jest.fn();
        jest.clearAllMocks();
    });

    it('returns 400 when email or password missing', async () => {
        req.body = { email: '' };
        await login(req, res, next);
        expect(next).toHaveBeenCalled();
        const err = next.mock.calls[0][0];
        expect(err.status).toBe(400);
    });

    it('returns 401 for unknown email', async () => {
        req.body = { email: 'nobody@test.com', password: 'pass' };
        mockQuery.mockResolvedValueOnce({ rows: [] });

        await login(req, res, next);
        expect(next).toHaveBeenCalled();
        const err = next.mock.calls[0][0];
        expect(err.status).toBe(401);
    });

    it('returns 401 for wrong password', async () => {
        req.body = { email: 'teacher@test.com', password: 'wrong' };
        mockQuery.mockResolvedValueOnce({
            rows: [{ id: 'u1', email: 'teacher@test.com', name: 'T', password_hash: 'hashed', role: 'teacher' }],
        });
        mockBcryptCompare.mockResolvedValueOnce(false);

        await login(req, res, next);
        expect(next).toHaveBeenCalled();
        const err = next.mock.calls[0][0];
        expect(err.status).toBe(401);
    });

    it('returns token on valid login', async () => {
        req.body = { email: 'teacher@test.com', password: 'correct' };
        mockQuery.mockResolvedValueOnce({
            rows: [{ id: 'u1', email: 'teacher@test.com', name: 'Teacher', password_hash: 'hashed', role: 'teacher' }],
        });
        mockBcryptCompare.mockResolvedValueOnce(true);
        mockJwtSign.mockReturnValueOnce('jwt-token-123');

        await login(req, res, next);
        expect(res.json).toHaveBeenCalledWith({
            token: 'jwt-token-123',
            name: 'Teacher',
            role: 'teacher',
            teacherId: 'u1',
        });
    });
});

/* ─── authenticate middleware tests ─────────────────────────────── */
describe('middleware/auth.authenticate', () => {
    let req, res, next;

    beforeEach(() => {
        req = { headers: {}, query: {} };
        res = { status: jest.fn().mockReturnThis(), json: jest.fn() };
        next = jest.fn();
        jest.clearAllMocks();
    });

    it('returns 401 when no token present', () => {
        authenticate(req, res, next);
        expect(res.status).toHaveBeenCalledWith(401);
        expect(next).not.toHaveBeenCalled();
    });

    it('returns 401 for invalid token', () => {
        req.headers.authorization = 'Bearer bad-token';
        mockJwtVerify.mockImplementation(() => { throw new Error('invalid'); });

        authenticate(req, res, next);
        expect(res.status).toHaveBeenCalledWith(401);
    });

    it('calls next() and sets req.user for valid token', () => {
        req.headers.authorization = 'Bearer valid-token';
        mockJwtVerify.mockReturnValueOnce({ userId: 'u1', email: 't@t.com', role: 'teacher' });

        authenticate(req, res, next);
        expect(next).toHaveBeenCalled();
        expect(req.user).toEqual({ userId: 'u1', email: 't@t.com', role: 'teacher' });
    });
});
