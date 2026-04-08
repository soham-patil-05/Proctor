// tests/unit/cache.test.js — Unit tests for the in-memory TTL cache
import { jest } from '@jest/globals';

const { cached, invalidate, clearCache } = await import('../../src/utils/cache.js');

describe('utils/cache', () => {
    afterEach(() => clearCache());

    it('returns fetcher result on first call', async () => {
        const fetcher = jest.fn().mockResolvedValue('data');
        const result = await cached('key1', 5000, fetcher);
        expect(result).toBe('data');
        expect(fetcher).toHaveBeenCalledTimes(1);
    });

    it('returns cached value within TTL', async () => {
        const fetcher = jest.fn().mockResolvedValue('data');
        await cached('key2', 5000, fetcher);
        const result2 = await cached('key2', 5000, fetcher);
        expect(result2).toBe('data');
        expect(fetcher).toHaveBeenCalledTimes(1); // not called again
    });

    it('re-fetches after TTL expires', async () => {
        const fetcher = jest.fn()
            .mockResolvedValueOnce('old')
            .mockResolvedValueOnce('new');

        await cached('key3', 1, fetcher); // 1ms TTL
        // Wait for TTL to expire
        await new Promise(r => setTimeout(r, 10));
        const result = await cached('key3', 1, fetcher);
        expect(result).toBe('new');
        expect(fetcher).toHaveBeenCalledTimes(2);
    });

    it('invalidate removes a key', async () => {
        const fetcher = jest.fn()
            .mockResolvedValueOnce('v1')
            .mockResolvedValueOnce('v2');

        await cached('key4', 60000, fetcher);
        invalidate('key4');
        const result = await cached('key4', 60000, fetcher);
        expect(result).toBe('v2');
        expect(fetcher).toHaveBeenCalledTimes(2);
    });

    it('clearCache removes all keys', async () => {
        const f1 = jest.fn().mockResolvedValue('a');
        const f2 = jest.fn().mockResolvedValue('b');

        await cached('c1', 60000, f1);
        await cached('c2', 60000, f2);
        clearCache();

        await cached('c1', 60000, f1);
        await cached('c2', 60000, f2);
        expect(f1).toHaveBeenCalledTimes(2);
        expect(f2).toHaveBeenCalledTimes(2);
    });
});
