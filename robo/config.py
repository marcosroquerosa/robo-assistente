"""
CONFIGURAÇÕES DO ROBÔ
=====================
Este é o "painel de controle" do robô. Quase tudo que você vai querer
ajustar está aqui. Mude um valor, salve e reinicie o robô
(no Linux, com o modo automático:  sudo systemctl restart robo-byte).
"""

# ---------------- Identidade ----------------
NOME_DO_ROBO = "Byte"

# Palavras que acordam o robô. Use palavras em português comum:
# o reconhecedor só entende palavras que estão no dicionário dele.
# "eu robô" está aqui porque o Vosk muitas vezes ouve assim quando dizemos "ei robô".
PALAVRAS_DE_ATIVACAO = ["ei robô", "eu robô", "oi robô", "olá robô"]

# ---------------- Ouvido ----------------
MODELO_VOSK = "modelos/vosk-model-small-pt-0.3"   # só para a palavra de ativação
TAXA_DE_AMOSTRAGEM = 16000        # 16 mil amostras por segundo (padrão de voz)
LIMIAR_DE_SILENCIO = 600          # abaixo disso é "silêncio" (aumente se a sala for barulhenta)
SEGUNDOS_DE_SILENCIO_PARA_PARAR = 3
SEGUNDOS_MAXIMOS_DE_FALA = 100
SEGUNDOS_ESPERANDO_PERGUNTA = 6   # depois de acordar ou responder, espera a pessoa falar

# ---------------- Entendimento (fala -> texto) ----------------
MOTOR_ENTENDIMENTO = "parakeet"   # "parakeet" (português do Brasil, erra menos) ou "whisper"

# Parakeet ajustado para português do Brasil (TAGARELA)
PASTA_PARAKEET = "modelos/parakeet-ptBR"
PARAKEET_QUANTIZACAO = None       # None = qualidade máxima; "int8" = mais leve, se o modelo tiver essa versão

# Whisper (usado só se MOTOR_ENTENDIMENTO = "whisper")
MODELO_WHISPER = "base"           # tiny, base ou small (no NucBox, o small leva uns 13 s)
PASTA_WHISPER = "modelos/whisper"
DICA_WHISPER = "Conversa em português com o robô Byte, numa aula de informática."
CAPRICHO_DO_WHISPER = 5           # 1 = mais rápido; 5 = compara 5 versões da frase, erra menos
NUCLEOS_DO_PROCESSADOR = 4        # o N5095 tem 4 núcleos

# True = nunca tenta baixar nada da internet (use depois de baixar os modelos)
SO_OFFLINE = True

# ---------------- Cérebro ----------------
CEREBRO = "web"                 # "local" (sem internet) ou "web" (IA na internet, mais esperta)
MODELO_IA = "gemma3:1b"           # cérebro local no Ollama. Mais esperto e mais lento: "gemma4:e2b"

ARQUIVO_PERSONALIDADE = "robo/personalidade.txt"
TROCAS_NA_MEMORIA = 6             # quantas perguntas e respostas ele lembra
TAMANHO_MAXIMO_DA_RESPOSTA = 300   # em "tokens" (pedaços de palavra); menor = mais rápido
CRIATIVIDADE = 0.3                # 0 a 1: mais baixo = respostas mais diretas, inventa menos

# IA na web (usada quando CEREBRO = "web"). Funciona com qualquer serviço "compatível com OpenAI".
# A chave fica no arquivo chave_web.txt, na pasta do projeto (nunca dentro deste arquivo).
#   Google Gemini (tem plano gratuito):
#       WEB_ENDERECO = "https://generativelanguage.googleapis.com/v1beta/openai/"
#       WEB_MODELO   = "gemini-3.8-flash"
#   Groq:
#       WEB_ENDERECO = "https://api.groq.com/openai/v1"
#   OpenAI:
#       WEB_ENDERECO = "https://api.openai.com/v1"
WEB_ENDERECO = "https://generativelanguage.googleapis.com/v1beta/openai/"
# WEB_MODELO = "gemini-3.8-flash"
WEB_MODELO = "gemini-3.5-flash-lite"
WEB_ARQUIVO_DA_CHAVE = "chave_web.txt"
WEB_TEMPO_MAXIMO = 15             # segundos esperando a IA da web antes de desistir
WEB_SE_FALHAR_USAR_LOCAL = True   # sem internet, responde com o cérebro local
WEB_OPCOES_EXTRAS = {}            # opções extras do serviço, se precisar

# ---------------- Servidor ----------------
PORTA = 8000
VOZ_PIPER = "modelos/piper/pt_BR-faber-medium.onnx"
