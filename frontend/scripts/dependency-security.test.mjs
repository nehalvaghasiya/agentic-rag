import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, realpathSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const vendor = join(root, "vendor", "picomatch");
const require = createRequire(join(root, "package.json"));
const picomatch = require("picomatch");

test("every installed Picomatch copy resolves to the reviewed local security fork", () => {
  const installed = [];
  function visitModules(directory) {
    if (!existsSync(directory)) return;
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name.startsWith(".")) continue;
      const path = join(directory, entry.name);
      if (entry.name === "picomatch") installed.push(path);
      if (entry.isDirectory()) {
        if (entry.name.startsWith("@")) {
          for (const child of readdirSync(path, { withFileTypes: true })) {
            if (child.isDirectory()) visitModules(join(path, child.name, "node_modules"));
          }
        } else visitModules(join(path, "node_modules"));
      }
    }
  }
  visitModules(join(root, "node_modules"));
  assert.ok(installed.length > 0, "Picomatch must be installed");
  for (const path of installed) assert.equal(realpathSync(path), realpathSync(vendor), path);
  assert.equal(realpathSync(require.resolve("picomatch")), join(realpathSync(vendor), "index.js"));
});

test("CVE-2026-112366 inputs and suffix variants cannot block the event loop", () => {
  const script = `
    const assert = require('node:assert/strict');
    const pm = require(${JSON.stringify(join(vendor, "index.js"))});
    const patterns = ['+(*a)', '*(*a)', '+(a|*a)', '+(a*)b', '+(*)', '*(*)', '+(?*a)', '+(@(*a))'];
    for (const pattern of patterns) {
      for (const options of [{}, {maxExtglobRecursion: false}]) {
        const match = pm(pattern, options);
        assert.equal(match('a'.repeat(64) + '!'), false, pattern);
        assert.equal(match('a'.repeat(64) + '/'), false, pattern);
        assert.equal(match(pattern), true, pattern + ' must be treated literally');
      }
    }
  `;
  execFileSync(process.execPath, ["-e", script], { cwd: root, timeout: 2000, stdio: "pipe" });
});

test("ordinary glob, extglob, escaping, and file-discovery behavior stays compatible", () => {
  const cases = [
    ["src/views/KnowledgeBaseDashboard.jsx", "src/**/*.{js,jsx,ts,tsx}", true],
    ["src/test/example.test.tsx", "**/*.{test,spec}.?(c|m)[jt]s?(x)", true],
    ["node_modules/example/index.js", "src/**/*.js", false],
    ["abbaa", "+(a|b)", true],
    ["one", "@(one|two)", true],
    ["prefix", "?(pre)fix", true],
    ["abba", "+(*(a)|*(b))", true],
    ["*", "+(\\*)", true],
    ["*", '+("*")', true],
    ["*", "+([*])", true],
    ["abcd", "+(@(ab|cd))", true],
  ];
  for (const [input, pattern, expected] of cases) assert.equal(picomatch.isMatch(input, pattern), expected, pattern);
  assert.equal(picomatch.isMatch(".hidden.js", "*.js"), false);
  assert.equal(picomatch.isMatch(".hidden.js", "*.js", { dot: true }), true);
  assert.equal(picomatch.isMatch("src\\docs\\note.txt", "src/**/*.txt", { windows: true }), true);
});

test("the fork preserves the upstream runtime outside the documented parser patch", () => {
  const original = JSON.parse(readFileSync(join(vendor, "upstream-sha256.json"), "utf8"));
  for (const [path, expected] of Object.entries(original)) {
    if (path === "lib/parse.js") continue;
    assert.equal(createHash("sha256").update(readFileSync(join(vendor, path))).digest("hex"), expected, path);
  }
  const metadata = JSON.parse(readFileSync(join(vendor, "package.json"), "utf8"));
  assert.equal(metadata.name, "@agentic-rag/picomatch");
  assert.equal(metadata.private, true);
  assert.equal(metadata.license, "MIT");
  assert.equal(metadata.scripts, undefined);
});
