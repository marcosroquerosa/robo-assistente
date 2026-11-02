"""
IMAGENS (o robô mostrando figuras na tela)
==========================================
"Byte, mostra uma placa-mãe": o robô procura o assunto em duas fontes e alterna
os resultados (a primeira imagem é a mais parecida; "mostra outra" passa para a próxima):
  - Wikipédia em português: a imagem principal dos artigos sobre o assunto.
  - Wikimedia Commons: o acervo de imagens livres que abastece a Wikipédia.

Não precisa de chave nem de cadastro. As imagens têm licença livre, e a tela mostra
a fonte, o autor e a licença. O Commons guarda fotos de todo tipo, então só entra na
busca quando a IA pode conferir cada imagem antes de ela aparecer para a turma.
Nada é gravado no disco: a imagem fica só na memória enquanto é mandada para a tela
do celular e depois é descartada.

Precisa de internet. Teste sozinho:   python -m robo.imagens placa-mãe
"""

import html
import re
import sys

import httpx

from robo import config
from robo.visao import Visao

ENDERECO_DO_COMMONS = "https://commons.wikimedia.org/w/api.php"


def cabecalho():
    """A Wikipédia e o Commons bloqueiam (erro 403) programas que não dizem quem são e como falar com o dono.
    O contato vem do config.py (IMAGENS_CONTATO)."""
    contato = getattr(config, "IMAGENS_CONTATO", "").strip()
    partes = "robo assistente de aulas, projeto escolar" + (f"; {contato}" if contato else "")
    return {"User-Agent": f"RoboByte/1.0 ({partes}) httpx/{httpx.__version__}"}


class WikipediaRecusou(Exception):
    """A Wikipédia ou o Commons responderam, mas não aceitaram o pedido (não é falta de internet)."""


