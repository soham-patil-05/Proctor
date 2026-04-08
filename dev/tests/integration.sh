#!/usr/bin/env bash
# integration.sh — Quick smoke test: start backend + agent, verify data appears in DB.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "==> Starting Docker Compose (postgres + redis) …"
docker compose -f "$ROOT/backend/docker-compose.yml" up -d

echo "==> Waiting for Postgres …"
until docker compose -f "$ROOT/backend/docker-compose.yml" exec -T postgres pg_isready -U labinsight; do
  sleep 1
done

echo "==> Running DB migrations …"
cd "$ROOT/backend"
npm run migrate 2>/dev/null || node src/scripts/migrate.js

echo "==> Starting HTTP + WS servers (background) …"
node src/server.js &
HTTP_PID=$!
node src/ws-server.js &
WS_PID=$!
sleep 2

echo "==> Creating a test teacher + session via seed …"
TEST_SESSION_ID=$(node -e "
  const { pool } = require('./src/db/index.js');
  (async () => {
    const t = await pool.query(
      \"INSERT INTO teachers(name,email,password_hash) VALUES('Test','test@test.com','dummy') ON CONFLICT(email) DO UPDATE SET name='Test' RETURNING id\"
    );
    const tid = t.rows[0].id;
    const s = await pool.query(
      \"INSERT INTO sessions(teacher_id, subject_id, is_live) VALUES(\$1, NULL, true) RETURNING id\",
      [tid]
    );
    console.log(s.rows[0].id);
    await pool.end();
  })();
")
echo "   Session ID: $TEST_SESSION_ID"

echo "==> Agent: joining session …"
cd "$ROOT/lab_guardian"
pip install -q -e . 2>/dev/null
lab_guardian join --roll-no TEST001 --session-id "$TEST_SESSION_ID" --api-url http://localhost:8000 --ws-url ws://localhost:8001 -vv &
AGENT_PID=$!
sleep 8   # let a snapshot cycle complete

echo "==> Checking DB for process data …"
PROC_COUNT=$(docker compose -f "$ROOT/backend/docker-compose.yml" exec -T postgres \
  psql -U labinsight -d labinsight -tAc \
  "SELECT count(*) FROM live_processes WHERE session_id='$TEST_SESSION_ID'")

echo "   live_processes rows: $PROC_COUNT"

# Cleanup
kill $AGENT_PID $HTTP_PID $WS_PID 2>/dev/null || true

if [ "$PROC_COUNT" -gt 0 ]; then
  echo "==> PASS — agent data visible in DB."
  exit 0
else
  echo "==> FAIL — no process data found."
  exit 1
fi
