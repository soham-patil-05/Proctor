// tests/unit/joinSession.test.js — Unit tests for the joinSession controller
import { jest } from '@jest/globals';

/* ── Mock deps ────────────────────────────────────────────────── */
const mockGetSessionById = jest.fn();
const mockUpsertStudent = jest.fn();
const mockEnsureSessionStudent = jest.fn();

jest.unstable_mockModule('../../src/services/studentService.js', () => ({
    getSessionById: mockGetSessionById,
    upsertStudent: mockUpsertStudent,
    ensureSessionStudent: mockEnsureSessionStudent,
}));

const mockJwtSign = jest.fn();
jest.unstable_mockModule('jsonwebtoken', () => ({
    default: { sign: mockJwtSign },
    sign: mockJwtSign,
}));

jest.unstable_mockModule('../../src/config/index.js', () => ({
    config: { jwtSecret: 'test-secret' },
}));

// Mock query to satisfy import even though joinSession doesn't use it directly
jest.unstable_mockModule('../../src/db/index.js', () => ({
    query: jest.fn(),
    pool: { end: jest.fn() },
}));

// Mock cache
jest.unstable_mockModule('../../src/utils/cache.js', () => ({
    cached: jest.fn((key, ttl, fn) => fn()),
    invalidate: jest.fn(),
    clearCache: jest.fn(),
}));

const { joinSession } = await import('../../src/controllers/studentsController.js');

/* ── Tests ────────────────────────────────────────────────────── */
describe('joinSession', () => {
    let req, res, next;

    beforeEach(() => {
        req = { body: {} };
        res = { json: jest.fn(), status: jest.fn().mockReturnThis() };
        next = jest.fn();
        jest.clearAllMocks();
    });

    it('returns 400 when rollNo or sessionId missing', async () => {
        req.body = { rollNo: 'STU001' }; // no sessionId
        await joinSession(req, res, next);
        expect(next).toHaveBeenCalled();
        expect(next.mock.calls[0][0].status).toBe(400);
    });

    it('returns 404 when session not found', async () => {
        req.body = { rollNo: 'STU001', sessionId: 'bad-uuid' };
        mockGetSessionById.mockResolvedValueOnce(null);

        await joinSession(req, res, next);
        expect(next.mock.calls[0][0].status).toBe(404);
    });

    it('returns 400 when session is not live', async () => {
        req.body = { rollNo: 'STU001', sessionId: 's1' };
        mockGetSessionById.mockResolvedValueOnce({ is_live: false });

        await joinSession(req, res, next);
        expect(next.mock.calls[0][0].status).toBe(400);
    });

    it('returns 403 for wrong password', async () => {
        req.body = { rollNo: 'STU001', sessionId: 's1', password: 'wrong' };
        mockGetSessionById.mockResolvedValueOnce({ is_live: true, password: 'correct' });

        await joinSession(req, res, next);
        expect(next.mock.calls[0][0].status).toBe(403);
    });

    it('returns token on successful join', async () => {
        req.body = { rollNo: 'STU001', sessionId: 's1' };
        mockGetSessionById.mockResolvedValueOnce({ is_live: true, password: null });
        mockUpsertStudent.mockResolvedValueOnce('student-uuid');
        mockEnsureSessionStudent.mockResolvedValueOnce();
        mockJwtSign.mockReturnValueOnce('test-jwt');

        await joinSession(req, res, next);

        expect(res.json).toHaveBeenCalledWith({
            token: 'test-jwt',
            studentId: 'student-uuid',
            sessionId: 's1',
            expiresIn: 3600,
        });
        expect(mockUpsertStudent).toHaveBeenCalledWith('STU001');
        expect(mockEnsureSessionStudent).toHaveBeenCalledWith('s1', 'student-uuid');
    });

    it('allows join when session password matches', async () => {
        req.body = { rollNo: 'STU001', sessionId: 's1', password: 'secret' };
        mockGetSessionById.mockResolvedValueOnce({ is_live: true, password: 'secret' });
        mockUpsertStudent.mockResolvedValueOnce('student-uuid');
        mockEnsureSessionStudent.mockResolvedValueOnce();
        mockJwtSign.mockReturnValueOnce('jwt-ok');

        await joinSession(req, res, next);
        expect(res.json).toHaveBeenCalledWith(
            expect.objectContaining({ token: 'jwt-ok' })
        );
    });
});
