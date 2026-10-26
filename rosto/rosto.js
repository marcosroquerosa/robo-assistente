/*
  ROSTO DO ROBÔ (roda no navegador do celular)
  ============================================
  1. Desenha os olhos e anima conforme o estado do robô.
  2. Pega o som do microfone e manda para o computador.
  3. Recebe a fala do robô (áudio) e toca no alto-falante.
  4. Mostra legendas do que foi dito.

  Escrito em JavaScript simples, para funcionar até em celulares antigos.
*/

var TAXA = 16000;              // o computador espera 16 mil amostras por segundo
var NOMES_DOS_ESTADOS = {
  desligado: "desligado",
  dormindo: "dormindo: diga \"ei robô\" ou toque na tela",
  ouvindo: "ouvindo...",
  pensando: "pensando...",
  falando: "falando"
};

var conexao = null;            // a ligação com o computador (WebSocket)
var somCtx = null;             // o "motor de som" do navegador
var analisador = null;         // mede o volume da fala (para mexer a boca)
var estado = "desligado";
var ligado = false;
var filaDeAudio = [];          // frases esperando para tocar
var tocando = false;
var fimDaFala = false;

// ---------------- conexão com o computador ----------------
function conectar() {
  var endereco = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
  conexao = new WebSocket(endereco);
  conexao.binaryType = "arraybuffer";
  conexao.onopen = function () { aviso(""); };
  conexao.onclose = function () {
    aviso("sem conexão com o computador... tentando de novo");
    mudarEstado("desligado");
    setTimeout(conectar, 2000);
  };
  conexao.onmessage = receber;
}

function enviar(mensagem) {
  if (conexao && conexao.readyState === 1) conexao.send(JSON.stringify(mensagem));
}

function receber(evento) {
  if (typeof evento.data !== "string") {
    // chegou áudio: coloca na fila para tocar
    filaDeAudio.push(evento.data);
    if (!tocando) tocarProxima();
    return;
  }
  var m = JSON.parse(evento.data);
  if (m.tipo === "estado") mudarEstado(m.estado);
  else if (m.tipo === "legenda") legenda(m.quem, m.texto);
  else if (m.tipo === "fim_da_fala") {
    fimDaFala = true;
    if (!tocando && filaDeAudio.length === 0) avisarQueTerminou();
  }
}

function avisarQueTerminou() {
  fimDaFala = false;
  enviar({ tipo: "terminei_de_falar" });
}

// ---------------- tocar a fala ----------------
function tocarProxima() {
  if (filaDeAudio.length === 0) {
    tocando = false;
    if (fimDaFala) avisarQueTerminou();
    return;
  }
  tocando = true;
  var dados = filaDeAudio.shift();
  somCtx.decodeAudioData(dados, function (som) {
    var fonte = somCtx.createBufferSource();
    fonte.buffer = som;
    fonte.connect(analisador);
    fonte.onended = tocarProxima;
    fonte.start();
  }, function () { tocarProxima(); });
}

// ---------------- microfone ----------------
function ligarMicrofone() {
  var pedido = { audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } };
  navigator.mediaDevices.getUserMedia(pedido).then(function (fluxo) {
    var entrada = somCtx.createMediaStreamSource(fluxo);
    var processador = somCtx.createScriptProcessor(4096, 1, 1);
    processador.onaudioprocess = function (e) {
      if (!conexao || conexao.readyState !== 1) return;
      if (document.visibilityState !== "visible") return; // aba escondida não manda som
      if (tocando || estado === "pensando" || estado === "falando") return; // não escuta a si mesmo
      conexao.send(converterPara16k(e.inputBuffer.getChannelData(0), somCtx.sampleRate));
    };
    entrada.connect(processador);
    processador.connect(somCtx.destination); // necessário para o Chrome processar o som
  }).catch(function (erro) {
    aviso("não consegui usar o microfone: " + erro.name);
  });
}

// O celular grava com 44 ou 48 mil amostras por segundo; o computador quer 16 mil.
// Aqui fazemos a média de cada grupinho de amostras e convertemos para números inteiros.
function converterPara16k(amostras, taxaOriginal) {
  var razao = taxaOriginal / TAXA;
  var tamanho = Math.floor(amostras.length / razao);
  var saida = new Int16Array(tamanho);
  for (var i = 0; i < tamanho; i++) {
    var ini = Math.floor(i * razao), fim = Math.floor((i + 1) * razao), soma = 0;
    for (var j = ini; j < fim; j++) soma += amostras[j];
    var valor = soma / Math.max(1, fim - ini);
    valor = Math.max(-1, Math.min(1, valor));
    saida[i] = valor < 0 ? valor * 32768 : valor * 32767;
  }
  return saida.buffer;
}

// ---------------- ligar tudo com um toque ----------------
var telaAcordada = null;
function manterTelaLigada() {
  if ("wakeLock" in navigator) {
    navigator.wakeLock.request("screen").then(function (t) { telaAcordada = t; }).catch(function () {});
  }
}

function ligar() {
  ligado = true;
  document.getElementById("inicio").style.display = "none";
  var Contexto = window.AudioContext || window.webkitAudioContext;
  somCtx = new Contexto();
  analisador = somCtx.createAnalyser();
  analisador.fftSize = 512;
  analisador.connect(somCtx.destination);
  ligarMicrofone();
  manterTelaLigada();
  var el = document.documentElement;
  if (el.requestFullscreen) {
    var pedido = el.requestFullscreen();
    if (pedido && pedido.catch) pedido.catch(function () {});
  }
}

