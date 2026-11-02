# Robô Byte no Lubuntu: passo a passo

## 1. Copiar o projeto

Descompacte este zip na sua pasta pessoal, para ficar `~/robo-assistente`.
Abra o terminal (QTerminal) e entre na pasta:

```
cd ~/robo-assistente
```

## 2. Instalar (uma vez, com internet)

```
bash instalar.sh
```

Ele pede sua senha, instala os programas, o Ollama, as bibliotecas e baixa os modelos.
Pode demorar bastante na primeira vez.

Depois, baixe o cérebro local:

```
ollama pull qwen2.5:0.5b
```

## 3. Testar à mão

1. Ligue o celular no NucBox pelo cabo e aceite "Permitir depuração USB"
   (marque "Sempre permitir deste computador").
2. Confira: `adb devices` deve mostrar um código seguido de `device`.
3. Ligue o robô:
   ```
   ./iniciar.sh
   ```
4. No Chrome do celular, abra `http://localhost:8000`, toque na tela e permita o microfone.

Para desligar: Ctrl+C no terminal.

## 4. Modo automático (liga sozinho com o NucBox)

```
./ativar_modo_automatico.sh
```

Depois disso, o robô vira um serviço do sistema: liga junto com o NucBox,
mesmo sem ninguém entrar no usuário, e religa sozinho se cair.

Ainda é preciso, uma vez:
- **Na BIOS do NucBox** (tecla Del ou Esc ao ligar): "Restore on AC Power Loss" em "Power On".
- **No celular:** bloqueio de tela "Nenhum", e permitir o microfone uma vez à mão.

Comandos úteis:

| Para | Comando |
| --- | --- |
| Ver o que o robô está fazendo (e os tempos) | `journalctl -u robo-byte -f` |
| Reiniciar o robô (depois de mudar o config.py) | `sudo systemctl restart robo-byte` |
| Parar até o próximo boot | `sudo systemctl stop robo-byte` |
| Desligar o modo automático | `./desativar_modo_automatico.sh` |

## 5. Cérebro na internet (mais esperto)

O robô vem com `CEREBRO = "web"` no `robo/config.py`: ele pensa com uma IA na internet e usa o
Qwen2.5 local como reserva. Se a internet cair, ou se não houver chave, ele responde com o Qwen2.5.
Vem configurado para o Google Gemini, que tem plano gratuito.

1. Crie uma chave em aistudio.google.com (entre com uma conta Google, menu "Get API key").
2. Salve a chave num arquivo chamado `chave_web.txt` na pasta do projeto:
   ```
   nano ~/robo-assistente/chave_web.txt
   ```
   Cole a chave, salve com Ctrl+O e Enter, saia com Ctrl+X.
3. Reinicie: `sudo systemctl restart robo-byte`.

Para usar só a IA local, sem internet, mude para `CEREBRO = "local"` e reinicie o robô.

No modo web, o texto das perguntas (não o áudio) vai para o serviço escolhido.
Confira os termos de uso dele antes de usar com alunos.

## Cérebro local: Qwen2.5

O cérebro sem internet é o **Qwen2.5 0.5B**, um modelo pequeno que roda no Ollama. No
`robo/config.py`, ele aparece assim:
```
CEREBRO = "web"
MODELO_IA = "qwen2.5:0.5b"
```
Se o robô já está instalado, baixe o modelo uma vez, com internet:
```
ollama pull qwen2.5:0.5b
sudo systemctl restart robo-byte
```
Para conferir, rode `ollama list`: o `qwen2.5:0.5b` deve aparecer na lista.

Os ajustes dele ficam em `MODELO_IA_OPCOES`, no `config.py`. Só a IA local usa esses ajustes.

## 6. Visão: câmera, fotos e reconhecer pessoas

O robô usa a câmera da frente do celular. Se o robô já está instalado, rode uma vez, com internet:
```
cd ~/robo-assistente
.venv/bin/pip install opencv-python-headless
.venv/bin/python ferramentas/baixar_modelos.py visao
sudo systemctl restart robo-byte
```
Depois recarregue a página no celular e toque em "Permitir" quando o Chrome pedir a câmera.

**O que ele faz sozinho:** abre os olhos quando alguém chega, olha para quem está falando,
atende quem levanta a mão e cumprimenta pelo nome quem já foi cadastrado (no máximo uma
vez a cada 30 minutos).

O comando `baixar_modelos.py visao` também baixa o detector de mãos. Sem ele, o robô
funciona normalmente, só que ignora as mãos. Para desligar esse recurso, use
`VISAO_MAO_LEVANTADA = False` no `config.py`.

**O que dá para pedir:**

