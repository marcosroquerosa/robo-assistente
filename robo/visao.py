"""
VISÃO (os olhos de verdade do robô)
===================================
O celular manda uma imagem pequena da câmera da frente umas duas vezes por segundo.
Aqui, sem internet, o computador:
  1. Acha os rostos na imagem (modelo YuNet, bem leve).
  2. Transforma cada rosto numa "assinatura": uma lista de 128 números que resume
     o rosto (modelo SFace). Rostos da mesma pessoa dão assinaturas parecidas.
  3. Compara com as assinaturas cadastradas para saber quem é.
  4. Havendo rostos, procura mãos (usa o detector de palmas do OpenCV Zoo, que roda
     sem a instrução AVX, ausente no processador do NucBox).

O cadastro (dados/rostos.json) guarda só as assinaturas, nunca as fotos.
Não dá para reconstruir o rosto a partir delas.

Teste sozinho com uma foto:   python -m robo.visao foto.jpg
"""

import json
import os
import re
import sys
import threading
import time
import unicodedata

import cv2
import numpy as np

from robo import config


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos: "Júlia" -> "julia" (para comparar nomes e frases)."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


class DetectorDeMaos:
    """Acha palmas de mão numa imagem. A rede olha um quadrado de 192 x 192 pixels e dá uma
    nota para cada uma de 2016 posições fixas (as "âncoras"); as melhores viram mãos."""
    LADO = 192

    def __init__(self):
        import onnxruntime   # só carrega se as mãos estiverem ligadas
        opcoes = onnxruntime.SessionOptions()
        opcoes.intra_op_num_threads = 2   # deixa núcleos livres para a voz e o entendimento
        self.sessao = onnxruntime.InferenceSession(config.MODELO_DETECTOR_DE_PALMAS, opcoes,
                                                   providers=["CPUExecutionProvider"])
        self.entrada = self.sessao.get_inputs()[0].name
        ancoras = []
        for grade, por_casa in ((24, 2), (12, 6)):
            for y in range(grade):
                for x in range(grade):
                    ancoras += [((x + 0.5) / grade, (y + 0.5) / grade)] * por_casa
        self.ancoras = np.array(ancoras, dtype=np.float32)

    def achar(self, imagem) -> list:
        """Devolve as mãos: x e y do centro (0 a 1), tamanho (0 a 1, da largura) e certeza."""
        altura, largura = imagem.shape[:2]
        lado = max(altura, largura)
        margem_x, margem_y = (lado - largura) // 2, (lado - altura) // 2
        quadrado = np.zeros((lado, lado, 3), dtype=np.uint8)   # completa com preto: não deforma a imagem
        quadrado[margem_y:margem_y + altura, margem_x:margem_x + largura] = imagem
        pequena = cv2.resize(cv2.cvtColor(quadrado, cv2.COLOR_BGR2RGB), (self.LADO, self.LADO),
                             interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        saidas = self.sessao.run(None, {self.entrada: pequena[None]})
        caixas = next(s for s in saidas if s.shape[-1] == 18)[0]
        notas = next(s for s in saidas if s.shape[-1] == 1)[0, :, 0]
        certezas = 1 / (1 + np.exp(-np.clip(notas, -50, 50)))
        escolhidas = np.where(certezas >= config.VISAO_CERTEZA_DA_MAO)[0]
        if len(escolhidas) == 0:
            return []
        centros = caixas[escolhidas, :2] / self.LADO + self.ancoras[escolhidas]
        tamanhos = caixas[escolhidas, 2:4] / self.LADO
        retangulos = [[float(c[0] - t[0] / 2), float(c[1] - t[1] / 2), float(t[0]), float(t[1])]
                      for c, t in zip(centros, tamanhos)]
        ficam = cv2.dnn.NMSBoxes(retangulos, [float(c) for c in certezas[escolhidas]],
                                 config.VISAO_CERTEZA_DA_MAO, 0.3)
        maos = []
        for i in np.array(ficam).flatten():
            maos.append({"x": (float(centros[i][0]) * lado - margem_x) / largura,
                         "y": (float(centros[i][1]) * lado - margem_y) / altura,
                         "tamanho": float(tamanhos[i][0]) * lado / largura,
                         "certeza": float(certezas[escolhidas[i]])})
        return maos


def _recortar(cinza, centro_x, centro_y, meia_largura, meia_altura):
    """Recorte pequeno e sem o brilho médio, para comparar quadros seguidos."""
    altura, largura = cinza.shape[:2]
    x1, x2 = max(0, int(centro_x - meia_largura)), min(largura, int(centro_x + meia_largura) + 1)
    y1, y2 = max(0, int(centro_y - meia_altura)), min(altura, int(centro_y + meia_altura) + 1)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    recorte = cv2.resize(cinza[y1:y2, x1:x2], (32, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
    return recorte - recorte.mean()


def recortes_do_rosto(cinza, achado):
    """Recortes da boca e dos olhos, a partir dos 5 pontos que o YuNet marca no rosto.
    Os olhos servem de comparação: se eles também mudaram, foi a cabeça que mexeu."""
    olho_a, olho_b = np.array(achado[4:6], float), np.array(achado[6:8], float)
    canto_a, canto_b = np.array(achado[10:12], float), np.array(achado[12:14], float)
    entre_olhos = max(float(np.linalg.norm(olho_a - olho_b)), 4.0)
    boca_x, boca_y = (canto_a + canto_b) / 2
    meio_x, meio_y = (olho_a + olho_b) / 2
    return (_recortar(cinza, boca_x, boca_y, entre_olhos * 0.6, entre_olhos * 0.45),
            _recortar(cinza, meio_x, meio_y, entre_olhos * 0.9, entre_olhos * 0.35))


class Visao:
    def __init__(self):
        self.ligada = False
        self.reconhecedor = None
        self.maos = None              # detector de mãos (None = desligado)
        self.ultima_busca_de_maos = 0.0
        self.pessoas = {}             # nome -> lista de assinaturas
        self.trava = threading.Lock()  # um quadro de cada vez
        if not config.VISAO_LIGADA:
            print("[visão] desligada no config.py")
            return
        if not os.path.exists(config.MODELO_DETECTOR_DE_ROSTOS):
            print(f"[visão] atenção: não achei {config.MODELO_DETECTOR_DE_ROSTOS}. "
                  "Rode: python ferramentas/baixar_modelos.py")
            return
        # 0.8 = só aceita rostos com bastante certeza
        self.detector = cv2.FaceDetectorYN.create(config.MODELO_DETECTOR_DE_ROSTOS, "", (320, 240), 0.8, 0.3, 50)
        if config.VISAO_RECONHECER_PESSOAS:
            if os.path.exists(config.MODELO_RECONHECEDOR_DE_ROSTOS):
                self.reconhecedor = cv2.FaceRecognizerSF.create(config.MODELO_RECONHECEDOR_DE_ROSTOS, "")
                self._carregar_cadastro()
            else:
                print(f"[visão] atenção: não achei {config.MODELO_RECONHECEDOR_DE_ROSTOS}; "
                      "vou ver rostos, mas sem saber quem é")
        if config.VISAO_MAO_LEVANTADA:
            self._ligar_maos()
        self.ligada = True
        quem = ", ".join(self.pessoas) or "ninguém ainda"
        print(f"[visão] pronta! Rostos conhecidos: {quem}")

    def _ligar_maos(self):
        if not os.path.exists(config.MODELO_DETECTOR_DE_PALMAS):
            print(f"[visão] atenção: não achei {config.MODELO_DETECTOR_DE_PALMAS}; vou ignorar as mãos. "
                  "Rode: python ferramentas/baixar_modelos.py visao")
            return
        try:
            self.maos = DetectorDeMaos()
        except Exception as erro:
            print(f"[visão] não consegui ligar o detector de mãos: {type(erro).__name__}: {erro}")

    # ---------- olhar uma imagem ----------
    def analisar(self, jpeg: bytes) -> list:
        """Só os rostos da imagem (veja ver)."""
        return self.ver(jpeg, procurar_maos=False)[0]

    def ver(self, jpeg: bytes, procurar_maos=True):
        """Devolve (rostos, mãos). Rostos do maior (mais perto) para o menor; cada um tem
        x e y do centro (0 a 1), tamanho e altura (0 a 1), pixels, nome (ou None) e assinatura.
        Mãos só são procuradas se houver rostos, no máximo umas 2 vezes por segundo."""
        imagem = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if imagem is None:
            return [], []
        rostos = self._achar_rostos(imagem)
        maos = []
        agora = time.time()
        if procurar_maos and rostos and self.maos is not None and agora - self.ultima_busca_de_maos >= 0.45:
            self.ultima_busca_de_maos = agora
            maos = self.maos.achar(imagem)
        return rostos, maos

    def _achar_rostos(self, imagem) -> list:
        altura, largura = imagem.shape[:2]
        with self.trava:
            self.detector.setInputSize((largura, altura))
            _, achados = self.detector.detect(imagem)
            if achados is None:
                return []
            achados = sorted(achados, key=lambda f: -f[2] * f[3])[:5]
            # com uma pessoa só não há dúvida de quem fala: nem compara as bocas
            cinza = (cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
                     if config.VISAO_OLHAR_QUEM_FALA and len(achados) >= 2 else None)
            rostos = []
            for achado in achados:
                x, y, l, a = (float(v) for v in achado[:4])
                rosto = {"x": (x + l / 2) / largura, "y": (y + a / 2) / altura,
                         "tamanho": l / largura, "altura": a / altura, "pixels": l,
                         "nome": None, "parecido": 0.0, "assinatura": None,
                         "boca": None, "olhos": None}
                if cinza is not None and l >= config.VISAO_TAMANHO_MINIMO_DO_ROSTO:
                    rosto["boca"], rosto["olhos"] = recortes_do_rosto(cinza, achado)
                if self.reconhecedor is not None and l >= config.VISAO_TAMANHO_MINIMO_DO_ROSTO:
                    rosto["assinatura"] = self._assinatura(imagem, achado)
                    rosto["nome"], rosto["parecido"] = self.quem_e(rosto["assinatura"])
                rostos.append(rosto)
            return rostos

    def _assinatura(self, imagem, achado):
        rosto_alinhado = self.reconhecedor.alignCrop(imagem, achado)
        vetor = self.reconhecedor.feature(rosto_alinhado).flatten().astype(np.float32)
        return vetor / (np.linalg.norm(vetor) + 1e-9)

    def quem_e(self, assinatura):
        """Compara com todo mundo cadastrado. 1 = idêntico; abaixo do limiar = desconhecido."""
        melhor_nome, melhor = None, 0.0
        for nome, assinaturas in self.pessoas.items():
            parecido = float(np.max(assinaturas @ assinatura))
            if parecido > melhor:
                melhor_nome, melhor = nome, parecido
        if melhor >= config.VISAO_LIMIAR_DE_PARECIDO:
            return melhor_nome, melhor
        return None, melhor

    # ---------- cadastro ----------
    def _carregar_cadastro(self):
        if not os.path.exists(config.ARQUIVO_DE_ROSTOS):
            return
        with open(config.ARQUIVO_DE_ROSTOS, encoding="utf-8") as f:
            dados = json.load(f)
        self.pessoas = {nome: np.array(lista, dtype=np.float32)
                        for nome, lista in dados.get("pessoas", {}).items() if lista}

    def _salvar_cadastro(self):
        pasta = os.path.dirname(config.ARQUIVO_DE_ROSTOS)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        dados = {"aviso": "Assinaturas de rostos (não são fotos). Apague com: "
                          "python ferramentas/rostos.py apagar NOME",
                 "pessoas": {nome: np.round(a, 5).tolist() for nome, a in self.pessoas.items()}}
        temporario = config.ARQUIVO_DE_ROSTOS + ".novo"
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
        os.replace(temporario, config.ARQUIVO_DE_ROSTOS)  # troca de uma vez: nunca fica pela metade

    def cadastrar(self, nome: str, assinaturas: list):
        existente = self.achar_nome(nome)
        if existente:
            nome = existente   # mesma pessoa: junta as assinaturas novas com as antigas
        novas = np.array(assinaturas, dtype=np.float32)
        if nome in self.pessoas:
            novas = np.vstack([self.pessoas[nome], novas])
        self.pessoas[nome] = novas[-20:]   # guarda no máximo as 20 mais recentes
        self._salvar_cadastro()
        print(f"[visão] cadastrei {nome} ({len(self.pessoas[nome])} assinaturas)")
        return nome

    def esquecer(self, nome: str):
        existente = self.achar_nome(nome)
        if not existente:
            return None
        del self.pessoas[existente]
        self._salvar_cadastro()
        print(f"[visão] apaguei o rosto de {existente}")
        return existente

    def achar_nome(self, texto: str):
        """Procura, no texto, o nome de alguém cadastrado (sem ligar para acentos)."""
        def so_palavras(t):
            return " " + " ".join(re.findall(r"\w+", normalizar(t))) + " "
        texto = so_palavras(texto)
        for nome in sorted(self.pessoas, key=len, reverse=True):
            if so_palavras(nome) in texto:
                return nome
        return None

    # ---------- foto para a IA ----------
    @staticmethod
    def reduzir(jpeg: bytes, lado_maximo=1024) -> bytes:
        """Diminui a foto antes de mandar para a internet (sobe mais rápido)."""
        imagem = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_UNCHANGED)
        if imagem is None:
            return jpeg
        if imagem.dtype != np.uint8:   # PNG de 16 bits
            imagem = (imagem / 257).astype(np.uint8)
        if imagem.ndim == 2:
            imagem = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR)
        elif imagem.shape[2] == 4:     # PNG com fundo transparente: põe fundo branco
            alfa = imagem[:, :, 3:4].astype(np.float32) / 255
            imagem = (imagem[:, :, :3] * alfa + 255 * (1 - alfa)).astype(np.uint8)
        altura, largura = imagem.shape[:2]
        escala = lado_maximo / max(altura, largura)
        if escala < 1:
            imagem = cv2.resize(imagem, (int(largura * escala), int(altura * escala)), interpolation=cv2.INTER_AREA)
        ok, saida = cv2.imencode(".jpg", imagem, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return saida.tobytes() if ok else jpeg


class Presenca:
    """Lembra quem está na frente do robô e decide quando cumprimentar."""

    def __init__(self):
        self.seguidos = {}            # nome -> em quantos quadros seguidos apareceu
        self.ultimo_cumprimento = {}  # nome -> quando foi cumprimentado
        self.ultima_vez_com_gente = 0.0
        self.chegada_nova = False     # alguém apareceu depois de a sala ficar vazia
        self.desconhecido_seguidos = 0
        self.rostos = []              # o último quadro
        self.quando = 0.0

    def atualizar(self, rostos: list, agora: float, pode_cumprimentar: bool) -> list:
        """Devolve quem cumprimentar agora: nomes, ou None para "alguém que não conheço"."""
        self.rostos, self.quando = rostos, agora
        cumprimentar = []
        nomes = {r["nome"] for r in rostos if r["nome"]}

        if rostos and agora - self.ultima_vez_com_gente > config.VISAO_SEGUNDOS_DE_SALA_VAZIA:
            self.chegada_nova = True
        if rostos:
            self.ultima_vez_com_gente = agora

        self.seguidos = {n: self.seguidos.get(n, 0) + 1 for n in nomes}
        intervalo = config.VISAO_MINUTOS_ENTRE_CUMPRIMENTOS * 60
        for nome in nomes:
            # 2 quadros seguidos = tem certeza de que é a pessoa (e não um engano de um quadro)
            if self.seguidos[nome] >= 2 and agora - self.ultimo_cumprimento.get(nome, -1e9) > intervalo:
                if pode_cumprimentar and config.VISAO_CUMPRIMENTAR_CONHECIDOS:
                    self.ultimo_cumprimento[nome] = agora
                    cumprimentar.append(nome)
        if nomes:
            self.chegada_nova = False

        self.desconhecido_seguidos = self.desconhecido_seguidos + 1 if rostos and not nomes else 0
        # espera uns 2 segundos para dar tempo de reconhecer, antes de achar que é desconhecido
        if (self.chegada_nova and self.desconhecido_seguidos >= 4 and pode_cumprimentar
                and config.VISAO_CUMPRIMENTAR_DESCONHECIDOS):
            self.chegada_nova = False
            cumprimentar.append(None)
        return cumprimentar

    def quem_esta_aqui(self, agora: float):
        """(nomes conhecidos, quantos desconhecidos), ou None se a câmera não mandou nada recente."""
        if agora - self.quando > 3:
            return None
        nomes = []
        for r in self.rostos:
            if r["nome"] and r["nome"] not in nomes:
                nomes.append(r["nome"])
        return nomes, sum(1 for r in self.rostos if not r["nome"])


# ---- Teste: python -m robo.visao foto.jpg ----
if __name__ == "__main__":
    visao = Visao()
    for caminho in sys.argv[1:]:
        with open(caminho, "rb") as f:
            inicio = time.time()
            achados, maos = visao.ver(f.read())
        print(f"{caminho}: {len(achados)} rosto(s) e {len(maos)} mão(s) em {(time.time() - inicio) * 1000:.0f} ms")
        for r in achados:
            print(f"  centro ({r['x']:.2f}, {r['y']:.2f}), {r['pixels']:.0f} px, "
                  f"quem: {r['nome'] or 'desconhecido'} (parecido {r['parecido']:.2f})")
        for m in maos:
            print(f"  mão em ({m['x']:.2f}, {m['y']:.2f}), certeza {m['certeza']:.2f}")
