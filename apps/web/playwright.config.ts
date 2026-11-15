import { defineConfig, devices } from "@playwright/test";

// The real API (tests/e2e/serve.py: fake marketplace, scripted models) behind the real web app.
const API_PORT = 8010;
const WEB_PORT = 3100;

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  workers: 1, // the tests share one API process and reset it between tests
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: `http://127.0.0.1:${WEB_PORT}`, trace: "retain-on-failure" },
  projects: [
    { name: "laptop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `uv run python -m tests.e2e.serve ${API_PORT}`,
      cwd: "../..",
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `npx next build && npx next start --port ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/login`,
      env: { API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: !process.env.CI,
      timeout: 300_000,
    },
  ],
});
