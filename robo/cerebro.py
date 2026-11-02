"""
CÉREBRO (a inteligência do robô)
================================
Dois jeitos de pensar (escolha no config.py, em CEREBRO):
  - "local": IA no próprio computador, pelo Ollama. Funciona sem internet.
  - "web":   IA na internet (Gemini, Groq, OpenAI...). Mais esperta, precisa de internet
             e de uma chave. Se a internet falhar, o robô usa o cérebro local sozinho.

Também sabe olhar uma foto (quando a pessoa pergunta "o que você está vendo?"):
a foto vai para a IA da web; sem internet, para um modelo local com visão, se houver.

Entrada: o que a pessoa disse.  Saída: a resposta, frase por frase
(assim o robô já começa a falar a primeira frase enquanto pensa na próxima).
No meio das frases podem vir pedidos para o rosto (expressões e cartões na tela):
veja marcas.py. Só a IA da web recebe essa instrução: o cérebro local é pequeno
demais para seguir as duas coisas ao mesmo tempo.

Teste sozinho:   python -m robo.cerebro
"""

import base64
import json
import os
import re
import time

import httpx
import ollama

from robo import config
from robo.marcas import LeitorDeMarcas, instrucao, limpar_marcas


INSTRUCAO_DA_FOTO = ("Você acabou de tirar esta foto com a câmera que fica no seu rosto, olhando para a sala. "
                     "Responda à pergunta olhando a foto, em poucas frases faladas. "
                     "Se a pergunta for sobre alguém, fale do que a pessoa está fazendo ou segurando, "
                     "nunca da aparência do corpo dela.")
SEM_VISAO = "Desculpe, agora eu não consigo enxergar. Para olhar as coisas eu preciso de internet."


