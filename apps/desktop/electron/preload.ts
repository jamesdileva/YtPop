import { contextBridge } from "electron";

/**
 * Runtime config for the renderer: the API base comes from the shell
 * (VITE_API_URL at launch), so the built bundle stays port-agnostic
 * (packaged installs and e2e both reuse the same dist/).
 */
contextBridge.exposeInMainWorld("ytpop", {
  apiUrl: process.env.VITE_API_URL ?? "http://127.0.0.1:8000",
  packaged: !!process.env.YTPOP_ROOT,
  version: "0.1.0",
});
