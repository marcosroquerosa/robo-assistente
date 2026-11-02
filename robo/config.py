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
PALAVRAS_DE_ATIVACAO = ["ei robô", "eu robô", "oi robô", "olá robô","byte", "ei robo", "oi robo", "oi byte"]

# ---------------- Ouvido ----------------
MODELO_VOSK = "modelos/vosk-model-small-pt-0.3"   # só para a palavra de ativação
TAXA_DE_AMOSTRAGEM = 16000        # 16 mil amostras por segundo (padrão de voz)
LIMIAR_DE_SILENCIO = 600          # abaixo disso é "silêncio" (aumente se a sala for barulhenta)
SEGUNDOS_DE_SILENCIO_PARA_PARAR = 1
SEGUNDOS_MAXIMOS_DE_FALA = 100
SEGUNDOS_ESPERANDO_PERGUNTA = 4   # depois de acordar ou responder, espera a pessoa falar

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
MODELO_IA = "qwen2.5:0.5b"         # cérebro local no Ollama: Tucano2 0.5B, feito para português
                                  # (criado pelo Modelfile.tucano2). Antes era "gemma3:1b".
# Ajustes do cérebro local. São os mesmos do Modelfile e valem mais que CRIATIVIDADE
# (que continua valendo para a IA da web). Para voltar ao Gemma, deixe {}.
MODELO_IA_OPCOES = {"temperature": 0.1, "repeat_penalty": 1.2, "num_ctx": 4096}

ARQUIVO_PERSONALIDADE = "robo/personalidade.txt"
TROCAS_NA_MEMORIA = 6             # quantas perguntas e respostas ele lembra
TAMANHO_MAXIMO_DA_RESPOSTA = 380   # em "tokens" (pedaços de palavra); menor = mais rápido.
                                   # Era 300: subiu para caber o cartão da tela sem cortar a fala.
CRIATIVIDADE = 0.3                # 0 a 1: mais baixo = respostas mais diretas, inventa menos

# IA na web (usada quando CEREBRO = "web"). Funciona com qualquer serviço "compatível com OpenAI".
# A chave fica no arquivo chave_web.txt, na pasta do projeto (nunca dentro deste arquivo).
#   Google Gemini (tem plano gratuito):
#       WEB_ENDERECO = "https://generativelanguage.googleapis.com/v1beta/openai/"
#       WEB_MODELO   = "gemini-3.8-flash"
#       Mais esperto (mais lento): WEB_MODELO = "gemini-3.8-flash"
#   OpenAI (ChatGPT). Pago por uso; a assinatura do ChatGPT não vale aqui.
#   Chave em platform.openai.com > API keys. Copie o nome do modelo da lista "Models" do site:
#       WEB_ENDERECO = "https://api.openai.com/v1"
#       WEB_MODELO   = "nome-do-modelo"
#   Groq:
#       WEB_ENDERECO = "https://api.groq.com/openai/v1"
# Ao trocar de serviço, troque também a chave dentro do chave_web.txt.
WEB_ENDERECO = "https://generativelanguage.googleapis.com/v1beta/openai/"
# WEB_MODELO = "gemini-3.8-flash"
WEB_MODELO = "gemini-3.5-flash-lite"
WEB_ARQUIVO_DA_CHAVE = "chave_web.txt"
WEB_TEMPO_MAXIMO = 15             # segundos esperando a IA da web antes de desistir
WEB_SE_FALHAR_USAR_LOCAL = True   # sem internet, responde com o cérebro local
WEB_OPCOES_EXTRAS = {}            # opções extras do serviço. Modelos que "raciocinam" respondem
                                  # mais rápido com: {"reasoning_effort": "low"}

# ---------------- Visão (câmera da frente do celular) ----------------
# Cada recurso liga e desliga sozinho. O reconhecimento de rostos roda SEMPRE aqui no
# computador; para a internet só vai a foto de quando você pede "o que você está vendo?".
VISAO_LIGADA = True                    # False = o celular nem liga a câmera
VISAO_OLHOS_SEGUEM = True              # os olhos acompanham o rosto de quem está na frente
VISAO_RECONHECER_PESSOAS = True        # lembra rostos cadastrados ("Byte, aprende meu rosto")
VISAO_CUMPRIMENTAR_CONHECIDOS = True   # diz "Oi, Ana!" quando vê alguém cadastrado
VISAO_CUMPRIMENTAR_DESCONHECIDOS = False  # diz "Oi!" para quem chega numa sala que estava vazia
VISAO_MINUTOS_ENTRE_CUMPRIMENTOS = 30  # não cumprimenta a mesma pessoa de novo antes disso
VISAO_SEGUNDOS_DE_SALA_VAZIA = 120     # quanto tempo sem ninguém conta como "sala vazia"
VISAO_FOTO_PARA_WEB = True             # "o que você está vendo?" manda a foto para a IA da web
VISAO_MODELO_LOCAL = None              # sem internet, olhar com um modelo local, ex.: "gemma3:4b"
                                       # (bem lento no NucBox). None = avisa que não consegue ver.
VISAO_CONTAR_NOMES_PARA_IA = True      # conta para a IA quem está na frente ("Ana, Marcos")

CUMPRIMENTOS = ["Oi, {nome}!", "Olá, {nome}! Que bom te ver.", "E aí, {nome}? Tudo bem?"]
CUMPRIMENTOS_DESCONHECIDOS = ["Oi! Tudo bem?", "Olá! Se precisar de mim, é só dizer ei robô."]

