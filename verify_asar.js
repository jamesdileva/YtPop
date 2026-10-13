const path = require("path");
const asar = require("@electron/asar");
const fs = require("fs");

const root = process.cwd();
const ASAR = path.join(root, "apps/desktop/release/win-unpacked/resources/app.asar");

const members = asar.listPackage(ASAR);
const norm = (p) => p.replace(/^\\+/, "");
const assets = members.filter((p) => /[\\/]dist[\\/]assets[\\/]/.test(p));
const bundle = assets
  .map((p) => {
    try {
      return asar.extractFile(ASAR, norm(p)).toString("utf8");
    } catch (e) {
      console.log("read failed:", p, e.message);
      return "";
    }
  })
  .join("\n");

// Renderer-shipped strings (frontend bundle only)
const checks = {
  "asar has discover-btn": bundle.includes("discover-btn"),
  "asar has discover-region": bundle.includes("discover-region"),
  "asar has dark studio theme": bundle.includes("--bg"),
  "asar ships styles.css": members.some((p) => p.endsWith(".css")),
  "asar ships main.js": members.some((p) => norm(p) === "electron\\main.js"),
};

// Backend ships as a PyInstaller onedir exe beside the asar (code is in a
// compressed archive, so string-greps cannot see it). Behavioral proof of
// the frozen backend's messages lives in the worklog; here we assert the
// exe is present.
const backendDir = path.join(
  root,
  "apps/desktop/release/win-unpacked/resources/backend/api-backend.exe",
);
const backendChecks = {
  "backend exe exists": fs.existsSync(backendDir),
};

for (const [k, v] of Object.entries({ ...checks, ...backendChecks }))
  console.log(`${k}: ${v}`);
console.log(`assets scanned: ${assets.length}`);
console.log(
  Object.values({ ...checks, ...backendChecks }).every(Boolean)
    ? "ALL OK"
    : "SOME CHECKS FAILED",
);
