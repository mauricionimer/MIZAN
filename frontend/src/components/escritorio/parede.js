// Geometria compartilhada pelo desenho e pelos testes de contenção do mural.
export const MURAL = { esquerda: 7, direita: 10.3, baixo: 34, alto: 72 }
export const FOLHAS_MURAL = [7.25, 8.25, 9.25].flatMap(x => [43, 59].map(z => ({ x, z, largura: .65, altura: 9 })))
export const PLACA = { esquerda: 10.9, direita: 15.3, baixo: 30, alto: 76, x: 11.1, z: 72, textoX: 22, textoY: 1, largura: 40, altura: 38 }
