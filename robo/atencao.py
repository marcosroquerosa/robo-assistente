"""
ATENÇÃO (para quem o robô olha quando há várias pessoas)
========================================================
A visão diz onde estão os rostos e as mãos em cada imagem. Aqui o robô junta as
imagens para entender o que está acontecendo ao longo do tempo:

  Rastreador    dá um número a cada rosto, para reconhecê-lo na imagem seguinte.
  QuemFala      havendo som no microfone, a pessoa cuja boca mais mexe é quem fala.
  PedidoDeVez   mão acima da cabeça por um tempo = a pessoa está pedindo a vez.

Nada disso vai para a internet nem é gravado: os recortes da boca só ficam na
memória até a imagem seguinte.
"""

from robo import config

DISTANCIA_MAXIMA = 0.15     # quanto um rosto anda de uma imagem para outra (0 a 1)
ESQUECER_ROSTO_DEPOIS = 1.5 # segundos sem aparecer para o número ser descartado
BOCA_VELHA_DEMAIS = 0.8     # segundos: mais que isso, não dá para comparar duas imagens
VANTAGEM_MINIMA = 1.3       # quem fala precisa mexer a boca 30% mais que o segundo colocado
MAO_SUMIDA_DEPOIS = 1.0     # o detector às vezes perde a mão num quadro; só depois disso ela baixou


class Rastreador:
    def __init__(self):
        self.proximo = 1
        self.rostos = {}   # número -> (x, y, quando foi visto)

    def atualizar(self, rostos: list, agora: float):
        """Coloca rosto["id"] em cada rosto, do maior para o menor."""
        livres = dict(self.rostos)
        for rosto in rostos:
            perto = None
            limite = DISTANCIA_MAXIMA + rosto["tamanho"] / 2
            for numero, (x, y, _) in livres.items():
                distancia = ((x - rosto["x"]) ** 2 + (y - rosto["y"]) ** 2) ** 0.5
                if distancia < limite:
                    perto, limite = numero, distancia
            if perto is None:
                perto = self.proximo
                self.proximo += 1
            else:
                del livres[perto]
            rosto["id"] = perto
            self.rostos[perto] = (rosto["x"], rosto["y"], agora)
        self.rostos = {n: d for n, d in self.rostos.items() if agora - d[2] <= ESQUECER_ROSTO_DEPOIS}


def _diferenca(a, b) -> float:
    return float(abs(a - b).mean())


class QuemFala:
    def __init__(self):
        self.anteriores = {}   # número do rosto -> (boca, olhos, quando)
        self.pontos = {}       # número do rosto -> quanto a boca mexeu enquanto havia som
        self.atual = None      # número de quem está falando (None = não sei)
        self.quando = 0.0

    def atualizar(self, rostos: list, agora: float, tem_voz: bool, manter=False):
        """Devolve o número do rosto de quem fala, ou None.
        manter=True: o robô está respondendo, então continua olhando para quem perguntou."""
        presentes = {r["id"] for r in rostos}
        for rosto in rostos:
            self._medir(rosto, agora, tem_voz)
        self.anteriores = {n: d for n, d in self.anteriores.items() if n in presentes}
        self.pontos = {n: p for n, p in self.pontos.items() if n in presentes}

        if tem_voz and self.pontos:
            ordem = sorted(self.pontos, key=self.pontos.get, reverse=True)
            primeiro = self.pontos[ordem[0]]
            segundo = self.pontos[ordem[1]] if len(ordem) > 1 else 0.0
            if primeiro >= config.VISAO_MOVIMENTO_MINIMO_DA_BOCA and primeiro >= segundo * VANTAGEM_MINIMA:
                self.atual, self.quando = ordem[0], agora
            elif self.atual in presentes:
                self.quando = agora    # empate: continua olhando para a mesma pessoa

        if self.atual not in presentes:
            self.atual = None
        elif not manter and not tem_voz and agora - self.quando > config.VISAO_SEGUNDOS_OLHANDO_QUEM_FALOU:
            self.atual = None
        return self.atual

    def _medir(self, rosto, agora, tem_voz):
        numero, boca, olhos = rosto["id"], rosto.get("boca"), rosto.get("olhos")
        if boca is None or olhos is None:
            return
        anterior = self.anteriores.get(numero)
        self.anteriores[numero] = (boca, olhos, agora)
        ponto = self.pontos.get(numero, 0.0)
        if tem_voz and anterior and agora - anterior[2] <= BOCA_VELHA_DEMAIS:
            # tira o que os olhos também mudaram: assim, virar a cabeça não conta como falar
            movimento = max(0.0, _diferenca(boca, anterior[0]) - _diferenca(olhos, anterior[1]))
            self.pontos[numero] = 0.6 * ponto + 0.4 * movimento
        elif not tem_voz:
            self.pontos[numero] = 0.9 * ponto
        else:
            self.pontos.setdefault(numero, 0.0)


