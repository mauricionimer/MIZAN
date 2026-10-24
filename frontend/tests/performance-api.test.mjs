import test from 'node:test'
import assert from 'node:assert/strict'
import { build } from 'esbuild'
import { readFileSync } from 'node:fs'
import { leituraEmCurso, invalidarLeiturasEmCurso } from '../src/lib/pedidosEmCurso.js'

test('fonte da marca continua no HTML sem import externo em cadeia no CSS', () => {
  const html=readFileSync(new URL('../index.html',import.meta.url),'utf8')
  const css=readFileSync(new URL('../src/index.css',import.meta.url),'utf8')
  assert.match(html,/fonts\.googleapis\.com\/css2\?family=Bricolage/)
  assert.doesNotMatch(css,/@import\s+url\(['"]https:\/\/fonts\.googleapis/)
})

test('leituras simultâneas compartilham trabalho, mas a próxima leitura é nova', async () => {
  let chamadas=0, liberar
  const executar=()=>{chamadas++;return new Promise(r=>{liberar=r})}
  const a=leituraEmCurso('a',executar), b=leituraEmCurso('a',executar)
  await Promise.resolve();assert.equal(chamadas,1)
  liberar(42);assert.deepEqual(await Promise.all([a,b]),[42,42])
  assert.equal(await leituraEmCurso('a',()=>99),99)
})

test('erro não fica memorizado e invalidação não apaga nova leitura', async () => {
  await assert.rejects(leituraEmCurso('erro',()=>Promise.reject(Error('offline'))))
  assert.equal(await leituraEmCurso('erro',()=>1),1)
  let fimAntigo, fimNovo
  const antigo=leituraEmCurso('k',()=>new Promise(r=>{fimAntigo=r}))
  await Promise.resolve();invalidarLeiturasEmCurso()
  const novo=leituraEmCurso('k',()=>new Promise(r=>{fimNovo=r}))
  await Promise.resolve();fimAntigo(1);await antigo
  assert.equal(leituraEmCurso('k',()=>{throw Error('duplicou')}),novo)
  fimNovo(2);await novo
})

test('API compartilha por token e parâmetros, sem atravessar escrita ou logout', async () => {
  const compilado=await build({entryPoints:[new URL('../src/api.js',import.meta.url).pathname.replace(/^\/(\w:)/,'$1')],
    bundle:true,write:false,format:'esm',platform:'node',define:{'import.meta.env.VITE_API_URL':'"https://qa.invalid"'}})
  const api=await import('data:text/javascript;base64,'+Buffer.from(compilado.outputFiles[0].text).toString('base64'))
  let token='a';globalThis.sessionStorage={getItem:()=>token,length:0}
  let chamadas=[]
  globalThis.fetch=(url,opcoes)=>new Promise(resolve=>chamadas.push({url,opcoes,resolve}))
  const concluir=i=>chamadas[i].resolve({status:200,ok:true,text:async()=>'{"alto":1}'})
  const a=api.resumoAgenda({escopo:'equipe'}), b=api.resumoAgenda({escopo:'equipe'})
  await Promise.resolve();assert.equal(chamadas.length,1)
  token='b';const c=api.resumoAgenda({escopo:'equipe'})
  await Promise.resolve();assert.equal(chamadas.length,2)
  assert.equal(chamadas[0].opcoes.headers.Authorization,'Bearer a')
  assert.equal(chamadas[1].opcoes.headers.Authorization,'Bearer b')
  const d=api.resumoAgenda({escopo:'minha'});await Promise.resolve();assert.equal(chamadas.length,3)
  const escrita=api.mudarAgenda('id','cumprir')
  assert.equal(chamadas.length,4);concluir(3);await escrita
  const nova=api.resumoAgenda({escopo:'equipe'});await Promise.resolve();assert.equal(chamadas.length,5)
  api.limparSessaoLocal()
  const aposLogout=api.resumoAgenda({escopo:'equipe'});await Promise.resolve();assert.equal(chamadas.length,6)
  for(const i of [0,1,2,4,5])concluir(i)
  await Promise.all([a,b,c,d,nova,aposLogout])
})
