"""
SERVIDOR (a ponte entre o computador e o celular)
=================================================
- Entrega a página do rosto (pasta "rosto") para o navegador do celular.
- Mantém uma conexão aberta (WebSocket) por onde passam:
    celular -> computador: o áudio do microfone e os toques na tela
    computador -> celular: o estado do robô, as legendas e o áudio da fala

Para ligar o robô:   python -m robo.servidor
"""

import json

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from robo import config
from robo.robo import Robo

app = FastAPI()
robo = None  # criado lá embaixo, quando o servidor liga


@app.websocket("/ws")
async def conexao_com_o_rosto(conexao: WebSocket):
    await conexao.accept()
    print("[servidor] o rosto (celular) conectou")
    await robo.conectar_rosto(conexao)
    try:
        while True:
            mensagem = await conexao.receive()
            if mensagem["type"] == "websocket.disconnect":
                break
            if mensagem.get("bytes"):
                await robo.receber_audio(mensagem["bytes"], conexao)
            elif mensagem.get("text"):
                await robo.receber_mensagem(json.loads(mensagem["text"]), conexao)
    except WebSocketDisconnect:
        pass
    finally:
        robo.desconectar_rosto(conexao)
        print("[servidor] o rosto desconectou")


# A página do rosto (tem que vir depois da rota /ws)
app.mount("/", StaticFiles(directory="rosto", html=True), name="rosto")


if __name__ == "__main__":
    robo = Robo()
    print()
    print("=" * 60)
    print(f"  {config.NOME_DO_ROBO} está no ar!")
    print(f"  No celular (ligado no cabo USB), abra: http://localhost:{config.PORTA}")
    print(f"  Para testar no próprio computador:     http://localhost:{config.PORTA}")
    print("  Para desligar: aperte Ctrl+C nesta janela")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=config.PORTA, log_level="warning")
