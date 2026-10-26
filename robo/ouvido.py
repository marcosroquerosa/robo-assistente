"""
OUVIDO (o robô prestando atenção)
=================================
Recebe o áudio do microfone do celular, pedacinho por pedacinho, e faz
duas coisas:
  1. Dormindo: fica esperando a palavra de ativação (ex.: "ei robô").
     Usa o Vosk, que é leve e roda o tempo todo sem pesar no computador.
  2. Gravando: guarda tudo que a pessoa fala até ela ficar em silêncio.

Ele devolve "eventos" para o sistema nervoso (robo.py):
  "acordou"        -> ouviu a palavra de ativação
  ("fala", audio)  -> a pessoa terminou de falar; aqui está o áudio
  "desistiu"       -> esperou e ninguém falou nada
"""

import json

import numpy as np
from vosk import KaldiRecognizer, Model, SetLogLevel

from robo import config

SetLogLevel(-1)  # deixa o Vosk quieto no terminal


class Ouvido:
    def __init__(self):
        print("[ouvido] carregando o Vosk...")
        modelo = Model(config.MODELO_VOSK)
        # A "gramática" diz ao Vosk para procurar só as palavras de ativação.
        # "[unk]" significa "qualquer outra coisa".
        gramatica = json.dumps(config.PALAVRAS_DE_ATIVACAO + ["[unk]"], ensure_ascii=False)
        self.reconhecedor = KaldiRecognizer(modelo, config.TAXA_DE_AMOSTRAGEM, gramatica)
        self.modo = "dormindo"
        self.audio_gravado = bytearray()
        self.pedaco_anterior = b""
        self.segundos_de_silencio = 0.0
        self.segundos_esperando = 0.0
        self.alguem_falou = False
        print("[ouvido] pronto!")

    # ---------- mudar de modo ----------
    def dormir(self):
        self.modo = "dormindo"
        self.reconhecedor.Reset()

    def comecar_a_gravar(self):
        self.modo = "gravando"
        self.audio_gravado = bytearray()
        self.pedaco_anterior = b""
        self.segundos_de_silencio = 0.0
        self.segundos_esperando = 0.0
        self.alguem_falou = False

    # ---------- receber um pedacinho de áudio ----------
    def ouvir(self, pedaco: bytes):
        if self.modo == "dormindo":
            return self._procurar_palavra(pedaco)
        if self.modo == "gravando":
            return self._gravar(pedaco)
        return None

    def _procurar_palavra(self, pedaco: bytes):
        if self.reconhecedor.AcceptWaveform(pedaco):
            texto = json.loads(self.reconhecedor.Result()).get("text", "")
        else:
            texto = json.loads(self.reconhecedor.PartialResult()).get("partial", "")
        if any(palavra in texto for palavra in config.PALAVRAS_DE_ATIVACAO):
            self.reconhecedor.Reset()
            return "acordou"
        return None

    def _gravar(self, pedaco: bytes):
        duracao = len(pedaco) / 2 / config.TAXA_DE_AMOSTRAGEM  # 2 bytes por amostra
        amostras = np.frombuffer(pedaco, dtype=np.int16).astype(np.float32)
        volume = float(np.sqrt(np.mean(amostras ** 2))) if len(amostras) else 0.0

        if volume > config.LIMIAR_DE_SILENCIO:
            if not self.alguem_falou:
                # guarda também o pedacinho anterior, para não cortar o começo da primeira palavra
                self.audio_gravado.extend(self.pedaco_anterior)
            self.alguem_falou = True
            self.segundos_de_silencio = 0.0
        else:
            self.segundos_de_silencio += duracao

        if not self.alguem_falou:
            self.pedaco_anterior = pedaco
            # ainda esperando a pessoa começar a falar
            self.segundos_esperando += duracao
            if self.segundos_esperando > config.SEGUNDOS_ESPERANDO_PERGUNTA:
                self.dormir()
                return "desistiu"
            return None

        self.audio_gravado.extend(pedaco)
        segundos_gravados = len(self.audio_gravado) / 2 / config.TAXA_DE_AMOSTRAGEM
        if (self.segundos_de_silencio >= config.SEGUNDOS_DE_SILENCIO_PARA_PARAR
                or segundos_gravados >= config.SEGUNDOS_MAXIMOS_DE_FALA):
            self.modo = "ocupado"   # para de ouvir enquanto o robô pensa e fala
            return ("fala", bytes(self.audio_gravado))
        return None
