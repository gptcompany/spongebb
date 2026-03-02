const { defineConfig, devices } = require("@playwright/test");

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8050";

module.exports = defineConfig({
  testDir: "tests",
  timeout: 60_000,
  expect: {
    timeout: 15_000
  },
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 1440, height: 900 },
    timezoneId: "UTC",
    colorScheme: "dark"
  },
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER
    ? undefined
    : {
        command:
          "env PYTHONHASHSEED=0 LIQUIDITY_DASHBOARD_FORCE_FALLBACK=1 LIQUIDITY_DASHBOARD_FIXED_NOW=2026-02-20T00:00:00+00:00 uv run python -m liquidity.dashboard --host 127.0.0.1 --port 8050",
        url: baseURL,
        timeout: 180_000,
        reuseExistingServer: !process.env.CI
      },
  projects: [
    {
      name: "chromium-desktop-visual",
      testDir: "tests/visual",
      use: { ...devices["Desktop Chrome"] }
    },
    {
      name: "chromium-mobile-visual",
      testDir: "tests/visual",
      use: { ...devices["Pixel 7"] }
    },
    {
      name: "chromium-desktop-e2e",
      testDir: "tests/e2e_ui",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
