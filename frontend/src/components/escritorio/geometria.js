// O enquadramento considera a sala desenhada, sem as margens vazias do buffer.
export const LIMITES_SALA = { x: 30, y: 22, largura: 464, altura: 334 }
export function enquadrar(largura, altura) {
  const b = LIMITES_SALA
  const s = Math.max(1, Math.min(5, Math.floor(Math.min(largura / b.largura, altura / b.altura))))
  return { s, x: Math.round((largura - b.largura * s) / 2 - b.x * s), y: Math.round((altura - b.altura * s) / 2 - b.y * s) }
}

export function posicionarNomes(pontos, largura, altura) {
  const usados = [], resultado = []
  const colide = r => usados.some(a => r.x < a.x+a.w+3 && r.x+r.w+3 > a.x && r.y < a.y+a.h+3 && r.y+r.h+3 > a.y)
  for (const p of [...pontos].sort((a,b) => a.y-b.y || a.x-b.x)) {
    if(p.x < 0 || p.x > largura || p.y < 0 || p.y > altura-25) continue
    const w=p.largura, h=22, x=Math.round(Math.max(5,Math.min(largura-w-5,p.x-w/2)))
    let escolhido
    // Procura uma linha próxima do boneco sem encobrir outro nome.
    for(let k=0;k<30;k++) {
      const deslocamento=k===0?0:Math.ceil(k/2)*25*(k%2?1:-1)
      const r={x,y:Math.round(Math.max(5,Math.min(altura-h-34,p.y+5+deslocamento))),w,h}
      if(!colide(r)){escolhido=r;break}
    }
    if(escolhido){usados.push(escolhido);resultado.push({nome:p.nome,...escolhido})}
  }
  return resultado
}
