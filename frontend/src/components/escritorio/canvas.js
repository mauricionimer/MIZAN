import { AGENTES } from './config'
import { PAREDES, texturaNome } from './marca.js'

export const W = 544, H = 380
export const P = (x, y, z = 0) => [240 + (x - y) * 16, 110 + (x + y) * 8 - z]
const ink = '#242b2e'
const rounded = p => p.map(Math.round)

// Rasterização explícita: nem diagonais nem polígonos dependem de antialiasing.
export function line(c, a, b, cor = ink) {
  let [x, y] = rounded(a), [tx, ty] = rounded(b)
  const dx = Math.abs(tx-x), dy = -Math.abs(ty-y), sx = x < tx ? 1 : -1, sy = y < ty ? 1 : -1
  let erro = dx+dy
  c.fillStyle = cor
  for (;;) {
    c.fillRect(x, y, 1, 1)
    if (x === tx && y === ty) break
    const e = 2*erro
    if (e >= dy) { erro += dy; x += sx }
    if (e <= dx) { erro += dx; y += sy }
  }
}
export function poly(c, pontos, cor, borda = ink) {
  const ps = pontos.map(rounded), ys = ps.map(p => p[1])
  c.fillStyle = cor
  for (let y = Math.min(...ys); y <= Math.max(...ys); y++) {
    const xs = []
    ps.forEach(([x1,y1], i) => {
      const [x2,y2] = ps[(i+1)%ps.length]
      if ((y1 <= y && y2 > y) || (y2 <= y && y1 > y)) xs.push(x1+(y-y1)*(x2-x1)/(y2-y1))
    })
    xs.sort((a,b)=>a-b)
    for (let i=0; i<xs.length; i+=2) c.fillRect(Math.ceil(xs[i]), y, Math.floor(xs[i+1])-Math.ceil(xs[i])+1, 1)
  }
  if (borda) ps.forEach((p,i)=>line(c,p,ps[(i+1)%ps.length],borda))
}
export function box(c, x, y, w, d, h, topo, esq, dir, z = 0) {
  const a=P(x,y,z), b=P(x+w,y,z), e=P(x,y+d,z), f=P(x+w,y+d,z)
  const up = p => [p[0],p[1]-h]
  poly(c,[e,f,up(f),up(e)],esq)
  poly(c,[f,b,up(b),up(f)],dir)
  poly(c,[up(a),up(b),up(f),up(e)],topo)
}
const letras = {
 A:['01110','10001','10001','11111','10001','10001','10001'], B:['11110','10001','10001','11110','10001','10001','11110'],
 C:['01111','10000','10000','10000','10000','10000','01111'], D:['11110','10001','10001','10001','10001','10001','11110'],
 E:['11111','10000','10000','11110','10000','10000','11111'], F:['11111','10000','10000','11110','10000','10000','10000'],
 G:['01111','10000','10000','10111','10001','10001','01110'], H:['10001','10001','10001','11111','10001','10001','10001'],
  I:['111','010','010','010','010','010','111'], J:['00111','00010','00010','00010','10010','10010','01100'], K:['10001','10010','10100','11000','10100','10010','10001'],
 L:['10000','10000','10000','10000','10000','10000','11111'], M:['10001','11011','10101','10101','10001','10001','10001'],
 N:['10001','11001','11001','10101','10011','10011','10001'], O:['01110','10001','10001','10001','10001','10001','01110'],
 P:['11110','10001','10001','11110','10000','10000','10000'], Q:['01110','10001','10001','10001','10101','10010','01101'],
 R:['11110','10001','10001','11110','10100','10010','10001'], S:['01111','10000','10000','01110','00001','00001','11110'],
 T:['11111','00100','00100','00100','00100','00100','00100'], U:['10001','10001','10001','10001','10001','10001','01110'],
  V:['10001','10001','10001','10001','10001','01010','00100'], W:['10001','10001','10001','10101','10101','11011','10001'], X:['10001','10001','01010','00100','01010','10001','10001'],
 Y:['10001','10001','01010','00100','00100','00100','00100'], Z:['11111','00001','00010','00100','01000','10000','11111'],
}
export function pixelText(c, texto, x, y, cor = '#f5eee4') {
  c.fillStyle=cor
  for (const char of texto.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase()) {
    const gl=letras[char]
    if (gl) gl.forEach((row,j)=>[...row].forEach((v,i)=>{if(v==='1')c.fillRect(Math.round(x+i),Math.round(y+j),1,1)}))
    x+=(gl?.[0].length||3)+1
  }
}
function placa(c, nome, x, y) {
  c.fillStyle='#362e29dd'; c.fillRect(x-4,y-3,nome.length*6+6,13)
  pixelText(c,nome,x,y,'#f0d3a4')
}
function janela(c, y) {
  poly(c,[P(0,y,73),P(0,y+2,73),P(0,y+2,29),P(0,y,29)],'#e8e9dc')
  poly(c,[P(0,y+.13,70),P(0,y+1.87,70),P(0,y+1.87,32),P(0,y+.13,32)],'#9bd0e2','#f5f0da')
  line(c,P(0,y+1,71),P(0,y+1,31),'#f8f5eb')
  line(c,P(0,y+.1,49),P(0,y+1.9,49),'#f8f5eb')
  line(c,P(0,y+.35,65),P(0,y+.75,37),'#cfedf1')
}
export function background(nomeEmpresa, logo) {
  const cv=document.createElement('canvas'); cv.width=W; cv.height=H
  const c=cv.getContext('2d'); c.imageSmoothingEnabled=false
  box(c,0,0,15.6,13,9,'#b5835a','#78563e','#624532',-2)
  poly(c,[P(0,0),P(15.6,0),P(15.6,13),P(0,13)],'#b5835a')
  for(let x=0;x<=15.6;x+=1/3) {
    line(c,P(x,0),P(x,13),'#a67652')
    for(let y=(Math.round(x*3)%3);y<13;y+=3) line(c,P(x,y),P(Math.min(x+1/3,15.6),y),'#8f6549')
  }
  poly(c,[P(0,13),P(0,0),P(0,0,84),P(0,13,84)],PAREDES.esquerda)
  poly(c,[P(0,0),P(15.6,0),P(15.6,0,84),P(0,0,84)],PAREDES.direita)
  poly(c,[P(0,13),P(0,0),P(0,0,5),P(0,13,5)],PAREDES.rodapeEsquerdo)
  poly(c,[P(0,0),P(15.6,0),P(15.6,0,5),P(0,0,5)],PAREDES.rodapeDireito)
  for(const y of [1.4,4.2,7.2,10]) janela(c,y)
  // Mural de cortiça e papéis presos na parede direita.
  poly(c,[P(7,0,72),P(10.3,0,72),P(10.3,0,34),P(7,0,34)],'#8a603b')
  for(let x=7.2;x<10;x+=.9) for(const z of [43,59]) {
    poly(c,[P(x,0,z+9),P(x+.65,0,z+9),P(x+.65,0,z),P(x,0,z)],'#f6eee0','#d0b486')
    line(c,P(x+.1,0,z+5),P(x+.52,0,z+5),'#a9b0a8')
  }
  const placaEmpresa=[P(10.9,0,76),P(15.3,0,76),P(15.3,0,30),P(10.9,0,30)]
  poly(c,placaEmpresa,'#f4f0df','#374594')
  c.save();c.beginPath();placaEmpresa.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.closePath();c.clip()
  const [lx,ly]=P(11.1,0,72)
  c.save(); c.setTransform(1,.5,0,1,lx,ly)
  if (logo) {const escala=Math.min(18/logo.width,18/logo.height);c.drawImage(logo,0,10+(18-logo.height*escala)/2,logo.width*escala,logo.height*escala)}
  else { c.fillStyle='#5966d9'; c.fillRect(1,22,4,10); c.fillRect(7,16,4,16); c.fillRect(13,10,4,22) }
  const nome=texturaNome(nomeEmpresa).canvas
  c.drawImage(nome,22,0,40,38);c.restore();c.restore()
  placa(c,'ATENDIMENTO',180,174); placa(c,'ESTRATEGIA',312,239)
  placa(c,'ACOMPANHAMENTO',62,214); placa(c,'COORDENACAO',190,294)
  return cv
}
function planta(c,x,y) {
  box(c,x,y,.55,.55,8,'#b87d4d','#97603a','#76482e')
  const [px,py]=P(x+.28,y+.28,8)
  c.fillStyle='#245e30'; c.fillRect(px-5,py-21,10,20); c.fillRect(px-10,py-13,20,9)
  c.fillStyle='#3d9a3d'; c.fillRect(px-3,py-24,6,12);c.fillRect(px-9,py-16,7,10);c.fillRect(px+2,py-11,7,10)
  c.fillStyle='#65b44a';c.fillRect(px-2,py-23,2,9);c.fillRect(px-8,py-15,2,5)
}
function vidro(c,x1,y1,x2,y2) {
  poly(c,[P(x1,y1),P(x2,y2),P(x2,y2,35),P(x1,y1,35)],'#b2d5df48','#c3cdd2')
  const n=Math.max(1,Math.ceil(Math.hypot(x2-x1,y2-y1)/1.5))
  for(let i=0;i<=n;i++) line(c,P(x1+(x2-x1)*i/n,y1+(y2-y1)*i/n),P(x1+(x2-x1)*i/n,y1+(y2-y1)*i/n,35),'#d8dde3')
  line(c,P(x1,y1,36),P(x2,y2,36),'#edf0ed')
}
function mesa(c,a,estado,t) {
  const {i:x,j:y,cor}=a
  if(a.acc==='servico') {
    box(c,x,y,1.2,.7,18,a.nome==='Travas'?'#dba2bc':'#98b2aa','#657c78','#465f60')
    box(c,x+.2,y+.12,.65,.3,8,'#273940','#273039','#17242a',18)
    const p=P(x+.5,y+.15,23);c.fillStyle=cor;c.fillRect(p[0]-2,p[1]-2,4,4)
    return
  }
  // Cadeira, pés da mesa e tampo de madeira.
  box(c,x+.65,y+1.25,.65,.6,4,'#46515a','#303943','#202a33',5)
  box(c,x+.65,y+1.65,.65,.15,14,'#57616a','#414a54','#2e3844',7)
  box(c,x+.08,y+.1,.12,.65,17,'#9b7753','#806044','#5c4735')
  box(c,x+1.8,y+.1,.12,.65,17,'#9b7753','#806044','#5c4735')
  box(c,x,y,2,1,3,'#d7ba8e','#ad8860','#97704f',17)
  box(c,x+.65,y+.25,.65,.08,4,'#677078','#46505a','#303b44',20)
  const monitor=[P(x+.35,y+.17,42),P(x+1.6,y+.17,42),P(x+1.6,y+.17,25),P(x+.35,y+.17,25)]
  poly(c,monitor,'#18252d','#707e83')
  const ativo=['trabalhando','pensando'].includes(estado)
  for(let z=29;z<39;z+=3) line(c,P(x+.48,y+.17,z),P(x+(ativo ? .95+(Math.floor(t/350+z)%4)*.12 : 1.25),y+.17,z),ativo?'#70c5b3':'#455b66')
  poly(c,[P(x+.5,y+.65,21),P(x+1.35,y+.65,21),P(x+1.35,y+.85,21),P(x+.5,y+.85,21)],'#ced2cb','#718083')
  box(c,x+1.65,y+.55,.2,.22,5,cor,cor,'#465058',20)
}
export const assento = a => [a.i+1, a.j+1.55]
export function avatar(c,a,pos,t,estado,direcao=0,andando=false,selecionado=false) {
  const [px,py]=P(...pos), x=Math.round(px),y=Math.round(py)
  const frame=Math.floor(t/150)%4, mexe=andando ? [0,1,0,-1][frame] : 0
  const r=(dx,dy,w,h,cor)=>{c.fillStyle=cor;c.fillRect(x+(direcao%2 ? -dx-w : dx),y+dy,w,h)}
  r(-7,-2,14,3,'#26303866')
  if(selecionado){line(c,[x-10,y+2],[x,y+7],'#f9d569');line(c,[x,y+7],[x+10,y+2],'#f9d569')}
  r(-5,-15,5,14,ink);r(0,-15,5,14,ink)
  r(-4,-14,3,11+mexe,'#344557');r(1,-14,3,11-mexe,'#415266')
  r(-5,-2+mexe,5,2,'#111c25');r(0,-2-mexe,5,2,'#111c25')
  r(-8,-28,16,15,ink);r(-7,-27,14,13,a.acc==='jaleco'?'#e3e8df':a.cor)
  const digitando=estado==='trabalhando' ? Math.floor(t/230)%2 : 0
  r(-8,-24,3,7,a.cor);r(5,-24,3,7,a.cor);r(-8,-17-digitando,3,3,a.pele);r(5,-17+digitando,3,3,a.pele)
  r(-3,-29,6,4,a.pele);r(-6,-41,12,13,ink);r(-5,-40,10,11,a.pele)
  r(-6,-41,12,4,a.cabelo);r(-6,-38,2,6,a.cabelo)
  if(direcao<2){r(-3,-34,1,2,ink);r(2,-34,1,2,ink);r(-1,-30,3,1,'#a77553')}
  else r(-5,-39,10,9,a.cabelo)
  if(['oculos','jaleco'].includes(a.acc)&&direcao<2){r(-4,-35,4,3,'#354052');r(1,-35,4,3,'#354052');r(0,-34,1,1,'#354052')}
  if(a.acc==='headset'){r(-7,-37,2,7,'#344055');r(-7,-31,5,1,'#344055')}
  if(a.acc==='gravata'){r(-2,-26,4,2,'#f4f1e4');r(-1,-24,2,7,'#a33e38')}
  if(estado==='pensando'||estado==='trabalhando') {
    const dy=Math.floor(t/700)%2
    r(-7,-57+dy,14,11,ink);r(-6,-56+dy,12,9,'#f6f5e9');r(-1,-46+dy,3,2,'#f6f5e9')
    if(estado==='pensando') for(let k=0;k<3;k++)r(-4+k*3,-52+dy,2,2,k<=Math.floor(t/300)%3?'#3b7dd8':'#bfc9d2')
    else {r(-3,-54+dy,6,6,'#2e9e44');r(-1,-52+dy,2,2,'#f6f5e9')}
  }
  if(selecionado){const dy=Math.floor(t/450)%2;poly(c,[[x-4,y-67+dy],[x+4,y-67+dy],[x,y-62+dy]],'#f9d569')}
}

