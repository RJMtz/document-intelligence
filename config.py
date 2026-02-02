#!/usr/bin/env python3
"""
config.py - Configuración centralizada
"""

import os
from pathlib import Path
import glob

API_KEY = "sk-1fd02fbdb4e340ae9203c9a7258acaa6"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
MAX_RESPONSE_TOKENS = 4000
TEMPERATURE = 0.1

PDF_BASE_PATH = "/home/roger/Downloads/Comunicados Secihti"

def get_pdf_files():
    pdf_files = glob.glob(os.path.join(PDF_BASE_PATH, "*.pdf"))
    return sorted([Path(f) for f in pdf_files])

PDF_FILES = get_pdf_files()

ARCHIVOS_SECIHTI = PDF_FILES
ARCHIVOS_ENTRADA = PDF_FILES
SOLO_SECIHTI = True

PDF_MAX_PAGES = 3
PDF_TEXT_LIMIT = 5000
TOKENS_PER_CHUNK = 26000

print(f"PDFs encontrados: {len(PDF_FILES)}")