# Olhar para quem está falando. Com duas pessoas ou mais, o robô compara o som do microfone
# com o movimento da boca de cada rosto (tudo aqui no computador; nada é gravado).
VISAO_OLHAR_QUEM_FALA = True

# Mão levantada para pedir a vez: segure a mão acima da cabeça e o robô olha para você e
# diz "Pode falar!". Funciona a até uns 2 m. Exige o modelo de palmas:
#   .venv/bin/python ferramentas/baixar_modelos.py visao
VISAO_MAO_LEVANTADA = True             # False = ignora as mãos (e economiza processador)
VISAO_SEGUNDOS_COM_A_MAO_LEVANTADA = 1.5  # menos que isso é um gesto qualquer
VISAO_SEGUNDOS_ENTRE_VEZES = 6         # intervalo entre chamar uma pessoa e chamar a próxima
FRASES_DA_VEZ = ["Pode falar, {nome}!", "Oi, {nome}! Pode falar."]
FRASES_DA_VEZ_SEM_NOME = ["Pode falar!", "Vi sua mão. Pode falar!"]

# Ajustes finos (normalmente não precisa mexer)
VISAO_LARGURA_DO_QUADRO = 640          # tamanho das imagens que o celular manda (pixels)
VISAO_QUADROS_POR_SEGUNDO = 2
VISAO_QUADROS_POR_SEGUNDO_EM_GRUPO = 4 # com 2 ou mais rostos, enquanto ouve (para ver as bocas mexendo)
VISAO_SEGUNDOS_OLHANDO_QUEM_FALOU = 3  # depois do silêncio, ainda olha para quem falou
VISAO_MOVIMENTO_MINIMO_DA_BOCA = 4     # abaixo disso a boca está parada (suba se errar quem fala)
VISAO_CERTEZA_DA_MAO = 0.5             # 0 a 1: mais alto = menos engano, mas acha menos mãos
VISAO_TAMANHO_MINIMO_DO_ROSTO = 40     # rostos menores que isso (pixels) não são reconhecidos
VISAO_LIMIAR_DE_PARECIDO = 0.40        # 0 a 1: mais alto = confunde menos, mas reconhece menos
VISAO_FOTOS_POR_CADASTRO = 6
VISAO_TEMPO_MAXIMO_WEB = 25            # segundos esperando a IA da web olhar a foto
VISAO_WEB_MODELO = None                # None = o mesmo WEB_MODELO de cima
MODELO_DETECTOR_DE_ROSTOS = "modelos/visao/face_detection_yunet_2023mar.onnx"
MODELO_RECONHECEDOR_DE_ROSTOS = "modelos/visao/face_recognition_sface_2021dec.onnx"
MODELO_DETECTOR_DE_PALMAS = "modelos/visao/palm_detection_mediapipe_2023feb.onnx"
ARQUIVO_DE_ROSTOS = "dados/rostos.json"   # só as "assinaturas" dos rostos, nunca as fotos
PASTA_DE_FOTOS = "fotos"                  # fotos de "Byte, tira uma foto"

# ---------------- Mostrar imagens ("Byte, mostra uma placa-mãe") ----------------
# Busca na Wikipédia em português e no Wikimedia Commons (grátis, sem chave).
# As imagens só ficam na memória enquanto vão para a tela: nada é gravado no disco.
IMAGENS_LIGADAS = True
# Onde procurar: a primeira fonte dá a primeira imagem, e "mostra outra" vai alternando.
# Só uma fonte: ["wikipedia"] ou ["commons"]. O Commons só entra se a IA puder conferir as imagens.
IMAGENS_FONTES = ["wikipedia", "commons"]
# A Wikipédia e o Commons exigem um contato de quem usa a busca (e-mail ou site), senão bloqueiam.
# Coloque o seu e-mail entre as aspas, ex.: IMAGENS_CONTATO = "professor@escola.com"
IMAGENS_CONTATO = ""
IMAGENS_SEGUNDOS_NA_TELA = 60          # depois some sozinha (ou toque na tela para fechar)
IMAGENS_VERIFICAR_COM_IA = True        # o Gemini confere se a imagem é a certa e serve para a aula
IMAGENS_EXPLICAR = True                # o robô fala uma ou duas frases sobre a imagem
IMAGENS_IDIOMA_DA_WIKIPEDIA = "pt"
IMAGENS_RESULTADOS = 8                 # quantos resultados pegar de cada fonte (para "mostra outra")
IMAGENS_TAMANHO = 1280                 # largura da imagem pedida à Wikipédia (pixels)
IMAGENS_TEMPO_MAXIMO = 10              # segundos esperando a Wikipédia

# ---------------- Rosto e tela ----------------
ROSTO_IA_ESCOLHE_EXPRESSAO = True      # a IA da web escolhe a expressão de cada resposta
ROSTO_SEGUNDOS_DE_EXPRESSAO = 6        # quanto tempo uma expressão fica no rosto
ROSTO_SEGUNDOS_PARA_SONO = 60          # dormindo com gente na frente: depois disso fica sonolento
TELA_IA_PODE_MOSTRAR = True            # a IA da web mostra listas, passos e textos enquanto fala
TELA_SEGUNDOS_NA_TELA = 60             # depois some sozinho (ou toque na tela para fechar)

# ---------------- Servidor ----------------
PORTA = 8000
VOZ_PIPER = "modelos/piper/pt_BR-faber-medium.onnx"
