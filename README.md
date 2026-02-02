# Sistema de Extracción Inteligente de Documentos

Sistema para extraer y analizar información de documentos PDF oficiales mexicanos.

## Archivos Principales

1. consultorsecihtyextractor.py - Extracción masiva de información
2. consultorsecihtyanalisis.py - Análisis con consultas en español natural
3. config.py - Configuración centralizada

## Instalación

pip install -r requirements.txt

## Uso

Extracción masiva:
python consultorsecihtyextractor.py proyectos
python consultorsecihtyextractor.py personas
python consultorsecihtyextractor.py instituciones

Consultas en español:
python consultorsecihtyanalisis.py "De qué trata el proyecto Olinia?"
python consultorsecihtyanalisis.py "En qué documentos aparece el IPN?"
python consultorsecihtyanalisis.py "proyectos"

## Configuración

Editar config.py para:
- Configurar API Key de DeepSeek
- Especificar ruta de documentos PDF

Los documentos PDF deben estar en: /home/roger/Downloads/Comunicados Secihti/
