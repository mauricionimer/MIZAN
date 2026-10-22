export const AZUL_MIZAN = '#5966d9'
export const PAREDES = { esquerda: '#6875e2', direita: AZUL_MIZAN, rodapeEsquerdo: '#424da6', rodapeDireito: '#35418f' }

/** Ajuste por medição real da fonte, incluindo palavras sem espaços. */
export function ajustarNomeEmpresa(nome, medir, largura=320, altura=228) {
  const texto=String(nome||'MIZAN').normalize('NFC').trim().replace(/\s+/g,' ') || 'MIZAN'
  let linhas=[], fonte=52
  for(;fonte>=22;fonte--) {
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
    if(linhas.length<=3&&linhas.length*fonte*1.2<=altura)break
  }
  fonte=Math.max(22,fonte)
  if(linhas.length>3){linhas=linhas.slice(0,3);let ultima=linhas[2];while(ultima&&medir(ultima+'…',fonte)>largura)ultima=ultima.slice(0,-1);linhas[2]=ultima+'…'}
  return {texto,linhas,fonte,alturaLinha:Math.ceil(fonte*1.2)}
}
export function texturaNome(nome) {
  const cv=document.createElement('canvas');cv.width=320;cv.height=228
  const c=cv.getContext('2d')
  const medir=(t,f)=>{c.font=`600 ${f}px system-ui, sans-serif`;return c.measureText(t).width}
  const layout=ajustarNomeEmpresa(nome,medir)
  c.fillStyle='#25334b';c.font=`600 ${layout.fonte}px system-ui, sans-serif`;c.textBaseline='top'
  const topo=Math.floor((cv.height-layout.linhas.length*layout.alturaLinha)/2)
  layout.linhas.forEach((l,i)=>c.fillText(l,0,topo+i*layout.alturaLinha))
  return {canvas:cv,layout}
}
export function validarPlaca(nome) {
  const {canvas,layout}=texturaNome(nome),c=canvas.getContext('2d')
  c.font=`600 ${layout.fonte}px system-ui, sans-serif`
  return {...layout,cabe:layout.linhas.every(l=>c.measureText(l).width<=320)&&layout.linhas.length*layout.alturaLinha<=228}
}
