// tests/e2e/seed.js — Seed the database with a teacher and student for E2E testing
import 'dotenv/config';
import pg from 'pg';
import bcrypt from 'bcrypt';

async function seed() {
    const client = new pg.Client({ connectionString: process.env.DATABASE_URL });
    await client.connect();

    // Create teacher
    const hash = await bcrypt.hash('password123', 10);
    await client.query(
        `INSERT INTO teachers (email, name, password_hash, role)
     VALUES ('e2e@test.com', 'E2E Teacher', $1, 'teacher')
     ON CONFLICT (email) DO NOTHING`,
        [hash]
    );

    // Create students
    await client.query(
        `INSERT INTO students (roll_no, name, email, department, year)
     VALUES
       ('STU001', 'Alice Student', 'alice@test.com', 'CS', 2),
       ('STU002', 'Bob Student',   'bob@test.com',   'CS', 2)
     ON CONFLICT (roll_no) DO NOTHING`
    );

    await client.end();
    console.log('[Seed] Done — teacher: e2e@test.com / password123, students: STU001, STU002');
}

seed().catch((err) => {
    console.error('[Seed] FAILED:', err);
    process.exit(1);
});
