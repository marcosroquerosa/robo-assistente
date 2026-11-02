# Comandos do Robô Byte

Oct 31, 2026 · @Marcos Rosa

Lista de tudo o que o Byte entende hoje, tirada direto do código. As frases podem variar: o robô ignora acentos e aceita jeitos parecidos de pedir.

## Acordar e conversar

O robô dorme até ouvir a palavra de ativação ou sentir um toque na tela.

| Como | O que acontece |
| --- | --- |
| "Ei robô", "Oi robô", "Olá robô" | Acorda e fica ouvindo |
| Tocar na tela | Acorda e fica ouvindo |
| Falar até 4 segundos depois de uma resposta | Continua a conversa, sem precisar dizer "ei robô" de novo |
| Ficar 4 segundos em silêncio | Volta a dormir |

As palavras de ativação ficam em `PALAVRAS_DE_ATIVACAO`, no `config.py`.

## Conversa livre

Qualquer frase que não seja um dos comandos abaixo vai para a IA (Gemini, ou o Gemma local sem internet). O Byte responde em voz alta e mostra a legenda.

- Exemplos: "O que é HTML?", "Como funciona um processador?", "Me conta uma piada de informática".
- Ele lembra as últimas 6 perguntas e respostas da conversa.
- Se reconhecer alguém na frente da câmera, conta o nome para a IA, para ela poder chamar a pessoa pelo nome.

## Reconhecer pessoas (sem internet)

| Diga | O que o robô faz |
| --- | --- |
| "Aprende meu rosto", "Decora minha cara", "Memoriza meu nome", "Aprende quem eu sou" | Pergunta "Como você se chama?" e espera até 30 segundos pela resposta |
| (resposta) "Ana", "Meu nome é Ana Clara", "Eu sou o João" | Pede para a pessoa olhar a tela e cadastra o rosto |
| "Meu nome é Ana, aprende meu rosto" | Cadastra direto, sem perguntar o nome |
| (resposta) "Deixa pra lá", "Cancela", "Nada" | Desiste do cadastro |
| "Quem sou eu?", "Você sabe quem eu sou?", "Você me conhece?", "Qual é o meu nome?" | Diz o nome de quem está na frente da câmera |
| "Quem está aqui?", "Quem você está vendo?", "Quantas pessoas você está vendo?" | Diz quem reconhece e quantas pessoas desconhecidas vê |
| "Esquece o rosto da Ana", "Apaga a Ana" | Apaga o cadastro da Ana |
| "Esquece meu rosto" | Apaga o cadastro de quem está na frente da câmera |

No cadastro, a pessoa precisa estar sozinha na frente da câmera e olhando para a tela.

## Câmera

| Diga | O que o robô faz |
| --- | --- |
| "Tira uma foto", "Bate uma selfie", "Faz um retrato" | Conta 3, 2, 1, mostra a foto e guarda na pasta `fotos/` do NucBox |
| "O que você está vendo?", "Descreve a sala", "Você consegue me ver?" | Tira uma foto, manda para o Gemini e descreve o que vê |
| "Lê o quadro", "Lê o que está escrito", "Leia isso" | Lê em voz alta o texto que aparece na foto |
| "O que é isso na minha mão?", "Que objeto é esse?", "Que cor é essa?", "Olha isso" | Diz o que é o objeto |
| "Quantos dedos tem aqui?" | Conta os dedos na foto |

Os pedidos para olhar precisam de internet. Quando a foto vai para o Gemini, aparece na tela o aviso laranja "foto enviada para a IA na internet". Essas fotos não são guardadas.

## Imagens da Wikipédia e do Commons

| Diga | O que o robô faz |
| --- | --- |
| "Mostra uma placa-mãe", "Me mostra a memória RAM", "Exibe um processador" | Busca na Wikipédia e no Wikimedia Commons, mostra a imagem e explica |
| "Mostra pra turma uma foto de um disco rígido" | O mesmo: ele tira "pra turma", "uma foto de" e "por favor" da busca |
| "Quero ver uma placa de vídeo" | O mesmo |
| "Mostra como é um roteador" | O mesmo |
| "Mostra outra", "A próxima", "Mais uma" | Mostra a próxima imagem da mesma busca, alternando as duas fontes |
| "Fecha a imagem", "Tira a imagem", "Esconde a figura" | Tira a imagem da tela |

A imagem sai da tela sozinha depois de 60 segundos, ou com um toque na tela. Precisa de internet e do seu e-mail em `IMAGENS_CONTATO`, no `config.py`.

