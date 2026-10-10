import { config as loadEnv } from "dotenv";
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, expect, test } from "@playwright/test";

const REPO = path.resolve(__dirname, "..", "..", "..");

// The live specs need a real YouTube key; repo .env is the source of truth
// (an actual environment variable still wins).
loadEnv({ path: path.join(REPO, ".env") });
const YT_KEY = process.env.YTPOP_YOUTUBE_API_KEY;

let apiProc: ReturnType<typeof spawn> | null = null;
let apiPort = 0;
let dbPath = "";

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const port = (srv.address() as net.AddressInfo).port;
      srv.close(() => resolve(port));
    });
  });
}

async function waitForHealth(timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${apiPort}/api/v1/health`);
      if (res.ok) return true;
    } catch {
      /* not up */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

async function api(path: string, init?: RequestInit) {
  const res = await fetch(`http://127.0.0.1:${apiPort}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : {} };
}

beforeAll(async () => {
  test.skip(!YT_KEY,
    "YTPOP_YOUTUBE_API_KEY not set - skipping live discovery e2e");

  apiPort = await freePort();
  const runDir = fs.mkdtempSync(path.join(os.tmpdir(), "ytpop-live-"));
  dbPath = path.join(runDir, "mega_clipper.db");

  const apiEnv = {
    ...process.env,
    YTPOP_DB_PATH: dbPath,
    YTPOP_YOUTUBE_API_KEY: YT_KEY,
    YTPOP_ROOT: REPO,
  };

  // fresh temp DB: give it the real schema via Alembic (source of truth)
  execFileSync("python", ["-m", "alembic", "upgrade", "head"], {
    cwd: path.join(REPO, "apps", "api"),
    env: apiEnv,
    stdio: "inherit",
  });

  apiProc = spawn(
    "python",
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
     "--port", String(apiPort)],
    { cwd: path.join(REPO, "apps", "api"), env: apiEnv, stdio: "ignore" },
  );
  expect(await waitForHealth(60000), "API did not become healthy").toBe(true);
});

afterAll(() => {
  apiProc?.kill();
  if (dbPath) {
    try {
      fs.rmSync(path.dirname(dbPath), { recursive: true, force: true });
    } catch {
      /* the killed backend may still hold the sqlite file */
    }
  }
});

test("live discovery seeds real YouTube data (1 quota unit)", async () => {
  const before = await api("/api/v1/sources");
  expect(before.status).toBe(200);
  expect(before.body).toEqual([]);

  const disc = await api("/api/v1/sources/discover", {
    method: "POST",
    body: JSON.stringify({ region: "US", max_results: 10 }),
  });
  expect(disc.status).toBe(200, disc.body.detail);
  expect(disc.body.seen).toBe(10);
  expect(disc.body.units_consumed).toBe(1);
  expect(disc.body.quota_used_today).toBeGreaterThanOrEqual(1);
  const imported = disc.body.imported;

  const after = await api("/api/v1/sources");
  expect(after.body.length).toBeGreaterThanOrEqual(imported);
  for (const s of after.body) {
    expect(s.provider).toBe("youtube");
    expect(s.external_id).toBeTruthy();
    expect(s.status).toBe("DISCOVERED");
  }

  // scores + dashboard sections render from real snapshots
  const refresh = await api("/api/v1/trends/discover", {
    method: "POST",
    body: JSON.stringify({}),
  });
  expect(refresh.status).toBe(200);
  expect(refresh.body.updated).toBeGreaterThanOrEqual(imported);

  const trends = await api("/api/v1/trends");
  expect(trends.status).toBe(200);
  expect(trends.body.trending_now.length).toBeGreaterThan(0);
  expect(trends.body.top_categories.length).toBeGreaterThan(0);

  // quota guard reflects the run we just made
  const jobs = await api("/api/v1/jobs");
  expect(jobs.status).toBe(200);
});
