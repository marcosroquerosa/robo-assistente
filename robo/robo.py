"""
SISTEMA NERVOSO (liga todas as partes do robô)
==============================================
O robô vive num ciclo de 4 estados:

   dormindo  --(ouviu "ei robô" ou tocaram na tela)-->  ouvindo
   ouvindo   --(a pessoa falou e fez silêncio)------->  pensando
   pensando  --(entendeu e começou a responder)------>  falando
   falando   --(o celular terminou de tocar a fala)-->  ouvindo (espera mais uma pergunta)
   ouvindo   --(ninguém falou por alguns segundos)--->  dormindo

Este arquivo decide o que fazer em cada momento e avisa o rosto (celular).
"""

import asyncio
import time
import traceback

from robo.cerebro import Cerebro
from robo.ouvido import Ouvido
from robo.transcricao import Transcritor
from robo.voz import Voz, limpar_texto

FRASE_DE_ERRO = "Ops, meus circuitos deram um nó. Pode repetir a pergunta?"


class Robo:
    def __init__(self):
        print("Ligando o robô... (a primeira vez demora um pouco)")
        self.ouvido = Ouvido()
        self.transcritor = Transcritor()
        self.cerebro = Cerebro()
        self.voz = Voz()
        self.rosto = None          # a conexão com o celular
        self.estado = "dormindo"
        self.tarefa = None         # o trabalho de pensar e responder, que roda em paralelo
        self.dormir_depois_de_falar = False
        print("Robô pronto!")

    # ---------- conversa com o rosto (celular) ----------
    async def conectar_rosto(self, conexao):
        self.rosto = conexao
        self.ouvido.dormir()
        await self.mudar_estado("dormindo")

    def desconectar_rosto(self, conexao):
        if self.rosto is conexao:
            self.rosto = None

    async def usar_este_rosto(self, conexao):
        """Se houver mais de uma aba aberta, o robô conversa com a última que mandou algo
        (a aba visível é a única que manda som e toques)."""
        if conexao is not None and conexao is not self.rosto:
            self.rosto = conexao
            print("[robô] trocando para a aba do rosto que está sendo usada")
            await self.enviar({"tipo": "estado", "estado": self.estado})

    async def enviar(self, mensagem: dict):
        if self.rosto is None:
            return
        try:
            await self.rosto.send_json(mensagem)
        except Exception:
            pass  # o celular desconectou; ele volta sozinho

    async def enviar_audio(self, audio: bytes):
        if self.rosto is None:
            return
        try:
            await self.rosto.send_bytes(audio)
        except Exception:
            pass

    async def mudar_estado(self, estado: str):
        self.estado = estado
        print(f"[robô] estado: {estado}")
        await self.enviar({"tipo": "estado", "estado": estado})

    # ---------- o que chega do celular ----------
    async def receber_audio(self, pedaco: bytes, conexao=None):
        await self.usar_este_rosto(conexao)
        if self.estado in ("pensando", "falando"):
            return  # enquanto pensa ou fala, o robô não escuta (assim não ouve a própria voz)
        evento = self.ouvido.ouvir(pedaco)
        if evento == "acordou":
            await self.acordar()
        elif evento == "desistiu":
            await self.mudar_estado("dormindo")
        elif isinstance(evento, tuple) and evento[0] == "fala":
            self.tarefa = asyncio.create_task(self.pensar_e_responder(evento[1]))

    async def receber_mensagem(self, mensagem: dict, conexao=None):
        await self.usar_este_rosto(conexao)
        tipo = mensagem.get("tipo")
        if tipo == "tocar" and self.estado == "dormindo":
            await self.acordar()
        elif tipo == "terminei_de_falar" and self.estado == "falando":
            if self.dormir_depois_de_falar:   # depois de um erro, volta a dormir
                self.dormir_depois_de_falar = False
                await self.dormir()
            else:
                await self.acordar()   # continua a conversa sem precisar da palavra de ativação
        elif tipo == "esquecer":
            self.cerebro.esquecer()

    async def acordar(self):
        self.ouvido.comecar_a_gravar()
        await self.mudar_estado("ouvindo")

    async def dormir(self):
        self.ouvido.dormir()
        await self.mudar_estado("dormindo")

    # ---------- pensar e responder ----------
    async def pensar_e_responder(self, audio: bytes):
        await self.mudar_estado("pensando")
        try:
            # asyncio.to_thread roda o trabalho pesado "ao lado", sem travar a conexão
            inicio = time.time()
            texto = await asyncio.to_thread(self.transcritor.transcrever, audio)
            print(f"[robô] ouvi: {texto!r}")
            print(f"[tempo] entender a fala: {time.time() - inicio:.1f} s")
            if len(texto) < 2:
                await self.dormir()
                return
            await self.enviar({"tipo": "legenda", "quem": "pessoa", "texto": texto})
            falou = await self.falar(lambda: self.cerebro.responder(texto))
            if not falou:
                await self.dormir()
        except Exception as erro:
            print(f"[robô] erro: {erro}")
            traceback.print_exc()      # mostra o caminho completo do erro na janela
            self.dormir_depois_de_falar = True
            try:
                await self.falar(lambda: [FRASE_DE_ERRO])
            except Exception:
                traceback.print_exc()
                await self.dormir()

    async def falar(self, gerar_frases) -> bool:
        """Pede as frases ao cérebro, transforma cada uma em áudio e manda para o celular.
        Enquanto o celular toca uma frase, o computador já prepara a próxima."""
        fila = asyncio.Queue()
        laco = asyncio.get_running_loop()

        def trabalhar():  # roda numa linha de execução separada
            try:
                for frase in gerar_frases():
                    audio = self.voz.falar(frase)
                    if audio is None:
                        continue  # frase sem nada para falar (ex.: só marcas <think>)
                    laco.call_soon_threadsafe(fila.put_nowait, (limpar_texto(frase), audio))
            finally:
                laco.call_soon_threadsafe(fila.put_nowait, None)  # sinal de "acabou"

        inicio = time.time()
        trabalho = asyncio.create_task(asyncio.to_thread(trabalhar))
        falou = False
        while True:
            item = await fila.get()
            if item is None:
                break
            frase, audio = item
            if not falou:
                print(f"[tempo] pensar a 1ª frase e virar voz: {time.time() - inicio:.1f} s")
                await self.mudar_estado("falando")
                falou = True
            print(f"[robô] falando: {frase}")
            await self.enviar({"tipo": "legenda", "quem": "robo", "texto": frase})
            await self.enviar_audio(audio)
        await trabalho  # se deu erro lá dentro, ele aparece aqui
        print(f"[tempo] resposta inteira pronta: {time.time() - inicio:.1f} s")
        if falou:
            await self.enviar({"tipo": "fim_da_fala"})
        return falou
