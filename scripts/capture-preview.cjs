const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto(process.env.CLIPFORGE_URL || 'http://127.0.0.1:8001');
  await page.getByRole('heading',{name:'Your next great clip starts here.'}).waitFor();
  await page.screenshot({path:path.join(__dirname,'../docs/preview.png'),fullPage:true});
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
