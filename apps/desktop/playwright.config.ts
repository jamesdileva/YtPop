import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"]],
  // Electron bundles Chromium, so no browser download is needed.
  use: {
    headless: false,
    screenshot: "only-on-failure",
    video: "off",
  },
});
