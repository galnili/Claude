import { createRequire } from 'module'; const { chromium } = createRequire(import.meta.url)('playwright');
import fs from 'fs'; import path from 'path';
const [,, htmlPath, mode, outDir, fps='30', w='1080', h='1920', angle=''] = process.argv;
const NM = path.resolve('node_modules');
const font = (pkg,file)=>fs.readFileSync(`${NM}/@fontsource/${pkg}/files/${file}`).toString('base64');
const css = ['400','500','700'].map(wt=>`@font-face{font-family:Heebo;font-weight:${wt};src:url(data:font/woff2;base64,${font('heebo',`heebo-hebrew-${wt}-normal.woff2`)})}
@font-face{font-family:Heebo;font-weight:${wt};src:url(data:font/woff2;base64,${font('heebo',`heebo-latin-${wt}-normal.woff2`)});unicode-range:U+0000-00FF}`).join('\n')
 + ['500','700'].map(wt=>`@font-face{font-family:Rubik;font-weight:${wt};src:url(data:font/woff2;base64,${font('rubik',`rubik-hebrew-${wt}-normal.woff2`)})}
@font-face{font-family:Rubik;font-weight:${wt};src:url(data:font/woff2;base64,${font('rubik',`rubik-latin-${wt}-normal.woff2`)});unicode-range:U+0000-00FF}`).join('\n');
const browser = await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const page = await browser.newPage({viewport:{width:+w,height:+h},deviceScaleFactor:1});
page.on('console',m=>console.log('console:',m.text())); page.on('pageerror',e=>console.log('ERR',e.message));
await page.route('**/*', async r=>{
  const u=new URL(r.request().url());
  if(u.host==='local.test') return r.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head><body>'+fs.readFileSync(htmlPath,'utf8')+'</body></html>'});
  if(u.host==='cdn.jsdelivr.net'){const p=u.pathname.replace('/npm/three@0.160.0','');return r.fulfill({contentType:'text/javascript',body:fs.readFileSync(`${NM}/three${p}`)});}
  if(u.host==='fonts.googleapis.com') return r.fulfill({contentType:'text/css',body:css});
  return r.abort();
});
await page.goto('http://local.test/'+(mode==='video'?'?video':''));
if(mode==='video'){
  await page.waitForFunction(()=>window.READY,null,{timeout:60000});
  const dur=await page.evaluate(()=>window.TOUR_DURATION); const n=Math.round(dur*fps)+1;
  fs.mkdirSync(outDir,{recursive:true});
  const only = angle? angle.split(',').map(Number):null;
  const frames = only? only.map(t=>Math.round(t*fps)) : [...Array(n).keys()];
  const t0=Date.now();
  for(const i of frames){
    await page.evaluate(t=>window.renderAt(t), i/fps);
    await page.screenshot({path:`${outDir}/f${String(i).padStart(5,'0')}.jpg`,type:'jpeg',quality:92});
    if(i%60===0) console.log('frame',i,'/',n,((Date.now()-t0)/1000).toFixed(0)+'s');
  }
}else{
  await page.waitForTimeout(4000);
  await page.screenshot({path:outDir});
}
await browser.close();
