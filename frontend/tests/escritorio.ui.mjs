/** QA/regressões do escritório. Executar: npm run test:escritorio:ui.
 * Usa Playwright instalado localmente ou MIZAN_PLAYWRIGHT_MODULE apontando
 * para uma instalação existente. Sessão e APIs são isoladas com fixtures.
 */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createServer } from 'vite'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.MIZAN_PLAYWRIGHT_MODULE || 'playwright')
const root = fileURLToPath(new URL('../', import.meta.url))
const output = process.env.MIZAN_QA_OUTPUT || join(tmpdir(), 'mizan-escritorio-qa')
await mkdir(output, { recursive: true })
process.chdir(root)
process.env.VITE_API_URL = 'http://127.0.0.1:8001'
const server = await createServer({ root, server: { host: '127.0.0.1', port: 0 } })
await server.listen()
const address = `http://127.0.0.1:${server.httpServer.address().port}`
const browser = await chromium.launch({ headless: true, ...(process.env.MIZAN_BROWSER_CHANNEL ? { channel: process.env.MIZAN_BROWSER_CHANNEL } : {}) })
const errors = []
let empresa = 'Goiás Bank', fail = false, chamadas = 0
const nomes = ['Triagem','Negociador','Estrategista','Cientista','Acompanhamento','Orquestrador','Supervisor','Auditor','Travas','Ferramenta']
const agora = () => new Date().toISOString()
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1800 }, reducedMotion: 'reduce' })
  page.on('pageerror', e => errors.push(e.message))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (url.origin === address) return route.continue()
    if (url.origin !== 'http://127.0.0.1:8001') return route.abort()
    let json = {}
    if (url.pathname === '/auth/refresh') json = {token:'local-qa',usuario:{id:'qa',role:'admin',empresa_id:'qa',nome:'QA'}}
    else if (url.pathname === '/empresa/config') json = {nome_exibicao:empresa}
    else if (url.pathname === '/agente/agentes') json = {agentes:nomes.map(nome=>({nome,acoes:12,tempo_medio_ms:389,tokens:1536,bloqueios:0,ultimo_em:agora()})),numeros:{conversas:7,respostas:18,acordos:2,bloqueios:0}}
    else if (url.pathname === '/agente/estacao') {
      chamadas++
      if (fail) return route.fulfill({status:503,json:{detail:'Falha de teste'}})
      json = {agora:agora(),ligado:true,executando:[{id:'evento-qa',quem:'Negociador',no:'negociar',estado:'pensando',caso_id:'4865ab',trace_id:'trace-qa'}],
        sinais:[{id:'sinal-qa',t:agora(),tipo:'inicio',quem:'Negociador',no:'negociar',caso_id:'4865ab',trace_id:'trace-qa'}],
        passos:[{quem:'Negociador',no:'negociar',explicacao:'Escreveu a resposta',resultado:'ok',duracao_ms:389,tokens_entrada:412,tokens_saida:123,criado_em:agora(),trace_id:'trace-qa'}],
        casos:[{id:'evento-qa',caso_id:'4865ab',tipo:'mensagem_devedor',situacao:'processando',quem:'Negociador',etapas:['Orquestrador','Triagem']}]}
    } else if (url.pathname === '/agenda/resumo') json = {alto:0,medio:0}
    return route.fulfill({status:200,json})
  })
  await page.addInitScript(() => {
    sessionStorage.setItem('mizan_token','local-qa')
    sessionStorage.setItem('mizan_user',JSON.stringify({id:'qa',role:'admin',empresa_id:'qa',nome:'QA'}))
    localStorage.setItem('mizan_tema','dark')
  })
  await page.goto(address+'/agente', {waitUntil:'domcontentloaded'})
  await page.locator('.ao-agent-row').first().waitFor()
  // REG-LAYOUT-001: agentes fora e abaixo do frame sala/detalhes.
  const geometria = await page.evaluate(() => {
    const lista=document.querySelector('.ao-agent-list'), sala=document.querySelector('.ao-room'), detalhes=document.querySelector('.ao-right')
    return {fora:!lista.closest('.ao-frame'),lista:lista.getBoundingClientRect().toJSON(),sala:sala.getBoundingClientRect().toJSON(),detalhes:detalhes.getBoundingClientRect().toJSON()}
  })
  assert.ok(geometria.lista.y >= Math.max(geometria.sala.bottom,geometria.detalhes.bottom), 'REG-LAYOUT-001: a lista precisa estar abaixo do escritório e dos detalhes')
  assert.ok(geometria.fora, 'REG-LAYOUT-001: lista fora do frame')
  assert.ok(geometria.sala.width >= 940, 'REG-SIZE-002: sala ampliada para a esquerda')
  const linhas = await page.locator('.ao-agent-row').evaluateAll(els=>els.slice(0,2).map(el=>el.getBoundingClientRect().toJSON()))
  assert.equal(linhas[0].y,linhas[1].y,'REG-LAYOUT-001: agentes na horizontal')
  console.log('ok REG-LAYOUT-001 / REG-SIZE-002')
  await page.locator('.ao-agent-row').filter({hasText:'Negociador'}).click()
  await page.locator('.ao-task').filter({hasText:'Conduzindo a negociação'}).waitFor()
  assert.equal(new URL(page.url()).pathname,'/agente','Seleção permanece na página')
  // REG-NAMES-003: nomes canônicos inteiros, sem truncamento nem colisões.
  await page.waitForFunction(() => document.querySelectorAll('.ao-agent-label:not([hidden])').length===10)
  const labels=await page.locator('.ao-agent-label:not([hidden])').evaluateAll(els=>els.map(el=>({nome:el.textContent,r:el.getBoundingClientRect().toJSON(),inteiro:el.scrollWidth<=el.clientWidth})))
  assert.deepEqual(labels.map(x=>x.nome).sort(),[...nomes].sort())
  for(const l of labels)assert.ok(l.inteiro,`REG-NAMES-003: ${l.nome} sem corte`)
  // REG-NAMES-007: coordenadas absolutas partem do topo do cenário,
  // nunca da posição do fluxo HTML depois do canvas (nomes invisíveis).
  const stage=await page.locator('.ao-stage').boundingBox()
  for(const {nome,r} of labels)assert.ok(r.x>=stage.x&&r.y>=stage.y&&r.right<=stage.x+stage.width&&r.bottom<=stage.y+stage.height,`REG-NAMES-007: ${nome} fora da sala`)
  for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++){
    const a=labels[i].r,b=labels[j].r
    assert.ok(a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top,`REG-NAMES-003: ${labels[i].nome}/${labels[j].nome} sobrepostos`)
  }
  console.log('ok REG-NAMES-003')
  await page.locator('.ao-office').screenshot({path:join(output,'escritorio-desktop.png')})
  // REG-BRAND-004: placa e texto inteiros dentro da parede, com nomes variados.
  for(const nome of ['Goiás Bank','WWK Crédito 2026','Cooperativa de Crédito e Investimentos do Estado de Goiás','EMPRESACOMNOMEMUITOLONGOSEMESPACOS']){
    empresa=nome
    await page.reload({waitUntil:'domcontentloaded'})
    await page.waitForFunction(nome=>document.querySelector('.ao-office-brand p')?.textContent.includes(nome),nome)
    const marca=await page.locator('.ao-stage canvas').evaluate(async(canvas,nome)=>{
      const {validarPlaca}=await import('/src/components/escritorio/marca.js')
      const {background,P}=await import('/src/components/escritorio/canvas.js')
      const base=background('MIZAN').getContext('2d').getImageData(0,0,544,380).data
      const atual=background(nome).getContext('2d').getImageData(0,0,544,380).data
      const [ox,oy]=P(11.1,0,72)
      let alterados=0,fora=0
      for(let k=0;k<atual.length;k+=4)if(atual[k]!==base[k]||atual[k+1]!==base[k+1]||atual[k+2]!==base[k+2]){
        alterados++;const x=(k/4)%544-ox,y=Math.floor(k/4/544)-oy-x/2
        if(x< -4.2||x>68.2||y< -5||y>43)fora++
      }
      const [sx,sy]=P(2,0,50),indice=(Math.round(sy)*544+Math.round(sx))*4
      return {...validarPlaca(nome),alterados,fora,cor:[...atual.slice(indice,indice+3)]}
    },nome)
    assert.ok(marca.cabe,`REG-BRAND-004: placa não contém ${nome}`)
    assert.ok(marca.alterados>0&&marca.fora===0,`REG-BRAND-004: texto fora da placa de ${nome}`)
    assert.deepEqual(marca.cor,[89,102,217],'REG-COLOR-006: azul da marca no desenho real')
  }
  console.log('ok REG-BRAND-004')
  empresa='Goiás Bank';await page.reload({waitUntil:'domcontentloaded'});await page.locator('.ao-agent-row').first().waitFor()
  for(const width of [1440,1280,1024,760,390,320]){
    await page.setViewportSize({width,height:1100})
    await page.waitForTimeout(250)
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`REG-RESP-005: overflow em ${width}px`)
    await page.locator('.ao-agent-row').filter({hasText:'Acompanhamento'}).focus()
    await page.keyboard.press('Enter')
    await page.locator('.ao-right h4').filter({hasText:'Acompanhamento'}).waitFor()
    if(width===390) await page.screenshot({path:join(output,'escritorio-mobile.png'),fullPage:true})
  }
  console.log('ok REG-RESP-005 / seleção por teclado')
  await page.setViewportSize({width:1920,height:1200})
  await page.getByRole('button',{name:'Casos',exact:true}).click();await page.locator('.ao-case').waitFor()
  await page.getByRole('button',{name:'Atividade',exact:true}).click();await page.locator('.ao-feed li').waitFor()
  assert.equal(await page.locator('.ao-feed li').count(),1,'Feed sem duplicação')
  await page.getByRole('button',{name:'Fechar Atividade',exact:true}).click()
  await page.getByRole('button',{name:'Seguir na sala',exact:true}).click()
  await page.getByRole('button',{name:'Centralizar sala',exact:true}).click()
  fail=true;await page.locator('.ao-warning').waitFor({timeout:10000})
  assert.equal(await page.locator('.ao-agent-row').count(),10,'Regressão: manter os agentes na reconexão')
  fail=false;await page.locator('.ao-warning').waitFor({state:'hidden',timeout:10000})
  assert.deepEqual(errors,[],'Nenhum erro de JavaScript')
  console.log(JSON.stringify({ok:true,chamadas,capturas:output}))
} finally { await browser.close(); await server.close() }