def mao_levantada(rosto: dict, mao: dict) -> bool:
    """A mão está no alto, perto da pessoa e do tamanho certo para ser dela?
    Vale acima da testa, ou ao lado da cabeça na altura dos olhos. Na frente do rosto
    não vale: quem coça a testa ou arruma o cabelo não está pedindo a vez."""
    distancia = abs(mao["x"] - rosto["x"])
    acima_da_testa = mao["y"] < rosto["y"] - rosto["altura"] * 0.35
    ao_lado_da_cabeca = mao["y"] < rosto["y"] - rosto["altura"] * 0.1 and distancia > rosto["tamanho"] * 0.6
    perto = distancia < rosto["tamanho"] * 2.2
    tamanho_certo = rosto["tamanho"] * 0.35 <= mao["tamanho"] <= rosto["tamanho"] * 2.0
    return (acima_da_testa or ao_lado_da_cabeca) and perto and tamanho_certo


class PedidoDeVez:
    def __init__(self):
        self.desde = {}          # número do rosto -> quando a mão subiu
        self.vista = {}          # número do rosto -> quando a mão foi vista por último
        self.atendidos = set()   # já foram chamados; precisam baixar a mão para pedir de novo
        self.chamado = None      # o último rosto chamado
        self.quando_chamou = -1e9
        self.pendente = None     # o rosto que está esperando a vez agora
        self.quando = 0.0

    def atualizar(self, rostos: list, maos: list, agora: float):
        """Devolve o rosto que está com a mão levantada há mais tempo (e já pode ser chamado)."""
        self.quando = agora
        por_numero = {r["id"]: r for r in rostos}
        for mao in maos:
            donos = [r for r in rostos if mao_levantada(r, mao)]
            if donos:
                dono = min(donos, key=lambda r: abs(r["x"] - mao["x"]))["id"]
                self.desde.setdefault(dono, agora)
                self.vista[dono] = agora

        for numero in list(self.vista):
            if numero not in por_numero or agora - self.vista[numero] > MAO_SUMIDA_DEPOIS:
                self.vista.pop(numero)
                self.desde.pop(numero, None)
                self.atendidos.discard(numero)

        prontos = [n for n, inicio in self.desde.items()
                   if agora - inicio >= config.VISAO_SEGUNDOS_COM_A_MAO_LEVANTADA and n not in self.atendidos]
        self.pendente = por_numero[min(prontos, key=self.desde.get)] if prontos else None
        return self.pendente

    def pode_chamar(self, agora: float) -> bool:
        return agora - self.quando_chamou >= config.VISAO_SEGUNDOS_ENTRE_VEZES

    def chamar(self, rosto: dict, agora: float):
        self.atendidos.add(rosto["id"])
        self.chamado, self.quando_chamou = rosto["id"], agora
        self.pendente = None

    def esperando(self, agora: float):
        """O rosto que pediu a vez, se a câmera ainda estiver mandando imagens."""
        return self.pendente if agora - self.quando < 2 and self.pode_chamar(agora) else None

    def tem_mao_no_ar(self) -> bool:
        return bool(self.desde)
