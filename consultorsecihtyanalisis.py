"""
CONSULTOR SECIHTI v32 - SISTEMA DE ANÁLISIS INTELIGENTE

Sistema para responder preguntas en español natural con razonamiento contextual,
analizando documentos oficiales y proporcionando respuestas verificadas.
"""

import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import hashlib
import glob

# =============================================================================
# CONFIGURACIÓN DEEPSEEK
# =============================================================================

DEEPSEEK_CONFIG = {
    "api_key": "sk-1fd02fbdb4e340ae9203c9a7258acaa6",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "max_context_tokens": 32000,
    "max_response_tokens": 4000,
}

# =============================================================================
# CLASE ANALIZADORCONSULTA
# =============================================================================

class AnalizadorConsulta:
    """
    Analiza consultas en español natural para determinar tipo y parámetros.
    
    Methods
    -------
    analizar(consulta_texto)
        Analiza texto de consulta y retorna estructura con tipo y parámetros.
    _determinar_accion(tipo)
        Mapea tipo de consulta a acción específica.
    
    Attributes
    ----------
    patrones : List[Tuple]
        Patrones regex para detectar tipos de consulta.
    
    Notes
    -----
    Los patrones están ordenados por especificidad (más específicos primero).
    """
    
    @staticmethod
    def analizar(consulta_texto: str) -> Dict[str, Any]:
        """
        Analiza una consulta en español natural.
        
        Parameters
        ----------
        consulta_texto : str
            Texto de la consulta del usuario.
        
        Returns
        -------
        Dict[str, Any]
            Diccionario con:
            - tipo: Categoría de la consulta
            - parametros: Parámetros extraídos
            - consulta_original: Texto original
            - accion: Acción a realizar
        
        Examples
        --------
        >>> AnalizadorConsulta.analizar("De qué trata el proyecto Olinia?")
        {'tipo': 'info_proyecto', 'parametros': {'proyecto': 'Olinia'}, ...}
        
        >>> AnalizadorConsulta.analizar("Es verdad que Kutsari trata sobre petróleo?")
        {'tipo': 'verificar', 'parametros': {'afirmacion': 'Kutsari trata sobre petróleo'}, ...}
        """
        consulta = consulta_texto.lower().strip()
        
        # Patrones de detección ordenados por especificidad
        patrones = [
            # Info de proyecto específico
            (r'(?:de\s+qu[ée]\s+trata|qu[ée]\s+es|en\s+qu[ée]\s+consiste)\s+(?:el\s+)?(proyecto)?\s*(?:["\'])?([^"\'\?]+)(?:["\'])?\s*\??', 
             'info_proyecto', lambda m: {"proyecto": m.group(2).strip()}),
            
            # Verificación de afirmaciones
            (r'(?:es\s+(?:verdad|mentira|cierto|falso)|verdad\s+o\s+mentira)[\s:,]*(.+)', 
             'verificar', lambda m: {"afirmacion": m.group(1).strip()}),
            
            # Búsqueda en documentos
            (r'(?:en\s+qu[ée]\s+documentos|d[óo]nde\s+aparece)[\s:,]+(.+)', 
             'buscar_documentos', lambda m: {"busqueda": m.group(1).strip()}),
            
            # Extracción de listas
            (r'^(?:dame|muestra|lista|extrae)\s+(?:los\s+)?(proyectos|personas|instituciones)', 
             'lista_simple', lambda m: {"tipo": m.group(1)}),
            
            # Consultas directas
            (r'^proyectos$', 'proyectos', lambda m: {}),
            (r'^personas$', 'personas', lambda m: {}),
            (r'^instituciones$', 'instituciones', lambda m: {}),
            
            # Preguntas generales
            (r'(.+\?)', 'pregunta_general', lambda m: {"pregunta": m.group(1)}),
        ]
        
        # Probar cada patrón
        for patron, tipo, extractor in patrones:
            match = re.match(patron, consulta, re.IGNORECASE)
            if match:
                return {
                    "tipo": tipo,
                    "parametros": extractor(match),
                    "consulta_original": consulta_texto,
                    "accion": AnalizadorConsulta._determinar_accion(tipo)
                }
        
        # Por defecto: búsqueda general
        return {
            "tipo": "busqueda_general",
            "parametros": {"texto": consulta_texto},
            "consulta_original": consulta_texto,
            "accion": "buscar_informacion"
        }
    
    @staticmethod
    def _determinar_accion(tipo: str) -> str:
        """
        Mapea tipo de consulta a acción específica.
        
        Parameters
        ----------
        tipo : str
            Tipo de consulta detectado.
        
        Returns
        -------
        str
            Acción correspondiente al tipo.
        """
        acciones = {
            'info_proyecto': 'obtener_info_proyecto',
            'verificar': 'verificar_afirmacion',
            'buscar_documentos': 'buscar_en_documentos',
            'lista_simple': 'extraer_lista',
            'proyectos': 'extraer_proyectos',
            'personas': 'extraer_personas',
            'instituciones': 'extraer_instituciones',
            'pregunta_general': 'responder_pregunta',
            'busqueda_general': 'buscar_informacion'
        }
        return acciones.get(tipo, 'buscar_informacion')

