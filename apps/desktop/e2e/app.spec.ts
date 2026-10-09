import { _electron as electron } from "playwright";
import type { ElectronApplication, Page } from "playwright";
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, expect, test } from "@playwright/test";

const REPO = path.resolve(__dirname, "..", "..", "..");
const DESKTOP = path.join(REPO, "apps", "desktop");
const E2E_DIR = path.join(DESKTOP, "e2e");
const MAIN_JS = path.join(DESKTOP, "electron", "main.js");

let apiProc: ReturnType<typeof spawn> | null = null;
let electronApp: ElectronApplication | null = null;
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

async function waitForHealth(timeoutMs = 60000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  const url = `http://127.0.0.1:${apiPort}/api/v1/health`;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

beforeAll(async () => {
  apiPort = await freePort();
  const runDir = fs.mkdtempSync(path.join(os.tmpdir(), "ytpop-e2e-"));
  dbPath = path.join(runDir, "mega_clipper.db");

  // 1. deterministic golden fixture (no network, no LLM)
  execFileSync("python", [path.join(E2E_DIR, "seed_golden.py"), dbPath], {
    stdio: "inherit",
  });

  // 2. real API on the fixture DB
  const env = {
    ...process.env,
    YTPOP_DB_PATH: dbPath,
    YTPOP_DEMO_MODE: "false",
    YTPOP_ROOT: REPO,
    PYTHONPATH: path.join(REPO, "apps", "api"),
  };
  apiProc = spawn(
    "python",
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
     "--port", String(apiPort)],
    { cwd: path.join(REPO, "apps", "api"), env, stdio: "pipe" });
  apiProc.stdout?.on("data", (d) => process.stdout.write(`[api] ${d}`));
  apiProc.stderr?.on("data", (d) => process.stderr.write(`[api] ${d}`));

  expect(await waitForHealth(), "API did not become healthy").toBe(true);

  // 3. compile the electron main + renderer bundle, then launch the app
  //    (typescript is hoisted to the repo root by npm workspaces)
  const tscEntry = path.join(
    DESKTOP, "..", "..", "node_modules", "typescript", "bin", "tsc");
  execFileSync(process.execPath, [tscEntry, "-p", "electron/tsconfig.json"], {
    cwd: DESKTOP, stdio: "inherit",
  });
  execFileSync("npm", ["run", "build"], {
    cwd: DESKTOP, stdio: "inherit", shell: process.platform === "win32",
  });
  electronApp = await electron.launch({
    cwd: DESKTOP,
    args: [MAIN_JS],
    env: {
      ...process.env,
      VITE_API_URL: `http://127.0.0.1:${apiPort}`,
      YTPOP_ROOT: REPO,
      // the spec owns the API; the shell must not spawn a second backend
      YTPOP_SKIP_BACKEND: "1",
    },
  });
});

afterAll(async () => {
  await electronApp?.close();
  apiProc?.kill();
});

test("packaged-quality UI: not blank and renders golden data", async () => {
  expect(electronApp).not.toBeNull();
  const page: Page = await (electronApp as ElectronApplication)
    .firstWindow();
  await page.waitForLoadState("domcontentloaded");

  // health badge proves the shell talks to the real API
  await expect(page.getByTestId("api-status")).toContainText("API: ok", {
    timeout: 30000,
  });
  await expect(page.locator("text=YtPop — Dashboard")).toBeVisible();

  // topics / sources / review / episodes / ops all carry golden rows
  await expect(page.getByTestId("trends-topics")).toContainText(
    "Golden Game Update");
  await expect(page.getByTestId("sources-list")).toContainText(
    "Golden Game Update Highlights");
  await expect(page.getByTestId("rights-1")).toContainText("UNKNOWN");
  await expect(page.getByTestId("transcript-1")).toContainText(
    "golden caption");
  await expect(page.getByTestId("episode-list")).toContainText(
    "Golden Episode");
  await expect(page.getByTestId("ops-depth")).toContainText("done: 1");
  await expect(page.getByTestId("ops-jobs")).toContainText("CLUSTER");

  // the review queue lists the single candidate from the fixture
  await expect(page.getByTestId("review-queue")).toContainText("#3");
});
