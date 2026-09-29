import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3217",
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: "/snap/bin/chromium",
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    },
  },
  projects: [{ name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run start -- -H 127.0.0.1 -p 3217",
    url: "http://127.0.0.1:3217",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
