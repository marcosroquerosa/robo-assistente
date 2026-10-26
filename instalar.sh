#!/bin/bash
# ============================================================
#  INSTALAR O ROBO NO LUBUNTU (rode uma vez, com internet)
#  Na pasta do projeto:   bash instalar.sh
# ============================================================
set -e
cd "$(dirname "$0")"

echo "[1/5] Instalando programas do sistema (pede sua senha)..."
sudo apt update
sudo apt install -y python3-venv python3-pip adb curl unzip alsa-utils

echo "[2/5] Instalando o Ollama (cérebro)..."
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "  o Ollama já está instalado."
fi

echo "[3/5] Criando o ambiente do robô (.venv) e instalando as bibliotecas..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "[4/5] Baixando os modelos de ouvido, entendimento e voz..."
.venv/bin/python ferramentas/baixar_modelos.py

echo "[5/5] Baixando o cérebro (IA local)..."
ollama pull gemma3:1b

chmod +x iniciar.sh ativar_modo_automatico.sh desativar_modo_automatico.sh
echo
echo "Tudo instalado!"
echo "  Para testar à mão:          ./iniciar.sh"
echo "  Para ligar sozinho sempre:  ./ativar_modo_automatico.sh"
