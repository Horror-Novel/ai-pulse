import { defineConfig } from "@playwright/test";

const python = process.env.PYTHON || (process.platform === "win32"
  ? "../.venv/Scripts/python.exe" : "../.venv/bin/python");

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45000,
  use: { baseURL: "http://127.0.0.1:5174", headless: true, trace: "retain-on-failure" },
  webServer: [
    { command: `"${python}" ../backend/tests/serve_e2e.py`, url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false, timeout: 60000 },
    { command: "npm run dev -- --host 127.0.0.1 --port 5174 --strictPort",
      url: "http://127.0.0.1:5174", reuseExistingServer: false,
      env: { VITE_API_URL: "http://127.0.0.1:8001" } },
  ],
});
