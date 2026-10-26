"""
CÉREBRO (a inteligência do robô)
================================
Dois jeitos de pensar (escolha no config.py, em CEREBRO):
  - "local": IA no próprio computador, pelo Ollama. Funciona sem internet.
  - "web":   IA na internet (Gemini, Groq, OpenAI...). Mais esperta, precisa de internet
             e de uma chave. Se a internet falhar, o robô usa o cérebro local sozinho.

Entrada: o que a pessoa disse.  Saída: a resposta, frase por frase
(assim o robô já começa a falar a primeira frase enquanto pensa na próxima).

Teste sozinho:   python -m robo.cerebro
"""

import json
import os
import re
import time

import httpx
import ollama

from robo import config


class Cerebro:
    def __init__(self):
        with open(config.ARQUIVO_PERSONALIDADE, encoding="utf-8") as f:
            self.personalidade = f.read()
        self.memoria = []  # lista das últimas mensagens da conversa
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

    # ---------- cérebro local (Ollama) ----------
    def _local(self, mensagens, tamanho=None):
        """Devolve a resposta da IA local em pedacinhos de texto."""
        # "criatividade" (temperature): 0 = sempre a resposta mais provável; alto = varia e inventa mais
        opcoes = {"num_predict": tamanho or config.TAMANHO_MAXIMO_DA_RESPOSTA,
                  "num_ctx": 2048, "temperature": getattr(config, "CRIATIVIDADE", 0.3)}
        extras = {}
        if config.MODELO_IA.startswith("qwen3"):
            # desliga o "pensar em voz alta" do Qwen3, que só deixaria o robô mais lento
            extras["think"] = False
        # keep_alive=-1: o Ollama nunca tira o cérebro da memória (recarregar demora)
        try:
            partes = ollama.chat(model=config.MODELO_IA, messages=mensagens, stream=True,
                                 options=opcoes, keep_alive=-1, **extras)
        except TypeError:
            # versões antigas da biblioteca não conhecem o "think"
            partes = ollama.chat(model=config.MODELO_IA, messages=mensagens, stream=True,
                                 options=opcoes, keep_alive=-1)
        for parte in partes:
            yield parte["message"]["content"] or ""

    # ---------- cérebro na web ----------
    def _web(self, mensagens):
        """Devolve a resposta da IA da web em pedacinhos de texto (formato compatível com OpenAI)."""
        endereco = config.WEB_ENDERECO.rstrip("/") + "/chat/completions"
        cabecalho = {"Authorization": f"Bearer {self.chave_web}", "Content-Type": "application/json"}
        corpo = {
            "model": config.WEB_MODELO,
            "messages": mensagens,
            "stream": True,
            "max_tokens": config.TAMANHO_MAXIMO_DA_RESPOSTA,
            "temperature": getattr(config, "CRIATIVIDADE", 0.3),
        }
        corpo.update(getattr(config, "WEB_OPCOES_EXTRAS", {}))
        with httpx.stream("POST", endereco, headers=cabecalho, json=corpo,
                          timeout=getattr(config, "WEB_TEMPO_MAXIMO", 15)) as resposta:
            resposta.raise_for_status()
            for linha in resposta.iter_lines():
                if not linha.startswith("data:"):
                    continue
                dado = linha[5:].strip()
                if dado == "[DONE]":
                    break
                escolhas = json.loads(dado).get("choices") or [{}]
                yield (escolhas[0].get("delta") or {}).get("content") or ""

    def _pensar(self, mensagens):
        """Usa a IA da web quando escolhida; se ela falhar antes de responder, usa a local."""
        if self.modo == "web" and self.chave_web:
            ja_respondeu = False
            try:
                for texto in self._web(mensagens):
                    ja_respondeu = True
                    yield texto
                return
            except Exception as erro:
                print(f"[cérebro] a IA da web falhou: {erro}")
                if ja_respondeu or not getattr(config, "WEB_SE_FALHAR_USAR_LOCAL", True):
                    return
                print("[cérebro] usando o cérebro local desta vez")
        yield from self._local(mensagens)

    # ---------- o que o resto do robô usa ----------
    def responder(self, pergunta: str):
        """Gera a resposta em pedaços: cada 'yield' é uma frase pronta para falar."""
        mensagens = [{"role": "system", "content": self.personalidade}]
        mensagens += self.memoria
        mensagens.append({"role": "user", "content": pergunta})

        resposta_inteira = ""
        pedaco = ""
        for texto in self._pensar(mensagens):
            resposta_inteira += texto
            pedaco += texto
            # Quando aparece um fim de frase (e a frase não é curtinha), entrega para a voz
            while True:
                corte = next((m.end() for m in re.finditer(r"[.!?:;\n]\s", pedaco) if m.end() >= 20), None)
                if corte is None:
                    break
                frase, pedaco = pedaco[:corte].strip(), pedaco[corte:]
                if frase:
                    yield frase
        if pedaco.strip():
            yield pedaco.strip()

        # Guarda a troca na memória e descarta o que for muito antigo
        self.memoria.append({"role": "user", "content": pergunta})
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
            print(frase, end=" ", flush=True)
        print(f"\n({time.time() - inicio:.1f} s)\n")
