/** O painel útil aparece enquanto uma integração lenta ainda está pendente. */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const require=createRequire(import.meta.url)
const {chromium}=require(process.env.MIZAN_PLAYWRIGHT_MODULE||'playwright')
const root=fileURLToPath(new URL('../',import.meta.url))
process.chdir(root);process.env.VITE_API_URL='http://127.0.0.1:8001'
const server=await createServer({root,server:{host:'127.0.0.1',port:0}})
await server.listen()
const origin=`http://127.0.0.1:${server.httpServer.address().port}`
const browser=await chromium.launch({headless:true,...(process.env.MIZAN_BROWSER_CHANNEL?{channel:process.env.MIZAN_BROWSER_CHANNEL}:{})})
let liberar
const espera=new Promise(r=>{liberar=r})
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}})
  const usuario={id:'qa',role:'comando',empresa_id:'',nome:'QA'}
  const erros=[],contagem={};let integraçãoPendente=false
  page.on('pageerror',e=>erros.push(e.message))
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url())
    if(url.origin===origin)return route.continue()
    if(url.origin!=='http://127.0.0.1:8001')return route.abort()
    contagem[url.pathname]=(contagem[url.pathname]||0)+1
    let json={}
    if(url.pathname==='/auth/refresh')json={token:'qa',usuario}
    else if(url.pathname==='/admin/modelos')json={versao_ativa:'QA-v2',total_versoes:0,versoes:[]}
    else if(url.pathname==='/admin/bandit/convergencia')json={alpha:1,acoes_convergidas:0,acoes_total:0}
    else if(url.pathname==='/admin/db-sync/status') {
      integraçãoPendente=true;await espera;integraçãoPendente=false
      json={n_sincronizacoes:7}
    }
    else if(url.pathname==='/admin/db-sync/config')json={ativo:true,tipo:'postgres'}
    else if(url.pathname==='/admin/feature-importance')return route.fulfill({status:503,json:{detail:'teste'}})
    return route.fulfill({status:200,json})
  })
  await page.addInitScript(usuario=>{
    sessionStorage.setItem('mizan_token','qa');sessionStorage.setItem('mizan_user',JSON.stringify(usuario))
  },usuario)
  await page.goto(origin+'/aprendizado',{waitUntil:'domcontentloaded'})
  await page.getByText('Ativa: QA-v2', {exact:false}).waitFor()
  assert.equal(integraçãoPendente,true,'Modelos aparecem antes da sincronização lenta')
  await page.getByText('Algumas informações não puderam ser carregadas.',{exact:false}).waitFor()
  const sinc=page.locator('div.rounded-2xl').filter({has:page.getByText('Sincronização com banco de dados do cliente',{exact:true})}).last()
  assert.equal(await sinc.locator('[aria-busy="true"]').count(),1)
  assert.equal(await page.getByRole('button',{name:'Atualizar',exact:true}).isDisabled(),true)
  liberar()
  await page.waitForFunction(()=>!document.querySelector('[aria-busy="true"]'))
  assert.equal(await page.getByRole('button',{name:'Atualizar',exact:true}).isEnabled(),true)
  await page.setViewportSize({width:390,height:844})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),true)
  assert.deepEqual(erros,[])
  console.log(JSON.stringify({ok:true,regressoes:['painel progressivo','falha isolada','integração lenta sinalizada','mobile'],contagem}))
} finally {liberar();await browser.close();await server.close()}
