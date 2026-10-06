import { app, BrowserWindow } from "electron";
import { spawn, ChildProcess } from "node:child_process";
import path from "node:path";

let backend: ChildProcess | null = null;
const API_URL = process.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const FRONTEND_URL = process.env.VITE_DEV_URL ?? "http://127.0.0.1:5173";

function startBackend(): void {
  // Dev: spawn uvicorn serving apps/api. Packaged: backend binary (S14).
  const apiDir = path.join(__dirname, "..", "..", "api");
  backend = spawn(
    "python",
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    { cwd: apiDir, shell: false },
  );
  backend.stdout?.on("data", (d: Buffer) => console.log(`[backend] ${d.toString().trim()}`));
  backend.stderr?.on("data", (d: Buffer) => console.error(`[backend] ${d.toString().trim()}`));
}

function createWindow(): void {
  const win = new BrowserWindow({ width: 1200, height: 800 });
  win.loadURL(FRONTEND_URL);
  console.log(`[electron] loading ${FRONTEND_URL}, api at ${API_URL}`);
}

app.whenReady().then(() => {
  startBackend();
  createWindow();
});

app.on("window-all-closed", () => {
  backend?.kill();
  if (process.platform !== "darwin") app.quit();
});
