#!/bin/bash
# ============================================================
#  ATIVAR O MODO AUTOMÁTICO
#  Depois disto, o robô liga sozinho sempre que o NucBox ligar,
#  sem precisar entrar no usuário. Rode:  ./ativar_modo_automatico.sh
# ============================================================
set -e
cd "$(dirname "$0")"
PASTA="$(pwd)"
USUARIO="$(whoami)"

echo "[1/4] Permissão para o robô usar o celular pelo cabo..."
# Regra para celulares Motorola (fabricante 22b8) e para o grupo plugdev
sudo tee /etc/udev/rules.d/51-robo-celular.rules >/dev/null <<EOF
SUBSYSTEM=="usb", ATTR{idVendor}=="22b8", MODE="0666", GROUP="plugdev"
EOF
sudo usermod -aG plugdev "$USUARIO"
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "[2/4] Impedindo o computador de dormir..."
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

echo "[3/4] Criando o serviço do robô (robo-byte)..."
sudo tee /etc/systemd/system/robo-byte.service >/dev/null <<EOF
[Unit]
Description=Robo Byte - assistente de aulas
After=network-online.target ollama.service
Wants=ollama.service

[Service]
User=$USUARIO
WorkingDirectory=$PASTA
Environment=PYTHONUNBUFFERED=1
ExecStart=$PASTA/.venv/bin/python $PASTA/ferramentas/automatico.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "[4/4] Ligando o serviço..."
sudo systemctl daemon-reload
sudo systemctl enable --now robo-byte

echo
echo "Modo automático ativo! O robô já está ligando."
echo "  Ver o que o robô está fazendo:  journalctl -u robo-byte -f"
echo "  Reiniciar o robô:               sudo systemctl restart robo-byte"
echo "  Desligar o modo automático:     ./desativar_modo_automatico.sh"
