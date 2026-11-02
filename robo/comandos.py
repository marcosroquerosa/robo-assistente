"""
COMANDOS (pedidos que o robô resolve sozinho, sem perguntar para a IA)
=====================================================================
Antes de mandar a pergunta para o cérebro, o robô confere se é um destes pedidos:

  aprender   "Byte, aprende meu rosto"      "meu nome é Ana, decora minha cara"
  esquecer   "esquece o rosto da Ana"       "apaga a Ana"     "esquece meu rosto"
  quem       "quem sou eu?"                 "quem você está vendo?"
  foto       "tira uma foto"                "bate uma selfie"
  olhar      "o que você está vendo?"       "lê o quadro"     "o que é isso na minha mão?"
  mostrar    "mostra uma placa-mãe"         "quero ver um processador"
  outra      "mostra outra"                 "a próxima"
  fechar     "fecha a imagem"               "limpa a tela"    "fecha a lista"

As frases são comparadas sem acentos e em minúsculas. Para o robô entender um jeito
novo de pedir, acrescente um padrão na lista certa (o \\b marca começo ou fim de palavra).

Teste sozinho:   python -m robo.comandos
"""

import re

from robo.visao import normalizar

APRENDER = [
    r"\b(aprend|memoriz|decor|grav|cadastr|guard|salv)\w* (o |a )?(meu|minha) (rosto|cara|nome)\b",
    r"\baprend\w* quem (eu sou|sou eu)\b",
]
ESQUECER = r"\b(esquec|apag|delet|remov)\w*\b"
QUEM = [
    r"\bquem (sou eu|e que eu sou|eu sou)\b",
    r"\bsabe quem (eu sou|sou eu)\b",
    r"\b(voce )?me conhece\b",
    r"\bqual (e )?(o )?meu nome\b",
    r"\bquem (esta|ta) (aqui|na sua frente|na frente)\b",
    r"\bquem (voce )?(esta |ta )?(vendo|ve|enxerga)\b",
    r"\bquantas pessoas (voce )?(esta |ta )?(vendo|ve|enxerga)\b",
]
FOTO = [
    r"\b(tira|tire|tirar|bate|bata|bater|faz|faca|fazer) (uma |um |a )?(foto|fotografia|selfie|retrato)\b",
    r"\bselfie\b",
]
OLHAR = [
    r"\bo que (e que )?(voce )?(esta |ta )?(vendo|enxergando)\b",
    r"\bo que voce ve\b",
    r"\b(olha|olhe|veja|repara) (isso|isto|aqui|so|esse|essa|este|esta|para|pra)\b",
    r"\bo que (e|tem) (isso|isto|aqui|na minha mao|nessa|nesta|neste|nesse)\b",
    r"\bque (objeto|coisa|animal|cor|planta|fruta|brinquedo|peca|marca|bicho) (e|eh) (essa|esse|esta|este|isso|isto)\b",
    r"\b(le|leia|ler) (o que esta |o que ta |o que )?(escrito|no quadro|o quadro|a lousa|na lousa|isso|isto|aqui|essa|esse|este|esta)\b",
    r"\bdescrev\w* (o que (voce )?(esta |ta )?(vendo|ve)|isso|isto|a sala|o ambiente|a foto|a turma)\b",
    r"\b(consegue|pode) (me )?(ver|enxergar)\b",
    r"\bna minha mao\b",
    r"\bquantos dedos\b",
]
MOSTRAR = [
    r"\b(me )?(mostra|mostre|mostrar|exibe|exiba|apresenta|apresente)( pra mim| para mim| pra gente| pra turma| para a turma)?"
    r"( uma imagem| uma foto| uma figura| a imagem| a foto| imagens| fotos| umas fotos)?( de| do| da| dos| das)?"
    r"( um| uma| o| a| os| as| uns| umas| como e| como sao)? (?P<assunto>.+)$",
    r"\bquero ver( uma imagem| uma foto| uma figura| imagens| fotos)?( de| do| da| dos| das)?"
    r"( um| uma| o| a| os| as| como e| como sao)? (?P<assunto>.+)$",
]
OUTRA = [r"\b(mostra|mostre|quero|tem|ve) (uma |a )?(outra|proxima|mais uma)\b", r"^(e )?(a )?(outra|proxima|outra imagem|mais uma)$"]
FECHAR = [r"\b(fecha|feche|tira|tire|esconde|esconda|apaga|apague|some com) (a |essa |esta )?(imagem|figura)\b",
          # "como limpa a tela do terminal?" é pergunta para a IA, não um comando
          r"^(?!.*\b(como|qual|quando|onde|por que|porque)\b).*"
          r"\b(fecha|feche|tira|tire|esconde|esconda|apaga|apague|limpa|limpe|some com) "
          r"(a |o |essa |esse |esta |este )?(tela|lista|texto|passos|passo a passo)\b"]
