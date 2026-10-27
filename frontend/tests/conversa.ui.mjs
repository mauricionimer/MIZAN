/** Regressão: espera técnica atualiza a resposta sem reenviar nem fingir handoff. */
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
const address=`http://127.0.0.1:${server.httpServer.address().port}`
const browser=await chromium.launch({headless:true,...(process.env.MIZAN_BROWSER_CHANNEL?{channel:process.env.MIZAN_BROWSER_CHANNEL}:{})})
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'})
  let enviado=false,leituras=0,posts=0,retomadas=0,humano=false
  const erros=[];page.on('pageerror',e=>erros.push(e.message))
  const usuario={id:'qa',role:'admin',empresa_id:'qa',nome:'QA'}
  const resposta=()=>({
    caso:{id:'caso-qa',situacao:humano?'com_pessoa':'em_contato',identidade_confirmada:true},
    evento:enviado?{id:'evento-qa',situacao:retomadas||humano?'feito':'pendente',disponivel_em:new Date(Date.now()-1000).toISOString()}:null,
    mensagens:enviado?[{direcao:'entrada',texto:'Como funciona?',criado_em:new Date().toISOString()},...(retomadas&&!humano?[{direcao:'saida',texto:'Resposta recuperada após a espera técnica.',criado_em:new Date().toISOString()}]:[])]:[],
    passos:[],caderno:[],silencio:enviado?'O serviço de IA está temporariamente indisponível.':null,
  })
  await page.route('**/*',async route=>{
    const url=new URL(route.request().url());if(url.origin===address)return route.continue()
    if(url.origin!=='http://127.0.0.1:8001')return route.abort()
    let json={}
    if(url.pathname==='/auth/refresh')json={token:'qa',usuario}
    else if(url.pathname==='/empresa/config')json={nome_exibicao:'MIZAN QA'}
    else if(url.pathname==='/agenda/resumo')json={alto:0,medio:0}
    else if(url.pathname==='/agente/devedores')json={devedores:[{id:'p1',nome:'Cliente QA'}]}
    else if(url.pathname==='/agente/casos/p1/mensagem'){posts++;enviado=true;json=resposta()}
    else if(url.pathname==='/agente/casos/p1/retomar'){retomadas++;json=resposta()}
    else if(url.pathname==='/agente/casos/p1'){if(enviado)leituras++;json=resposta()}
    return route.fulfill({status:200,json})
  })
  await page.addInitScript(usuario=>{sessionStorage.setItem('mizan_token','qa');sessionStorage.setItem('mizan_user',JSON.stringify(usuario));localStorage.setItem('mizan_tema','dark')},usuario)
  await page.goto(address+'/agente?aba=conversas&caso=p1&nome=Cliente%20QA',{waitUntil:'domcontentloaded'})
  await page.getByLabel('Mensagem do devedor').fill('Como funciona?')
  await page.getByRole('button',{name:'Enviar',exact:true}).click()
  await page.getByRole('status').filter({hasText:'tentará responder novamente'}).waitFor()
  assert.equal(await page.getByText(/O agente não respondeu\./).count(),0,'Espera técnica não vira mensagem definitiva de falha')
  await page.getByText('Resposta recuperada após a espera técnica.',{exact:true}).waitFor({timeout:18000})
  assert.equal(posts,1,'Polling não pode reenviar a mensagem')
  assert.equal(retomadas,1,'REG-IA-OCUPADA-002: a conversa retoma a tentativa pronta')
  assert.ok(leituras>=2,'Resposta é atualizada automaticamente')
  humano=true;await page.reload({waitUntil:'domcontentloaded'})
  await page.getByRole('status').filter({hasText:'Este caso está com a equipe'}).waitFor()
  assert.equal(await page.getByText(/O agente não respondeu\./).count(),0,'Handoff legítimo tem indicação própria')
  await page.getByRole('button',{name:'Devolver ao agente',exact:true}).waitFor()
  assert.deepEqual(erros,[])
  console.log(JSON.stringify({ok:true,posts,retomadas,leituras,regressoes:['espera técnica','retomada automática','sem reenvio','controle humano preservado']}))
}finally{await browser.close();await server.close()}
