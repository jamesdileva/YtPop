import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("ytpop", {
  apiUrl: process.env.VITE_API_URL ?? "http://127.0.0.1:8000",
  version: "0.1.0",
});
