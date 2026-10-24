import test from 'node:test'
import assert from 'node:assert/strict'
import { iniciarAtualizacaoVisivel } from '../src/lib/atualizacaoVisivel.js'

const resolver = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a; reject=b}); return {promise,resolve,reject} }
const flush = async () => { for(let i=0;i<10;i++) await Promise.resolve() }
function ambiente() {
  const documento = new EventTarget(), timers = new Map()
  documento.hidden=false
  let id=0
  return {
    documento, timers,
    agendar(fn) { timers.set(++id,fn); return id }, cancelar(id) { timers.delete(id) },
    async tick() { const fns=[...timers.values()]; timers.clear(); for(const fn of fns) void fn(); await flush() },
    ocultar(hidden) { documento.hidden=hidden; documento.dispatchEvent(new Event('visibilitychange')) },
  }
}

test('leitura lenta não acumula rodadas; pausa oculta e retoma uma vez', async () => {
  const a=ambiente(), p=resolver();let n=0
  const parar=iniciarAtualizacaoVisivel(()=>{ n++;return n===1?p.promise:Promise.resolve() },a)
  assert.equal(n,1);await a.tick();assert.equal(n,1)
  a.ocultar(true);a.ocultar(false);a.ocultar(false);assert.equal(n,1)
  p.resolve();await flush();assert.equal(a.timers.size,1)
  a.ocultar(true);assert.equal(a.timers.size,0);await a.tick();assert.equal(n,1)
  a.ocultar(false);await flush();assert.equal(n,2);assert.equal(a.timers.size,1)
  parar();assert.equal(a.timers.size,0);a.ocultar(false);assert.equal(n,2)
})

test('não começa oculta e desmontagem impede reagendamento após resposta tardia', async () => {
  const a=ambiente(),p=resolver();a.ocultar(true);let n=0
  const parar=iniciarAtualizacaoVisivel(()=>{n++;return p.promise},a)
  assert.equal(n,0);a.ocultar(false);assert.equal(n,1)
  parar();p.resolve();await flush();assert.equal(a.timers.size,0)
  a.ocultar(false);assert.equal(n,1)
})

test('para depois de três erros e permite nova tentativa ao voltar à aba', async () => {
  const a=ambiente();let n=0
  const parar=iniciarAtualizacaoVisivel(async()=>{n++;throw new Error('offline')},a)
  await flush();await a.tick();await a.tick();await a.tick()
  assert.equal(n,3);assert.equal(a.timers.size,0)
  a.ocultar(true);a.ocultar(false);await flush();assert.equal(n,4)
  parar()
})

test('sucesso zera erros consecutivos', async () => {
  const a=ambiente();let n=0
  const parar=iniciarAtualizacaoVisivel(async()=>{if(++n!==3)throw new Error('offline')},a)
  await flush();for(let i=0;i<4;i++)await a.tick()
  assert.equal(n,5);assert.equal(a.timers.size,1)
  await a.tick();assert.equal(n,6);assert.equal(a.timers.size,0);parar()
})
