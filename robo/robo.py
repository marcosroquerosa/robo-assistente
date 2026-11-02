"""
SISTEMA NERVOSO (liga todas as partes do robô)
==============================================
O robô vive num ciclo de 4 estados:

   dormindo  --(ouviu "ei robô" ou tocaram na tela)-->  ouvindo
   ouvindo   --(a pessoa falou e fez silêncio)------->  pensando
   pensando  --(entendeu e começou a responder)------>  falando
   falando   --(o celular terminou de tocar a fala)-->  ouvindo (espera mais uma pergunta)
   ouvindo   --(ninguém falou por alguns segundos)--->  dormindo

Além disso, a câmera do celular manda imagens o tempo todo (receber_quadro):
o robô vê quem está na frente, segue com os olhos quem está falando, percebe a mão
levantada de quem pede a vez e cumprimenta quem conhece.
Pedidos como "tira uma foto" ou "aprende meu rosto" são resolvidos aqui (veja comandos.py).

Este arquivo decide o que fazer em cada momento e avisa o rosto (celular).
"""

import asyncio
import base64
import os
import random
import time
import traceback
import uuid

from robo import comandos, config
from robo.atencao import PedidoDeVez, QuemFala, Rastreador
from robo.cerebro import Cerebro
from robo.imagens import BuscaDeImagens, WikipediaRecusou
from robo.ouvido import Ouvido, medir_volume
from robo.transcricao import Transcritor
from robo.visao import Presenca, Visao
from robo.voz import Voz, limpar_texto

FRASE_DE_ERRO = "Ops, meus circuitos deram um nó. Pode repetir a pergunta?"


