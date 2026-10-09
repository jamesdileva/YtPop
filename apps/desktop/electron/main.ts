import { app, BrowserWindow } from "electron";
import { spawn, ChildProcess } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";

// userData/login paths derive from the app name; the scoped npm name
// ("@ytpop/desktop") would scatter data under Roaming/@ytpop/desktop.
app.setName("YtPop");
app.setPath("userData", path.join(app.getPath("appData"), "YtPop"));

let backend: ChildProcess | null = null;
const FRONTEND_URL = process.env.VITE_DEV_URL ?? "http://127.0.0.1:5173";
const isPackaged = app.isPackaged;

function userDataDir(): string {
  return isPackaged ? app.getPath("userData") : path.join(
    process.env.YTPOP_ROOT ?? path.join(__dirname, "..", "..", ".."));
}

function logFile(): string {
  const dir = isPackaged
    ? path.join(app.getPath("userData"), "logs")
    : path.join(__dirname, "..", "..", "..", "data", "logs");
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch {
    /* ignore */
  }
  return path.join(dir, "electron.log");
}

function log(message: string): void {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  try {
    fs.appendFileSync(logFile(), line);
  } catch {
    /* ignore */
  }
  try {
    // unconditional trail so a hang/crash is always diagnosable
    fs.appendFileSync(path.join(process.env.TEMP ?? "/tmp",
                                "ytpop-main.log"), line);
  } catch {
    /* ignore */
  }
}

process.on("uncaughtException", (err) =>
  log(`uncaughtException: ${err.message}`));
process.on("unhandledRejection", (reason) =>
  log(`unhandledRejection: ${String(reason)}`));

function freePort(): Promise<number> {
  // Ephemeral port: another project on this machine (8000 is frequently
  // taken) must never hijack the UI. The chosen port is handed to the
  // renderer through the preload at runtime.
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const port = (srv.address() as net.AddressInfo).port;
      srv.close(() => resolve(port));
    });
  });
}

function bundledApiDir(): string | null {
  // electron-builder `extraResources` copies apps/api and configs into
  // resources/api and resources/configs. `python -m uvicorn app.main:app`
  // needs resources/api as cwd (app package lives one level down).
  const candidate = path.join(process.resourcesPath, "api");
  return fs.existsSync(path.join(candidate, "app"))
    ? candidate
    : null;
}

function resolveRootDir(): string {
  const override = process.env.YTPOP_ROOT;
  if (override) return override;
  if (isPackaged) return process.resourcesPath;
  // dev: repo root relative to electron/main.js
  return path.join(__dirname, "..", "..", "..");
}

async function waitForBackend(apiUrl: string,
                              timeoutMs = 60000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (backend && backend.exitCode !== null) return false;
    try {
      const res = await fetch(`${apiUrl}/api/v1/health`);
      if (res.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

async function startBackend(): Promise<string> {
  // adopt an externally managed API (dev server / e2e fixture) instead of
  // spawning one and shadowing the caller's VITE_API_URL
  if (process.env.YTPOP_SKIP_BACKEND === "1" &&
      process.env.VITE_API_URL) {
    log(`using external api ${process.env.VITE_API_URL}`);
    return process.env.VITE_API_URL;
  }
  log("startBackend: enter");
  const apiDir = bundledApiDir();
  const cwd = apiDir ?? path.join(__dirname, "..", "..", "api");
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    YTPOP_ROOT: resolveRootDir(),
    YTPOP_DEMO_MODE: process.env.YTPOP_DEMO_MODE ?? "true",
  };
  if (isPackaged) {
    // packaged installs must not write into the read-only resources/ dir
    const dataRoot = path.join(app.getPath("userData"), "data");
    for (const dir of ["database", "media", "transcripts", "clips",
                      "renders", "captions", "storyboards", "raw", "thumbnails"]) {
      fs.mkdirSync(path.join(dataRoot, dir), { recursive: true });
    }
    env.YTPOP_DATA_DIR = dataRoot;
    env.YTPOP_DB_PATH = path.join(dataRoot, "database", "mega_clipper.db");
  }
  const port = await freePort();
  log(`startBackend: port=${port}`);
  const apiUrl = `http://127.0.0.1:${port}`;
  // stdio 'ignore' keeps the backend writing nowhere that can EPIPE when
  // the parent's pipe closes (a GUI app has no console to write to)
  backend = spawn(
    "python",
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
     "--port", String(port)],
    { cwd, shell: false, env, stdio: "ignore" },
  );
  backend.on("exit", (code, signal) =>
    log(`backend exited code=${code} signal=${signal} port=${port}`));
  log(`backend spawned cwd=${cwd} port=${port} packaged=${isPackaged} ` +
      `root=${env.YTPOP_ROOT} db=${env.YTPOP_DB_PATH ?? "(default)"} ` +
      `data=${env.YTPOP_DATA_DIR ?? "(default)"}`);
  return apiUrl;
}

function createWindow(apiUrl: string): void {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  const distIndex = path.join(__dirname, "..", "dist", "index.html");
  if (fs.existsSync(distIndex)) {
    // built UI (dev-from-repo and packaged) - no dev server needed
    win.loadFile(distIndex);
  } else {
    win.loadURL(FRONTEND_URL);
  }
  win.webContents.on("did-fail-load", (_e, _code, desc) =>
    log(`load failed: ${desc}`));
  log(`window ready, api at ${apiUrl}`);
}

app.whenReady().then(async () => {
  const apiUrl = await startBackend();
  // set BEFORE the window exists so the preload reads the chosen port
  process.env.VITE_API_URL = apiUrl;
  // show the shell right away; the renderer polls health while the backend
  // finishes starting (it also retries if the port is momentarily busy)
  createWindow(apiUrl);
  void waitForBackend(apiUrl).then((ok) =>
    log(`backend health after wait: ${ok} (${apiUrl})`));
});

app.on("window-all-closed", () => {
  backend?.kill();
  if (process.platform !== "darwin") app.quit();
});