As imagens do Commons mostram o autor e a licença na tela. O Commons só entra na busca quando o Gemini pode conferir cada imagem antes de ela aparecer. Para escolher as fontes, mude `IMAGENS_FONTES`, no `config.py`.

## Listas, passos e textos na tela

Quando a resposta tem etapas ou vários itens, o Gemini monta um cartão ao lado do rosto enquanto o Byte fala. Funciona só com a IA da web.

| Diga | O que o robô faz |
| --- | --- |
| "Como eu salvo um arquivo?" | Explica e mostra os passos numerados |
| "Quais são as partes do computador?" | Explica e mostra a lista |
| "Fecha a lista", "Limpa a tela", "Apaga o texto" | Tira o cartão da tela |

O cartão sai sozinho depois de 60 segundos, quando chega a próxima pergunta ou com um toque na tela.

## O que ele faz sozinho

- **Alguém chega:** abre os olhos pela metade, mesmo dormindo.
- **Alguém se mexe:** os olhos seguem o rosto mais perto.
- **Duas pessoas ou mais:** os olhos vão para quem está falando (o robô compara o som com o movimento das bocas, a até uns 2 m).
- **Alguém levanta a mão:** depois de 1,5 segundo, aparece ✋ na tela, o Byte olha para a pessoa e diz "Pode falar!". Se ele estiver falando, espera terminar. Para pedir de novo, baixe a mão e levante outra vez.
- **Chega alguém cadastrado:** cumprimenta pelo nome ("Oi, Ana!"), no máximo uma vez a cada 30 minutos, e fica ouvindo.
- **Chega alguém desconhecido numa sala vazia:** diz "Oi!". Vem desligado: liga em `VISAO_CUMPRIMENTAR_DESCONHECIDOS`.
- **Todos saem:** fecha os olhos e volta o "z z z".
- **Ninguém fala com ele por 1 minuto:** fica sonolento e boceja.

**Expressões:** alegria, dúvida, surpresa e sono. O Gemini escolhe a expressão de cada resposta, e o robô usa as mesmas ao cumprimentar, tirar uma foto ou não entender algo.

**Toques na tela:**

- Com uma imagem aberta, o toque só fecha a imagem.
- Com um cartão aberto, o toque só fecha o cartão.
- Sem imagem nem cartão, o toque acorda o robô.

## No computador (para o professor)

Rode na pasta do projeto, no terminal do NucBox.

| Comando | Para quê |
| --- | --- |
| `sudo systemctl restart robo-byte` | Reiniciar o robô (depois de mudar o `config.py`) |
| `sudo systemctl stop robo-byte` | Parar o robô até o próximo boot |
| `journalctl -u robo-byte -f` | Ver o que o robô está fazendo e os erros |
| `./iniciar.sh` | Ligar à mão, para testes (pare o modo automático antes) |
| `./ativar_modo_automatico.sh` | Ligar sozinho sempre que o NucBox ligar |
| `./desativar_modo_automatico.sh` | Desligar o modo automático |
| `.venv/bin/python ferramentas/rostos.py listar` | Ver quem o robô conhece |
| `.venv/bin/python ferramentas/rostos.py renomear Ana "Ana Clara"` | Corrigir um nome mal entendido |
| `.venv/bin/python ferramentas/rostos.py apagar Ana` | Apagar uma pessoa |
| `.venv/bin/python ferramentas/rostos.py apagar-todos` | Apagar todo mundo (pede confirmação) |
| `.venv/bin/python ferramentas/rostos.py cadastrar Ana f1.jpg f2.jpg` | Cadastrar a partir de fotos |
| `.venv/bin/python ferramentas/rostos.py testar foto.jpg` | Ver quem ele reconhece numa foto |
| `.venv/bin/python -m robo.imagens placa-mãe` | Testar a busca na Wikipédia |
| `.venv/bin/python -m robo.cerebro` | Conversar com a IA pelo teclado |
| `.venv/bin/python -m robo.comandos` | Ver qual comando cada frase vira |
| `.venv/bin/python -m robo.voz` | Testar a voz (salva `teste_voz.wav`) |
| `.venv/bin/python ferramentas/baixar_modelos.py` | Baixar de novo os modelos |
| `.venv/bin/python ferramentas/baixar_modelos.py visao` | Baixar só os modelos de rostos e mãos |
| `.venv/bin/python -m robo.visao foto.jpg` | Ver quantos rostos e mãos ele acha numa foto, e o tempo gasto |
| `.venv/bin/python -m robo.marcas "[alegria] Oi!"` | Ver como uma resposta da IA é separada em fala e marcas |

Depois de mexer no cadastro de rostos pelo terminal, reinicie o robô.
