"""
CONSULTOR SECIHTI v31 - SISTEMA DE EXTRACCIÓN MASIVA

Sistema optimizado para extraer información estructurada de documentos PDF,
procesando grandes volúmenes mediante chunks inteligentes con límites de tokens.
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import hashlib

# =============================================================================
# CONFIGURACIÓN DEEPSEEK
# =============================================================================

DEEPSEEK_CONFIG = {
    "api_key": "sk-1fd02fbdb4e340ae9203c9a7258acaa6",
    "base_url": "https://api.deepseek.com/v1/chat/completions",
    "model": "deepseek-chat",
    "max_context_tokens": 32000,
    "max_response_tokens": 4000,
    "reserved_tokens": 2000,
}

TOKENS_POR_CHUNK = 26000  # 32K (máximo) - 4K (respuesta) - 2K (reserva)

# =============================================================================
# FUNCIONES DE ESTIMACIÓN DE TOKENS
# =============================================================================

def estimar_tokens_espanol(texto: str) -> int:
    """
    Estima el número de tokens para texto en español.
    
    Parameters
    ----------
    texto : str
        Texto a analizar.
    
    Returns
    -------
    int
        Número estimado de tokens (1.3 tokens por palabra).
    
    Notes
    -----
    Esta estimación es específica para español, donde el promedio es
    1.3 tokens por palabra debido a la morfología del idioma.
    """
    palabras = len(texto.split())
    return int(palabras * 1.3)


def crear_chunks_inteligentes(textos: List[str], max_tokens: int = TOKENS_POR_CHUNK) -> List[List[str]]:
    """
    Divide una lista de textos en chunks respetando límites de tokens.
    
    Parameters
    ----------
    textos : List[str]
        Lista de textos a dividir en chunks.
    max_tokens : int, optional
        Máximo de tokens por chunk (por defecto TOKENS_POR_CHUNK).
    
    Returns
    -------
    List[List[str]]
        Lista de chunks, donde cada chunk es una lista de textos.
    
    Strategy
    --------
    1. Textos muy grandes (>80% del límite) van en chunks individuales
    2. Textos se agrupan mientras no superen 75% del límite
    3. Se respeta el orden original de los textos
    """
    chunks = []
    chunk_actual = []
    tokens_actual = 0
    
    for texto in textos:
        tokens_texto = estimar_tokens_espanol(texto)
        
        # Caso 1: Texto muy grande para un chunk
        if tokens_texto > max_tokens * 0.8:
            if chunk_actual:
                chunks.append(chunk_actual)
                chunk_actual = []
                tokens_actual = 0
            chunks.append([texto])
        
        # Caso 2: Chunk actual lleno
        elif tokens_actual + tokens_texto > max_tokens * 0.75:
            chunks.append(chunk_actual)
            chunk_actual = [texto]
            tokens_actual = tokens_texto
        
        # Caso 3: Agregar al chunk actual
        else:
            chunk_actual.append(texto)
            tokens_actual += tokens_texto
    
    # Agregar el último chunk si no está vacío
    if chunk_actual:
        chunks.append(chunk_actual)
    
    return chunks

# =============================================================================
# FUNCIONES DE EXTRACCIÓN DE TEXTO
# =============================================================================

def extraer_texto_relevante(pdf_path: str, paginas: int = 3) -> str:
    """
    Extrae texto de las primeras páginas de un documento PDF.
    
    Parameters
    ----------
    pdf_path : str
        Ruta al archivo PDF.
    paginas : int, optional
        Número de páginas a extraer (por defecto 3).
    
    Returns
    -------
    str
        Texto extraído concatenado, o string vacío en caso de error.
    
    Raises
    ------
    ImportError
        Si no está instalada la librería pdfplumber.
    
    Notes
    -----
    Solo extrae las primeras N páginas ya que la información relevante
    suele estar al inicio de documentos oficiales.
    """
    try:
        import pdfplumber
        
        with pdfplumber.open(pdf_path) as pdf:
            texto = ""
            
            for i, page in enumerate(pdf.pages[:paginas]):
                page_text = page.extract_text()
                if page_text:
                    texto += page_text + "\n\n"
            
            return texto
        
    except Exception as e:
        print(f"Error en PDF {Path(pdf_path).name[:30]}: {str(e)[:50]}")
        return ""

# =============================================================================
# FUNCIONES DE CONSULTA A DEEPSEEK
# =============================================================================

def consultar_deepseek(prompt: str, system_message: str = None) -> str:
    """
    Envía una consulta a la API de DeepSeek con manejo de errores.
    
    Parameters
    ----------
    prompt : str
        Prompt del usuario para la consulta.
    system_message : str, optional
        Mensaje del sistema para contextualizar la consulta.
    
    Returns
    -------
    str
        Respuesta de la API o mensaje de error.
    
    Notes
    -----
    Incluye manejo de rate limiting (código 429) con reintento automático
    después de 10 segundos.
    """
    import requests
    import time
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_CONFIG['api_key']}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": DEEPSEEK_CONFIG["model"],
        "messages": messages,
        "max_tokens": DEEPSEEK_CONFIG["max_response_tokens"],
        "temperature": 0.1,
        "stream": False
    }
    
    try:
        response = requests.post(
            DEEPSEEK_CONFIG["base_url"],
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        elif response.status_code == 429:  # Rate limiting
            print("Rate limit detectado, esperando 10 segundos...")
            time.sleep(10)
            return consultar_deepseek(prompt, system_message)  # Reintentar
        else:
            print(f"Error API {response.status_code}: {response.text[:100]}")
            return f"ERROR_API_{response.status_code}"
            
    except Exception as e:
        print(f"Error de conexión: {str(e)[:50]}")
        return f"ERROR_CONEXION: {str(e)[:50]}"

# =============================================================================
# PLANTILLAS DE PROMPT
# =============================================================================

PROMPTS = {
    "proyectos": {
        "system": """Eres un experto en análisis de documentos oficiales mexicanos.
        Extrae información precisa y verificable. Responde en español.""",
        
        "user": """Analiza estos documentos y extrae todos los proyectos de investigación y desarrollo tecnológico.