document.addEventListener("visibilitychange", function () {
  if (document.visibilityState === "visible" && ligado) {
    manterTelaLigada();
    enviar({ tipo: "visivel" }); // avisa o robô que esta é a aba que está na tela
  }
});

document.body.addEventListener("click", function () {
  if (!ligado) { ligar(); return; }
  if (somCtx && somCtx.state === "suspended") somCtx.resume();
  enviar({ tipo: "tocar" }); // tocar na tela acorda o robô
});

// ---------------- textos na tela ----------------
function mudarEstado(novo) {
  estado = novo;
  document.getElementById("situacao").textContent = NOMES_DOS_ESTADOS[novo] || novo;
  if (novo === "ouvindo") legenda("robo", "");
}

function legenda(quem, texto) {
  if (quem === "pessoa") {
    document.getElementById("legenda-pessoa").textContent = texto ? "Você: " + texto : "";
    document.getElementById("legenda-robo").textContent = "";
  } else {
    var caixa = document.getElementById("legenda-robo");
    caixa.textContent = texto ? (caixa.textContent ? caixa.textContent + " " : "") + texto : "";
  }
}

function aviso(texto) { document.getElementById("aviso").textContent = texto; }

// ---------------- os olhos ----------------
var tela = document.getElementById("olhos");
var g = tela.getContext("2d");
var olho = { altura: 0.1, olharX: 0, olharY: 0, boca: 0 };   // valores atuais (suavizados)
var proximaPiscada = Date.now() + 3000;

function ajustarTamanho() {
  tela.width = window.innerWidth * (window.devicePixelRatio || 1);
  tela.height = window.innerHeight * (window.devicePixelRatio || 1);
}
window.addEventListener("resize", ajustarTamanho);
ajustarTamanho();

function retanguloArredondado(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
  g.fill();
}

function volumeDaFala() {
  if (!analisador || !tocando) return 0;
  var dados = new Uint8Array(analisador.fftSize);
  analisador.getByteTimeDomainData(dados);
  var soma = 0;
  for (var i = 0; i < dados.length; i++) { var v = (dados[i] - 128) / 128; soma += v * v; }
  return Math.min(1, Math.sqrt(soma / dados.length) * 4);
}

function desenhar() {
  var W = tela.width, H = tela.height, agora = Date.now();
  var base = Math.min(W, H);

  // Como os olhos devem ficar em cada estado
  var alvo = { altura: 1, olharX: 0, olharY: 0, cor: "#5dcaa5" };
  if (estado === "desligado") { alvo.altura = 0.08; alvo.cor = "#2a3a40"; }
  if (estado === "dormindo") { alvo.altura = 0.1; alvo.cor = "#3f8f78"; }
  if (estado === "ouvindo") { alvo.altura = 1.15; }
  if (estado === "pensando") { alvo.altura = 0.75; alvo.olharX = 0.35; alvo.olharY = -0.35; alvo.cor = "#ef9f27"; }

  // Piscar de vez em quando
  if (estado !== "dormindo" && estado !== "desligado") {
    if (agora > proximaPiscada) {
      alvo.altura = 0.05;
      if (agora > proximaPiscada + 140) proximaPiscada = agora + 2500 + Math.random() * 3500;
    }
  }

  // Movimento suave até o alvo
  olho.altura += (alvo.altura - olho.altura) * 0.25;
  olho.olharX += (alvo.olharX - olho.olharX) * 0.1;
  olho.olharY += (alvo.olharY - olho.olharY) * 0.1;
  olho.boca += (volumeDaFala() - olho.boca) * 0.4;

  g.clearRect(0, 0, W, H);
  g.fillStyle = alvo.cor;

  var largura = base * 0.22, alturaMax = base * 0.3;
  var centroY = H * 0.4 + olho.olharY * base * 0.06;
  var afastamento = base * 0.2;
  [-1, 1].forEach(function (lado) {
    var cx = W / 2 + lado * afastamento + olho.olharX * base * 0.06;
    var h = Math.max(base * 0.012, alturaMax * olho.altura);
    retanguloArredondado(cx - largura / 2, centroY - h / 2, largura, h, base * 0.06);
  });

  // Boca: uma barrinha que mexe com o volume da fala
  if (estado === "falando") {
    var bocaL = base * 0.18, bocaH = base * 0.015 + olho.boca * base * 0.09;
    retanguloArredondado(W / 2 - bocaL / 2, H * 0.68 - bocaH / 2, bocaL, bocaH, bocaH / 2);
  }

  // Pensando: três pontinhos
  if (estado === "pensando") {
    for (var i = 0; i < 3; i++) {
      var sobe = Math.sin(agora / 250 + i) * base * 0.01;
      g.beginPath();
      g.arc(W / 2 + (i - 1) * base * 0.05, H * 0.68 + sobe, base * 0.015, 0, Math.PI * 2);
      g.fill();
    }
  }

  // Dormindo: "z z z"
  if (estado === "dormindo") {
    g.font = Math.round(base * 0.06) + "px sans-serif";
    g.globalAlpha = 0.5 + 0.5 * Math.sin(agora / 600);
    g.fillText("z z z", W / 2 + afastamento + largura / 2, centroY - base * 0.12);
    g.globalAlpha = 1;
  }

  requestAnimationFrame(desenhar);
}

desenhar();
conectar();
