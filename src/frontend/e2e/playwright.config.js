import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.js",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  outputDir: "../test-results",
  reporter: [["list"], ["html", { outputFolder: "../playwright-report", open: "never" }]],
  use: {
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