# =============================================================================
# CLASE GESTORPROMPTS
# =============================================================================

class GestorPrompts:
    """
    Administra prompts especializados para cada tipo de consulta.
    
    Attributes
    ----------
    PROMPTS : Dict[str, Dict]
        Diccionario de prompts organizados por tipo de consulta.
    
    Methods
    -------
    obtener_prompt(tipo_consulta, parametros)
        Retorna prompt personalizado con parámetros insertados.
    """
    
    PROMPTS = {
        'info_proyecto': {
            'system': """Eres un experto en proyectos de investigación mexicano.
            Analiza documentos oficiales y extrae información precisa.
            Responde en español con claridad.""",
            
            'user': """Analiza los documentos e informa sobre este proyecto:

PROYECTO: {proyecto}

DOCUMENTOS:
{documentos}

INSTRUCCIONES:
1. Enfócate exclusivamente en el proyecto "{proyecto}"
2. Extrae toda la información relevante
3. Organiza en categorías:
   - Descripción
   - Objetivo
   - Instituciones participantes
   - Estado actual
   - Alcance
   - Impacto

4. Para cada información, cita el documento exacto
5. Si no hay información sobre algún aspecto, indica "No se menciona"

RESPONDA en formato JSON:
{{
  "proyecto": "{proyecto}",
  "informacion_encontrada": {{
    "descripcion": {{
      "texto": "Descripción",
      "documentos": ["doc1.pdf"],
      "confianza": "alta/media/baja"
    }},
    "objetivo": {{...}}
  }},
  "documentos_relevantes": ["doc1.pdf"],
  "resumen_ejecutivo": "Resumen breve"
}}"""
        },
        
        'verificar': {
            'system': """Eres un verificador de hechos basado en documentos.
            Determina la veracidad usando solo evidencia documental.""",
            
            'user': """Verifica esta afirmación:

AFIRMACIÓN: "{afirmacion}"

DOCUMENTOS:
{documentos}

INSTRUCCIONES:
1. Busca evidencia concreta
2. Clasifica como:
   - VERDADERA: Evidencia clara la respalda
   - FALSA: Evidencia clara la contradice
   - NO CONCLUYENTE: Evidencia insuficiente
   - PARCIALMENTE VERDADERA: Algunos elementos son ciertos

3. Para cada evidencia:
   - Cita el documento
   - Copia la frase relevante
   - Indica si respalda o refuta

RESPONDA en formato JSON:
{{
  "afirmacion": "{afirmacion}",
  "veredicto": "verdadera/falsa/no_concluyente/parcialmente_verdadera",
  "explicacion_detallada": "Análisis completo",
  "evidencia": [
    {{
      "tipo": "respalda/refuta",
      "texto": "Frase exacta",
      "documento": "nombre.pdf"
    }}
  ],
  "confianza_general": "alta/media/baja"
}}"""
        },
        
        'buscar_documentos': {
            'system': """Eres un buscador experto en documentos oficiales.""",
            
            'user': """Encuentra esta información:

BÚSQUEDA: "{busqueda}"

DOCUMENTOS:
{documentos}

INSTRUCCIONES:
1. Busca todas las menciones relacionadas
2. Para cada mención:
   - Extrae el contexto
   - Identifica el documento
   - Indica relevancia

3. Organiza por relevancia

RESPONDA en formato JSON:
{{
  "busqueda": "{busqueda}",
  "resultados": {{
    "encontrado": true/false,
    "total_menciones": número,
    "menciones_detalladas": [
      {{
        "documento": "nombre.pdf",
        "contexto": "Texto completo",
        "relevancia": "alta/media/baja"
      }}
    ]
  }},
  "resumen": "Resumen de lo encontrado"
}}"""
        }
    }
    
    @classmethod
    def obtener_prompt(cls, tipo_consulta: str, parametros: Dict) -> Dict:
        """
        Obtiene prompt personalizado para tipo de consulta.
        
        Parameters
        ----------
        tipo_consulta : str
            Tipo de consulta detectado.
        parametros : Dict
            Parámetros extraídos de la consulta.
        
        Returns
        -------
        Dict
            Diccionario con 'system' y 'user' prompts.
        
        Notes
        -----
        Reemplaza placeholders {param} en el prompt con valores reales.
        Si no encuentra el tipo, usa prompt genérico.
        """
        if tipo_consulta in cls.PROMPTS:
            prompt_data = cls.PROMPTS[tipo_consulta].copy()
            user_prompt = prompt_data['user']
            
            # Reemplazar parámetros en el prompt
            for key, value in parametros.items():
                user_prompt = user_prompt.replace(f"{{{key}}}", str(value))
            
            prompt_data['user'] = user_prompt
            return prompt_data
        
        # Prompt genérico para consultas no especificadas
        return {
            'system': "Analiza documentos y responde preguntas.",
            'user': f"Responde a: {parametros.get('texto', '')}\n\nDocumentos:\n{{documentos}}"
        }

