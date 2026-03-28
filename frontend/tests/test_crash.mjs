import { chromium } from 'playwright';
import fs from 'fs';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  fs.writeFileSync('crash_log.txt', '--- START ---\n');

  page.on('pageerror', exception => {
    fs.appendFileSync('crash_log.txt', `\n[PAGE ERROR] ${exception}\n`);
  });

  page.on('console', async msg => {
    const text = msg.text();
    fs.appendFileSync('crash_log.txt', `[CONSOLE] ${msg.type()}: ${text}\n`);
  });

  try {
    await page.goto('http://localhost:5173/register');
    await page.fill('input[type="text"]', 'Test DumpUser');
    await page.fill('input[type="email"]', 'test_dump_' + Date.now() + '@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(2000);

    await page.goto('http://localhost:5173/login');
    await page.fill('input[type="email"]', 'test_dump_' + Date.now() + '@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    
    await page.waitForTimeout(2000);
    
    await page.goto('http://localhost:5173/instructions');
    await page.waitForTimeout(2000);
    await page.click('button:has-text("Start Assessment")').catch(()=>{});
    await page.click('button:has-text("assessment")').catch(()=>{});
    
    await page.waitForTimeout(1000);
    await page.click('button:has-text("I Understand, Begin Assessment")').catch(()=>{});
    
    await page.goto('http://localhost:5173/aptitude');
    
    // We strictly just wait. No evaluate, no nothing that can throw if the tab crashes.
    for (let i = 0; i < 5; i++) {
        await page.waitForTimeout(1000).catch(()=>{});
    }
  } catch (err) {
    fs.appendFileSync('crash_log.txt', `\n[RUNNER ERROR] ${err.message}\n`);
  } finally {
    await browser.close().catch(()=>{});
  }
})();
