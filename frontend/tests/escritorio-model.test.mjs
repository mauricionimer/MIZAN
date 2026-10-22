import test from 'node:test'
import assert from 'node:assert/strict'
import { enquadrar, LIMITES_SALA, posicionarNomes } from '../src/components/escritorio/geometria.js'
import { ajustarNomeEmpresa, AZUL_MIZAN, PAREDES } from '../src/components/escritorio/marca.js'

test('REG-SIZE-002: ampliar a sala usando os limites desenhados e manter o zoom inteiro', () => {
  for(const [largura,altura] of [[956,730],[1190,730],[930,730]]){
    const c=enquadrar(largura,altura), b=LIMITES_SALA
    assert.equal(c.s,2)
    assert.ok(Number.isInteger(c.s))
    assert.ok(c.x+b.x*c.s>=0)
    assert.ok(c.x+(b.x+b.largura)*c.s<=largura)
    assert.ok(c.y+b.y*c.s>=0)
    assert.ok(c.y+(b.y+b.altura)*c.s<=altura)
  }
  assert.equal(enquadrar(320,460).s,1)
})
test('REG-NAMES-003: nomes longos e próximos não se sobrepõem nem saem da área', () => {
  const ps=['Acompanhamento','Orquestrador','Estrategista','Negociador'].map((nome,i)=>({nome,x:100+i*4,y:120,largura:120}))
  const nomes=posicionarNomes(ps,320,460)
  assert.equal(nomes.length,ps.length)
  for(let i=0;i<nomes.length;i++){
    const a=nomes[i]
    assert.ok(a.x>=0&&a.x+a.w<=320&&a.y>=0&&a.y+a.h<=460)
    for(const b of nomes.slice(i+1))assert.ok(a.x+a.w<=b.x||b.x+b.w<=a.x||a.y+a.h<=b.y||b.y+b.h<=a.y)
  }
  assert.equal(posicionarNomes([{nome:'Fora',x:-100,y:100,largura:60}],320,460).length,0)
})
test('REG-BRAND-004: manter Goiás Bank completo, incluindo o K e o acento', () => {
  const medir=(texto,fonte)=>[...texto].length*fonte*.6
  const nome=ajustarNomeEmpresa('Goiás Bank',medir)
  assert.equal(nome.linhas.join(' '),'Goiás Bank')
  assert.ok(nome.linhas.every(l=>medir(l,nome.fonte)<=320))
})
test('REG-BRAND-004: marcas extensas e palavras sem espaços cabem na placa', () => {
  const medir=(texto,fonte)=>[...texto].length*fonte*.65
  for(const empresa of ['WWK Crédito 2026','Cooperativa de Crédito e Investimentos do Estado de Goiás','X'.repeat(300)]){
    const a=ajustarNomeEmpresa(empresa,medir)
    assert.ok(a.linhas.length<=3)
    assert.ok(a.linhas.every(l=>medir(l,a.fonte)<=320))
    assert.ok(a.linhas.length*a.alturaLinha<=228)
  }
})
test('REG-COLOR-006: paredes usam o azul da marca MIZAN', () => {
  assert.equal(AZUL_MIZAN,'#5966d9')
  assert.equal(PAREDES.direita,AZUL_MIZAN)
})
