import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.E2E_PORT || "5277";
const AGENT_PORT = process.env.E2E_AGENT_PORT || "5278";
const baseURL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: {
    command: "bash scripts/start-prod.sh",
    url: `${baseURL}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      ...process.env,
      PORT,
      COPLAND_AGENT_HOST: "127.0.0.1",
      COPLAND_AGENT_PORT: AGENT_PORT,
      COPLAND_AGENT_URL: `http://127.0.0.1:${AGENT_PORT}`,
    },
  },
});