export function objects(views,t,clock) {
  const out=views.map(a=>({depth:a.i+a.j+1,draw:c=>mesa(c,a,a.status,t)}))
  for(const [x,y] of [[.5,.5],[6.1,.7],[15,.6],[.6,6.5],[7.9,7],[15,12]]) out.push({depth:x+y+.5,draw:c=>planta(c,x,y)})
  for(const g of [[0,5.8,4.4,5.8],[6,5.8,11,5.8],[12.5,5.8,15.6,5.8],[7.1,0,7.1,3.8],[7.1,5,7.1,5.8],[4.4,7.3,4.4,10],[4.4,11.5,4.4,13]]) out.push({depth:g[0]+g[1]+.1,draw:c=>vidro(c,...g)})
  // Arquivo, rack, impressora, café, bebedouro, sofá e mesa de reunião.
  out.push({depth:8.5,draw:c=>{
    box(c,5.4,.5,1,.7,33,'#9da8a8','#778285','#555f65')
    for(let z=5;z<31;z+=7)line(c,P(5.45,1.21,z),P(6.3,1.21,z),'#3b4850')
    box(c,6.5,.6,.5,.6,34,'#45505a','#35404b','#202c36')
    const p=P(6.65,1.21,28);c.fillStyle=Math.floor(t/900)%2?'#62ba87':'#4b806a';c.fillRect(p[0],p[1],2,2)
  }})
  out.push({depth:16,draw:c=>{
    box(c,.6,11.8,1.2,.6,16,'#a88968','#897052','#67543f')
    box(c,.8,11.9,.6,.35,12,'#d1d4c8','#a1a89f','#717b78',16)
    const p=P(1.1,12.1,29);c.fillStyle='#27414b';c.fillRect(p[0]-3,p[1]-3,6,4)
  }})
  out.push({depth:21,draw:c=>{
    box(c,7.2,11,1.4,.75,14,'#af8d67','#8c6d4d','#705637')
    box(c,7.35,11.1,.4,.4,12,'#c4c7ba','#646f71','#3b484f',14)
    box(c,8,11.1,.3,.3,5,'#ebe7d8','#b3b5a6','#7f8a83',14)
    box(c,8.9,11.4,.45,.45,18,'#e8e9e1','#bdc9c9','#8ba2a6')
    box(c,9,11.45,.25,.3,12,'#a4dce5','#83bdcb','#649ba8',18)
  }})
  out.push({depth:22.5,draw:c=>{
    box(c,10.2,11.4,2,.6,8,'#716d91','#545372','#403f5b')
    box(c,10.2,11.4,2,.13,13,'#8580a3','#666486','#51506f',8)
    box(c,11,12.25,1.5,.55,6,'#e9dfbf','#cbbd98','#b0a586')
  }})
  out.push({depth:-1,draw:c=>{
    const p=P(5.5,0,58); const [x,y]=p
    poly(c,[[x-8,y-14],[x+6,y-7],[x+8,y+4],[x+2,y+12],[x-7,y+6],[x-10,y-4]],'#f1ead5')
    const hr=clock.getHours()%12, mn=clock.getMinutes()
    line(c,[x,y],[x+Math.sin(mn*Math.PI/30)*6,y-Math.cos(mn*Math.PI/30)*7],'#283442')
    line(c,[x,y],[x+Math.sin(hr*Math.PI/6)*4,y-Math.cos(hr*Math.PI/6)*4],'#283442')
  }})
  return out
}

