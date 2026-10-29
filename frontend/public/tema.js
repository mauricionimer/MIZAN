// Aplica o tema salvo antes da primeira pintura, senão a página pisca no tema
// errado enquanto o React monta. Três estados: sem preferência salva, nenhum
// atributo é escrito e o CSS segue o tema do sistema.
// Arquivo à parte (e não <script> embutido no index.html) para o CSP poder
// proibir script embutido: ver vercel.json.
(function () {
  try {
    var t = localStorage.getItem('mizan_tema');
    if (t === 'dark' || t === 'light') {
      document.documentElement.setAttribute('data-theme', t);
    }
  } catch (e) { /* modo privativo: segue o sistema */ }
})();
