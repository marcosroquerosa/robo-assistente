"""
TRANSCRIÇÃO (o robô entendendo o que ouviu)
===========================================
Transforma áudio de fala em texto, sem internet. Dois "motores" possíveis
(escolha no config.py, em MOTOR_ENTENDIMENTO):
  - "parakeet": Parakeet ajustado para português do Brasil (TAGARELA). Erra menos.
  - "whisper":  Whisper (faster-whisper). Era o motor anterior.

Entrada: áudio (16 mil amostras por segundo).  Saída: o texto falado.

Teste sozinho (use o arquivo criado pelo teste da voz):
    python -m robo.transcricao teste_voz.wav
"""

import sys

import numpy as np

from robo import config

TAXA = 16000


class Transcritor:
    def __init__(self):
        self.motor = getattr(config, "MOTOR_ENTENDIMENTO", "whisper")
        if self.motor == "parakeet":
            self._carregar_parakeet()
        else:
            self._carregar_whisper()

    # ---------- Parakeet ----------
    def _carregar_parakeet(self):
        import onnx_asr
        print("[transcrição] carregando o Parakeet (português do Brasil)...")
        quantizacao = getattr(config, "PARAKEET_QUANTIZACAO", None)
        extras = {"quantization": quantizacao} if quantizacao else {}
        self.modelo = onnx_asr.load_model("nemo-conformer-tdt", config.PASTA_PARAKEET, **extras)
        print("[transcrição] pronta!")

    def _transcrever_parakeet(self, audio) -> str:
        if isinstance(audio, str):
            resultado = self.modelo.recognize(audio, language="pt")
        else:
            resultado = self.modelo.recognize(audio, sample_rate=TAXA, language="pt")
        return str(resultado).strip()

    # ---------- Whisper ----------
    def _carregar_whisper(self):
        from faster_whisper import WhisperModel
        print(f"[transcrição] carregando o Whisper '{config.MODELO_WHISPER}'...")
        self.modelo = WhisperModel(
            config.MODELO_WHISPER,
            device="cpu",
            compute_type="int8",        # versão mais leve, boa para processador sem placa de vídeo
            cpu_threads=config.NUCLEOS_DO_PROCESSADOR,
            download_root=config.PASTA_WHISPER,
            local_files_only=config.SO_OFFLINE,
        )
        print("[transcrição] pronta!")

    def _transcrever_whisper(self, audio) -> str:
        # "capricho": quantas versões da frase o Whisper compara antes de escolher (mais = erra menos, mais lento)
        capricho = getattr(config, "CAPRICHO_DO_WHISPER", 5)
        trechos, _info = self.modelo.transcribe(audio, language="pt", beam_size=capricho, vad_filter=True,
                                                initial_prompt=config.DICA_WHISPER)
        return " ".join(t.text.strip() for t in trechos).strip()

    # ---------- o que o resto do robô usa ----------
    def transcrever(self, audio) -> str:
        """Aceita bytes de áudio (16 bits, 16 kHz) ou o caminho de um arquivo."""
        if isinstance(audio, (bytes, bytearray)):
            # converte os bytes em números entre -1 e 1, que é o formato que os motores usam
            audio = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        if self.motor == "parakeet":
            return self._transcrever_parakeet(audio)
        return self._transcrever_whisper(audio)


# ---- Teste: python -m robo.transcricao arquivo.wav ----
if __name__ == "__main__":
    arquivo = sys.argv[1] if len(sys.argv) > 1 else "teste_voz.wav"
    transcritor = Transcritor()
    print("Texto entendido:", transcritor.transcrever(arquivo))
