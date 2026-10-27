const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try {
 const page=await browser.newPage({viewport:{width:1440,height:1080}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.BASE_URL||'http://127.0.0.1:8000');
 await page.getByRole('heading',{name:'Đồ án chỉn chu, nội dung vẹn nguyên.'}).waitFor();
 assert(await page.locator('#start').isDisabled());
 await page.screenshot({path:'.runtime/ui-desktop.png',fullPage:true});
 await page.locator('#file').setInputFiles(path.join(__dirname,'../.runtime/demo.docx'));
 await page.locator('#start').click();
 await page.locator('#results').waitFor({state:'visible'});
 assert(await page.locator('#review').isHidden());
 assert.equal(await page.locator('#changed').innerText(),'5');
 assert((await page.locator('#recognition-summary').innerText()).includes('1 chương, 2 đề mục'));
 const download=page.waitForEvent('download');await page.locator('#download').click();
 await(await download).saveAs('.runtime/browser-result.docx');
 await page.screenshot({path:'.runtime/ui-results.png',fullPage:true});
 // Hold an old session's poll response until after deletion and selecting a new file.
 const oldRid=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('doclint-session')).run_id);
 let release, observed, finished;
 const gate=new Promise(r=>release=r); const intercepted=new Promise(r=>observed=r);const delivered=new Promise(r=>finished=r);
 await page.route(`**/api/v1/runs/${oldRid}`,async route=>{
   const response=await route.fetch();const body=await response.body();observed();await gate;await route.fulfill({status:response.status(),headers:response.headers(),body});finished();
 });
 await page.evaluate(()=>{poll()});await intercepted;
 page.once('dialog',dialog=>dialog.accept());await page.locator('#delete').click();
 await page.locator('#upload-view').waitFor({state:'visible'});
 assert.equal(await page.locator('#file-title').innerText(),'Kéo thả tài liệu vào đây');
 assert.equal(await page.locator('#file').inputValue(),'');assert(await page.locator('#start').isDisabled());
 assert.equal(await page.locator('#document-name').innerText(),'');
 await page.locator('#file').setInputFiles(path.join(__dirname,'fixtures/complex/02_de_muc_mo_ho.docx'));
 release();await delivered;await page.unrouteAll({behavior:'wait'});await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 assert.equal(await page.locator('#file-title').innerText(),'02_de_muc_mo_ho.docx');
 assert(await page.locator('#run-view').isHidden());
 await page.locator('#start').click();await page.locator('#review').waitFor({state:'visible'});
 assert.equal(await page.locator('#document-name').innerText(),'02_de_muc_mo_ho.docx');
 assert.equal(await page.locator('[data-block]').count(),2);
 await page.locator('#keep-all').click();await page.locator('#continue').click();
 await page.locator('#results').waitFor({state:'visible'});
 await page.reload();await page.locator('#results').waitFor({state:'visible'});
 await page.locator('#rerun').click();await page.locator('#review').waitFor({state:'visible'});
 await page.locator('#cancel').click();await page.locator('#failed').waitFor({state:'visible'});
 page.once('dialog',dialog=>dialog.accept());await page.locator('#delete').click();
 await page.locator('#upload-view').waitFor({state:'visible'});
 // Unsuitable input must stay on upload with a clear message and require a new selection.
 await page.locator('#file').setInputFiles(path.join(__dirname,'fixtures/complex/05_khong_phai_do_an.docx'));
 const rejected=page.waitForResponse(r=>r.url().endsWith('/api/v1/sessions')&&r.request().method()==='POST');
 await page.locator('#start').click();assert.equal((await rejected).status(),422);
 await page.locator('#error').waitFor({state:'visible'});
 assert((await page.locator('#error').innerText()).includes('Vui lòng tải lên một file đồ án khác'));
 assert(await page.locator('#run-view').isHidden());assert(await page.locator('#start').isDisabled());
 assert.equal(await page.locator('#file-title').innerText(),'Kéo thả tài liệu vào đây');
 assert.equal(await page.evaluate(()=>sessionStorage.getItem('doclint-session')),null);
 await page.screenshot({path:'.runtime/ui-rejected-v012.png',fullPage:true});
 // Verify front-matter recognition and both landscape/portrait margin plans via real downloads.
 for (const [name,kind] of [['01_do_an_tong_hop.docx','front'],['03_bang_gop_section_ngang.docx','tables']]) {
  await page.locator('#file').setInputFiles(path.join(__dirname,'fixtures/complex',name));
  await page.locator('#start').click();await page.locator('#results').waitFor({state:'visible'});
  const jsonDownload=page.waitForEvent('download');await page.locator('#report').click();
  const jsonFile=await jsonDownload;const jsonPath=path.join(__dirname,'../.runtime/browser-'+kind+'-v012.json');
  await jsonFile.saveAs(jsonPath);const report=JSON.parse(require('node:fs').readFileSync(jsonPath,'utf8'));
  if(kind==='front') {assert.equal(report.recognition.front_matter_blocks,4);assert.equal(report.front_matter.length,2);assert((await page.locator('#front-matter-summary').innerText()).includes('Lời cảm ơn'));assert((await page.locator('#front-matter-summary').innerText()).includes('Tóm tắt'))}
  else {assert.deepEqual(report.page_sections_applied,[0,1]);assert.equal(report.table_geometry_changes[0].after_width_twips,8504)}
  const wordDownload=page.waitForEvent('download');await page.locator('#download').click();
  await(await wordDownload).saveAs('.runtime/browser-'+kind+'-v012.docx');
  page.once('dialog',dialog=>dialog.accept());await page.locator('#delete').click();await page.locator('#upload-view').waitFor({state:'visible'});
 }
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'.runtime/ui-mobile.png',fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 console.log('Browser PASS: automatic headings, selective review, delete/reset/new filename, stale response isolation, download, restore, rerun, cancel, unsuitable rejection, front formatting, merged/landscape margins, mobile.');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
