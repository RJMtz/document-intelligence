#!/usr/bin/env python3
"""
CONFIG.PY - Configuración del sistema
"""

# ========== CONFIGURACIÓN API ==========
API_KEY = "sk-1fd02fbdb4e340ae9203c9a7258acaa6"
BASE_URL = "https://api.deepseek.com"

# ========== RUTAS PARA COMUNICADOS SECIHTI ==========
import glob
import os

CARPETA_SECIHTI = "/home/roger/Downloads/Comunicados Secihti"

# Obtener todos los PDFs
ARCHIVOS_SECIHTI = glob.glob(os.path.join(CARPETA_SECIHTI, "*.pdf"))

# Para compatibilidad con scripts anteriores
ARCHIVOS_ENTRADA = ARCHIVOS_SECIHTI
SOLO_SECIHTI = True

# ========== CONFIGURACIÓN OPCIONAL ==========
# (Las variables que usaban tus scripts originales)
MAX_TOKENS_RESPUESTA = 4000
TEMPERATURA = 0.1
MODELO = "deepseek-chat"