DOCUMENTOS:
{textos}

INSTRUCCIONES:
1. Busca proyectos con nombre propio (ej: "Kutsari", "Olinia")
2. Incluye proyectos mencionados como "Proyecto X", "Iniciativa Y"
3. Para cada proyecto, proporciona:
   - Nombre completo
   - Descripción breve
   - Instituciones involucradas
   - Documentos donde aparece

FORMATO DE RESPUESTA (JSON):
{{
  "proyectos": [
    {{
      "nombre": "Nombre del proyecto",
      "descripcion": "Descripción concisa",
      "instituciones": ["Inst1", "Inst2"],
      "documentos": ["doc1.pdf", "doc2.pdf"]
    }}
  ]
}}"""
    },
    
    "personas": {
        "system": """Eres un experto en extraer nombres de personas de documentos oficiales.""",
        
        "user": """Extrae todos los nombres de personas mencionadas en estos documentos.

DOCUMENTOS:
{textos}

INSTRUCCIONES:
1. Extrae nombres completos (Nombre + Apellidos)
2. Incluye cargos/roles si se mencionan
3. Para cada persona, indica en qué documentos aparece

FORMATO (JSON):
{{
  "personas": [
    {{
      "nombre_completo": "Nombre Apellido1 Apellido2",
      "cargo": "Cargo/Rol mencionado",
      "documentos": ["doc1.pdf", "doc2.pdf"]
    }}
  ]
}}"""
    },
    
    "instituciones": {
        "system": """Eres un experto en identificar instituciones en documentos oficiales.""",
        
        "user": """Identifica todas las instituciones mencionadas en estos documentos.

DOCUMENTOS:
{textos}

INSTRUCCIONES:
1. Incluye universidades, institutos, secretarías, centros de investigación
2. Usa el nombre completo
3. Para cada institución, indica en qué documentos aparece

