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

## 5. Cérebro na internet (opcional, mais esperto)

O robô pode usar uma IA na internet no lugar do Gemma local. Se a internet cair,
ele volta sozinho para o Gemma. Vem configurado para o Google Gemini, que tem plano gratuito.

1. Crie uma chave em aistudio.google.com (entre com uma conta Google, menu "Get API key").
2. Salve a chave num arquivo chamado `chave_web.txt` na pasta do projeto:
   ```
   nano ~/robo-assistente/chave_web.txt
   ```
   Cole a chave, salve com Ctrl+O e Enter, saia com Ctrl+X.
3. No `robo/config.py`, mude `CEREBRO = "local"` para `CEREBRO = "web"`.
4. Reinicie: `sudo systemctl restart robo-byte`.

No modo web, o texto das perguntas (não o áudio) vai para o serviço escolhido.
Confira os termos de uso dele antes de usar com alunos.

## Se der problema

- **`adb devices` mostra `no permissions`:** rode `./ativar_modo_automatico.sh` (ele cria a permissão),
  depois desconecte e reconecte o cabo.
- **Erro do pip ao instalar as bibliotecas:** me mande a mensagem. Algumas bibliotecas podem
  ainda não ter versão pronta para o Python mais novo do sistema.
- **Erro de conexão com o Ollama:** `sudo systemctl restart ollama`.
