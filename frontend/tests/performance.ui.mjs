/** Navegação, consultas duplicadas e custo do fundo na aplicação real com API falsa. */
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
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader'],
  ...(process.env.MIZAN_BROWSER_CHANNEL?{channel:process.env.MIZAN_BROWSER_CHANNEL}:{})})
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}})
  const usuario={id:'qa',role:'admin',empresa_id:'qa',nome:'QA'}
  const contagem={},modulos=[],erros=[]
  page.on('request',r=>{if(r.url().includes('/src/pages/'))modulos.push(new URL(r.url()).pathname)})
  page.on('pageerror',e=>erros.push(e.message))
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url())
    if(url.origin===origin)return route.continue()
    if(url.origin!=='http://127.0.0.1:8001')return route.abort()
    contagem[url.pathname]=(contagem[url.pathname]||0)+1
    let json={}
    if(url.pathname==='/auth/refresh')json={token:'qa',usuario}
    else if(url.pathname==='/empresa/config')json={nome_exibicao:'QA'}
    else if(url.pathname==='/agenda/resumo') {
      // Força os dois consumidores (menu e início) a sobreporem a leitura.
      await new Promise(r=>setTimeout(r,250));json={alto:2,medio:1}
    }
    else if(url.pathname==='/agenda/equipe')json={ativo:true,operadores:[]}
    else if(url.pathname==='/agenda/administracao/tarefas')json={itens:[],total:0}
    return route.fulfill({status:200,json})
  })
  await page.addInitScript(usuario=>{
    sessionStorage.setItem('mizan_token','qa');sessionStorage.setItem('mizan_user',JSON.stringify(usuario))
    localStorage.setItem('mizan_tema','dark')
    window.__quadros=0
    const desenhar=WebGLRenderingContext.prototype.drawArrays
    WebGLRenderingContext.prototype.drawArrays=function(...args){window.__quadros++;return desenhar.apply(this,args)}
  },usuario)
  await page.goto(origin+'/inicio',{waitUntil:'networkidle'})
  assert.equal(contagem['/agenda/resumo'],1,'Menu e Início devem compartilhar a leitura simultânea')
  assert.ok(!modulos.some(m=>m.endsWith('/Agenda.jsx')),'Não baixa todas as telas na entrada')
  const card=page.getByRole('link',{name:'Hoje: Agenda'})
  await Promise.all([page.waitForRequest(r=>r.url().includes('/src/pages/Agenda.jsx')),card.hover()])
  assert.ok(modulos.some(m=>m.endsWith('/Agenda.jsx')),'Hover antecipa o código da próxima página')
  assert.ok(page.url().endsWith('/inicio'),'Antecipação não navega nem busca dados da próxima tela')
  assert.equal(contagem['/agenda/equipe']||0,0)
  await card.click();await page.getByRole('heading',{name:'Agenda',exact:true}).waitFor()
  await page.waitForTimeout(300)
  const antes=await page.evaluate(()=>window.__quadros)
  await page.waitForTimeout(2000)
  const quadros=await page.evaluate(()=>window.__quadros)-antes
  assert.ok(quadros>0 && quadros<=52,`Fundo limitado a 24 fps: ${quadros} quadros/2s`)
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))})
  const oculto=await page.evaluate(()=>window.__quadros)
  await page.waitForTimeout(350)
  assert.equal(await page.evaluate(()=>window.__quadros),oculto,'Não desenha em aba oculta')
  await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))})
  await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(200)
  const parado=await page.evaluate(()=>window.__quadros)
  await page.waitForTimeout(350)
  assert.equal(await page.evaluate(()=>window.__quadros),parado,'Movimento reduzido não mantém animação')
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200)
  assert.ok(await page.evaluate(()=>window.__quadros)>parado,'Quadro estático redesenha após resize')
  assert.deepEqual(erros,[])
  // Painel real: rede lenta não sobrepõe ciclos e aba oculta não consulta.
  const painel=await browser.newPage({viewport:{width:1440,height:1000}})
  const consultas={},emCurso={},maximo={}
  painel.on('pageerror',e=>erros.push(e.message))
  await painel.route('**/*',async route=>{
    const url=new URL(route.request().url())
    if(url.origin===origin)return route.continue()
    if(url.origin!=='http://127.0.0.1:8001')return route.abort()
    let json={}
    if(url.pathname==='/auth/refresh')json={token:'qa',usuario}
    if(url.pathname.includes('/ranking'))json={itens:[],filtrado:0}
    if(url.pathname==='/performance/pagamentos'||url.pathname==='/feedbacks/status') {
      const chave=url.pathname
      consultas[chave]=(consultas[chave]||0)+1
      emCurso[chave]=(emCurso[chave]||0)+1
      maximo[chave]=Math.max(maximo[chave]||0,emCurso[chave])
      await new Promise(r=>setTimeout(r,150))
      json=chave==='/performance/pagamentos'?[]:{}
      await route.fulfill({status:200,json});emCurso[chave]--;return
    }
    return route.fulfill({status:200,json})
  })
  await painel.addInitScript(usuario=>{
    sessionStorage.setItem('mizan_token','qa');sessionStorage.setItem('mizan_user',JSON.stringify(usuario))
    sessionStorage.setItem('mizan_analysis',JSON.stringify({resumo:{carteira_id:'qa-carteira',total_devedores:0,
      total_em_risco:0,score_medio:0},distribuicao_aging:[],distribuicao_cluster:[],top_10:[]}))
    const original=window.setTimeout
    window.setTimeout=(fn,ms,...args)=>original(fn,ms===15000?50:ms,...args)
  },usuario)
  await painel.goto(origin+'/',{waitUntil:'domcontentloaded'})
  await painel.getByText('Total de Devedores',{exact:false}).first().waitFor()
  await painel.waitForTimeout(800)
  assert.ok(consultas['/performance/pagamentos']>=2)
  assert.equal(maximo['/performance/pagamentos'],1)
  assert.equal(maximo['/feedbacks/status'],1)
  await painel.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))})
  await painel.waitForTimeout(200)
  const pausa={...consultas};await painel.waitForTimeout(300)
  assert.deepEqual(consultas,pausa,'Painel oculto não consulta pagamentos/status')
  await painel.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))})
  await painel.waitForTimeout(200)
  assert.ok(consultas['/performance/pagamentos']>pausa['/performance/pagamentos'])
  assert.deepEqual(erros,[])
  await painel.close()
  console.log(JSON.stringify({ok:true,consultasResumo:contagem['/agenda/resumo'],quadrosEm2s:quadros,
    regressoes:['consulta compartilhada','código antecipado sem dados','limite de quadros','aba oculta','movimento reduzido','resize','painel sem sobreposição ou polling oculto']}))
} finally {await browser.close();await server.close()}
