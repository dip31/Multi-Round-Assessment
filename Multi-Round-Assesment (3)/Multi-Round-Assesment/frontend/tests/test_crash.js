const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Log all errors to a file
  page.on('pageerror', exception => {
    console.log('Uncaught exception:', exception);
    fs.appendFileSync('react_crash_dump.txt', `[PAGE ERROR] ${exception.stack || exception}\n`);
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      fs.appendFileSync('react_crash_dump.txt', `[CONSOLE ERROR] ${msg.text()}\n`);
    } else {
      fs.appendFileSync('react_crash_dump.txt', `[LOG] ${msg.text()}\n`);
    }
  });

  try {
    fs.writeFileSync('react_crash_dump.txt', 'Starting test...\n');
    console.log('Navigating and creating test user...');
    
    // Register
    await page.goto('http://localhost:5173/register');
    await page.fill('input[type="text"]', 'Test User');
    await page.fill('input[type="email"]', 'test_crash@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(2000);

    // Login
    await page.goto('http://localhost:5173/login');
    await page.fill('input[type="email"]', 'test_crash@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    await page.waitForNavigation({ waitUntil: 'networkidle' }).catch(() => {});
    
    // Start Assessment
    console.log('Starting assessment...');
    await page.goto('http://localhost:5173/instructions');
    await page.waitForTimeout(2000);
    const startBtn = await page.$('button.bg-\\[var\\(--color-accent\\)\\]:has-text("Start Assessment")');
    if (startBtn) {
        await startBtn.click();
    } else {
        await page.click('button:has-text("assessment")');
    }
    
    await page.waitForTimeout(1000);
    const agreeBtn = await page.$('button:has-text("I Understand, Begin Assessment")');
    if (agreeBtn) await agreeBtn.click();
    
    await page.goto('http://localhost:5173/aptitude');
    
    console.log('Waiting for crash to be logged...');
    await page.waitForTimeout(5000); // give enough time for errors
    
  } catch (err) {
    console.error('Playwright error:', err);
  } finally {
    await browser.close();
    console.log('Done, check react_crash_dump.txt');
  }
})();
