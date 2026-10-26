#!/bin/bash
# ============================================================
#  DESATIVAR O MODO AUTOMÁTICO
#  O robô para e não liga mais sozinho. Rode:  ./desativar_modo_automatico.sh
# ============================================================
sudo systemctl disable --now robo-byte
sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target
echo "Modo automático desativado. Para ligar à mão: ./iniciar.sh"
