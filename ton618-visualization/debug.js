import puppeteer from 'puppeteer';
import fs from 'fs';

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  const errors = [];
  
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`[Console Error] ${msg.text()}`);
    }
  });

  page.on('pageerror', error => {
    errors.push(`[Page Error] ${error.message}`);
  });

  try {
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle0', timeout: 10000 });
  } catch (e) {
    errors.push(`[Navigation Error] ${e.message}`);
  }
  
  fs.writeFileSync('console_errors.txt', errors.join('\n'));
  await browser.close();
})();