FORMATO (JSON):
{{
  "instituciones": [
    {{
      "nombre": "Nombre completo de la institución",
      "siglas": "Siglas (si aplica)",
      "documentos": ["doc1.pdf", "doc2.pdf"]
    }}
  ]
}}"""
    }
}

# =============================================================================
# CLASE PRINCIPAL - PROCESADORDOCUMENTOS
# =============================================================================

class ProcesadorDocumentos:
    """
    Procesador principal para extracción de información de documentos PDF.
    
    Attributes
    ----------
    consulta_tipo : str
        Tipo de consulta ("proyectos", "personas", "instituciones").
    resultados_chunks : List[Dict]
        Resultados acumulados de cada chunk procesado.
    cache_dir : Path
        Directorio para almacenar resultados en cache.
    
    Methods
    -------
    procesar_chunk(chunk_id, documentos, textos)
        Procesa un chunk de documentos con consulta a DeepSeek.
    procesar_documentos(pdf_paths, max_docs=None)
        Procesa todos los documentos divididos en chunks.
    consolidar_resultados()
        Consolida resultados de todos los chunks.
    """
    
    def __init__(self, consulta_tipo: str):
        """
        Inicializa el procesador de documentos.
        
        Parameters
        ----------
        consulta_tipo : str
            Tipo de consulta a realizar ("proyectos", "personas", "instituciones").
        """
        self.consulta_tipo = consulta_tipo
        self.resultados_chunks = []
        self.cache_dir = Path("cache_v31")
        self.cache_dir.mkdir(exist_ok=True)
    
    def procesar_chunk(self, chunk_id: int, documentos: List[str], textos: List[str]) -> Dict:
        """
        Procesa un chunk de documentos con consulta a DeepSeek.
        
        Parameters
        ----------
        chunk_id : int
            Identificador del chunk (0-indexed).
        documentos : List[str]
            Nombres de los documentos en el chunk.
        textos : List[str]
            Textos extraídos de los documentos.
        
        Returns
        -------
        Dict
            Resultado de la consulta en formato JSON.
        
        Notes
        -----
        Utiliza cache para evitar reprocesamiento del mismo chunk.
        El cache se basa en hash de los textos y tipo de consulta.
        """
        # Generar hash único para el cache
        cache_hash = hashlib.md5(
            f"{chunk_id}:{self.consulta_tipo}:{hash(str(textos))}".encode()
        ).hexdigest()
        
        cache_file = self.cache_dir / f"{cache_hash}.json"
        
        # Intentar cargar desde cache
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass  # Si falla el cache, procesar normalmente
        
        print(f"Procesando chunk {chunk_id + 1} ({len(documentos)} documentos)...")
        
        # Preparar prompt según tipo de consulta
        prompt_template = PROMPTS[self.consulta_tipo]["user"]
        system_message = PROMPTS[self.consulta_tipo]["system"]
        
        # Formatear textos combinados
        if len(documentos) == 1:
            encabezado = f"DOCUMENTO: {documentos[0]}"
        else:
            encabezado = f"{len(documentos)} documentos"
        
        textos_combinados = f"\n\n--- {encabezado} ---\n{'\n\n'.join(textos)}"
        prompt = prompt_template.format(textos=textos_combinados)
        
        # Consultar a DeepSeek
        respuesta = consultar_deepseek(prompt, system_message)
        resultado = self._parsear_respuesta_json(respuesta)
        
        # Agregar metadatos
        resultado["chunk_id"] = chunk_id
        resultado["documentos"] = documentos
        
        # Guardar en cache
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
        except:
            pass  # Si falla el cache, continuar sin él
        
        return resultado
    
    def _parsear_respuesta_json(self, respuesta: str) -> Dict:
        """
        Intenta extraer y parsear JSON de la respuesta de DeepSeek.
        
        Parameters
        ----------
        respuesta : str
            Respuesta completa de la API de DeepSeek.
        
        Returns
        -------
        Dict
            Diccionario parseado o diccionario con error.
        
        Notes
        -----
        Busca el primer '{' y el último '}' correspondiente.
        Si no encuentra JSON válido, retorna la respuesta como texto.
        """
        lines = respuesta.split('\n')
        json_start = -1
        
        # Buscar inicio del JSON
        for i, line in enumerate(lines):
            if line.strip().startswith('{'):
                json_start = i
                break
        
        if json_start != -1:
            # Encontrar el cierre correspondiente
            brace_count = 0
            json_end = -1
            
            for i in range(json_start, len(lines)):
                brace_count += lines[i].count('{')
                brace_count -= lines[i].count('}')
                
                if brace_count == 0:
                    json_end = i
                    break
            
            if json_end != -1:
                json_str = '\n'.join(lines[json_start:json_end + 1])
                try:
                    return json.loads(json_str)
                except:
                    pass  # Si falla el parseo, continuar con fallback
        
        # Fallback: respuesta no es JSON válido
        return {
            "respuesta_texto": respuesta[:500],
            "error": "no_json_valido"
        }
    
    def procesar_documentos(self, pdf_paths: List[str], max_docs: int = None) -> Dict:
        """
        Procesa todos los documentos, dividiéndolos en chunks inteligentes.
        
        Parameters
        ----------
        pdf_paths : List[str]
            Lista de rutas a archivos PDF.
        max_docs : int, optional
            Número máximo de documentos a procesar (para pruebas).
        
        Returns
        -------
        Dict
            Resultados consolidados de todo el procesamiento.
        
        Workflow
        --------
        1. Extraer texto de cada PDF (limitado a primeras páginas)
        2. Dividir textos en chunks respetando límites de tokens
        3. Procesar cada chunk con DeepSeek
        4. Consolidar resultados de todos los chunks
        """
        # Limitar documentos para pruebas
        if max_docs:
            pdf_paths = pdf_paths[:max_docs]
        
        print(f"Procesando {len(pdf_paths)} documentos...")
        print(f"Consulta: {self.consulta_tipo}")
        print()
        
        # Paso 1: Extraer textos de todos los PDFs
        textos = []
        documentos_nombres = []
        
        for i, pdf_path in enumerate(pdf_paths, 1):
            nombre = Path(pdf_path).name
            print(f"  [{i:3d}/{len(pdf_paths)}] Extrayendo: {nombre[:45]:45}", end="")
            
            texto = extraer_texto_relevante(pdf_path)
            if texto and len(texto) > 200:
                textos.append(texto[:5000])  # Limitar tamaño por documento
                documentos_nombres.append(nombre)
                print(" OK")
            else:
                print(" Sin texto")
        
        # Paso 2: Crear chunks inteligentes
        chunks_docs = crear_chunks_inteligentes(textos)
        print(f"Chunks creados: {len(chunks_docs)}")
        
        # Paso 3: Procesar cada chunk
        self.resultados_chunks = []
        
        for i, chunk_textos in enumerate(chunks_docs):
            # Mapear índices de textos a nombres de documentos
            if i + len(chunk_textos) <= len(documentos_nombres):
                chunk_docs = documentos_nombres[i:i+len(chunk_textos)]
            else:
                chunk_docs = documentos_nombres[i:]
            
            resultado = self.procesar_chunk(i, chunk_docs, chunk_textos)
            self.resultados_chunks.append(resultado)
            
            # Mostrar progreso
            if "proyectos" in resultado:
                print(f"  Chunk {i+1}: {len(resultado.get('proyectos', []))} proyectos")
            elif "personas" in resultado:
                print(f"  Chunk {i+1}: {len(resultado.get('personas', []))} personas")
            elif "instituciones" in resultado:
                print(f"  Chunk {i+1}: {len(resultado.get('instituciones', []))} instituciones")
        
        # Paso 4: Consolidar resultados
        return self.consolidar_resultados()
    
    def consolidar_resultados(self) -> Dict:
        """
        Consolida resultados de todos los chunks procesados.
        
        Returns
        -------
        Dict
            Resultados consolidados según el tipo de consulta.
        
        Notes
        -----
        Para consultas de "proyectos", elimina duplicados y cuenta menciones.
        Para otros tipos, se necesita implementar lógica específica.
        """
        if not self.resultados_chunks:
            return {"error": "sin_resultados"}
        
        # Consolidar proyectos (eliminar duplicados)
        if self.consulta_tipo == "proyectos":
            todos_proyectos = {}
            
            for chunk in self.resultados_chunks:
                if "proyectos" in chunk:
                    for proyecto in chunk["proyectos"]:
                        nombre = proyecto.get("nombre", "")
                        if nombre:
                            # Primer avistamiento del proyecto
                            if nombre not in todos_proyectos:
                                todos_proyectos[nombre] = proyecto.copy()
                                todos_proyectos[nombre]["documentos"] = set()
                            
                            # Agregar documentos donde aparece
                            docs_proyecto = proyecto.get("documentos", [])
                            if isinstance(docs_proyecto, list):
                                todos_proyectos[nombre]["documentos"].update(docs_proyecto)
            
            # Convertir sets a listas y agregar conteo de menciones
            for proyecto in todos_proyectos.values():
                proyecto["documentos"] = list(proyecto["documentos"])
                proyecto["menciones"] = len(proyecto["documentos"])
            
            return {
                "proyectos": list(todos_proyectos.values()),
                "total_proyectos": len(todos_proyectos)
            }
        
        # Para otros tipos de consulta, retornar estructura básica
        return {
            "consulta": self.consulta_tipo,
            "chunks_procesados": len(self.resultados_chunks),
            "resultados": self.resultados_chunks
        }

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def main() -> None:
    """
    Función principal de la interfaz de línea de comandos.
    
    Usage
    -----
    python consultorsecihty31.py <consulta> [opciones]
    
    Examples
    --------
    >>> python consultorsecihty31.py proyectos
    >>> python consultorsecihty31.py personas --probar 5
    >>> python consultorsecihty31.py --limpiar
    """
    # Verificar argumentos mínimos
    if len(sys.argv) < 2:
        print("""