# =============================================================================
# CLASE PRINCIPAL - CONSULTORSECIHTIV32
# =============================================================================

class ConsultorSecihtiV32:
    """
    Sistema principal para consultas avanzadas en español natural.
    
    Attributes
    ----------
    cache_dir : Path
        Directorio para cache de resultados.
    
    Methods
    -------
    procesar_consulta(consulta_texto, max_documentos=None)
        Procesa consulta completa desde análisis hasta respuesta.
    extraer_texto_pdf(ruta_pdf, max_paginas=3)
        Extrae texto de PDF de forma eficiente.
    consultar_deepseek(prompt, system_message=None)
        Consulta a API de DeepSeek con cliente OpenAI.
    """
    
    def __init__(self):
        """Inicializa consultor con directorio de cache."""
        self.cache_dir = Path("cache_v32")
        self.cache_dir.mkdir(exist_ok=True)
    
    def extraer_texto_pdf(self, ruta_pdf: str, max_paginas: int = 3) -> str:
        """
        Extrae texto de las primeras páginas de un PDF.
        
        Parameters
        ----------
        ruta_pdf : str
            Ruta al archivo PDF.
        max_paginas : int, optional
            Máximo de páginas a procesar (por defecto 3).
        
        Returns
        -------
        str
            Texto extraído, limitado a 5000 caracteres.
        
        Notes
        -----
        Extrae solo primeras páginas ya que contienen información principal.
        Limitado a 5000 caracteres por eficiencia en procesamiento.
        """
        try:
            import pdfplumber
            
            texto = ""
            with pdfplumber.open(ruta_pdf) as pdf:
                for i, pagina in enumerate(pdf.pages[:max_paginas]):
                    texto_pag = pagina.extract_text()
                    if texto_pag:
                        texto += texto_pag + "\n\n"
            
            return texto[:5000]  # Limitar para eficiencia
            
        except Exception as e:
            print(f"Error en {Path(ruta_pdf).name[:30]}: {str(e)[:50]}")
            return ""
    
    def consultar_deepseek(self, prompt: str, system_message: str = None) -> str:
        """
        Consulta a DeepSeek API usando cliente OpenAI compatible.
        
        Parameters
        ----------
        prompt : str
            Prompt del usuario.
        system_message : str, optional
            Mensaje del sistema para contexto.
        
        Returns
        -------
        str
            Respuesta de la API o mensaje de error.
        
        Raises
        ------
        ImportError
            Si no está instalado el paquete openai.
        
        Notes
        -----
        Usa temperatura baja (0.1) para respuestas más determinísticas.
        """
        try:
            from openai import OpenAI
            
            cliente = OpenAI(
                api_key=DEEPSEEK_CONFIG['api_key'],
                base_url=DEEPSEEK_CONFIG['base_url']
            )
            
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            respuesta = cliente.chat.completions.create(
                model=DEEPSEEK_CONFIG['model'],
                messages=messages,
                max_tokens=DEEPSEEK_CONFIG['max_response_tokens'],
                temperature=0.1
            )
            
            return respuesta.choices[0].message.content
            
        except Exception as e:
            return f"ERROR: {str(e)[:100]}"
    
    def procesar_consulta(self, consulta_texto: str, max_documentos: int = None) -> Dict:
        """
        Procesa consulta completa: análisis, extracción, consulta y respuesta.
        
        Parameters
        ----------
        consulta_texto : str
            Consulta del usuario en español natural.
        max_documentos : int, optional
            Límite de documentos para pruebas.
        
        Returns
        -------
        Dict
            Resultado estructurado de la consulta.
        
        Workflow
        --------
        1. Analizar consulta para determinar tipo y parámetros
        2. Cargar y extraer texto de documentos
        3. Preparar prompt específico para el tipo de consulta
        4. Consultar a DeepSeek API
        5. Procesar y formatear respuesta
        6. Guardar resultados
        """
        # Paso 1: Analizar consulta
        print(f"\nCONSULTA: {consulta_texto}")
        print("=" * 60)
        
        analisis = AnalizadorConsulta.analizar(consulta_texto)
        print(f"Tipo detectado: {analisis['tipo']}")
        
        # Paso 2: Cargar documentos
        pdf_paths = self._cargar_documentos(max_documentos)
        
        if not pdf_paths:
            return {"error": "No se encontraron documentos"}
        
        print(f"Documentos a procesar: {len(pdf_paths)}")
        
        # Paso 3: Extraer textos
        textos_documentos = self._extraer_textos_documentos(pdf_paths)
        
        if not textos_documentos:
            return {"error": "No se pudo extraer texto de los documentos"}
        
        # Paso 4: Preparar prompt
        prompt_data = GestorPrompts.obtener_prompt(
            analisis['tipo'], 
            analisis['parametros']
        )
        
        textos_combinados = self._formatear_textos_documentos(
            textos_documentos, 
            pdf_paths
        )
        
        prompt_final = prompt_data['user'].replace("{documentos}", textos_combinados)
        
        # Paso 5: Consultar a DeepSeek
        print("Consultando a DeepSeek...")
        respuesta = self.consultar_deepseek(prompt_final, prompt_data['system'])
        
        # Paso 6: Procesar respuesta
        resultado = self._procesar_respuesta(respuesta, analisis)
        self._guardar_resultado(consulta_texto, resultado)
        self._mostrar_resultado(resultado, analisis['tipo'])
        
        return resultado
    
    def _cargar_documentos(self, max_docs: int = None) -> List[str]:
        """
        Carga rutas de documentos PDF desde directorio predeterminado.
        
        Parameters
        ----------
        max_docs : int, optional
            Límite de documentos a cargar.
        
        Returns
        -------
        List[str]
            Lista de rutas a archivos PDF.
        
        Notes
        -----
        Ruta predeterminada: /home/roger/Downloads/Comunicados Secihti/
        Ordena por nombre descendente para priorizar documentos recientes.
        """
        pdf_paths = glob.glob("/home/roger/Downloads/Comunicados Secihti/*.pdf")
        
        if max_docs and max_docs < len(pdf_paths):
            # Priorizar documentos más recientes (orden alfabético inverso)
            pdf_paths = sorted(
                pdf_paths,
                key=lambda x: Path(x).name,
                reverse=True
            )[:max_docs]
        
        return pdf_paths
    
    def _extraer_textos_documentos(self, pdf_paths: List[str]) -> List[tuple]:
        """
        Extrae texto de todos los documentos PDF.
        
        Parameters
        ----------
        pdf_paths : List[str]
            Rutas a archivos PDF.
        
        Returns
        -------
        List[tuple]
            Lista de tuplas (nombre_documento, texto_extraído).
        
        Notes
        -----
        Muestra progreso durante la extracción.
        Solo incluye documentos con más de 200 caracteres de texto.
        """
        textos = []
        
        for i, ruta in enumerate(pdf_paths, 1):
            nombre = Path(ruta).name
            print(f"  [{i:3d}/{len(pdf_paths)}] {nombre[:45]:45}", end="")
            
            texto = self.extraer_texto_pdf(ruta)
            
            if texto and len(texto) > 200:
                textos.append((nombre, texto))
                print(" OK")
            else:
                print(" Sin texto")
        
        return textos
    
    def _formatear_textos_documentos(self, textos: List[tuple], rutas: List[str]) -> str:
        """
        Formatea textos para inclusión en prompt.
        
        Parameters
        ----------
        textos : List[tuple]
            Lista de (nombre, texto) de documentos.
        rutas : List[str]
            Rutas originales (no usadas, mantenido por compatibilidad).
        
        Returns
        -------
        str
            Texto formateado con encabezados de documentos.
        
        Notes
        -----
        Limita cada documento a 2000 caracteres para mantener prompt manejable.
        """
        resultado = []
        
        for nombre, texto in textos:
            resultado.append(f"--- DOCUMENTO: {nombre} ---")
            resultado.append(texto[:2000])  # Limitar tamaño
            resultado.append("")  # Línea en blanco
        
        return "\n".join(resultado)
    
    def _procesar_respuesta(self, respuesta: str, analisis: Dict) -> Dict:
        """
        Procesa respuesta de DeepSeek extrayendo JSON si está presente.
        
        Parameters
        ----------
        respuesta : str
            Respuesta completa de la API.
        analisis : Dict
            Análisis original de la consulta.
        
        Returns
        -------
        Dict
            Respuesta procesada con metadatos.
        
        Notes
        -----
        Intenta extraer JSON de la respuesta usando regex.
        Si no encuentra JSON, incluye respuesta como texto.
        """
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{.*\}', respuesta, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                data["consulta"] = analisis["consulta_original"]
                data["tipo_consulta"] = analisis["tipo"]
                data["timestamp"] = datetime.now().isoformat()
                return data
        except:
            pass  # Si falla, continuar con respuesta textual
        
        # Fallback: respuesta no JSON
        return {
            "consulta": analisis["consulta_original"],
            "tipo_consulta": analisis["tipo"],
            "respuesta_texto": respuesta[:1000],
            "timestamp": datetime.now().isoformat(),
            "advertencia": "Respuesta no está en formato JSON estructurado"
        }
    
    def _guardar_resultado(self, consulta: str, resultado: Dict) -> None:
        """
        Guarda resultado en archivo JSON con timestamp.
        
        Parameters
        ----------
        consulta : str
            Consulta original del usuario.
        resultado : Dict
            Resultado procesado.
        
        Notes
        -----
        Nombre de archivo incluye timestamp para unicidad.
        Formato: resultados_v32_YYYYMMDD_HHMMSS.json
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = f"resultados_v32_{timestamp}.json"
        
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump({
                "consulta": consulta,
                "fecha": datetime.now().isoformat(),
                "resultado": resultado
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\nResultado guardado en: {archivo}")
    
    def _mostrar_resultado(self, resultado: Dict, tipo_consulta: str) -> None:
        """
        Muestra resultado de forma legible según tipo de consulta.
        
        Parameters
        ----------
        resultado : Dict
            Resultado a mostrar.
        tipo_consulta : str
            Tipo de consulta para formateo específico.
        """
        print(f"\n{'='*60}")
        print(f"RESULTADO - Tipo: {tipo_consulta}")
        print(f"{'='*60}")
        
        if "error" in resultado:
            print(f"Error: {resultado['error']}")
            return
        
        # Mostrar según tipo de consulta
        if tipo_consulta == "info_proyecto":
            self._mostrar_info_proyecto(resultado)
        elif tipo_consulta == "verificar":
            self._mostrar_verificacion(resultado)
        elif tipo_consulta == "buscar_documentos":
            self._mostrar_busqueda(resultado)
        else:
            # Mostrar genérico
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
    
    def _mostrar_info_proyecto(self, resultado: Dict) -> None:
        """Muestra información de proyecto de forma legible."""
        if "proyecto" in resultado:
            print(f"\nPROYECTO: {resultado['proyecto']}")
        
        if "resumen_ejecutivo" in resultado:
            print(f"\nRESUMEN: {resultado['resumen_ejecutivo']}")
        
        if "informacion_encontrada" in resultado:
            info = resultado["informacion_encontrada"]
            print(f"\nINFORMACIÓN ENCONTRADA:")
            
            for categoria, datos in info.items():
                if isinstance(datos, dict) and "texto" in datos:
                    print(f"\n  {categoria.upper()}: {datos['texto'][:150]}...")
    
    def _mostrar_verificacion(self, resultado: Dict) -> None:
        """Muestra resultado de verificación."""
        if "afirmacion" in resultado:
            print(f"\nAFIRMACIÓN: {resultado['afirmacion']}")
        
        if "veredicto" in resultado:
            veredicto = resultado["veredicto"]
            print(f"\nVEREDICTO: {veredicto.upper()}")
        
        if "explicacion_detallada" in resultado:
            print(f"\nEXPLICACIÓN: {resultado['explicacion_detallada'][:300]}...")
    
    def _mostrar_busqueda(self, resultado: Dict) -> None:
        """Muestra resultados de búsqueda."""
        if "busqueda" in resultado:
            print(f"\nBÚSQUEDA: {resultado['busqueda']}")
        
        if "resultados" in resultado:
            res = resultado["resultados"]
            
            if res.get("encontrado", False):
                print(f"\nENCONTRADO: {res.get('total_menciones', 0)} menciones")
                
                if "menciones_detalladas" in res and res["menciones_detalladas"]:
                    primera = res["menciones_detalladas"][0]
                    print(f"\nDOCUMENTO: {primera.get('documento', '')}")
                    print(f"CONTEXTO: {primera.get('contexto', '')[:200]}...")
            else:
                print(f"\nNO SE ENCONTRÓ INFORMACIÓN")

# =============================================================================
# FUNCIONES DE INTERFAZ
# =============================================================================

def mostrar_ayuda() -> None:
    """
    Muestra mensaje de ayuda con ejemplos de uso.
    
    Notes
    -----
    Incluye ejemplos reales de consultas que el sistema puede procesar.
    """
    print("""
