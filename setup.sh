#!/bin/bash

echo "Instalando Sistema de Extracción de Documentos"

if ! command -v python3 &> /dev/null; then
    echo "Python3 no encontrado. Instalar con: sudo apt install python3"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "pip3 no encontrado. Instalar con: sudo apt install python3-pip"
    exit 1
fi

read -p "Crear entorno virtual? (s/n): " crear_venv
if [[ $crear_venv == "s" || $crear_venv == "S" ]]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Entorno virtual activado"
fi

echo "Instalando dependencias..."
pip3 install -r requirements.txt

echo "Verificando instalación..."
python3 -c "import pdfplumber; print('pdfplumber instalado')"
python3 -c "import requests; print('requests instalado')"
python3 -c "import openai; print('openai instalado')"

echo "Ejecutando pruebas..."
python3 tests/test_config.py

echo ""
echo "Instalación completada"
echo ""
echo "USO:"
echo "   Extracción masiva:  python consultorsecihtyextractor.py proyectos"
echo "   Consulta natural:   python consultorsecihtyanalisis.py 'De qué trata el proyecto Olinia?'"
echo ""
echo "Recordar:"
echo "   1. Verificar API Key en config.py"
echo "   2. Los PDFs deben estar en /home/roger/Downloads/Comunicados Secihti/"
