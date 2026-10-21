const {defineConfig, devices} = require('@playwright/test');
const python = process.env.SIGNSIGHT_TEST_PYTHON || 'python';
module.exports = defineConfig({
  testDir: './tests/browser',
  timeout: 30000,
  expect: {timeout: 7000},
  workers: 1,
  use: {baseURL:'http://127.0.0.1:8765', trace:'retain-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHANNEL ? {channel:process.env.PLAYWRIGHT_CHANNEL} : {}},
  projects: [
    {name:'desktop',use:{...devices['Desktop Chrome']}},
    {name:'phone',use:{...devices['iPhone 13'],browserName:'chromium'}},
  ],
  webServer: {
    command:'"'+python+'" tests/browser_server.py',
    url:'http://127.0.0.1:8765/',
    reuseExistingServer:false,
    timeout:60000,
  },
});
