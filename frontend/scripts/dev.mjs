/** Supervise a single chat app. Provider secrets are passed only to Python children. */
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const root = resolve(frontend, "..");
const envPath = resolve(root, ".env");
if (existsSync(envPath)) process.loadEnvFile(envPath);
const backendEnv = { ...process.env };
const children = [];
let stopping = false;
function launch(command, args, cwd = root, env = backendEnv) {
  const child = spawn(command, args, { cwd, env, stdio: "inherit", detached: process.platform !== "win32" });
  children.push(child);
  child.on("error", error => { process.stderr.write(`${error.message}\n`); stop(1); });
  return child;
}
function killChild(child, signal) {
  try {
    if (process.platform !== "win32" && child.pid) process.kill(-child.pid, signal);
    else child.kill(signal);
  } catch (error) { if (error.code !== "ESRCH") throw error; }
}
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) if (child.exitCode === null) killChild(child, "SIGTERM");
  setTimeout(() => {
    for (const child of children) if (child.exitCode === null) killChild(child, "SIGKILL");
    process.exit(code);
  }, 1000).unref();
  process.exitCode = code;
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
async function command(command, args, env = backendEnv) {
  const child = launch(command, args, root, env);
  const code = await new Promise(resolveExit => child.once("exit", resolveExit));
  if (code !== 0) throw new Error(`${command} failed. Check database configuration and the output above.`);
}
async function ready(url, child) {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (stopping || child?.exitCode !== null && child?.exitCode !== undefined) throw new Error("The API stopped during startup.");
    try { const response = await fetch(url, { signal: AbortSignal.timeout(500) }); if (response.ok) return; } catch { /* Retry startup only. */ }
    await delay(250);
  }
  throw new Error("Chat API did not become ready. Check PostgreSQL and server configuration.");
}
async function main() {
  const apiPort = backendEnv.AGENTIC_RAG_DEV_API_PORT || "8001";
  const api = `http://127.0.0.1:${apiPort}`;
  let reused = false;
  try {
    const response = await fetch(`${api}/api/v2/settings/public`, { signal: AbortSignal.timeout(800) });
    if (!response.ok) throw new Error("Port is occupied by an incompatible backend. Stop it before running the integrated chat.");
    if (response.ok) {
      const settings = await response.json();
      if (settings.contract_version !== "chat-v1" || settings.knowledge_management_version !== 1 || settings.store !== "postgres") throw new Error("Port is occupied by an incompatible backend. Stop the old API and worker, then restart npm run dev to apply migrations and load knowledge management.");
      reused = true;
    }
  } catch (error) {
    if (error.message.startsWith("Port is occupied")) throw error;
    if (error instanceof SyntaxError) throw new Error("Port is occupied by an incompatible backend. Stop it before running the integrated chat.");
  }
  if (!reused) {
    backendEnv.AGENTIC_RAG_STORE = "postgres";
    backendEnv.AGENTIC_RAG_ENVIRONMENT ||= "demo";
    if (!backendEnv.AGENTIC_RAG_DATABASE_URL) {
      const stateDir = backendEnv.AGENTIC_RAG_DEV_STATE_DIR || resolve(root, ".data");
      const statePath = resolve(stateDir, "local-runtime.json");
      const databasePort = backendEnv.POSTGRES_PORT || "5432";
      mkdirSync(stateDir, { recursive: true });
      const state = existsSync(statePath) ? JSON.parse(readFileSync(statePath, "utf8")) : {
        adminPassword: backendEnv.POSTGRES_PASSWORD || randomBytes(24).toString("hex"),
        appPassword: randomBytes(24).toString("hex"),
      };
      if (!existsSync(statePath)) writeFileSync(statePath, JSON.stringify(state), { mode: 0o600 });
      backendEnv.POSTGRES_PASSWORD ||= state.adminPassword;
      backendEnv.AGENTIC_RAG_DATABASE_ADMIN_URL = `postgresql://rag:${encodeURIComponent(backendEnv.POSTGRES_PASSWORD)}@127.0.0.1:${databasePort}/rag`;
      backendEnv.AGENTIC_RAG_DATABASE_URL = `postgresql://rag_app:${state.appPassword}@127.0.0.1:${databasePort}/rag`;
      process.stdout.write("Starting local PostgreSQL. Data is retained in the existing Docker volume.\n");
      await command("docker", ["compose", "up", "-d", "--wait", "postgres"]);
    }
    if (backendEnv.AGENTIC_RAG_DATABASE_ADMIN_URL) await command("uv", ["run", "--no-sync", "agentic-rag", "migrate"]);
    const child = launch("uv", ["run", "--no-sync", "agentic-rag", "serve", "--host", "127.0.0.1", "--port", apiPort]);
    await ready(`${api}/api/v2/health/ready`, child);
    child.on("exit", code => { if (!stopping) stop(code || 1); });
    const worker = launch("uv", ["run", "--no-sync", "agentic-rag", "worker"]);
    worker.on("exit", code => { if (!stopping) stop(code || 1); });
  } else process.stdout.write("Using the running chat API.\n");
  const webEnv = {};
  for (const key of ["PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "TMPDIR", "TMP", "TEMP", "LANG"]) if (process.env[key]) webEnv[key] = process.env[key];
  webEnv.API_PROXY_TARGET = api;
  const web = launch(process.execPath, [resolve(frontend, "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--strictPort", ...process.argv.slice(2)], frontend, webEnv);
  web.on("exit", code => { if (!stopping) stop(code || 0); });
}
main().catch(error => { process.stderr.write(`${error.message}\n`); stop(1); });
