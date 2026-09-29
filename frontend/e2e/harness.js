import { spawn } from "node:child_process";
import { access, mkdtemp, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { basename, join, resolve, sep } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

import { expect, test as base } from "@playwright/test";

const E2E_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)));
const FRONTEND_ROOT = resolve(E2E_ROOT, "..");
const PROJECT_ROOT = resolve(FRONTEND_ROOT, "..");
const TEMP_PREFIX = "agentic-rag-e2e-";
const STARTUP_TIMEOUT_MS = 30_000;
const STOP_TIMEOUT_MS = 5_000;
const MAX_LOG_LENGTH = 128_000;

const PYTHON_EXECUTABLE =
  process.platform === "win32"
    ? join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    : join(PROJECT_ROOT, ".venv", "bin", "python");
const VITE_EXECUTABLE = join(FRONTEND_ROOT, "node_modules", "vite", "bin", "vite.js");

function inheritedEnvironment(extra = {}) {
  const environment = {};
  const inheritedKeys = [
    "PATH",
    "LANG",
    "LC_ALL",
    "HOME",
    "USERPROFILE",
    "SYSTEMROOT",
    "WINDIR",
    "TMP",
    "TEMP",
    "TMPDIR",
  ];

  for (const key of inheritedKeys) {
    if (process.env[key] !== undefined) {
      environment[key] = process.env[key];
    }
  }

  return { ...environment, ...extra };
}

async function availablePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Unable to allocate a loopback port"));
        return;
      }
      const { port } = address;
      server.close((error) => {
        if (error) {
          reject(error);
        } else {
          resolvePort(port);
        }
      });
    });
  });
}

function startProcess(name, command, args, options) {
  const child = spawn(command, args, {
    ...options,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";

  const append = (stream, data) => {
    output += "[" + stream + "] " + data.toString();
    if (output.length > MAX_LOG_LENGTH) {
      output = output.slice(-MAX_LOG_LENGTH);
    }
  };

  child.stdout.on("data", (data) => append("stdout", data));
  child.stderr.on("data", (data) => append("stderr", data));
  child.on("error", (error) => append("process", String(error) + "\n"));

  return {
    child,
    name,
    output: () => output,
  };
}

function processEnded(processHandle) {
  return (
    processHandle.child.exitCode !== null ||
    processHandle.child.signalCode !== null
  );
}

function processSummary(processHandle) {
  return (
    processHandle.name +
    " exited with code " +
    String(processHandle.child.exitCode) +
    " and signal " +
    String(processHandle.child.signalCode)
  );
}

function processLogs(processHandle) {
  const output = processHandle?.output() || "(no output)";
  return "== " + (processHandle?.name || "unknown") + " ==\n" + output;
}

async function waitForEndpoint(url, processHandle, validate = async () => {}) {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  let lastError = null;

  while (Date.now() < deadline) {
    if (processEnded(processHandle)) {
      throw new Error(
        processSummary(processHandle) + "\n" + processLogs(processHandle)
      );
    }

    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(1_000),
      });
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      await validate(response);
      return;
    } catch (error) {
      lastError = error;
      await delay(100);
    }
  }

  throw new Error(
    "Timed out waiting for " +
      url +
      ": " +
      String(lastError) +
      "\n" +
      processLogs(processHandle)
  );
}

async function waitForExit(processHandle, timeoutMs) {
  if (processEnded(processHandle)) {
    return true;
  }

  return Promise.race([
    new Promise((resolveExit) => {
      processHandle.child.once("exit", () => resolveExit(true));
    }),
    delay(timeoutMs).then(() => false),
  ]);
}

async function stopProcess(processHandle) {
  if (!processHandle || processEnded(processHandle)) {
    return;
  }

  processHandle.child.kill("SIGTERM");
  if (!(await waitForExit(processHandle, STOP_TIMEOUT_MS))) {
    processHandle.child.kill("SIGKILL");
    await waitForExit(processHandle, STOP_TIMEOUT_MS);
  }

  if (!processEnded(processHandle)) {
    throw new Error("Unable to stop " + processHandle.name);
  }
}

function validateTempRoot(tempRoot) {
  const resolvedRoot = resolve(tempRoot);
  const resolvedTemp = resolve(tmpdir());
  if (
    basename(resolvedRoot).startsWith(TEMP_PREFIX) &&
    resolvedRoot.startsWith(resolvedTemp + sep)
  ) {
    return resolvedRoot;
  }
  throw new Error("Refusing to remove unexpected directory: " + resolvedRoot);
}

async function removeTempRoot(tempRoot) {
  const validatedRoot = validateTempRoot(tempRoot);
  await rm(validatedRoot, { recursive: true, force: true });

  try {
    await access(validatedRoot);
  } catch (error) {
    if (error?.code === "ENOENT") {
      return;
    }
    throw error;
  }
  throw new Error("Temporary directory still exists: " + validatedRoot);
}

async function stopHarness(harness) {
  const errors = [];

  for (const processHandle of [harness.frontend, harness.backend]) {
    try {
      await stopProcess(processHandle);
    } catch (error) {
      errors.push(error);
    }
  }

  try {
    await removeTempRoot(harness.tempRoot);
  } catch (error) {
    errors.push(error);
  }

  if (errors.length > 0) {
    throw new AggregateError(errors, "Browser harness teardown failed");
  }
}

