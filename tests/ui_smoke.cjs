const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1080}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8000');
 await page.getByRole('heading',{name:'Đồ án chỉn chu, nội dung vẹn nguyên.'}).waitFor();
 assert(await page.locator('#start').isDisabled());
 await page.screenshot({path:'.runtime/ui-desktop.png',fullPage:true});
 await page.locator('#file').setInputFiles(path.join(__dirname,'../.runtime/demo.docx'));
 await page.locator('#start').click();
 await page.locator('#review').waitFor({state:'visible'});
 for(const select of await page.locator('[data-block]').all()){
  const id=await select.getAttribute('data-block');await select.selectOption(id==='b0'?'chapter':'heading');
 }
 await page.locator('#continue').click();
 await page.locator('#results').waitFor({state:'visible'});
 assert.equal(await page.locator('#changed').innerText(),'5');
 const download=page.waitForEvent('download');await page.locator('#download').click();
 const file=await download;await file.saveAs('.runtime/browser-result.docx');
 await page.screenshot({path:'.runtime/ui-results.png',fullPage:true});
 await page.reload();await page.locator('#results').waitFor({state:'visible'});
 await page.locator('#rerun').click();await page.locator('#review').waitFor({state:'visible'});
 await page.locator('#cancel').click();await page.locator('#failed').waitFor({state:'visible'});
 page.once('dialog',dialog=>dialog.accept());await page.locator('#delete').click();
 await page.locator('#upload-view').waitFor({state:'visible'});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'.runtime/ui-mobile.png',fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 await browser.close();console.log('Browser smoke PASS: upload, review, export, restore, rerun, cancel, delete, mobile.');
})().catch(e=>{console.error(e);process.exit(1)});
