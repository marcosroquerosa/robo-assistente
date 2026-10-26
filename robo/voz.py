"""
VOZ (a "boca" do robô)
======================
Transforma texto em fala usando o Piper, que roda sem internet.
Entrada: um texto.  Saída: um arquivo de áudio WAV (em bytes),
ou None se o texto não tiver nada para falar.

Teste sozinho:   python -m robo.voz
"""

import io
import re
import wave

from piper import PiperVoice

from robo import config


def limpar_texto(texto: str) -> str:
    """Tira o que a voz leria de um jeito estranho: marcas <think>, *, #, emojis..."""
    texto = re.sub(r"<think>.*?</think>", " ", texto, flags=re.DOTALL)
    texto = re.sub(r"</?\w+>", " ", texto)                              # outras marcas <...>
    texto = re.sub(r"[*_#`>|~]", " ", texto)
    texto = re.sub(r"[\U0001F000-\U0001FFFF☀-➿]", " ", texto)  # emojis
    return re.sub(r"\s+", " ", texto).strip()


class Voz:
    def __init__(self):
        print("[voz] carregando a voz...")
        self.voz = PiperVoice.load(config.VOZ_PIPER)
        print("[voz] pronta!")

    def falar(self, texto: str):
        """Recebe um texto e devolve o áudio WAV pronto para tocar (ou None)."""
        texto = limpar_texto(texto)
        if not re.search(r"\w", texto):
            return None  # não sobrou nenhuma letra ou número para falar

        pedacos = list(self.voz.synthesize(texto))
        if not pedacos:
            return None

        memoria = io.BytesIO()
        with wave.open(memoria, "wb") as arquivo_wav:
            arquivo_wav.setnchannels(pedacos[0].sample_channels)
            arquivo_wav.setsampwidth(pedacos[0].sample_width)
            arquivo_wav.setframerate(pedacos[0].sample_rate)
            for pedaco in pedacos:
                arquivo_wav.writeframes(pedaco.audio_int16_bytes)
        return memoria.getvalue()


# ---- Teste: python -m robo.voz ----
if __name__ == "__main__":
    voz = Voz()
    audio = voz.falar(f"Olá! Eu sou o {config.NOME_DO_ROBO}, o seu robô assistente de aulas.")
    with open("teste_voz.wav", "wb") as f:
        f.write(audio)
    print("[voz] salvei o arquivo teste_voz.wav")
    try:
        import winsound  # só existe no Windows
        winsound.PlaySound("teste_voz.wav", winsound.SND_FILENAME)
    except ImportError:
        import shutil
        import subprocess
        if shutil.which("aplay"):  # Linux
            subprocess.run(["aplay", "-q", "teste_voz.wav"])
        else:
            print("[voz] abra o arquivo teste_voz.wav para ouvir")