CONSULTOR SECIHTI v32 - PREGUNTAS EN ESPAÑOL NATURAL

USO:
  python consultorsecihty32.py "tu consulta"

EJEMPLOS:

SOBRE PROYECTOS:
  python consultorsecihty32.py "De qué trata el proyecto Olinia?"
  python consultorsecihty32.py "Qué es el proyecto Kutsari?"

VERIFICACIONES:
  python consultorsecihty32.py "Es verdad que Kutsari trata sobre petróleo?"

BÚSQUEDAS:
  python consultorsecihty32.py "En qué documentos aparece el IPN?"

EXTRACCIONES:
  python consultorsecihty32.py "Dame los proyectos"
  python consultorsecihty32.py "proyectos"

OPCIONES:
  python consultorsecihty32.py --probar 5    # Probar con 5 documentos
  python consultorsecihty32.py --limpiar     # Limpiar cache
  python consultorsecihty32.py --ayuda       # Mostrar esta ayuda
""")


def limpiar_cache() -> None:
    """Elimina directorio de cache si existe."""
    import shutil
    cache_dir = Path("cache_v32")
    
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("Cache limpiado")
    else:
        print("No hay cache para limpiar")


def main() -> None:
    """
    Función principal de línea de comandos.
    
    Workflow
    --------
    1. Verificar argumentos
    2. Procesar comandos especiales
    3. Crear consultor y procesar consulta
    4. Manejar errores
    
    Raises
    ------
    SystemExit
        Si hay errores fatales o dependencias faltantes.
    """
    # Verificar argumentos mínimos
    if len(sys.argv) < 2:
        mostrar_ayuda()
        return
    
    # Comandos especiales
    if sys.argv[1] == "--ayuda" or sys.argv[1] == "-h":
        mostrar_ayuda()
        return
    elif sys.argv[1] == "--limpiar":
        limpiar_cache()
        return
    elif sys.argv[1] == "--test":
        # Modo prueba de detección de consultas
        pruebas = [
            "De qué trata el proyecto Olinia?",
            "En qué documentos aparece el IPN?",
            "Es verdad que el proyecto Kutsari trata sobre petróleo?",
        ]
        
        print("PROBANDO DETECCIÓN DE CONSULTAS:")
        print("=" * 60)
        
        for prueba in pruebas:
            analisis = AnalizadorConsulta.analizar(prueba)
            print(f"\nConsulta: '{prueba}'")
            print(f"  → Tipo: {analisis['tipo']}")
            print(f"  → Parámetros: {analisis['parametros']}")
        
        return
    
    # Unir argumentos como consulta
    consulta_texto = " ".join(sys.argv[1:])
    
    # Verificar modo prueba
    max_docs = None
    if "--probar" in sys.argv:
        for arg in sys.argv:
            if arg.isdigit():
                max_docs = int(arg)
                break
        max_docs = max_docs or 5
        print(f"MODO PRUEBA: {max_docs} documentos")
    
    # Crear y ejecutar consultor
    consultor = ConsultorSecihtiV32()
    
    try:
        resultado = consultor.procesar_consulta(consulta_texto, max_docs)
        
        # Mostrar finalización
        print(f"\n{'='*60}")
        print("CONSULTA COMPLETADA")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        print("\nSUGERENCIAS:")
        print("   1. Verifica que los PDFs estén en la carpeta correcta")
        print("   2. Asegúrate de tener conexión a internet")
        print("   3. Prueba con menos documentos: --probar 3")


def verificar_dependencias() -> bool:
    """
    Verifica que las dependencias requeridas estén instaladas.
    
    Returns
    -------
    bool
        True si todas las dependencias están instaladas, False en caso contrario.
    
    Notes
    -----
    Dependencias críticas:
    - pdfplumber: Para extracción de texto de PDF
    - openai: Cliente para API de DeepSeek
    """
    dependencias = [
        ("pdfplumber", "pip install pdfplumber"),
        ("openai", "pip install openai"),
    ]
    
    faltantes = []
    
    for modulo, comando in dependencias:
        try:
            __import__(modulo)
        except ImportError:
            faltantes.append((modulo, comando))
    
    if faltantes:
        print("DEPENDENCIAS FALTANTES:")
        for modulo, comando in faltantes:
            print(f"   - {modulo}: {comando}")
        print("\nEjecuta los comandos de instalación arriba.")
        return False
    
    return True

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    """
    Punto de entrada principal del script.
    
    Workflow
    --------
    1. Mostrar banner de inicio
    2. Verificar dependencias
    3. Ejecutar función principal
    4. Salir con código apropiado
    """
    print("CONSULTOR SECIHTI v32 - INICIANDO...")
    
    # Verificar dependencias críticas
    if not verificar_dependencias():
        sys.exit(1)
    
    # Ejecutar función principal
    main()