FIM_DO_ASSUNTO = {"por", "favor", "pra", "para", "mim", "byte", "robo", "ai", "agora", "na", "tela", "turma", "gente"}
CANCELAR = r"^(nada|nao|cancela|cancelar|deixa|deixa pra la|esquece|para)$"

# Palavras que não fazem parte do nome em "meu nome é Ana", "eu sou o João"...
FORA_DO_NOME = {"meu", "nome", "e", "eu", "sou", "o", "a", "me", "chamo", "oi", "ola", "byte",
                "robo", "pode", "chamar", "de", "aprende", "aprenda", "decora", "grava", "memoriza",
                "rosto", "cara", "minha", "por", "favor", "isso", "tudo", "bem", "bom", "dia",
                "boa", "tarde", "noite", "ei", "entao", "ah", "eh", "hum", "professor", "professora"}
GATILHOS_DO_NOME = [["meu", "nome", "e"], ["me", "chamo"], ["pode", "me", "chamar", "de"], ["eu", "sou"]]


def _palavras(texto: str):
    originais = re.findall(r"\w+", texto)
    return originais, [normalizar(p) for p in originais]


def _algum(padroes, texto):
    return any(re.search(p, texto) for p in padroes)


def extrair_nome(texto: str, so_com_gatilho=False):
    """ "meu nome é ana clara" -> "Ana Clara".  Sem "meu nome é", usa a frase inteira
    (é a resposta para "como você se chama?"), a não ser que so_com_gatilho=True."""
    originais, normais = _palavras(texto)
    inicio = None
    for gatilho in GATILHOS_DO_NOME:
        for i in range(len(normais) - len(gatilho) + 1):
            if normais[i:i + len(gatilho)] == gatilho:
                inicio = i + len(gatilho)
                break
        if inicio is not None:
            break
    if inicio is None:
        if so_com_gatilho:
            return None
        inicio = 0
    nome = []
    for original, normal in zip(originais[inicio:], normais[inicio:]):
        if normal in FORA_DO_NOME:
            if nome:
                break          # o nome acabou ("Ana, aprende...")
            continue           # ainda não começou ("é o João")
        if not original.isalpha():
            break
        nome.append(original.capitalize())
        if len(nome) == 2:
            break
    return " ".join(nome) or None


def extrair_assunto(texto: str, padrao_normalizado: str, posicao: int):
    """Pega o assunto com acentos, do texto original: "mostra uma placa-mãe" -> "placa-mãe"."""
    originais, normais = _palavras(texto)
    inicio = padrao_normalizado[:posicao].count(" ")
    fim = len(originais)
    while inicio < fim and normais[inicio] in ("um", "uma", "uns", "umas", "o", "a", "os", "as"):
        inicio += 1
    while fim > inicio and normais[fim - 1] in FIM_DO_ASSUNTO:
        fim -= 1   # tira "por favor", "pra turma"... do final
    # junta de volta as palavras com hífen, como estavam: "placa-mãe"
    trecho = re.search(r"\w+(?:\W+\w+){%d}" % max(0, fim - inicio - 1),
                       texto[[m.start() for m in re.finditer(r"\w+", texto)][inicio]:]) if fim > inicio else None
    return trecho.group(0).strip() if trecho else None


def entender(texto: str, nomes_conhecidos=(), esperando_nome=False):
    """Devolve (comando, valor) ou (None, None) se for uma conversa normal para a IA."""
    t = " ".join(_palavras(texto)[1])
    if esperando_nome:
        if re.match(CANCELAR, t):
            return "cancelar", None
        return "nome", extrair_nome(texto)
    if _algum(APRENDER, t):
        return "aprender", extrair_nome(texto, so_com_gatilho=True)
    if _algum(FECHAR, t):
        return "fechar", None
    if re.search(ESQUECER, t):
        nome = next((n for n in nomes_conhecidos if f" {' '.join(_palavras(n)[1])} " in f" {t} "), None)
        if nome:
            return "esquecer", nome
        if re.search(r"\b(meu rosto|minha cara)\b", t):
            return "esquecer", None         # None = quem estiver na frente da câmera
        if re.search(r"\brosto\b", t):
            return "esquecer", "?"          # falou de rosto, mas de ninguém que eu conheça
    if _algum(QUEM, t):
        return "quem", None
    if _algum(FOTO, t):
        return "foto", None
    if _algum(OLHAR, t):
        return "olhar", None
    if _algum(OUTRA, t):
        return "outra", None
    for padrao in MOSTRAR:
        achou = re.search(padrao, t)
        if achou:
            assunto = extrair_assunto(texto, t, achou.start("assunto"))
            if assunto:
                return "mostrar", assunto
    return None, None


# ---- Teste: python -m robo.comandos ----
if __name__ == "__main__":
    print("Digite frases para ver qual comando o robô entende. 'sair' para terminar.")
    while True:
        frase = input("> ").strip()
        if frase == "sair":
            break
        print("  ", entender(frase, nomes_conhecidos=["Ana", "Marcos"]))
