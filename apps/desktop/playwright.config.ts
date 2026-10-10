import { config as loadEnv } from "dotenv";
import path from "node:path";
import { defineConfig } from "@playwright/test";

// The live specs (and the API they spawn) read YTPOP_* from process.env; the
// repo .env is the source of truth, so load it here the same way the backend
// does. A real environment variable still wins.
loadEnv({ path: path.resolve(__dirname, "..", "..", "..", ".env") });

export default defineConfig({
  testDir: "e2e",
  timeout: 180_000,
  expect: { timeout: 45_000 },
  workers: 1,
  reporter: [["list"]],
  // Electron bundles Chromium, so no browser download is needed.
  use: {
    headless: false,
    screenshot: "only-on-failure",
    video: "off",
  },
});
