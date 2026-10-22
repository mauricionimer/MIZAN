import { useEffect, useRef, useState } from 'react'
import { AGENTES, MESAS, mensagem } from './config'
import { P, background, objects, avatar, assento, caminho, desenharNomeEmpresa } from './canvas'
import { enquadrar, posicionarNomes } from './geometria.js'
import { prepararNomeEmpresa } from './marca.js'

export default function SalaCanvas({ agentes, sinais, selecionado, onSelecionar, controle, seguir, nomeEmpresa, logoUrl, obsoleto, onManual }) {
  const area=useRef(null), canvas=useRef(null), dados=useRef({}), camera=useRef({s:1,x:0,y:0}), passeios=useRef(new Map())
  const vistos=useRef(null), [baloes,setBaloes]=useState([]), [hover,setHover]=useState(null)
  const etiquetas=useRef(new Map()), larguras=useRef(new Map())
  dados.current={agentes,selecionado,seguir,obsoleto,onManual}
  useEffect(()=>{
    if(!vistos.current){vistos.current=new Set(sinais.map(e=>e.id));return}
    const novos=sinais.filter(e=>e.id&&!vistos.current.has(e.id))
    sinais.forEach(e=>vistos.current.add(e.id))
    if(vistos.current.size>500)vistos.current=new Set(sinais.map(e=>e.id))
    const recentes=novos.filter(e=>Math.abs(Date.now()-new Date(e.t))<15000)
    if(recentes.length)setBaloes(b=>[...recentes.slice(0,3).map(e=>({id:e.id,msg:mensagem(e),nascimento:Date.now()})),...b].slice(0,3))
    if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches) for(const e of recentes.filter(e=>e.tipo==='handoff').reverse()) {
      const a=MESAS[e.de], b=MESAS[e.para]
      if(!a||!b||a.acc==='servico'||passeios.current.has(e.de))continue
      const rota=caminho(assento(a),b.acc==='servico'?[b.i+.5,b.j+1.5]:assento(b))
      if(rota.length)passeios.current.set(e.de,{rota:[...rota,...rota.slice(0,-1).reverse()],inicio:performance.now()})
    }
  },[sinais])
  useEffect(()=>{const t=setInterval(()=>setBaloes(b=>b.length?b.filter(x=>Date.now()-x.nascimento<6500):b),1000);return()=>clearInterval(t)},[])
  useEffect(()=>{
    const el=area.current, cv=canvas.current
    let vivo=true, frame, largura=0, altura=0, cache=background(nomeEmpresa), ultimo=0, drag=null
    const nomeLegivel=prepararNomeEmpresa(nomeEmpresa)
    const reduz=window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let pontos=[]
    const centrar=()=>{camera.current=enquadrar(largura,altura)}
    const resize=new ResizeObserver(([e])=>{
      largura=Math.floor(e.contentRect.width);altura=Math.floor(e.contentRect.height)
      cv.width=largura;cv.height=altura;centrar()
    })
    resize.observe(el)
    const img=logoUrl ? new Image() : null
    if(img){img.onload=()=>{if(vivo)cache=background(nomeEmpresa,img)};img.src=logoUrl}
    const context=cv.getContext('2d')
    const render=t=>{
      frame=requestAnimationFrame(render)
      if(document.hidden||t-ultimo<(reduz?200:33)||!largura)return
      ultimo=t
      let {s,x,y}=camera.current
      const ds=dados.current
      const atores=[]
      for(const a of ds.agentes || AGENTES){
        if(a.acc==='servico')continue
        let pos=assento(a),dir=0,andando=false
        const passeio=passeios.current.get(a.nome)
        if(passeio&&!ds.obsoleto){
          const idx=(t-passeio.inicio)/140, k=Math.floor(idx)
          if(k>=passeio.rota.length-1)passeios.current.delete(a.nome)
          else {const p=passeio.rota[k],q=passeio.rota[k+1],f=idx-k;pos=p.map((v,i)=>v+(q[i]-v)*f);dir=q[0]<p[0]?2:q[1]<p[1]?3:q[0]>p[0]?1:0;andando=true}
        }
        atores.push({...a,pos,dir,andando})
      }
      if(ds.seguir&&ds.selecionado){const a=atores.find(a=>a.nome===ds.selecionado);if(a){const p=P(...a.pos);x=Math.round(largura/2-p[0]*s);y=Math.round(altura/2-(p[1]-22)*s);camera.current={s,x,y}}}
      context.setTransform(1,0,0,1,0,0);context.fillStyle='#0d1318';context.fillRect(0,0,largura,altura)
      context.imageSmoothingEnabled=false; context.setTransform(s,0,0,s,x,y);context.drawImage(cache,0,0)
      desenharNomeEmpresa(context,nomeLegivel)
      const desenhos=objects(ds.agentes||AGENTES,reduz?0:t)
      for(const a of atores)desenhos.push({depth:a.pos[0]+a.pos[1]+.1,draw:c=>avatar(c,a,a.pos,reduz?0:t,ds.obsoleto?'desconhecido':a.status,a.dir,a.andando,a.nome===ds.selecionado)})
      desenhos.sort((a,b)=>a.depth-b.depth).forEach(o=>o.draw(context))
      pontos=(ds.agentes||AGENTES).map(a=>{
        const pos=atores.find(b=>b.nome===a.nome)?.pos || [a.i+.6,a.j+.5]
        const p=P(...pos)
        return {nome:a.nome,papel:a.papel,x:p[0]*s+x,y:p[1]*s+y,raio:a.acc==='servico'?22:14,altura:a.acc==='servico'?25:43}
      })
      const nomes=posicionarNomes(pontos.map(p=>{
        const el=etiquetas.current.get(p.nome), medida=el?.offsetWidth || larguras.current.get(p.nome) || p.nome.length*7+20
        larguras.current.set(p.nome,medida)
        return {...p,largura:medida}
      }),largura,altura)
      const visiveis=new Set(nomes.map(n=>n.nome))
      etiquetas.current.forEach((el,nome)=>{el.hidden=!visiveis.has(nome)})
      nomes.forEach(n=>{const el=etiquetas.current.get(n.nome);if(el)el.style.transform=`translate(${n.x}px,${n.y}px)`})
      cv.dataset.zoom=String(s)
    }
    const relativo=e=>{const r=cv.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top]}
    const hit=e=>{const [x,y]=relativo(e);return [...pontos].reverse().find(p=>Math.abs(x-p.x)<p.raio*camera.current.s && y<=p.y+5*camera.current.s && y>p.y-p.altura*camera.current.s)}
    const down=e=>{if(e.button!==0)return;drag={x:e.clientX,y:e.clientY,original:{...camera.current},moveu:false};cv.setPointerCapture(e.pointerId)}
    const move=e=>{
      if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y; if(Math.abs(dx)+Math.abs(dy)>5)drag.moveu=true
        if(drag.moveu){dados.current.onManual?.();camera.current={...drag.original,x:Math.round(drag.original.x+dx),y:Math.round(drag.original.y+dy)}}
      } else {const h=hit(e);cv.style.cursor=h?'pointer':'grab';setHover(h?{nome:h.nome,papel:h.papel}:null)}
    }
    const up=e=>{if(drag&&!drag.moveu){const h=hit(e);if(h)onSelecionar(h.nome)}drag=null;if(cv.hasPointerCapture(e.pointerId))cv.releasePointerCapture(e.pointerId)}
    const wheel=e=>{e.preventDefault();dados.current.onManual?.();const [px,py]=relativo(e),a=camera.current; const s=Math.max(1,Math.min(5,a.s+(e.deltaY<0?1:-1)));camera.current={s,x:Math.round(px-(px-a.x)*s/a.s),y:Math.round(py-(py-a.y)*s/a.s)}}
    cv.addEventListener('pointerdown',down);cv.addEventListener('pointermove',move);cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',up);cv.addEventListener('wheel',wheel,{passive:false})
    frame=requestAnimationFrame(render)
    return()=>{vivo=false;cancelAnimationFrame(frame);resize.disconnect();if(img)img.onload=null;cv.removeEventListener('pointerdown',down);cv.removeEventListener('pointermove',move);cv.removeEventListener('pointerup',up);cv.removeEventListener('pointercancel',up);cv.removeEventListener('wheel',wheel)}
  },[nomeEmpresa,logoUrl,onSelecionar])
  useEffect(()=>{
    if(!controle)return
    const r=area.current.getBoundingClientRect(), a=camera.current
    if(controle.tipo==='centrar'){camera.current=enquadrar(r.width,r.height)}
    else {const s=Math.max(1,Math.min(5,a.s+controle.delta));camera.current={s,x:Math.round(r.width/2-(r.width/2-a.x)*s/a.s),y:Math.round(r.height/2-(r.height/2-a.y)*s/a.s)}}
  },[controle])
  return <div className="ao-stage" ref={area}>
    <canvas ref={canvas} tabIndex={0} aria-label="Sala isométrica dos agentes. Selecione também pela lista. Arraste ou use as setas para mover; roda, mais e menos para ampliar." onPointerLeave={()=>setHover(null)} onKeyDown={e=>{
      const a=camera.current, passos={ArrowLeft:[20,0],ArrowRight:[-20,0],ArrowUp:[0,20],ArrowDown:[0,-20]}
      if(passos[e.key]){e.preventDefault();onManual?.();camera.current={...a,x:a.x+passos[e.key][0],y:a.y+passos[e.key][1]}}
      else if(['+','-','='].includes(e.key)){e.preventDefault();onManual?.();const r=area.current.getBoundingClientRect(),s=Math.max(1,Math.min(5,a.s+(e.key==='-'?-1:1)));camera.current={s,x:Math.round(r.width/2-(r.width/2-a.x)*s/a.s),y:Math.round(r.height/2-(r.height/2-a.y)*s/a.s)}}
    }}/>
    {agentes.map(a=><button type="button" key={a.nome} hidden ref={el=>el?etiquetas.current.set(a.nome,el):etiquetas.current.delete(a.nome)} className="ao-agent-label" style={{'--ao-agent':a.cor}} onClick={()=>onSelecionar(a.nome)} aria-pressed={selecionado===a.nome} title={`${a.nome} · ${a.papel}`}>{a.nome}</button>)}
    <div className="ao-bubbles" aria-live="polite">{baloes.map((b,i)=><div key={b.id} className="ao-bubble" style={{opacity:1-i*.25}}>{b.msg.slice(0,80)}</div>)}</div>
    <div className="ao-scene-caption">{hover ? `${hover.nome} · ${hover.papel}` : 'Arraste para explorar · Role para ampliar'}</div>
  </div>
}
