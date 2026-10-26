"""
BAIXAR OS MODELOS (precisa de internet só desta vez)
====================================================
Baixa para a pasta "modelos":
  - Vosk em português (palavra de ativação)
  - Voz brasileira "faber" do Piper (voz)
  - Parakeet em português do Brasil (entendimento)
  - Whisper (entendimento reserva)
O modelo de IA (cérebro) é baixado pelo Ollama, com o comando:
  ollama pull gemma3:1b

Rode a partir da pasta do projeto:   python ferramentas/baixar_modelos.py
"""

import os
import sys
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from robo import config  # noqa: E402

VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
PIPER_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/"
PIPER_ARQUIVOS = ["pt_BR-faber-medium.onnx", "pt_BR-faber-medium.onnx.json"]
PARAKEET_REPO = "alefiury/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx"


def baixar(url, destino, tentativas=3):
    """Baixa um arquivo mostrando o andamento, e tenta de novo se a conexão cair."""
    nome = os.path.basename(destino)
    for tentativa in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resposta, open(destino, "wb") as arquivo:
                total = int(resposta.headers.get("Content-Length") or 0)
                baixado = 0
                while True:
                    pedaco = resposta.read(256 * 1024)
                    if not pedaco:
                        break
                    arquivo.write(pedaco)
                    baixado += len(pedaco)
                    if total:
                        print(f"\r  baixando {nome}: {baixado * 100 // total}% "
                              f"({baixado // 1_000_000} de {total // 1_000_000} MB)", end="", flush=True)
                    else:
                        print(f"\r  baixando {nome}: {baixado // 1_000_000} MB", end="", flush=True)
            print()
            return
        except Exception as erro:
            print(f"\n  falhou ({erro}); tentativa {tentativa} de {tentativas}")
            if os.path.exists(destino):
                os.remove(destino)
    raise SystemExit(f"Não consegui baixar {nome}. Confira a internet e rode de novo.")


def main():
    os.makedirs("modelos/piper", exist_ok=True)

    # 1. Vosk
    if os.path.isdir(config.MODELO_VOSK):
        print("[1/4] Vosk já está baixado.")
    else:
        print("[1/4] Vosk (palavra de ativação)")
        baixar(VOSK_URL, "modelos/vosk.zip")
        with zipfile.ZipFile("modelos/vosk.zip") as z:
            z.extractall("modelos")
        os.remove("modelos/vosk.zip")

    # 2. Piper
    print("[2/4] Voz do Piper")
    for nome in PIPER_ARQUIVOS:
        destino = os.path.join("modelos/piper", nome)
        if not os.path.exists(destino):
            baixar(PIPER_URL + nome, destino)

    # 3. Parakeet em português do Brasil (é grande: pode demorar)
    print("[3/4] Parakeet português do Brasil (entendimento)")
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=PARAKEET_REPO, local_dir=config.PASTA_PARAKEET)

    # 4. Whisper (reserva; a própria biblioteca baixa na primeira vez)
    print(f"[4/4] Whisper '{config.MODELO_WHISPER}' (reserva)")
    from faster_whisper import WhisperModel
    WhisperModel(config.MODELO_WHISPER, device="cpu", compute_type="int8",
                 download_root=config.PASTA_WHISPER, local_files_only=False)

    print("\nPronto! Agora o robô funciona sem internet.")


if __name__ == "__main__":
    main()
