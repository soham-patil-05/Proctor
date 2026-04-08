// tests/unit/dashboard.test.js — Unit test for dashboard endpoint
import { jest } from '@jest/globals';

const mockQuery = jest.fn();
jest.unstable_mockModule('../../src/db/index.js', () => ({
    query: mockQuery,
    pool: { end: jest.fn() },
}));

const { getDashboard } = await import('../../src/controllers/dashboardController.js');

describe('dashboardController.getDashboard', () => {
    let req, res, next;

    beforeEach(() => {
        req = { user: { userId: 'teacher-1' } };
        res = { json: jest.fn(), status: jest.fn().mockReturnThis() };
        next = jest.fn();
        jest.clearAllMocks();
    });

    it('returns aggregated stats', async () => {
        mockQuery.mockResolvedValueOnce({
            rows: [{ total_subjects: 3, active_session: 1, total_sessions: 10 }],
        });

        await getDashboard(req, res, next);

        expect(res.json).toHaveBeenCalledWith({
            totalSubjects: 3,
            activeSession: 1,
            totalSessions: 10,
        });
    });

    it('calls next on DB error', async () => {
        mockQuery.mockRejectedValueOnce(new Error('DB down'));
        await getDashboard(req, res, next);
        expect(next).toHaveBeenCalled();
    });
});