def limpar_html(texto: str) -> str:
    """O Commons manda o nome do autor com marcas de página: <a href="...">Ana</a> -> Ana."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(texto or ""))).strip()


def intercalar(listas: list) -> list:
    """[[a, b], [1, 2, 3]] -> [a, 1, b, 2, 3]: alterna as fontes, na ordem de cada uma."""
    saida = []
    for posicao in range(max((len(lista) for lista in listas), default=0)):
        saida += [lista[posicao] for lista in listas if posicao < len(lista)]
    return saida


class BuscaDeImagens:
    def __init__(self):
        self.ligada = getattr(config, "IMAGENS_LIGADAS", True)
        idioma = getattr(config, "IMAGENS_IDIOMA_DA_WIKIPEDIA", "pt")
        self.endereco = f"https://{idioma}.wikipedia.org/w/api.php"
        self.fontes = list(getattr(config, "IMAGENS_FONTES", ["wikipedia"]))
        self.termo = None
        self.resultados = []   # imagens encontradas, alternando as fontes

    def _perguntar(self, endereco: str, parametros: dict) -> list:
        resposta = httpx.get(endereco, params=parametros, headers=cabecalho(),
                             timeout=getattr(config, "IMAGENS_TEMPO_MAXIMO", 10))
        if resposta.status_code != 200:
            raise WikipediaRecusou(f"erro {resposta.status_code}: {resposta.text[:200]}")
        paginas = (resposta.json().get("query") or {}).get("pages") or []
        paginas.sort(key=lambda p: p.get("index", 99))   # na ordem da busca
        return paginas

    def _buscar_na_wikipedia(self, termo: str) -> list:
        """A imagem principal dos artigos em português que falam do assunto."""
        paginas = self._perguntar(self.endereco, {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrsearch": termo,
            "gsrlimit": str(getattr(config, "IMAGENS_RESULTADOS", 8)),
            "prop": "pageimages|description", "piprop": "thumbnail",
            "pithumbsize": str(getattr(config, "IMAGENS_TAMANHO", 1280)),
        })
        return [{"url": p["thumbnail"]["source"], "titulo": p.get("title", termo),
                 "descricao": p.get("description", ""), "domain": f"Wikipédia: {p.get('title', termo)}",
                 "origem": "wikipedia"}
                for p in paginas
                if (p.get("thumbnail") or {}).get("source")
                and p["thumbnail"].get("width", 0) >= 150]   # pula ícones pequenos

    def _buscar_no_commons(self, termo: str) -> list:
        """Os arquivos do Wikimedia Commons. Lá muitas descrições estão em inglês, então uma
        busca em português acha menos do que a mesma busca em inglês."""
        paginas = self._perguntar(ENDERECO_DO_COMMONS, {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrsearch": f"{termo} filetype:bitmap", "gsrnamespace": "6",
            "gsrlimit": str(getattr(config, "IMAGENS_RESULTADOS", 8)),
            "prop": "imageinfo", "iiprop": "url|mime|extmetadata",
            "iiurlwidth": str(getattr(config, "IMAGENS_TAMANHO", 1280)),
            "iiextmetadatafilter": "Artist|LicenseShortName", "iiextmetadatalanguage": "pt",
        })
        achadas = []
        for pagina in paginas:
            info = (pagina.get("imageinfo") or [{}])[0]
            if info.get("mime") not in ("image/jpeg", "image/png") or not info.get("thumburl"):
                continue
            if info.get("thumbwidth", 0) < 150:
                continue
            dados = info.get("extmetadata") or {}
            autor = limpar_html((dados.get("Artist") or {}).get("value"))[:60]
            licenca = limpar_html((dados.get("LicenseShortName") or {}).get("value"))
            titulo = re.sub(r"\.\w+$", "", pagina.get("title", termo).split(":", 1)[-1])
            # a licença da maioria das imagens do Commons exige dar o crédito ao autor
            credito = ", ".join(c for c in (autor, licenca) if c)
            achadas.append({"url": info["thumburl"], "titulo": titulo, "descricao": "",
                            "domain": f"Wikimedia Commons: {credito}" if credito else "Wikimedia Commons",
                            "origem": "commons"})
        return achadas

    def buscar(self, termo: str, com_commons=True):
        """Procura o assunto em cada fonte e guarda a lista de imagens.
        com_commons=False: só a Wikipédia. O Commons guarda fotos de todo tipo, então só
        é usado quando a IA pode conferir cada imagem antes de ela ir para a tela.
        Se uma fonte falhar, usa a outra; se todas falharem, dá erro (quem chamou avisa a pessoa)."""
        buscas = {"wikipedia": self._buscar_na_wikipedia}
        if com_commons:
            buscas["commons"] = self._buscar_no_commons
        elif "commons" in self.fontes:
            print("[imagens] sem a IA para conferir as imagens, o Commons fica de fora desta busca")
        listas, erro = [], None
        for fonte in self.fontes:
            if fonte not in buscas:
                continue
            try:
                listas.append(buscas[fonte](termo))
            except Exception as falha:
                print(f"[imagens] a busca em {fonte} falhou: {type(falha).__name__}: {falha}")
                erro = falha
        if erro is not None and not listas:
            raise erro
        self.termo = termo
        self.resultados = intercalar(listas)
        print(f"[imagens] '{termo}': {len(self.resultados)} imagem(ns)")

    def tem_mais(self) -> bool:
        return bool(self.resultados)

    def proxima(self):
        """Baixa a próxima imagem da lista. Devolve (JPEG em bytes, informações) ou (None, None)."""
        while self.resultados:
            achada = self.resultados.pop(0)
            try:
                resposta = httpx.get(achada["url"], headers=cabecalho(),
                                     timeout=getattr(config, "IMAGENS_TEMPO_MAXIMO", 10),
                                     follow_redirects=True)
                resposta.raise_for_status()
            except Exception as erro:
                print(f"[imagens] não consegui baixar a imagem de '{achada['titulo']}': {erro}")
                continue
            # converte para JPEG (os desenhos vêm em PNG, às vezes com fundo transparente)
            return Visao.reduzir(resposta.content, lado_maximo=1280), achada
        return None, None


# ---- Teste: python -m robo.imagens placa-mãe ----
if __name__ == "__main__":
    busca = BuscaDeImagens()
    busca.buscar(" ".join(sys.argv[1:]) or "placa-mãe")
    while busca.tem_mais():
        imagem, info = busca.proxima()
        if imagem:
            print(f"  {info['domain']}: {len(imagem) // 1024} KB")