class Robo:
    def __init__(self):
        print("Ligando o robô... (a primeira vez demora um pouco)")
        self.ouvido = Ouvido()
        self.transcritor = Transcritor()
        self.cerebro = Cerebro()
        self.voz = Voz()
        self.visao = Visao()
        self.presenca = Presenca()
        self.rastreador = Rastreador()
        self.quem_fala = QuemFala()
        self.vez = PedidoDeVez()
        self.ultima_voz = 0.0      # quando o microfone ouviu alguém por último
        self.imagens = BuscaDeImagens()
        self.camera_ok = False     # o celular conseguiu ligar a câmera?
        self.camera_erro = None    # o motivo, quando não conseguiu (ex.: "NotAllowedError")
        self.ultimo_quadro = 0.0   # quando chegou a última imagem da câmera
        self.fotos_esperadas = {}  # pedido de foto -> resposta que vai chegar do celular
        self.coleta = None         # assinaturas de rosto juntadas durante um cadastro
        self.esperando_nome_ate = 0.0  # depois de "aprende meu rosto", espera a pessoa dizer o nome
        self.rosto = None          # a conexão com o celular
        self.estado = "dormindo"
        self.tarefa = None         # o trabalho de pensar e responder, que roda em paralelo
        self.dormir_depois_de_falar = False
        print("Robô pronto!")

    # ---------- conversa com o rosto (celular) ----------
    async def conectar_rosto(self, conexao):
        self.rosto = conexao
        self.ouvido.dormir()
        await self.enviar_ajustes_da_visao()
        await self.mudar_estado("dormindo")

    async def enviar_ajustes_da_visao(self):
        await self.enviar({"tipo": "visao", "ligada": self.visao.ligada,
                           "largura": config.VISAO_LARGURA_DO_QUADRO,
                           "intervalo": self.intervalo_da_camera(),
                           "sono": config.ROSTO_SEGUNDOS_PARA_SONO})

    @staticmethod
    def intervalo_da_camera(em_grupo=False) -> int:
        por_segundo = config.VISAO_QUADROS_POR_SEGUNDO_EM_GRUPO if em_grupo else config.VISAO_QUADROS_POR_SEGUNDO
        return int(1000 / max(0.2, por_segundo))

    def desconectar_rosto(self, conexao):
        if self.rosto is conexao:
            self.rosto = None

    async def usar_este_rosto(self, conexao):
        """Se houver mais de uma aba aberta, o robô conversa com a última que mandou algo
        (a aba visível é a única que manda som e toques)."""
        if conexao is not None and conexao is not self.rosto:
            self.rosto = conexao
            print("[robô] trocando para a aba do rosto que está sendo usada")
            await self.enviar_ajustes_da_visao()
            await self.enviar({"tipo": "estado", "estado": self.estado})

    async def enviar(self, mensagem: dict):
        if self.rosto is None:
            return
        try:
            await self.rosto.send_json(mensagem)
        except Exception:
            pass  # o celular desconectou; ele volta sozinho

    async def expressao(self, nome: str, segundos=None, na_fila=False):
        """Muda a expressão do rosto. na_fila=True: espera a fala que já está tocando."""
        await self.enviar({"tipo": "expressao", "nome": nome, "na_fila": na_fila,
                           "segundos": segundos or config.ROSTO_SEGUNDOS_DE_EXPRESSAO})

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
        if medir_volume(pedaco) > config.LIMIAR_DE_SILENCIO:
            self.ultima_voz = time.time()
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
            elif self.vez.esperando(time.time()) is not None:
                self.tarefa = asyncio.create_task(self.dar_a_vez(self.vez.esperando(time.time())))
            else:
                await self.acordar()   # continua a conversa sem precisar da palavra de ativação
        elif tipo == "esquecer":
            self.cerebro.esquecer()
        elif tipo == "camera":
            self.camera_ok = bool(mensagem.get("ok"))
            self.camera_erro = None if self.camera_ok else (mensagem.get("erro") or "desconhecido")
            print(f"[robô] câmera do celular: {'ligada' if self.camera_ok else 'não funcionou: ' + self.camera_erro}")

    # ---------- o que chega da câmera ----------
    async def receber_quadro(self, jpeg: bytes) -> dict:
        """Uma imagem pequena da câmera (umas 2 por segundo). Responde onde estão os rostos,
        para os olhos do celular seguirem a pessoa."""
        if not self.visao.ligada or not jpeg:
            return {"rostos": [], "alguem": False}
        if not self.camera_ok:
            print("[robô] câmera do celular: chegando imagens")
        self.camera_ok, self.camera_erro = True, None
        rostos, maos = await asyncio.to_thread(self.visao.ver, jpeg)
        agora = time.time()
        self.ultimo_quadro = agora
        self.rastreador.atualizar(rostos, agora)
        ocupado = self.estado in ("pensando", "falando")
        tem_voz = agora - self.ultima_voz < 0.5
        falante = self.quem_fala.atualizar(rostos, agora, tem_voz, manter=ocupado)
        self.vez.atualizar(rostos, maos, agora)

        # cadastro em andamento: guarda a assinatura se tiver uma pessoa só na frente
        if self.coleta is not None and len(rostos) == 1 and rostos[0]["assinatura"] is not None:
            self.coleta.append(rostos[0]["assinatura"])

        livre = self.estado == "dormindo" and (self.tarefa is None or self.tarefa.done())
        pede = self.vez.esperando(agora)
        if pede is not None and (livre or self.ouvindo_em_silencio()):
            self.tarefa = asyncio.create_task(self.dar_a_vez(pede))
            livre = False
        for nome in self.presenca.atualizar(rostos, agora, pode_cumprimentar=livre):
            self.tarefa = asyncio.create_task(self.cumprimentar(nome))
            break  # um cumprimento de cada vez

        # o rosto que os olhos devem seguir vai primeiro na lista
        alvo = self.para_quem_olhar(falante, agora)
        ordem = sorted(rostos, key=lambda r: r["id"] != alvo)
        em_grupo = len(rostos) >= 2 and not ocupado and config.VISAO_OLHAR_QUEM_FALA
        seguir = config.VISAO_OLHOS_SEGUEM
        return {"alguem": bool(rostos), "mao": self.vez.tem_mao_no_ar(),
                "intervalo": self.intervalo_da_camera(em_grupo),
                "rostos": [{"x": round(r["x"], 3), "y": round(r["y"], 3), "tamanho": round(r["tamanho"], 3)}
                           for r in ordem] if seguir else []}

    def para_quem_olhar(self, falante, agora: float):
        """Quem acabou de ser chamado, depois quem pede a vez, depois quem está falando."""
        if agora - self.vez.quando_chamou < config.VISAO_SEGUNDOS_ENTRE_VEZES:
            return self.vez.chamado
        if self.vez.pendente is not None:
            return self.vez.pendente["id"]
        return falante

    def ouvindo_em_silencio(self) -> bool:
        return (self.estado == "ouvindo" and self.ouvido.modo == "gravando" and not self.ouvido.alguem_falou
                and (self.tarefa is None or self.tarefa.done()))

    async def dar_a_vez(self, rosto: dict):
        """Alguém está com a mão levantada: olha para a pessoa e deixa ela falar."""
        try:
            self.vez.chamar(rosto, time.time())
            nome = rosto.get("nome")
            print(f"[robô] {nome or 'alguém'} levantou a mão")
            modelos = config.FRASES_DA_VEZ if nome else config.FRASES_DA_VEZ_SEM_NOME
            frase = random.choice(modelos).format(nome=nome)
            await self.mudar_estado("falando")   # para de ouvir antes de preparar a frase
            if not await self.falar(lambda: [frase], expressao="surpresa"):
                await self.dormir()
        except Exception:
            traceback.print_exc()
            await self.dormir()

    def receber_foto(self, pedido: str, jpeg: bytes):
        espera = self.fotos_esperadas.get(pedido)
        if espera is not None and not espera.done():
            espera.set_result(jpeg or None)   # vazio = o celular não conseguiu tirar a foto

    async def pedir_foto(self, contagem=0, mostrar=False, para_web=False):
        """Pede uma foto grande ao celular e espera ela chegar (ou None)."""
        if self.rosto is None or not self.visao.ligada or not self.camera_ok:
            return None
        pedido = uuid.uuid4().hex[:10]
        espera = asyncio.get_running_loop().create_future()
        self.fotos_esperadas[pedido] = espera
        await self.enviar({"tipo": "tirar_foto", "pedido": pedido, "contagem": contagem,
                           "mostrar": mostrar, "para_web": para_web})
        try:
            return await asyncio.wait_for(espera, timeout=contagem + 8)
        except asyncio.TimeoutError:
            print("[robô] o celular não mandou a foto a tempo")
            return None
        finally:
            self.fotos_esperadas.pop(pedido, None)

    def frase_sem_camera(self) -> str:
        """Explica POR QUE o robô não está enxergando (e escreve a dica na janela do computador)."""
        if not self.visao.ligada:
            print("[robô] a visão está desligada: veja as mensagens [visão] quando o robô liga "
                  "(VISAO_LIGADA no config.py ou falta baixar os modelos)")
            return "A minha visão está desligada no computador."
        if self.camera_erro in ("NotAllowedError", "PermissionDeniedError", "SecurityError"):
            print("[robô] o Chrome do celular bloqueou a câmera: cadeado > Permissões > Câmera")
            return "O celular não me deu permissão para usar a câmera."
        if self.camera_erro in ("NotReadableError", "TrackStartError", "AbortError"):
            print("[robô] a câmera do celular está ocupada por outro aplicativo")
            return "Outro aplicativo está usando a câmera do celular."
        if self.camera_erro:
            print(f"[robô] a câmera do celular deu erro: {self.camera_erro}")
            return "A câmera do celular deu um erro."
        print("[robô] o celular nunca avisou da câmera: provavelmente está com a página antiga. "
              "Recarregue a página do rosto no celular.")
        return "O celular ainda não ligou a câmera. Recarregue a minha página no celular."

    async def cumprimentar(self, nome):
        try:
            modelos = config.CUMPRIMENTOS if nome else config.CUMPRIMENTOS_DESCONHECIDOS
            frase = random.choice(modelos).format(nome=nome)
            print(f"[robô] vi {nome or 'alguém'} chegando")
            await self.falar(lambda: [frase], expressao="alegria" if nome else None)
        except Exception:
            traceback.print_exc()
            await self.dormir()

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
                await self.expressao("duvida", 2)
                await self.dormir()
                return
            await self.enviar({"tipo": "fechar_cartao"})   # o cartão da resposta anterior
            await self.enviar({"tipo": "legenda", "quem": "pessoa", "texto": texto})
            if await self.executar_comando(texto):
                return
            contexto = self.contexto_de_quem_esta_aqui()
            falou = await self.falar(lambda: self.cerebro.responder(texto, contexto=contexto))
            if not falou:
                await self.dormir()
        except Exception as erro:
            print(f"[robô] erro: {erro}")
            traceback.print_exc()      # mostra o caminho completo do erro na janela
            self.dormir_depois_de_falar = True
            try:
                await self.falar(lambda: [FRASE_DE_ERRO], expressao="duvida")
            except Exception:
                traceback.print_exc()
                await self.dormir()

    # ---------- pedidos que o robô resolve sozinho ----------
    async def executar_comando(self, texto: str) -> bool:
        """Se o texto for um comando (comandos.py), executa e devolve True."""
        esperando_nome = time.time() < self.esperando_nome_ate
        self.esperando_nome_ate = 0.0
        comando, valor = comandos.entender(texto, list(self.visao.pessoas), esperando_nome)
        if comando is None:
            return False
        print(f"[robô] comando: {comando} {valor or ''}")
        reconhece = self.visao.ligada and self.visao.reconhecedor is not None

        if comando == "cancelar":
            await self.falar(lambda: ["Tudo bem, fica para outra hora."])
        elif comando in ("aprender", "nome") and not reconhece:
            await self.falar(lambda: ["Meu reconhecimento de rostos está desligado."])
        elif comando == "aprender" and not valor:
            self.esperando_nome_ate = time.time() + 30
            await self.falar(lambda: ["Claro! Como você se chama?"])
        elif comando in ("aprender", "nome"):
            if valor:
                await self.cadastrar_rosto(valor)
            else:
                await self.falar(lambda: ["Não entendi o seu nome. Peça de novo: aprende meu rosto."],
                                 expressao="duvida")
        elif comando == "esquecer":
            await self.esquecer_rosto(valor)
        elif comando == "quem":
            await self.falar(lambda: [self.frase_de_quem_esta_aqui()])
        elif comando == "foto":
            await self.tirar_foto()
        elif comando == "olhar":
            await self.olhar(texto)
        elif comando == "mostrar":
            await self.mostrar_imagem(valor)
        elif comando == "outra":
            await self.mostrar_imagem(None)
        elif comando == "fechar":
            await self.enviar({"tipo": "fechar_imagem"})
            await self.enviar({"tipo": "fechar_cartao"})
            await self.acordar()
        return True

    async def mostrar_imagem(self, assunto):
        """Busca na Wikipédia e no Commons, confere com a IA e mostra na tela do celular.
        assunto=None: "mostra outra" (a próxima da última busca)."""
        if not self.imagens.ligada:
            await self.falar(lambda: ["A busca de imagens está desligada no computador."])
            return
        conferir = config.IMAGENS_VERIFICAR_COM_IA and self.cerebro.pode_olhar_na_web()
        if assunto:
            try:
                await asyncio.to_thread(self.imagens.buscar, assunto, conferir)
            except WikipediaRecusou as erro:
                print(f"[imagens] a Wikipédia recusou a busca ({erro}). Se for erro 403, "
                      "preencha IMAGENS_CONTATO no config.py e reinicie o robô.")
                await self.falar(lambda: ["A Wikipédia recusou a minha busca. "
                                          "O professor pode ver o motivo na tela do computador."])
                return
            except Exception as erro:
                print(f"[imagens] a busca falhou: {type(erro).__name__}: {erro}")
                await self.falar(lambda: ["Não consegui falar com a Wikipédia agora. Será que a internet caiu?"])
                return
        elif self.imagens.tem_mais():
            assunto = self.imagens.termo
        else:
            await self.falar(lambda: ["Não tenho outra imagem. Peça de novo, por exemplo: mostra uma placa-mãe."])
            return

        if config.IMAGENS_VERIFICAR_COM_IA and not conferir:
            print("[imagens] atenção: sem a IA da web, as imagens aparecem sem ninguém conferir")
        imagem, resultado = None, None
        for _ in range(4):   # tenta até 4 imagens da lista
            imagem, resultado = await asyncio.to_thread(self.imagens.proxima)
            if imagem is None:
                break
            if not conferir or await asyncio.to_thread(self.cerebro.conferir_imagem, assunto, imagem):
                break
            imagem = None
        if imagem is None:
            await self.falar(lambda: [f"Não achei uma boa imagem de {assunto}."], expressao="duvida")
            return

        fonte = resultado.get("domain") or resultado.get("source") or ""
        print(f"[imagens] mostrando '{assunto}' de {fonte}")
        await self.enviar({"tipo": "mostrar_imagem", "legenda": assunto, "fonte": fonte,
                           "segundos": config.IMAGENS_SEGUNDOS_NA_TELA,
                           "imagem": "data:image/jpeg;base64," + base64.b64encode(imagem).decode("ascii")})
        if config.IMAGENS_EXPLICAR and self.cerebro.pode_olhar_na_web():
            pedido = f"Mostra {assunto}."
            origem = (f"do artigo {resultado['titulo']} da Wikipédia" if resultado["origem"] == "wikipedia"
                      else f"chamada {resultado['titulo']}, do Wikimedia Commons")
            instrucao = (f"Você mostrou na sua tela esta imagem de {assunto}, {origem}. "
                         "Explique para a turma, em uma ou duas frases faladas, o que é e para que serve, "
                         "comentando o que aparece na imagem.")
            falou = await self.falar(lambda: self.cerebro.responder(pedido, foto=imagem, instrucao_da_foto=instrucao))
            if not falou:
                await self.dormir()
        else:
            await self.falar(lambda: [f"Olha aqui: {assunto}."])
        # a imagem não é gravada em lugar nenhum: some da memória quando esta função termina

    async def cadastrar_rosto(self, nome: str):
        if not self.camera_ok:
            await self.falar(lambda: [self.frase_sem_camera()])
            return
        self.coleta = []
        # terminar=False: o robô continua "falando" (sem ouvir) enquanto junta as fotos
        await self.falar(lambda: [f"Muito prazer, {nome}! Olhe para a minha tela e fique paradinho."],
                         terminar=False)
        limite = time.time() + 10
        while len(self.coleta) < config.VISAO_FOTOS_POR_CADASTRO and time.time() < limite:
            await asyncio.sleep(0.2)
        assinaturas, self.coleta = self.coleta, None
        if len(assinaturas) >= max(2, config.VISAO_FOTOS_POR_CADASTRO // 2):
            nome = self.visao.cadastrar(nome, assinaturas)
            await self.falar(lambda: [f"Pronto! Agora eu sei quem você é, {nome}."], expressao="alegria")
        else:
            await self.falar(lambda: ["Não consegui ver bem o seu rosto. Fique sozinho na frente da "
                                      "câmera, bem de frente para mim, e peça de novo."], expressao="duvida")

    async def esquecer_rosto(self, nome):
        if nome is None:   # "esquece meu rosto": quem está mais perto da câmera
            atual = self.presenca.quem_esta_aqui(time.time())
            nome = atual[0][0] if atual and atual[0] else None
            if nome is None:
                await self.falar(lambda: ["Não estou reconhecendo ninguém na minha frente agora."])
                return
        apagado = self.visao.esquecer(nome) if nome != "?" else None
        if apagado:
            await self.falar(lambda: [f"Pronto, esqueci o rosto de {apagado}."])
        else:
            await self.falar(lambda: ["Não conheço ninguém com esse nome."], expressao="duvida")

    def frase_de_quem_esta_aqui(self) -> str:
        atual = self.presenca.quem_esta_aqui(time.time()) if self.visao.ligada else None
        if atual is None:
            return self.frase_sem_camera()
        nomes, desconhecidos = atual
        if not nomes and not desconhecidos:
            return "Não estou vendo ninguém na minha frente."
        partes = list(nomes)
        if desconhecidos:
            alguem = "uma pessoa" if desconhecidos == 1 else f"{desconhecidos} pessoas"
            partes.append(f"{alguem} que eu ainda não conheço" if nomes else alguem)
        lista = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]
        if len(nomes) == 1 and not desconhecidos:
            return f"Você é {nomes[0]}!"
        if not nomes:
            return f"Estou vendo {lista}, mas não sei quem é." if desconhecidos == 1 else \
                   f"Estou vendo {lista}, mas não conheço ninguém."
        return f"Estou vendo {lista}."

    def contexto_de_quem_esta_aqui(self):
        """Recado para a IA: quem o robô reconhece na frente da câmera agora."""
        if not (self.visao.ligada and config.VISAO_CONTAR_NOMES_PARA_IA):
            return None
        atual = self.presenca.quem_esta_aqui(time.time())
        if not atual or not atual[0]:
            return None
        return "Pessoas que você reconhece na frente da câmera agora: " + ", ".join(atual[0])

    async def tirar_foto(self):
        if not self.camera_ok:
            await self.falar(lambda: [self.frase_sem_camera()])
            return
        foto = await self.pedir_foto(contagem=3, mostrar=True)
        if foto is None:
            await self.falar(lambda: ["Ih, não consegui tirar a foto."], expressao="duvida")
            return
        os.makedirs(config.PASTA_DE_FOTOS, exist_ok=True)
        arquivo = os.path.join(config.PASTA_DE_FOTOS, time.strftime("%Y-%m-%d_%H-%M-%S") + ".jpg")
        with open(arquivo, "wb") as f:
            f.write(foto)
        print(f"[robô] foto guardada em {arquivo}")
        await self.falar(lambda: ["Prontinho! Guardei a foto."], expressao="alegria")

    async def olhar(self, pergunta: str):
        if not self.camera_ok:
            await self.falar(lambda: [self.frase_sem_camera()])
            return
        vai_para_web = (self.cerebro.modo == "web" and bool(self.cerebro.chave_web)
                        and config.VISAO_FOTO_PARA_WEB)
        if not vai_para_web and not config.VISAO_MODELO_LOCAL:
            await self.falar(lambda: ["Desculpe, agora eu não consigo enxergar. "
                                      "Para olhar as coisas eu preciso de internet."])
            return
        foto = await self.pedir_foto(mostrar=True, para_web=vai_para_web)
        if foto is None:
            await self.falar(lambda: ["Ih, não consegui usar a câmera."])
            return
        foto = await asyncio.to_thread(self.visao.reduzir, foto)
        contexto = self.contexto_de_quem_esta_aqui()
        falou = await self.falar(lambda: self.cerebro.responder(pergunta, foto=foto, contexto=contexto))
        if not falou:
            await self.dormir()

    async def falar(self, gerar_frases, terminar=True, expressao=None) -> bool:
        """Pede as frases ao cérebro, transforma cada uma em áudio e manda para o celular.
        Enquanto o celular toca uma frase, o computador já prepara a próxima.
        As marcas da IA (expressões e cartões) entram na mesma fila do áudio, para o celular
        mostrar cada uma na hora certa da fala.
        terminar=False: não avisa o fim da fala (o robô ainda vai falar mais em seguida).
        expressao: a expressão do rosto durante esta fala."""
        fila = asyncio.Queue()
        laco = asyncio.get_running_loop()

        def trabalhar():  # roda numa linha de execução separada
            try:
                for frase in gerar_frases():
                    if isinstance(frase, dict):
                        laco.call_soon_threadsafe(fila.put_nowait, frase)
                        continue
                    audio = self.voz.falar(frase)
                    if audio is None:
                        continue  # frase sem nada para falar (ex.: só marcas <think>)
                    laco.call_soon_threadsafe(fila.put_nowait, (limpar_texto(frase), audio))
            finally:
                laco.call_soon_threadsafe(fila.put_nowait, None)  # sinal de "acabou"

        inicio = time.time()
        if expressao:
            await self.expressao(expressao, na_fila=True)
        trabalho = asyncio.create_task(asyncio.to_thread(trabalhar))
        falou = False
        while True:
            item = await fila.get()
            if item is None:
                break
            if isinstance(item, dict):
                await self.mandar_marca(item)
                continue
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
        if falou and terminar:
            await self.enviar({"tipo": "fim_da_fala"})
        return falou

    async def mandar_marca(self, marca: dict):
        """Um pedido da IA para o rosto (veja marcas.py)."""
        if marca["tipo"] == "expressao":
            await self.expressao(marca["nome"], na_fila=True)
        elif marca["itens"]:
            print(f"[robô] na tela: {marca['titulo']} ({len(marca['itens'])} itens)")
            await self.enviar({"tipo": "mostrar_cartao", "modelo": marca["modelo"], "titulo": marca["titulo"],
                               "itens": marca["itens"], "segundos": config.TELA_SEGUNDOS_NA_TELA, "na_fila": True})
