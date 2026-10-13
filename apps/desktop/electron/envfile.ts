import fs from "node:fs";
import path from "node:path";

/** Minimal .env parser for the Electron shell.
 *
 * The main process cannot `require("dotenv")`: electron-builder ships no
 * node_modules for main, so this stays dependency-free. Supports KEY=VALUE,
 * `export KEY=VALUE`, full-line `#` comments, and single/double quotes.
 * Only `YTPOP_*` keys are returned; everything else is ignored so a stray
 * PATH= line in a file can never hijack the backend environment.
 */
export function parseEnvText(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const body = line.startsWith("export ")
      ? line.slice("export ".length).trim()
      : line;
    const eq = body.indexOf("=");
    if (eq <= 0) continue;
    const key = body.slice(0, eq).trim();
    if (!/^YTPOP_[A-Z0-9_]+$/.test(key)) continue;
    let value = body.slice(eq + 1).trim();
    const quoted =
      (value.startsWith('"') && value.endsWith('"') && value.length >= 2) ||
      (value.startsWith("'") && value.endsWith("'") && value.length >= 2);
    if (quoted) value = value.slice(1, -1);
    else value = value.split("#")[0].trim();
    out[key] = value;
  }
  return out;
}

/** Load .env files in order; later files win. Missing files are skipped.
 *  Returns the merged map plus the files actually read (for logging). */
export function loadEnvFiles(files: string[]): {
  values: Record<string, string>;
  loaded: string[];
} {
  const values: Record<string, string> = {};
  const loaded: string[] = [];
  for (const file of files) {
    try {
      if (!fs.existsSync(file)) continue;
      Object.assign(values, parseEnvText(fs.readFileSync(file, "utf8")));
      loaded.push(file);
    } catch {
      /* unreadable file: skip, backend reports the missing key itself */
    }
  }
  return { values, loaded };
}

/** Copy file-provided YTPOP_* vars into `env` without overriding real
 *  environment variables (explicit env always wins over files). */
export function applyFileEnv(
  env: NodeJS.ProcessEnv,
  values: Record<string, string>,
): string[] {
  const applied: string[] = [];
  for (const [key, value] of Object.entries(values)) {
    if (env[key] === undefined) {
      env[key] = value;
      applied.push(key);
    }
  }
  return applied;
}

/** Candidate .env locations for the spawned backend, lowest precedence
 *  first: checkout `.env` (dev runs from a repo), then the packaged
 *  install's user-data `.env` (wins - see runbook §4b). */
export function candidateEnvFiles(
  isPackaged: boolean,
  repoRoot: string,
  dataRoot: string,
): string[] {
  const files = [path.join(repoRoot, ".env")];
  if (isPackaged) files.push(path.join(dataRoot, ".env"));
  return files;
}
