"""Responsive public pages in real Chrome; API intercepted, no messages sent."""
import asyncio,json,os,signal,socket,subprocess,tempfile
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(tempfile.mkdtemp(prefix='mysecop-ux-public-'))
async def main():
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 server=subprocess.Popen(['npm','run','start','--','-p',str(port)],cwd=ROOT/'frontend',start_new_session=True,stdout=open(OUT/'next.log','w'),stderr=subprocess.STDOUT)
 try:
  import httpx
  async with httpx.AsyncClient() as c:
   for _ in range(100):
    try:
     if (await c.get(f'http://127.0.0.1:{port}',timeout=1)).status_code==200:break
    except Exception:pass
    await asyncio.sleep(.2)
  results=[]
  async with async_playwright() as p:
   browser=await p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'),headless=True)
   for width,height in [(320,760),(390,844),(768,1024),(1024,768),(1440,900),(844,390)]:
    for theme in ['light','dark']:
     ctx=await browser.new_context(viewport={'width':width,'height':height});await ctx.add_init_script(f"localStorage.setItem('licitaia-theme','{theme}')")
     page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
     await page.route('**/api/**',lambda r:r.fulfill(status=200,json={}))
     for path in ['/','/contacto','/iniciar-sesion','/registro','/restablecer-contrasena']:
      await page.goto(f'http://127.0.0.1:{port}{path}');await page.wait_for_timeout(300)
      overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth')
      assert not overflow,(width,theme,path,'horizontal overflow')
      await page.screenshot(path=str(OUT/f'{width}-{theme}-{path.strip("/") or "landing"}.png'),full_page=True)
      await page.add_script_tag(path=os.environ.get('AXE_CORE_PATH','/private/tmp/mysecop-ux-tools/node_modules/axe-core/axe.min.js'))
      axe=await page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))}")
      results.append({'width':width,'theme':theme,'path':path,'violations':axe})
     assert not errors,errors
     await ctx.close()
   await browser.close()
  (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({'pages':len(results),'evidence':str(OUT),'violations':sorted(set(v['id'] for r in results for v in r['violations']))}))
 finally:os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=20)
asyncio.run(main())
