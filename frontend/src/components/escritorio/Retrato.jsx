import { MESAS } from './config'
export default function Retrato({ nome, cor, tamanho = 48 }) {
  const a = MESAS[nome] || { pele: '#e8b48a', cabelo: '#374151' }
  const r = (x, y, w, h, fill) => <rect x={x} y={y} width={w} height={h} fill={fill} />
  return <svg viewBox="0 0 22 38" width={tamanho} height={tamanho * 38 / 22} shapeRendering="crispEdges" aria-hidden="true">
    {r(5, 20, 12, 16, '#172332')}{r(11, 29, 1, 7, '#090e16')}{r(4, 35, 6, 2, '#090e16')}{r(12, 35, 6, 2, '#090e16')}
    {r(3, 16, 16, 14, '#171d28')}{r(4, 17, 14, 12, a.acc === 'jaleco' ? '#e9ede5' : cor || a.cor)}
    {r(8, 15, 6, 4, a.pele)}{r(5, 3, 12, 13, '#171d28')}{r(6, 5, 10, 10, a.pele)}
    {r(5, 3, 12, 4, a.cabelo)}{r(5, 6, 2, 5, a.cabelo)}{r(8, 10, 1, 2, '#171d28')}{r(13, 10, 1, 2, '#171d28')}
    {a.acc === 'gravata' && <>{r(9, 18, 4, 2, '#fff')}{r(10, 20, 2, 7, '#9e3b38')}</>}
    {['oculos', 'jaleco'].includes(a.acc) && <>{r(7, 9, 4, 3, '#354052')}{r(12, 9, 4, 3, '#354052')}{r(10, 10, 3, 1, '#354052')}</>}
    {a.acc === 'headset' && <>{r(4, 6, 2, 7, '#344055')}{r(4, 12, 5, 1, '#344055')}</>}
  </svg>
}
