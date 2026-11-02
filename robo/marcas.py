"""
MARCAS (o que a IA pede para o rosto fazer, sem falar em voz alta)
==================================================================
A IA da web escreve marcas entre colchetes no meio da resposta:

  [alegria]  [duvida]  [surpresa]  [sono]        muda a expressão do rosto
  [lista: Título | item | item]                  lista na tela
  [passos: Título | primeiro | segundo]          passos numerados na tela
  [texto: Título | uma palavra, comando ou conta] texto grande na tela

O leitor abaixo tira as marcas do texto, para a voz e as legendas nunca lerem
"colchete alegria", e entrega cada uma ao robô no momento certo da fala.
A resposta chega aos pedacinhos, então uma marca pode vir cortada no meio:
o leitor segura o trecho até o "]" chegar.

Teste sozinho:   python -m robo.marcas "[alegria] Oi! [lista: Cores | azul | verde] Tudo bem?"
"""

import re
import sys

from robo.visao import normalizar

EXPRESSOES = ("alegria", "duvida", "surpresa", "sono")
MODELOS_DE_CARTAO = ("lista", "passos", "texto")
MAXIMO_DE_ITENS = 8
MAXIMO_DE_LETRAS_NO_TITULO = 60
MAXIMO_DE_LETRAS_NO_ITEM = 90
MAXIMO_DE_LETRAS_NA_MARCA = 700  # sem "]" até aqui, não era uma marca de verdade

INSTRUCAO_DE_EXPRESSOES = """
Expressão do rosto: comece a resposta com uma destas marcas, se alguma combinar com o que você vai dizer:
[alegria] para boas notícias, elogios e brincadeiras; [duvida] quando não tiver certeza ou não entender; [surpresa] para curiosidades impressionantes; [sono] se falarem de cansaço ou de dormir.
Se nenhuma combinar, não use marca."""

INSTRUCAO_DA_TELA = """
Tela: quando a resposta tiver etapas, itens ou uma palavra importante, escreva uma marca de tela antes da fala, numa linha só:
[passos: Título | primeiro passo | segundo passo] para um passo a passo.
[lista: Título | item | item] para vários itens.
[texto: Título | palavra, comando ou conta] para destacar uma coisa só.
Use no máximo uma marca de tela por resposta, com até 6 itens de até 6 palavras cada. Em cumprimentos e conversas simples, não use.
A tela é só um resumo: a sua fala continua sendo frases normais, sem ler a tela palavra por palavra.
Exemplo: [passos: Salvar um arquivo | Abra o menu Arquivo | Clique em Salvar | Escolha a pasta] Salvar é fácil! Primeiro abra o menu Arquivo, depois clique em Salvar e escolha a pasta."""

INSTRUCAO_COMUM = """

Marcas: tudo que estiver entre colchetes é para o seu rosto e a sua tela, e nunca é falado. Só use as marcas abaixo."""


def instrucao(expressoes=True, tela=True) -> str:
    """O trecho que ensina a IA a usar as marcas (vazio se as duas estiverem desligadas)."""
    if not expressoes and not tela:
        return ""
    return (INSTRUCAO_COMUM + (INSTRUCAO_DE_EXPRESSOES if expressoes else "")
            + (INSTRUCAO_DA_TELA if tela else ""))


def entender_marca(conteudo: str):
    """ "alegria" ou "lista: Cores | azul" -> o pedido para o rosto. None = marca desconhecida."""
    nome, separador, resto = conteudo.partition(":")
    nome = normalizar(nome).strip()
    if nome in EXPRESSOES and not separador:
        return {"tipo": "expressao", "nome": nome}
    if nome in MODELOS_DE_CARTAO and separador:
        partes = [p.strip() for p in resto.split("|")]
        partes = [p for p in partes if p]
        if not partes:
            return None
        if len(partes) == 1:   # só uma parte: é o conteúdo, sem título
            partes = [""] + partes
        return {"tipo": "cartao", "modelo": nome,
                "titulo": partes[0][:MAXIMO_DE_LETRAS_NO_TITULO],
                "itens": [p[:MAXIMO_DE_LETRAS_NO_ITEM] for p in partes[1:1 + MAXIMO_DE_ITENS]]}
    return None


class LeitorDeMarcas:
    """Recebe a resposta aos pedacinhos e separa o que é fala do que é marca."""

    def __init__(self):
        self.guardado = ""

    def ler(self, texto: str) -> list:
        """Devolve uma lista, em ordem: textos (para falar) e dicionários (marcas)."""
        self.guardado += texto
        saida = []
        while self.guardado:
            inicio = self.guardado.find("[")
            if inicio < 0:
                saida.append(self.guardado)
                self.guardado = ""
                break
            if inicio > 0:
                saida.append(self.guardado[:inicio])
                self.guardado = self.guardado[inicio:]
            fim = self.guardado.find("]")
            if fim < 0:
                if len(self.guardado) > MAXIMO_DE_LETRAS_NA_MARCA:
                    self.guardado = ""   # nunca fechou: joga fora em vez de falar colchetes
                break
            marca = entender_marca(self.guardado[1:fim])
            if marca:
                saida.append(marca)
            self.guardado = self.guardado[fim + 1:]
        return saida

    def terminar(self):
        """Fim da resposta. Uma marca cortada no meio é descartada, nunca falada."""
        self.guardado = ""


def limpar_marcas(texto: str) -> str:
    """Tira todas as marcas de um texto inteiro."""
    return re.sub(r"\s*\[[^\[\]]*\]?", " ", texto).strip()


# ---- Teste: python -m robo.marcas "texto com [marcas]" ----
if __name__ == "__main__":
    leitor = LeitorDeMarcas()
    for item in leitor.ler(" ".join(sys.argv[1:])):
        print(repr(item))