function combinedLogs(harness) {
  return [processLogs(harness.backend), processLogs(harness.frontend)].join(
    "\n\n"
  );
}

async function startHarness() {
  await access(PYTHON_EXECUTABLE);
  await access(VITE_EXECUTABLE);

  const tempRoot = await mkdtemp(join(tmpdir(), TEMP_PREFIX));
  const backendPort = await availablePort();
  let frontendPort = await availablePort();
  while (frontendPort === backendPort) {
    frontendPort = await availablePort();
  }
  const apiUrl = "http://127.0.0.1:" + backendPort;
  const frontendUrl = "http://127.0.0.1:" + frontendPort;
  const harness = {
    apiUrl,
    backend: null,
    fixtureFile: join(E2E_ROOT, "data", "browser-fixture.txt"),
    frontend: null,
    frontendUrl,
    tempRoot,
  };

  try {
    harness.backend = startProcess(
      "FastAPI",
      PYTHON_EXECUTABLE,
      [
        "-m",
        "uvicorn",
        "frontend.e2e.backend_fixture:app",
        "--app-dir",
        PROJECT_ROOT,
        "--host",
        "127.0.0.1",
        "--port",
        String(backendPort),
      ],
      {
        cwd: tempRoot,
        env: inheritedEnvironment({
          CORS_ORIGINS: JSON.stringify([frontendUrl]),
          DATA_DIR: join(tempRoot, "data"),
          HF_HOME: join(tempRoot, "models"),
          HF_HUB_OFFLINE: "1",
          MODE: "deterministic",
          NO_PROXY: "127.0.0.1,localhost",
          PYTHONDONTWRITEBYTECODE: "1",
          PYTHONNOUSERSITE: "1",
          PYTHONUNBUFFERED: "1",
          TRANSFORMERS_OFFLINE: "1",
          UPLOAD_DIR: join(tempRoot, "uploads"),
        }),
      }
    );

    await waitForEndpoint(apiUrl + "/api/health", harness.backend);
    await waitForEndpoint(apiUrl + "/api/kb", harness.backend, async (response) => {
      const knowledgeBases = await response.json();
      if (!Array.isArray(knowledgeBases) || knowledgeBases.length !== 0) {
        throw new Error("Browser fixture storage was not empty");
      }
    });

    harness.frontend = startProcess(
      "Vite",
      process.execPath,
      [
        VITE_EXECUTABLE,
        "--host",
        "127.0.0.1",
        "--port",
        String(frontendPort),
        "--strictPort",
      ],
      {
        cwd: FRONTEND_ROOT,
        env: inheritedEnvironment({
          BROWSER: "none",
          NO_PROXY: "127.0.0.1,localhost",
          VITE_API_URL: apiUrl,
        }),
      }
    );

    await waitForEndpoint(frontendUrl, harness.frontend);
    return harness;
  } catch (error) {
    const logs = combinedLogs(harness);
    try {
      await stopHarness(harness);
    } catch (cleanupError) {
      throw new AggregateError(
        [error, cleanupError],
        "Browser harness startup and cleanup failed\n" + logs,
        { cause: cleanupError }
      );
    }
    throw new Error("Browser harness startup failed\n" + logs, {
      cause: error,
    });
  }
}

function isAllowedNetworkUrl(rawUrl, allowedHosts) {
  const url = new URL(rawUrl);
  if (!["http:", "https:", "ws:", "wss:"].includes(url.protocol)) {
    return true;
  }
  return allowedHosts.has(url.host);
}

export const test = base.extend({
  app: async ({}, use, testInfo) => {
    const harness = await startHarness();
    try {
      await use(harness);
    } finally {
      if (testInfo.status !== testInfo.expectedStatus) {
        await testInfo.attach("application-server-logs", {
          body: Buffer.from(combinedLogs(harness)),
          contentType: "text/plain",
        });
      }
      await stopHarness(harness);
    }
  },

  context: async ({ app, browser }, use) => {
    const violations = [];
    const allowedHosts = new Set(
      [app.frontendUrl, app.apiUrl].map((url) => new URL(url).host)
    );
    const context = await browser.newContext({ baseURL: app.frontendUrl });

    await context.route("**/*", async (route) => {
      const url = route.request().url();
      if (!isAllowedNetworkUrl(url, allowedHosts)) {
        violations.push(url);
        await route.abort("blockedbyclient");
        return;
      }
      await route.continue();
    });

    if (typeof context.routeWebSocket === "function") {
      await context.routeWebSocket(/.*/, (webSocket) => {
        const url = webSocket.url();
        if (!isAllowedNetworkUrl(url, allowedHosts)) {
          violations.push(url);
          webSocket.close({
            code: 1008,
            reason: "Non-loopback browser traffic is forbidden",
          });
          return;
        }
        webSocket.connectToServer();
      });
    }

    try {
      await use(context);
    } finally {
      await context.close();
      expect(
        violations,
        "Browser tests attempted non-fixture network requests"
      ).toEqual([]);
    }
  },
});

export { expect };

