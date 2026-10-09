import type { ElectronApplication } from "playwright";
import { _electron as electron } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, expect, test } from "@playwright/test";

const REPO = path.resolve(__dirname, "..", "..", "..");
const DESKTOP = path.join(REPO, "apps", "desktop");
const EXE = path.join(DESKTOP, "release", "win-unpacked", "YtPop.exe");
const APP_DATA = path.join(os.homedir(), "AppData", "Roaming", "YtPop");

let app: ElectronApplication | null = null;
let hadExisting = "";

beforeAll(async () => {
  test.skip(!fs.existsSync(EXE),
    `packaged build not found at ${EXE} - run 'npm run dist' first`);

  // the packaged app resolves its data root to userData; seed the golden DB
  // there so a fresh install shows deterministic content
  const dbDir = path.join(APP_DATA, "data", "database");
  const dbPath = path.join(dbDir, "mega_clipper.db");
  if (fs.existsSync(dbPath)) {
    hadExisting = `${dbPath}.bak`;
    fs.copyFileSync(dbPath, hadExisting);
  }
  fs.mkdirSync(dbDir, { recursive: true });
  execFileSync("python", [
    path.join(DESKTOP, "e2e", "seed_golden.py"), dbPath], {
      stdio: "inherit",
  });

  app = await electron.launch({ executablePath: EXE, cwd: DESKTOP });
});

afterAll(async () => {
  await app?.close();
  if (hadExisting) {
    fs.copyFileSync(hadExisting,
      path.join(APP_DATA, "data", "database", "mega_clipper.db"));
    fs.rmSync(hadExisting, { force: true });
  } else {
    fs.rmSync(path.join(APP_DATA, "data"), { recursive: true, force: true });
  }
});

test("packaged exe boots with real data (not a blank screen)", async () => {
  expect(app).not.toBeNull();
  const page = await (app as ElectronApplication).firstWindow();
  await page.waitForLoadState("domcontentloaded");

  // the shell mounts the built UI and its backend answers
  await expect(page.getByTestId("api-status")).toContainText("API: ok", {
    timeout: 45000,
  });
  await expect(page.locator("h1")).toContainText("YtPop");

  // golden rows prove the packaged backend reads the seeded DB
  await expect(page.getByTestId("trends-topics")).toContainText(
    "Golden Game Update");
  await expect(page.getByTestId("sources-list")).toContainText(
    "Golden Game Update Highlights");
  await expect(page.getByTestId("episode-list")).toContainText("Golden Episode");
  await expect(page.getByTestId("ops-depth")).toContainText("done: 1");
});
