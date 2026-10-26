#!/bin/bash
# ============================================================
#  LIGAR O ROBO À MÃO (para testes)
#  1. Ligue o celular no NucBox pelo cabo (Depuração USB ativada)
#  2. Rode:  ./iniciar.sh
#  3. No celular, abra o Chrome em http://localhost:8000
#  Se o modo automático estiver ativo, pare-o antes:
#     sudo systemctl stop robo-byte
# ============================================================
cd "$(dirname "$0")"
echo "Ligando o caminho do celular até o computador (adb reverse)..."
adb reverse tcp:8000 tcp:8000
.venv/bin/python -m robo.servidor