| Diga | O robô |
| --- | --- |
| "aprende meu rosto" (ou "meu nome é Ana, aprende meu rosto") | pergunta o nome, pede para você olhar a tela e cadastra |
| "quem sou eu?", "quem você está vendo?" | responde sem internet |
| "esquece o rosto da Ana", "esquece meu rosto" | apaga o cadastro da pessoa |
| "tira uma foto" | conta 3, 2, 1, mostra a foto e guarda na pasta `fotos/` |
| "o que você está vendo?", "lê o quadro", "o que é isso na minha mão?" | manda a foto para o Gemini e responde |

**Privacidade (LGPD):**
- O reconhecimento roda todo no NucBox. O arquivo `dados/rostos.json` guarda só uma
  "assinatura" numérica de cada rosto, nunca a foto.
- Para a internet só vai a foto de quando alguém pede para o robô olhar. Nessa hora aparece
  na tela o aviso laranja "foto enviada para a IA na internet". Essas fotos não são guardadas.
- Rosto é dado biométrico sensível. Para cadastrar alunos, peça autorização dos responsáveis e da escola.
- Cada recurso liga e desliga no `robo/config.py`, na parte "Visão".

**Gerenciar o cadastro pelo teclado:**
```
.venv/bin/python ferramentas/rostos.py listar
.venv/bin/python ferramentas/rostos.py renomear Ana "Ana Clara"
.venv/bin/python ferramentas/rostos.py apagar Ana
.venv/bin/python ferramentas/rostos.py apagar-todos
```
Depois de mexer no cadastro pelo teclado, reinicie o robô.

**Ajustes comuns:**
- Os olhos olham para o lado errado: no `rosto/rosto.js`, troque `INVERTER_OLHAR = false` para `true`.
- Confunde pessoas: aumente `VISAO_LIMIAR_DE_PARECIDO` (ex.: 0.45). Não reconhece: diminua (ex.: 0.36)
  ou cadastre a pessoa de novo (as assinaturas novas se somam às antigas).
- Testar o reconhecimento com uma foto: `.venv/bin/python ferramentas/rostos.py testar foto.jpg`.

## 7. Mostrar imagens ("Byte, mostra uma placa-mãe")

O robô procura o assunto na **Wikipédia em português** e no **Wikimedia Commons** e mostra a imagem
na tela do celular, explicando em voz alta. Não precisa de chave nem de cadastro, só de internet.

1. A Wikipédia e o Commons exigem um contato de quem usa a busca, senão bloqueiam (erro 403). No `robo/config.py`,
   coloque seu e-mail em `IMAGENS_CONTATO`, por exemplo `IMAGENS_CONTATO = "professor@escola.com"`.
   Ele só vai para a Wikipédia e o Commons, junto com o pedido, para eles poderem avisar se houver algum problema.
2. Reinicie: `sudo systemctl restart robo-byte`.
Para testar sem o robô: `.venv/bin/python -m robo.imagens placa-mãe` (só lista o que achou).

| Diga | O robô |
| --- | --- |
| "mostra uma placa-mãe", "quero ver uma memória RAM" | busca, mostra e explica |
| "mostra outra", "a próxima" | a próxima imagem da mesma busca, alternando as duas fontes |
| "fecha a imagem" (ou toque na tela) | tira a imagem da tela |

**Como ele cuida da turma:**
- As imagens têm licença livre. Embaixo da imagem aparece o artigo de onde ela veio ou, no
  Commons, o autor e a licença.
- Antes de mostrar, o Gemini confere se a imagem é mesmo o que foi pedido e se serve para a turma.
  Se não servir, ele tenta a próxima.
- O Commons guarda fotos de todo tipo, então só entra na busca quando o Gemini pode conferir as
  imagens. Sem a IA da web, o robô usa só a Wikipédia, e as imagens aparecem sem conferência.
- Para escolher as fontes, mude `IMAGENS_FONTES` no `config.py`. No Commons, muitas descrições estão
  em inglês, então a busca em português acha menos imagens por lá.
- Nenhuma imagem é gravada no disco: ela fica só na memória e é apagada quando sai da tela
  (depois de 60 segundos, com um toque ou com "fecha a imagem").
- Às vezes a imagem principal do artigo é um desenho ou um esquema, e não uma foto. Se não
  servir, peça "mostra outra" ou use um nome mais específico ("mostra um pente de memória RAM").

## Se der problema

- **`adb devices` mostra `no permissions`:** rode `./ativar_modo_automatico.sh` (ele cria a permissão),
  depois desconecte e reconecte o cabo.
- **Erro do pip ao instalar as bibliotecas:** me mande a mensagem. Algumas bibliotecas podem
  ainda não ter versão pronta para o Python mais novo do sistema.
- **Erro de conexão com o Ollama:** `sudo systemctl restart ollama`.
- **Erro de modelo não encontrado no Ollama:** rode `ollama pull qwen2.5:0.5b` e reinicie o robô.
- **A câmera não liga:** no Chrome do celular, toque no cadeado ao lado do endereço, em
  Permissões, e libere a Câmera. Feche outros apps que usam a câmera.