CONSULTOR SECIHTI v31 - SISTEMA DE EXTRACCIÓN MASIVA

USO:
  python consultorsecihty31.py consulta [opciones]

EJEMPLOS:
  python consultorsecihty31.py proyectos
  python consultorsecihty31.py personas
  python consultorsecihty31.py instituciones

OPCIONES:
  --limpiar    Limpia el cache
  --estado     Muestra estado del sistema
  --probar N   Prueba con N documentos
""")
        return
    
    comando = sys.argv[1]
    
    # Comandos especiales
    if comando == "--limpiar":
        import shutil
        if os.path.exists("cache_v31"):
            shutil.rmtree("cache_v31")
        print("Cache limpiado")
        return
    
    if comando == "--estado":
        print("Sistema v31 listo")
        print(f"Límite tokens por chunk: {TOKENS_POR_CHUNK:,}")
        return
    
    # Cargar documentos PDF
    import glob
    pdf_paths = glob.glob("/home/roger/Downloads/Comunicados Secihti/*.pdf")
    
    if not pdf_paths:
        print("No se encontraron PDFs en la ruta especificada")
        return
    
    # Determinar tipo de consulta
    consulta_tipo = comando
    
    # Verificar modo prueba
    max_docs = None
    if "--probar" in sys.argv:
        for arg in sys.argv:
            if arg.isdigit():
                max_docs = int(arg)
                break
        max_docs = max_docs or 5
        print(f"Modo prueba activado: {max_docs} documentos")
    
    # Encabezado de procesamiento
    print(f"\nCONSULTA: {consulta_tipo}")
    print("=" * 60)
    
    # Crear procesador y ejecutar
    procesador = ProcesadorDocumentos(consulta_tipo)
    resultados = procesador.procesar_documentos(pdf_paths, max_docs)
    
    # Mostrar resultados finales
    print(f"\n{'='*60}")
    print(f"RESULTADOS FINALES")
    print(f"{'='*60}")
    
    # Guardar resultados en archivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_resultados = f"resultados_{consulta_tipo}_{timestamp}.json"
    
    with open(archivo_resultados, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    
    print(f"Resultados guardados en: {archivo_resultados}")
    
    # Mostrar resumen de proyectos si aplica
    if "proyectos" in resultados:
        proyectos = resultados["proyectos"]
        print(f"\nPROYECTOS ENCONTRADOS: {len(proyectos)}")
        
        # Ordenar por número de menciones (descendente)
        proyectos.sort(key=lambda x: x.get("menciones", 0), reverse=True)
        
        # Mostrar top 10
        for i, proyecto in enumerate(proyectos[:10], 1):
            nombre = proyecto.get("nombre", "")
            desc = proyecto.get("descripcion", "")
            menciones = proyecto.get("menciones", 0)
            
            print(f"\n{i:2d}. {nombre}")
            if desc:
                print(f"    {desc[:70]}...")
            print(f"    Menciones: {menciones} documentos")

# =============================================================================
# VERIFICACIÓN DE DEPENDENCIAS Y EJECUCIÓN
# =============================================================================

if __name__ == "__main__":
    # Verificar dependencias críticas
    try:
        import pdfplumber
        import requests
    except ImportError:
        print("""
ERROR: Dependencias faltantes

Instala las dependencias requeridas:
    pip install pdfplumber requests
""")
        sys.exit(1)
    
    # Ejecutar función principal
    main()
