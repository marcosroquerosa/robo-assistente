/*
  ROSTO DO ROBÔ (roda no navegador do celular)
  ============================================
  1. Desenha os olhos e anima conforme o estado do robô.
  2. Pega o som do microfone e manda para o computador.
  3. Recebe a fala do robô (áudio) e toca no alto-falante.
  4. Mostra legendas do que foi dito.
  5. Liga a câmera da frente: manda imagens pequenas para o computador
     (que acha os rostos e as mãos) e tira fotos quando o robô pede.
  6. Faz as expressões (alegria, dúvida, surpresa e sono) e mostra listas,
     passos e textos num cartão ao lado do rosto.

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

// Câmera
var INVERTER_OLHAR = false;    // se os olhos olharem para o lado errado, troque para true
var visao = { ligada: false, largura: 640, intervalo: 500 };  // o computador manda os valores certos
var video = document.getElementById("camera");
var cameraPronta = false;
var pedindoCamera = false;
var rostosVistos = [];         // onde estão os rostos (de 0 a 1), o maior primeiro
var alguemNaFrente = false;
var ultimoQuadro = 0;          // quando chegou a última resposta sobre os rostos
var maoNoAr = false;           // tem alguém pedindo a vez?

// ---------------- conexão com o computador ----------------
function conectar() {
  var endereco = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
  conexao = new WebSocket(endereco);
  conexao.binaryType = "arraybuffer";
  conexao.onopen = function () {
    aviso("");
    if (cameraPronta) enviar({ tipo: "camera", ok: true }); // o computador pode ter reiniciado
  };
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
  if (m.na_fila) {
    // expressões e cartões entram na fila do áudio, para combinar com a frase certa
    filaDeAudio.push(m);
    if (!tocando) tocarProxima();
    return;
  }
  executar(m);
}

function executar(m) {
  if (m.tipo === "estado") mudarEstado(m.estado);
  else if (m.tipo === "legenda") legenda(m.quem, m.texto);
  else if (m.tipo === "visao") { visao = m; ligarCamera(); }
  else if (m.tipo === "tirar_foto") { fecharImagem(); tirarFoto(m); }
  else if (m.tipo === "mostrar_imagem") mostrarImagem(m);
  else if (m.tipo === "fechar_imagem") fecharImagem();
  else if (m.tipo === "expressao") iniciarExpressao(m.nome, m.segundos);
  else if (m.tipo === "mostrar_cartao") mostrarCartao(m);
  else if (m.tipo === "fechar_cartao") fecharCartao();
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
  if (dados.tipo) { executar(dados); tocarProxima(); return; } // não é som: é um pedido para o rosto
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
    ligarCamera(); // só depois do microfone, para o navegador perguntar uma coisa de cada vez
  }).catch(function (erro) {
    aviso("não consegui usar o microfone: " + erro.name);
    ligarCamera();
  });
}

// ---------------- câmera ----------------
function ligarCamera() {
  if (!ligado || !visao.ligada || cameraPronta || pedindoCamera) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    aviso("este navegador não deixa usar a câmera");
    enviar({ tipo: "camera", ok: false, erro: "SemSuporte" });
    return;
  }
  pedindoCamera = true;
  var pedido = { audio: false, video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } } };
  navigator.mediaDevices.getUserMedia(pedido).then(function (fluxo) {
    video.srcObject = fluxo;
    var tocar = video.play();
    if (tocar && tocar.catch) tocar.catch(function () {});
    cameraPronta = true;
    pedindoCamera = false;
    enviar({ tipo: "camera", ok: true });
    setTimeout(mandarQuadro, 1000);
  }).catch(function (erro) {
    pedindoCamera = false;
    aviso("não consegui usar a câmera: " + erro.name);
    enviar({ tipo: "camera", ok: false, erro: erro.name || String(erro) });
  });
}

// Desenha a imagem da câmera numa "tela" escondida e transforma em JPEG
function fotografar(largura, qualidade, depois) {
  var tela = document.createElement("canvas");
  var escala = Math.min(1, largura / video.videoWidth);
  tela.width = Math.round(video.videoWidth * escala);
  tela.height = Math.round(video.videoHeight * escala);
  tela.getContext("2d").drawImage(video, 0, 0, tela.width, tela.height);
  tela.toBlob(depois, "image/jpeg", qualidade);
}

// Manda uma imagem pequena; quando o computador responde, espera um pouco e manda outra
function mandarQuadro() {
  var inicio = Date.now();
  function deNovo() { setTimeout(mandarQuadro, Math.max(50, visao.intervalo - (Date.now() - inicio))); }
  var pronto = cameraPronta && video.videoWidth && visao.ligada && conexao && conexao.readyState === 1;
  if (!pronto || document.visibilityState !== "visible") { setTimeout(mandarQuadro, 1000); return; }
  fotografar(visao.largura, 0.7, function (imagem) {
    if (!imagem) { deNovo(); return; }
    fetch("/visao/quadro", { method: "POST", body: imagem })
      .then(function (r) { return r.json(); })
      .then(function (r) {
        rostosVistos = r.rostos || [];
        alguemNaFrente = !!r.alguem;
        ultimoQuadro = Date.now();
        if (r.intervalo) visao.intervalo = r.intervalo; // com várias pessoas, olha mais rápido
        mostrarMao(!!r.mao);
      })
      .catch(function () {})
      .then(deNovo);
  });
}

// O robô pediu uma foto grande (com contagem 3, 2, 1 se for "tira uma foto")
function tirarFoto(m) {
  var endereco = "/visao/foto/" + m.pedido;
  if (!cameraPronta || !video.videoWidth) { fetch(endereco, { method: "POST", body: "" }); return; }
  var falta = m.contagem || 0;
  function passo() {
    if (falta > 0) { mostrarContagem(String(falta)); falta--; setTimeout(passo, 1000); return; }
    mostrarContagem("");
    fotografar(4000, 0.9, function (imagem) {
      fetch(endereco, { method: "POST", body: imagem || "" }).catch(function () {});
      if (m.contagem) piscarFlash();
      if (m.para_web) avisoNaWeb();
      if (m.mostrar && imagem) mostrarFoto(imagem);
    });
  }
  passo();
}

function mostrarContagem(texto) {
  var el = document.getElementById("contagem");
  el.textContent = texto;
  el.style.display = texto ? "flex" : "none";
}

function piscarFlash() {
  var el = document.getElementById("flash");
  el.style.display = "block";
  setTimeout(function () { el.style.display = "none"; }, 150);
}

var fotoTimer = null;
function mostrarFoto(imagem) {
  var el = document.getElementById("foto");
  if (el.src) URL.revokeObjectURL(el.src);
  el.src = URL.createObjectURL(imagem);
  el.style.display = "block";
  clearTimeout(fotoTimer);
  fotoTimer = setTimeout(function () { el.style.display = "none"; }, 5000);
}

// Imagem que o robô buscou ("mostra uma placa-mãe"). Fica só na memória:
// quando sai da tela, é apagada.
var imagemTimer = null;
function mostrarImagem(m) {
  document.getElementById("imagem-figura").src = m.imagem;
  document.getElementById("imagem-titulo").textContent = m.legenda || "";
  document.getElementById("imagem-fonte").textContent = m.fonte ? "imagem: " + m.fonte : "";
  document.getElementById("imagem-busca").style.display = "flex";
  clearTimeout(imagemTimer);
  imagemTimer = setTimeout(fecharImagem, (m.segundos || 60) * 1000);
}

function imagemAberta() { return document.getElementById("imagem-busca").style.display === "flex"; }

function fecharImagem() {
  clearTimeout(imagemTimer);
  document.getElementById("imagem-busca").style.display = "none";
  document.getElementById("imagem-figura").removeAttribute("src");  // solta a imagem da memória
}

// Lista, passos ou texto ao lado do rosto, enquanto o robô fala
var cartaoTimer = null;
var cartaoAberto = false;
function mostrarCartao(m) {
  if (imagemAberta()) return; // a imagem está ocupando a tela
  var titulo = document.getElementById("cartao-titulo");
  var caixa = document.getElementById("cartao-itens");
  titulo.textContent = m.titulo || "";
  titulo.style.display = m.titulo ? "block" : "none";
  caixa.className = m.modelo;
  caixa.textContent = "";
  for (var i = 0; i < m.itens.length; i++) {
    var item = document.createElement(m.modelo === "texto" ? "div" : "li");
    item.textContent = m.itens[i];
    caixa.appendChild(item);
  }
  document.body.className = "com-cartao";
  document.getElementById("cartao").style.display = "flex";
  cartaoAberto = true;
  ajustarLetraDoCartao(m.modelo === "texto" ? 56 : 28);
  clearTimeout(cartaoTimer);
  cartaoTimer = setTimeout(fecharCartao, (m.segundos || 60) * 1000);
}

// Começa com a letra grande e diminui até tudo caber no cartão
function ajustarLetraDoCartao(tamanho) {
  var cartao = document.getElementById("cartao");
  var caixa = document.getElementById("cartao-itens");
  for (; tamanho >= 12; tamanho -= 2) {
    caixa.style.fontSize = tamanho + "px";
    if (cartao.scrollHeight <= cartao.clientHeight && caixa.scrollWidth <= caixa.clientWidth) break;
  }
}

function fecharCartao() {
  clearTimeout(cartaoTimer);
  cartaoAberto = false;
  document.body.className = "";
  document.getElementById("cartao").style.display = "none";
}

// Aviso de que alguém está pedindo a vez
function mostrarMao(sim) {
  maoNoAr = sim;
  document.getElementById("mao").style.display = sim ? "block" : "none";
}

// Aviso de que uma foto saiu para a internet (fica uns segundos na tela)
var webTimer = null;
function avisoNaWeb() {
  var el = document.getElementById("na-web");
  el.style.display = "block";
  clearTimeout(webTimer);
  webTimer = setTimeout(function () { el.style.display = "none"; }, 8000);
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
  if (imagemAberta()) { fecharImagem(); return; } // com uma imagem na tela, o toque só fecha a imagem
  if (cartaoAberto) { fecharCartao(); return; }   // o mesmo vale para o cartão
  enviar({ tipo: "tocar" }); // tocar na tela acorda o robô
});

// ---------------- textos na tela ----------------
function mudarEstado(novo) {
  estado = novo;
  ultimaAtividade = Date.now();
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

// ---------------- os olhos e as expressões ----------------
var tela = document.getElementById("olhos");
var g = tela.getContext("2d");
var FUNDO = "#0b0f14";         // a mesma cor do fundo da página: "apaga" pedaços dos olhos

// O rosto é feito destes números. Cada expressão muda alguns deles, e o desenho vai
// escorregando até o valor novo: é isso que faz o rosto mudar sem dar saltos.
//   altura     olhos abertos (1 = normal)        assimetria  um olho maior que o outro
//   tamanho    tamanho dos olhos                 palpebra    quanto a pálpebra de cima desce
//   inclinacao pálpebra caída para fora          sorriso     bochecha empurra o olho para cima
//   sobrancelha aparece com 1                    sobrAlta    sobrancelha levantada
//   sobrLado   só uma sobrancelha levanta        giro        cabeça inclinada (radianos)
//   bocaL, bocaA  largura e abertura da boca     bocaC       curva (+ sorriso, - tristeza)
//   bocaX      boca de lado                      r, g2, b    cor
var NEUTRO = {
  altura: 1, assimetria: 0, tamanho: 1, palpebra: 0, inclinacao: 0, sorriso: 0,
  sobrancelha: 0, sobrAlta: 0, sobrLado: 0, giro: 0,
  bocaL: 0, bocaA: 0, bocaC: 0, bocaX: 0,
  r: 93, g2: 202, b: 165
};
var EXPRESSOES = {
  alegria: { altura: 1, sorriso: 0.62, bocaL: 0.22, bocaA: 0.03, bocaC: 0.5, r: 127, g2: 232, b: 190 },
  surpresa: { altura: 1.25, tamanho: 1.08, sobrancelha: 1, sobrAlta: 1, bocaL: 0.06, bocaA: 0.13,
              r: 143, g2: 211, b: 255, simbolo: "!" },
  duvida: { altura: 0.85, assimetria: 0.32, sobrancelha: 1, sobrAlta: 0.8, sobrLado: 1, giro: -0.07,
            bocaL: 0.11, bocaA: 0.008, bocaC: -0.2, bocaX: 0.05, olharX: 0.3, olharY: -0.3,
            r: 196, g2: 167, b: 255, simbolo: "?" },
  sono: { altura: 0.62, palpebra: 0.42, inclinacao: 0.35, bocaL: 0.07, bocaA: 0.008, r: 63, g2: 143, b: 120 }
};
var CAMPOS = ["altura", "assimetria", "tamanho", "palpebra", "inclinacao", "sorriso", "sobrancelha", "sobrAlta",
              "sobrLado", "giro", "bocaL", "bocaA", "bocaC", "bocaX", "r", "g2", "b"];

var olho = { olharX: 0, olharY: 0, boca: 0, cartao: 0 };   // valores atuais (suavizados)
for (var c = 0; c < CAMPOS.length; c++) olho[CAMPOS[c]] = NEUTRO[CAMPOS[c]];
olho.altura = 0.1;

var proximaPiscada = Date.now() + 3000;
var expressao = null;          // nome da expressão atual
var expressaoAte = 0;          // quando ela acaba
var ultimaAtividade = Date.now();
var ultimaSurpresa = 0;        // para não se assustar a toda hora
var tinhaGente = false;
var proximoBocejo = Date.now() + 15000;
var bocejoAte = 0;

function iniciarExpressao(nome, segundos) {
  if (!EXPRESSOES[nome]) return;
  expressao = nome;
  expressaoAte = Date.now() + (segundos || 6) * 1000;
}

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

// Decide como o rosto deve ficar agora
function calcularAlvo(agora, temGente, cochilando) {
  var alvo = {}, i;
  for (i = 0; i < CAMPOS.length; i++) alvo[CAMPOS[i]] = NEUTRO[CAMPOS[i]];
  alvo.olharX = 0;
  alvo.olharY = 0;
  alvo.velocidade = 0.2;

  if (agora > expressaoAte) expressao = null;
  var sonolento = estado === "dormindo" && temGente && !expressao &&
                  agora - ultimaAtividade > (visao.sono || 60) * 1000;
  var nome = estado === "pensando" || estado === "desligado" || cochilando ? null : expressao;
  if (sonolento) nome = "sono";
  var receita = nome ? EXPRESSOES[nome] : null;
  if (receita) for (i = 0; i < CAMPOS.length; i++) {
    if (receita[CAMPOS[i]] !== undefined) alvo[CAMPOS[i]] = receita[CAMPOS[i]];
  }

  if (estado === "desligado") { alvo.altura = 0.08; alvo.r = 42; alvo.g2 = 58; alvo.b = 64; }
  if (estado === "dormindo" && !nome) { alvo.altura = temGente ? 0.55 : 0.1; alvo.r = 63; alvo.g2 = 143; alvo.b = 120; }
  // Olhar para a pessoa (o computador coloca primeiro quem está falando ou pedindo a vez).
  // A câmera vê o mundo "de frente": quem está à esquerda na imagem está à direita da tela.
  if (temGente && rostosVistos.length && estado !== "pensando" && estado !== "desligado") {
    var r = rostosVistos[0], lado = INVERTER_OLHAR ? -1 : 1;
    alvo.olharX = Math.max(-1, Math.min(1, (0.5 - r.x) * 2.2 * lado));
    alvo.olharY = Math.max(-1, Math.min(1, (r.y - 0.45) * 2));
  } else if (receita && receita.olharX !== undefined) {
    alvo.olharX = receita.olharX;
    alvo.olharY = receita.olharY;
  }
  if (estado === "ouvindo" && !nome) { alvo.altura = 1.15; }
  if (estado === "pensando") { alvo.altura = 0.75; alvo.olharX = 0.35; alvo.olharY = -0.35; alvo.r = 239; alvo.g2 = 159; alvo.b = 39; }
  if (estado === "falando") {
    alvo.bocaL = Math.max(alvo.bocaL, 0.18);
    alvo.bocaA = Math.max(alvo.bocaA, 0.015) + olho.boca * 0.09;
  }

  // Bocejo: de vez em quando, se estiver com sono
  if (sonolento) {
    if (agora > proximoBocejo) {
      bocejoAte = agora + 2600;
      proximoBocejo = agora + 25000 + Math.random() * 35000;
    }
    if (agora < bocejoAte) {
      alvo.altura = 0.12; alvo.bocaL = 0.1; alvo.bocaA = 0.2; alvo.bocaC = 0; alvo.velocidade = 0.06;
    }
  }

  // Piscar de vez em quando (com sono, pisca devagar)
  if (!cochilando && estado !== "desligado" && agora >= bocejoAte) {
    if (agora > proximaPiscada) {
      alvo.altura = 0.05;
      if (agora > proximaPiscada + (sonolento ? 420 : 140)) proximaPiscada = agora + 2500 + Math.random() * 3500;
    }
  }
  alvo.simbolo = receita ? receita.simbolo : null;
  return alvo;
}

function desenharOlho(cx, cy, w, h, lado, base) {
  g.fillStyle = "rgb(" + Math.round(olho.r) + "," + Math.round(olho.g2) + "," + Math.round(olho.b) + ")";
  retanguloArredondado(cx - w / 2, cy - h / 2, w, h, base * 0.06);
  g.fillStyle = FUNDO;

  // Pálpebra: cobre a parte de cima do olho, caindo para o lado de fora
  if (olho.palpebra > 0.01) {
    var y = cy - h / 2 + h * olho.palpebra, caida = olho.inclinacao * w * 0.5;
    g.beginPath();
    g.moveTo(cx - w, cy - h * 2);
    g.lineTo(cx + w, cy - h * 2);
    g.lineTo(cx + w, y + lado * caida * 2);
    g.lineTo(cx - w, y - lado * caida * 2);
    g.closePath();
    g.fill();
  }

  // Sorriso: a bochecha sobe e deixa só o arco de cima do olho
  if (olho.sorriso > 0.01) {
    var raio = w * 0.8;
    g.beginPath();
    g.arc(cx, cy + h / 2 - h * olho.sorriso + raio, raio, 0, Math.PI * 2);
    g.fill();
  }

  // Sobrancelha
  if (olho.sobrancelha > 0.02) {
    var sobe = olho.sobrAlta * (1 - olho.sobrLado * 0.5 * (1 - lado)) * base * 0.06;
    var linha = cy - h / 2 - base * 0.05 - sobe;
    g.globalAlpha = Math.min(1, olho.sobrancelha);
    g.strokeStyle = "rgb(" + Math.round(olho.r) + "," + Math.round(olho.g2) + "," + Math.round(olho.b) + ")";
    g.lineWidth = base * 0.02;
    g.lineCap = "round";
    g.beginPath();
    g.moveTo(cx - w * 0.4, linha + lado * base * 0.012);
    g.lineTo(cx + w * 0.4, linha - lado * base * 0.012);
    g.stroke();
    g.globalAlpha = 1;
  }
}

function desenharBoca(y, base) {
  if (olho.bocaL < 0.012) return;
  var L = olho.bocaL * base, A = olho.bocaA * base, x = olho.bocaX * base;
  var curva = olho.bocaC * L * 0.6;
  var cor = "rgb(" + Math.round(olho.r) + "," + Math.round(olho.g2) + "," + Math.round(olho.b) + ")";
  g.fillStyle = cor;
  g.strokeStyle = cor;
  g.lineWidth = base * 0.014;
  g.lineCap = "round";
  g.lineJoin = "round";
  if (A > L * 0.7) {   // boca bem aberta: "ó" de surpresa ou bocejo
    g.beginPath();
    g.ellipse(x, y, L * 0.6, A * 0.55, 0, 0, Math.PI * 2);
    g.fill();
    return;
  }
  g.beginPath();
  g.moveTo(x - L / 2, y);
  g.quadraticCurveTo(x, y + curva - A, x + L / 2, y);
  g.quadraticCurveTo(x, y + curva + A, x - L / 2, y);
  g.closePath();
  g.fill();
  g.stroke();
}

function desenhar() {
  var W = tela.width, H = tela.height, agora = Date.now();
  var base = Math.min(W, H);

  // Tem alguém na frente da câmera? (resposta recente do computador)
  var temGente = alguemNaFrente && agora - ultimoQuadro < 2000;
  var cochilando = estado === "dormindo" && !temGente;

  // Levar um susto quando alguém aparece numa sala vazia
  if (temGente && !tinhaGente && estado === "dormindo" && agora - ultimaSurpresa > 30000) {
    ultimaSurpresa = agora;
    iniciarExpressao("surpresa", 1.2);
  }
  tinhaGente = temGente;

  var alvo = calcularAlvo(agora, temGente, cochilando);

  // Movimento suave até o alvo
  for (var i = 0; i < CAMPOS.length; i++) {
    var campo = CAMPOS[i];
    // o piscar precisa ser rápido; só o bocejo fecha os olhos devagar
    var rapidez = campo === "altura" && alvo.velocidade > 0.1 ? 0.25 : alvo.velocidade;
    olho[campo] += (alvo[campo] - olho[campo]) * rapidez;
  }
  olho.olharX += (alvo.olharX - olho.olharX) * 0.1;
  olho.olharY += (alvo.olharY - olho.olharY) * 0.1;
  olho.boca += (volumeDaFala() - olho.boca) * 0.4;
  olho.cartao += ((cartaoAberto ? 1 : 0) - olho.cartao) * 0.15;

  g.clearRect(0, 0, W, H);

  // Com um cartão aberto, o rosto encolhe e vai para o lado (ou para cima, com o celular em pé)
  var emPe = H > W, abre = olho.cartao;
  var origemX = W / 2 + (emPe ? 0 : -W * 0.26 * abre);
  var origemY = H * 0.4 + (emPe ? -H * 0.22 * abre : -H * 0.03 * abre);
  var escala = 1 - 0.28 * abre;

  g.save();
  g.translate(origemX, origemY);
  g.rotate(olho.giro);
  g.scale(escala, escala);

  var largura = base * 0.22 * olho.tamanho, alturaMax = base * 0.3 * olho.tamanho;
  var centroY = olho.olharY * base * 0.07;
  var afastamento = base * 0.2;
  [-1, 1].forEach(function (lado) {
    var cx = lado * afastamento + olho.olharX * base * 0.1;
    var abertura = olho.altura * (1 - olho.assimetria * (1 - lado) / 2);
    var h = Math.max(base * 0.012, alturaMax * abertura);
    desenharOlho(cx, centroY, largura, h, lado, base);
  });

  var bocaY = base * 0.28;
  desenharBoca(bocaY, base);
  var cor = "rgb(" + Math.round(olho.r) + "," + Math.round(olho.g2) + "," + Math.round(olho.b) + ")";
  g.fillStyle = cor;

  // Pensando: três pontinhos
  if (estado === "pensando") {
    for (var p = 0; p < 3; p++) {
      var sobe = Math.sin(agora / 250 + p) * base * 0.01;
      g.beginPath();
      g.arc((p - 1) * base * 0.05, bocaY + sobe, base * 0.015, 0, Math.PI * 2);
      g.fill();
    }
  }

  // Símbolo da expressão: "?" na dúvida e "!" na surpresa
  if (alvo.simbolo) {
    g.font = "bold " + Math.round(base * 0.13) + "px sans-serif";
    g.textAlign = "center";
    g.fillText(alvo.simbolo, afastamento + largura * 0.95, -base * 0.2 + Math.sin(agora / 300) * base * 0.012);
    g.textAlign = "start";
  }

  // Dormindo: "z z z"
  if (cochilando) {
    g.font = Math.round(base * 0.06) + "px sans-serif";
    g.globalAlpha = 0.5 + 0.5 * Math.sin(agora / 600);
    g.fillText("z z z", afastamento + largura / 2, centroY - base * 0.12);
    g.globalAlpha = 1;
  }
  g.restore();

  requestAnimationFrame(desenhar);
}

desenhar();
conectar();
