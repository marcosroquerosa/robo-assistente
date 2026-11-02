"""
ROSTOS CADASTRADOS (gerenciar pelo teclado)
===========================================
Rode a partir da pasta do projeto (com o robô desligado ou reinicie depois):

  python ferramentas/rostos.py listar                       quem o robô conhece
  python ferramentas/rostos.py apagar Ana                   esquece uma pessoa
  python ferramentas/rostos.py apagar-todos                 esquece todo mundo
  python ferramentas/rostos.py renomear Ana "Ana Clara"     corrige um nome mal entendido
  python ferramentas/rostos.py cadastrar Ana f1.jpg f2.jpg  cadastra a partir de fotos
  python ferramentas/rostos.py testar foto.jpg              mostra quem ele reconhece na foto

O arquivo dados/rostos.json guarda só as assinaturas dos rostos, nunca as fotos.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from robo.visao import Visao  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    acao, resto = sys.argv[1], sys.argv[2:]
    visao = Visao()
    if not visao.ligada or visao.reconhecedor is None:
        raise SystemExit("O reconhecimento de rostos está desligado ou sem os modelos.")

    if acao == "listar":
        if not visao.pessoas:
            print("Ninguém cadastrado.")
        for nome, assinaturas in visao.pessoas.items():
            print(f"  {nome} ({len(assinaturas)} assinaturas)")

    elif acao == "apagar" and resto:
        nome = visao.esquecer(" ".join(resto))
        print(f"Apaguei {nome}." if nome else "Não achei esse nome.")

    elif acao == "apagar-todos":
        if input("Apagar TODOS os rostos? Digite sim: ").strip().lower() == "sim":
            for nome in list(visao.pessoas):
                visao.esquecer(nome)
            print("Pronto, o robô não conhece mais ninguém.")

    elif acao == "renomear" and len(resto) == 2:
        antigo = visao.achar_nome(resto[0])
        if not antigo:
            raise SystemExit("Não achei esse nome.")
        visao.pessoas[resto[1]] = visao.pessoas.pop(antigo)
        visao._salvar_cadastro()
        print(f"{antigo} agora se chama {resto[1]}.")

    elif acao == "cadastrar" and len(resto) >= 2:
        nome, assinaturas = resto[0], []
        for caminho in resto[1:]:
            with open(caminho, "rb") as f:
                rostos = visao.analisar(f.read())
            if len(rostos) == 1 and rostos[0]["assinatura"] is not None:
                assinaturas.append(rostos[0]["assinatura"])
                print(f"  {caminho}: ok")
            else:
                print(f"  {caminho}: precisa ter um rosto só, grande e de frente ({len(rostos)} achados)")
        if assinaturas:
            print(f"Cadastrei {visao.cadastrar(nome, assinaturas)} com {len(assinaturas)} foto(s).")

    elif acao == "testar" and resto:
        for caminho in resto:
            with open(caminho, "rb") as f:
                rostos = visao.analisar(f.read())
            print(f"{caminho}: {len(rostos)} rosto(s)")
            for r in rostos:
                print(f"  {r['nome'] or 'desconhecido'} (parecido {r['parecido']:.2f}, {r['pixels']:.0f} px)")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