class Cerebro:
    def __init__(self):
        with open(config.ARQUIVO_PERSONALIDADE, encoding="utf-8") as f:
            self.personalidade = f.read()
        self.memoria = []  # lista das últimas mensagens da conversa
        self.ajustes_recusados = {}  # modelo da web -> ajustes que ele não aceita
        self.modo = getattr(config, "CEREBRO", "local")
        self.chave_web = self._ler_chave_web() if self.modo == "web" else None
        if self.modo == "web":
            print(f"[cérebro] usando a IA da web: {config.WEB_MODELO} (reserva: {config.MODELO_IA})")
        else:
            print(f"[cérebro] usando o modelo local {config.MODELO_IA}")
        self._aquecer()  # o cérebro local fica pronto mesmo no modo web, como reserva

    # ---------- preparação ----------
    def _ler_chave_web(self):
        arquivo = getattr(config, "WEB_ARQUIVO_DA_CHAVE", "chave_web.txt")
        if not os.path.exists(arquivo):
            print(f"[cérebro] atenção: não achei o arquivo {arquivo} com a chave da IA da web; "
                  "vou usar o cérebro local.")
            return None
        with open(arquivo, encoding="utf-8") as f:
            return f.read().strip()

    def _aquecer(self):
        """Carrega a IA local na memória e já faz ela ler a personalidade.
        O Ollama guarda essa leitura, então as próximas respostas começam mais rápido."""
        print("[cérebro] aquecendo o cérebro local (lendo a personalidade)...")
        inicio = time.time()
        try:
            mensagens = [{"role": "system", "content": self.personalidade},
                         {"role": "user", "content": "Oi"}]
            for _ in self._local(mensagens, tamanho=1):
                pass
            print(f"[cérebro] pronto em {time.time() - inicio:.1f} s")
        except Exception as erro:
            print(f"[cérebro] não consegui aquecer: {erro}")

    def esquecer(self):
        """Apaga a memória da conversa (por exemplo, ao começar outra aula)."""
        self.memoria = []

    # ---------- marcas (expressões e cartões): só para a IA da web ----------
    @staticmethod
    def _com_marcas(mensagens):
        extra = instrucao(getattr(config, "ROSTO_IA_ESCOLHE_EXPRESSAO", True),
                          getattr(config, "TELA_IA_PODE_MOSTRAR", True))
        return [{**mensagens[0], "content": mensagens[0]["content"] + extra}] + mensagens[1:]

    @staticmethod
    def _sem_marcas(mensagens):
        """Para o cérebro local não imitar as marcas que estão na memória da conversa."""
        return [{**m, "content": limpar_marcas(m["content"])} if m["role"] == "assistant" else m
                for m in mensagens]

    # ---------- cérebro local (Ollama) ----------
    def _local(self, mensagens, tamanho=None, modelo=None):
        """Devolve a resposta da IA local em pedacinhos de texto."""
        modelo = modelo or config.MODELO_IA
        # "criatividade" (temperature): 0 = sempre a resposta mais provável; alto = varia e inventa mais
        opcoes = {"num_predict": tamanho or config.TAMANHO_MAXIMO_DA_RESPOSTA,
                  "num_ctx": 2048, "temperature": getattr(config, "CRIATIVIDADE", 0.3)}
        if modelo == config.MODELO_IA:
            # ajustes próprios do cérebro local (os mesmos do Modelfile), que valem mais que os de cima
            opcoes.update(getattr(config, "MODELO_IA_OPCOES", {}))
        extras = {}
        if modelo.startswith("qwen3"):
            # desliga o "pensar em voz alta" do Qwen3, que só deixaria o robô mais lento
            extras["think"] = False
        # keep_alive=-1: o Ollama nunca tira o cérebro da memória (recarregar demora)
        try:
            partes = ollama.chat(model=modelo, messages=mensagens, stream=True,
                                 options=opcoes, keep_alive=-1, **extras)
        except TypeError:
            # versões antigas da biblioteca não conhecem o "think"
            partes = ollama.chat(model=modelo, messages=mensagens, stream=True,
                                 options=opcoes, keep_alive=-1)
        for parte in partes:
            yield parte["message"]["content"] or ""

    # ---------- cérebro na web ----------
    def _web(self, mensagens, modelo=None, tempo_maximo=None):
        """Devolve a resposta da IA da web em pedacinhos de texto (formato compatível com OpenAI).
        Alguns modelos (os mais novos da OpenAI, por exemplo) recusam "max_tokens" ou "temperature".
        Quando isso acontece, o robô tira o ajuste recusado, tenta de novo e lembra para as próximas."""
        endereco = config.WEB_ENDERECO.rstrip("/") + "/chat/completions"
        cabecalho = {"Authorization": f"Bearer {self.chave_web}", "Content-Type": "application/json"}
        modelo = modelo or config.WEB_MODELO
        recusados = self.ajustes_recusados.setdefault(modelo, set())
        for _tentativa in range(3):
            corpo = {"model": modelo, "messages": mensagens, "stream": True}
            if "max_tokens" in recusados:
                corpo["max_completion_tokens"] = config.TAMANHO_MAXIMO_DA_RESPOSTA
            else:
                corpo["max_tokens"] = config.TAMANHO_MAXIMO_DA_RESPOSTA
            if "temperature" not in recusados:
                corpo["temperature"] = getattr(config, "CRIATIVIDADE", 0.3)
            corpo.update(getattr(config, "WEB_OPCOES_EXTRAS", {}))
            with httpx.stream("POST", endereco, headers=cabecalho, json=corpo,
                              timeout=tempo_maximo or getattr(config, "WEB_TEMPO_MAXIMO", 15)) as resposta:
                if resposta.status_code == 400:
                    erro = resposta.read().decode("utf-8", "replace")
                    novo = next((a for a in ("max_tokens", "temperature")
                                 if a in erro and a not in recusados), None)
                    if novo:
                        print(f"[cérebro] o modelo {modelo} não aceita '{novo}'; tentando sem ele")
                        recusados.add(novo)
                        continue
                    raise RuntimeError(f"a IA da web recusou o pedido: {erro[:300]}")
                resposta.raise_for_status()
                for linha in resposta.iter_lines():
                    if not linha.startswith("data:"):
                        continue
                    dado = linha[5:].strip()
                    if dado == "[DONE]":
                        break
                    escolhas = json.loads(dado).get("choices") or [{}]
                    yield (escolhas[0].get("delta") or {}).get("content") or ""
                return

    def _pensar(self, mensagens):
        """Usa a IA da web quando escolhida; se ela falhar antes de responder, usa a local."""
        if self.modo == "web" and self.chave_web:
            ja_respondeu = False
            try:
                for texto in self._web(self._com_marcas(mensagens)):
                    ja_respondeu = True
                    yield texto
                return
            except Exception as erro:
                print(f"[cérebro] a IA da web falhou: {erro}")
                if ja_respondeu or not getattr(config, "WEB_SE_FALHAR_USAR_LOCAL", True):
                    return
                print("[cérebro] usando o cérebro local desta vez")
        yield from self._local(self._sem_marcas(mensagens))

    def _olhar(self, mensagens, foto: bytes, instrucao=None):
        """Como _pensar, mas a última mensagem vai junto com a foto."""
        pedido = (instrucao or INSTRUCAO_DA_FOTO) + "\n\n" + mensagens[-1]["content"]
        anteriores = mensagens[:-1]
        if self.modo == "web" and self.chave_web and getattr(config, "VISAO_FOTO_PARA_WEB", True):
            foto_em_texto = base64.b64encode(foto).decode("ascii")
            com_foto = self._com_marcas(anteriores) + [{"role": "user", "content": [
                {"type": "text", "text": pedido},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + foto_em_texto}},
            ]}]
            ja_respondeu = False
            try:
                for texto in self._web(com_foto, modelo=getattr(config, "VISAO_WEB_MODELO", None),
                                       tempo_maximo=getattr(config, "VISAO_TEMPO_MAXIMO_WEB", 25)):
                    ja_respondeu = True
                    yield texto
                return
            except Exception as erro:
                print(f"[cérebro] a IA da web não conseguiu olhar a foto: {erro}")
                if ja_respondeu:
                    return
        modelo_local = getattr(config, "VISAO_MODELO_LOCAL", None)
        if modelo_local:
            print(f"[cérebro] olhando a foto com o modelo local {modelo_local} (demora)")
            yield from self._local(self._sem_marcas(anteriores) + [{"role": "user", "content": pedido, "images": [foto]}],
                                   modelo=modelo_local)
        else:
            yield SEM_VISAO

    def pode_olhar_na_web(self):
        return self.modo == "web" and bool(self.chave_web)

    def conferir_imagem(self, assunto: str, foto: bytes) -> bool:
        """Pergunta à IA da web se a imagem mostra o assunto e serve para a aula.
        Na dúvida (ou se der erro), responde False: melhor não mostrar."""
        pergunta = (f'Esta imagem vai aparecer numa aula de informática com crianças e adolescentes, '
                    f'para mostrar "{assunto}". Ela mostra mesmo isso, de um jeito claro, e é adequada '
                    f'para a turma (sem violência, nudez, palavrões ou propaganda chamativa)? '
                    f'Responda só SIM ou NAO.')
        conteudo = [{"type": "text", "text": pergunta},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
                                                        base64.b64encode(foto).decode("ascii")}}]
        try:
            texto = "".join(self._web([{"role": "user", "content": conteudo}],
                                      modelo=getattr(config, "VISAO_WEB_MODELO", None),
                                      tempo_maximo=getattr(config, "VISAO_TEMPO_MAXIMO_WEB", 25)))
        except Exception as erro:
            print(f"[cérebro] não consegui conferir a imagem: {erro}")
            return False
        resposta = texto.strip().upper()
        print(f"[cérebro] a imagem serve para '{assunto}'? {resposta[:20]}")
        return resposta.startswith("SIM")

    # ---------- o que o resto do robô usa ----------
    def responder(self, pergunta: str, foto: bytes = None, contexto: str = None, instrucao_da_foto: str = None):
        """Gera a resposta em pedaços: cada 'yield' é uma frase pronta para falar
        (texto) ou um pedido para o rosto (dicionário: veja marcas.py).
        foto: imagem JPEG para a IA olhar.  contexto: um recado extra, por exemplo quem está na sala."""
        mensagens = [{"role": "system", "content": self.personalidade}]
        mensagens += self.memoria
        mensagens.append({"role": "user", "content": f"{pergunta}\n\n({contexto})" if contexto else pergunta})

        resposta_inteira = ""
        pedaco = ""
        leitor = LeitorDeMarcas()
        for texto in (self._olhar(mensagens, foto, instrucao_da_foto) if foto else self._pensar(mensagens)):
            resposta_inteira += texto
            for item in leitor.ler(texto):
                if isinstance(item, dict):
                    yield item
                else:
                    pedaco += item
            # Quando aparece um fim de frase (e a frase não é curtinha), entrega para a voz
            while True:
                corte = next((m.end() for m in re.finditer(r"[.!?:;\n]\s", pedaco) if m.end() >= 20), None)
                if corte is None:
                    break
                frase, pedaco = pedaco[:corte].strip(), pedaco[corte:]
                if frase:
                    yield frase
        leitor.terminar()
        if pedaco.strip():
            yield pedaco.strip()

        # Guarda a troca na memória e descarta o que for muito antigo
        # (a foto não fica na memória: só um lembrete de que ele olhou)
        self.memoria.append({"role": "user", "content": pergunta + (" [você olhou uma foto da câmera]" if foto else "")})
        self.memoria.append({"role": "assistant", "content": resposta_inteira})
        self.memoria = self.memoria[-2 * config.TROCAS_NA_MEMORIA:]


# ---- Teste: python -m robo.cerebro ----
if __name__ == "__main__":
    cerebro = Cerebro()
    print("Converse com o robô pelo teclado. Digite 'sair' para terminar.\n")
    while True:
        pergunta = input("Você: ").strip()
        if pergunta.lower() == "sair":
            break
        inicio = time.time()
        print("Robô:", end=" ", flush=True)
        for frase in cerebro.responder(pergunta):
            print(frase if isinstance(frase, str) else f"\n  (para o rosto: {frase})\n", end=" ", flush=True)
        print(f"\n({time.time() - inicio:.1f} s)\n")
