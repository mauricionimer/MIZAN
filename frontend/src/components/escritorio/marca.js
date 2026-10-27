export const AZUL_MIZAN = '#5966d9'
export const PAREDES = { esquerda: '#6875e2', direita: AZUL_MIZAN, rodapeEsquerdo: '#424da6', rodapeDireito: '#35418f' }

/** Ajuste por medição real da fonte, incluindo palavras sem espaços. */
export function ajustarNomeEmpresa(nome, medir, largura=320, altura=228, {maxFonte=52,minFonte=22,maxLinhas=3}={}) {
  const texto=String(nome||'MIZAN').normalize('NFC').trim().replace(/\s+/g,' ') || 'MIZAN'
  let linhas=[], fonte=maxFonte
  for(;fonte>=minFonte;fonte--) {
    linhas=['']
    for(const palavra of texto.split(' ')) {
      const i=linhas.length-1, candidato=linhas[i]?`${linhas[i]} ${palavra}`:palavra
      if(medir(candidato,fonte)<=largura)linhas[i]=candidato
      else if(medir(palavra,fonte)<=largura){if(linhas[i])linhas.push(palavra);else linhas[i]=palavra}
      else {
        if(linhas[i])linhas.push('')
        for(const char of palavra){const k=linhas.length-1;if(medir(linhas[k]+char,fonte)>largura&&linhas[k])linhas.push(char);else linhas[k]+=char}
      }
    }
    if(linhas.length<=maxLinhas&&linhas.length*Math.ceil(fonte*1.2)<=altura)break
  }
  fonte=Math.max(minFonte,fonte)
  if(linhas.length>maxLinhas){linhas=linhas.slice(0,maxLinhas);let ultima=linhas[maxLinhas-1];while(ultima&&medir(ultima+'…',fonte)>largura)ultima=ultima.slice(0,-1);linhas[maxLinhas-1]=ultima+'…'}
  return {texto,linhas,fonte,alturaLinha:Math.ceil(fonte*1.2)}
}
export function prepararNomeEmpresa(nome) {
  const c=document.createElement('canvas').getContext('2d')
  const medir=(t,f)=>{c.font=`700 ${f}px system-ui, sans-serif`;return c.measureText(t).width}
  return ajustarNomeEmpresa(nome,medir,40,38,{maxFonte:11,minFonte:6,maxLinhas:3})
}
export function validarPlaca(nome) {
  const layout=prepararNomeEmpresa(nome),c=document.createElement('canvas').getContext('2d')
  c.font=`700 ${layout.fonte}px system-ui, sans-serif`
  return {...layout,cabe:layout.linhas.every(l=>c.measureText(l).width<=40)&&layout.linhas.length*layout.alturaLinha<=38}
}