// Grade em meios de tile; impede cortar diagonalmente quinas de móveis/vidros.
const obstaculos = new Set()
for(const a of AGENTES) for(let x=Math.floor(a.i*2);x<Math.ceil((a.i+(a.acc==='servico'?1.2:2))*2);x++) for(let y=Math.floor(a.j*2);y<Math.ceil((a.j+1)*2);y++)obstaculos.add(`${x},${y}`)
for(const [x1,y1,x2,y2] of [[0,5.8,4.4,5.8],[6,5.8,11,5.8],[12.5,5.8,15.6,5.8],[7.1,0,7.1,3.8],[7.1,5,7.1,5.8],[4.4,7.3,4.4,10],[4.4,11.5,4.4,13]]) {
  const n=Math.ceil(Math.hypot(x2-x1,y2-y1)*3)
  for(let k=0;k<=n;k++)obstaculos.add(`${Math.round((x1+(x2-x1)*k/n)*2)},${Math.round((y1+(y2-y1)*k/n)*2)}`)
}
export function caminho(de, para) {
  const ini=de.map(x=>Math.round(x*2)), fim=para.map(x=>Math.round(x*2)), key=p=>p.join(',')
  const fila=[ini], pais=new Map([[key(ini),null]])
  const livre=(x,y)=>x>=0&&x<32&&y>=0&&y<26&&!obstaculos.has(`${x},${y}`)
  for(let i=0;i<fila.length;i++) {
    const p=fila[i]
    if(key(p)===key(fim)) { const out=[];let v=p;while(v){out.unshift(v.map(x=>x/2));v=pais.get(key(v))}return out }
    for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]) {
      const q=[p[0]+dx,p[1]+dy]
      if(!livre(...q)||pais.has(key(q))||(dx&&dy&&(!livre(p[0]+dx,p[1])||!livre(p[0],p[1]+dy))))continue
      pais.set(key(q),p);fila.push(q)
    }
  }
  return []
}
