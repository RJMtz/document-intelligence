"""
CONSULTOR SECIHTI v31 - EXTRACCIÓN MASIVA
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
import hashlib

DEEPSEEK_CONFIG = {
    "api_key": "sk-1fd02fbdb4e340ae9203c9a7258acaa6",
    "base_url": "https://api.deepseek.com/v1/chat/completions",
    "model": "deepseek-chat",
    "max_context_tokens": 32000,
    "max_response_tokens": 4000,
    "reserved_tokens": 2000,
}

TOKENS_POR_CHUNK = 26000

def estimar_tokens_espanol(texto):
    palabras = len(texto.split())
    return int(palabras * 1.3)

def crear_chunks_inteligentes(textos, max_tokens=TOKENS_POR_CHUNK):
    chunks = []
    chunk_actual = []
    tokens_actual = 0
    
    for texto in textos:
        tokens_texto = estimar_tokens_espanol(texto)
        
        if tokens_texto > max_tokens * 0.8:
            if chunk_actual:
                chunks.append(chunk_actual)
                chunk_actual = []
                tokens_actual = 0
            chunks.append([texto])
        
        elif tokens_actual + tokens_texto > max_tokens * 0.75:
            chunks.append(chunk_actual)
            chunk_actual = [texto]
            tokens_actual = tokens_texto
        
        else:
            chunk_actual.append(texto)
            tokens_actual += tokens_texto
    
    if chunk_actual:
        chunks.append(chunk_actual)
    
    return chunks

def extraer_texto_relevante(pdf_path, paginas=3):
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

def consultar_deepseek(prompt, system_message=None):
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
        elif response.status_code == 429:
            print("Rate limit detectado, esperando 10 segundos...")
            time.sleep(10)
            return consultar_deepseek(prompt, system_message)
        else:
            print(f"Error API {response.status_code}: {response.text[:100]}")
            return f"ERROR_API_{response.status_code}"
            
    except Exception as e:
        print(f"Error de conexión: {str(e)[:50]}")
        return f"ERROR_CONEXION: {str(e)[:50]}"

PROMPTS = {
    "proyectos": {
        "system": "Eres un experto en análisis de documentos oficiales mexicanos. Extrae información precisa y verificable. Responde en español.",
        
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
        "system": "Eres un experto en extraer nombres de personas de documentos oficiales.",
        
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
        "system": "Eres un experto en identificar instituciones en documentos oficiales.",
        
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

class ProcesadorDocumentos:
    def __init__(self, consulta_tipo):
        self.consulta_tipo = consulta_tipo
        self.resultados_chunks = []
        self.cache_dir = Path("cache_v31")
        self.cache_dir.mkdir(exist_ok=True)
    
    def procesar_chunk(self, chunk_id, documentos, textos):
        cache_hash = hashlib.md5(
            f"{chunk_id}:{self.consulta_tipo}:{hash(str(textos))}".encode()
        ).hexdigest()
        
        cache_file = self.cache_dir / f"{cache_hash}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        print(f"Procesando chunk {chunk_id + 1} ({len(documentos)} documentos)...")
        
        prompt_template = PROMPTS[self.consulta_tipo]["user"]
        system_message = PROMPTS[self.consulta_tipo]["system"]
        
        if len(documentos) == 1:
            encabezado = f"DOCUMENTO: {documentos[0]}"
        else:
            encabezado = f"{len(documentos)} documentos"
        
        textos_combinados = f"\n\n--- {encabezado} ---\n{'\n\n'.join(textos)}"
        prompt = prompt_template.format(textos=textos_combinados)
        
        respuesta = consultar_deepseek(prompt, system_message)
        resultado = self._parsear_respuesta_json(respuesta)
        
        resultado["chunk_id"] = chunk_id
        resultado["documentos"] = documentos
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
        except:
            pass
        
        return resultado
    
    def _parsear_respuesta_json(self, respuesta):
        lines = respuesta.split('\n')
        json_start = -1
        
        for i, line in enumerate(lines):
            if line.strip().startswith('{'):
                json_start = i
                break
        
        if json_start != -1:
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
                    pass
        
        return {
            "respuesta_texto": respuesta[:500],
            "error": "no_json_valido"
        }
    
    def procesar_documentos(self, pdf_paths, max_docs=None):
        if max_docs:
            pdf_paths = pdf_paths[:max_docs]
        
        print(f"Procesando {len(pdf_paths)} documentos...")
        print(f"Consulta: {self.consulta_tipo}")
        print()
        
        textos = []
        documentos_nombres = []
        
        for i, pdf_path in enumerate(pdf_paths, 1):
            nombre = Path(pdf_path).name
            print(f"  [{i:3d}/{len(pdf_paths)}] Extrayendo: {nombre[:45]:45}", end="")
            
            texto = extraer_texto_relevante(pdf_path)
            if texto and len(texto) > 200:
                textos.append(texto[:5000])
                documentos_nombres.append(nombre)
                print(" OK")
            else:
                print(" Sin texto")
        
        chunks_docs = crear_chunks_inteligentes(textos)
        print(f"Chunks creados: {len(chunks_docs)}")
        
        self.resultados_chunks = []
        
        for i, chunk_textos in enumerate(chunks_docs):
            if i + len(chunk_textos) <= len(documentos_nombres):
                chunk_docs = documentos_nombres[i:i+len(chunk_textos)]
            else:
                chunk_docs = documentos_nombres[i:]
            
            resultado = self.procesar_chunk(i, chunk_docs, chunk_textos)
            self.resultados_chunks.append(resultado)
            
            if "proyectos" in resultado:
                print(f"  Chunk {i+1}: {len(resultado.get('proyectos', []))} proyectos")
            elif "personas" in resultado:
                print(f"  Chunk {i+1}: {len(resultado.get('personas', []))} personas")
            elif "instituciones" in resultado:
                print(f"  Chunk {i+1}: {len(resultado.get('instituciones', []))} instituciones")
        
        return self.consolidar_resultados()
    
    def consolidar_resultados(self):
        if not self.resultados_chunks:
            return {"error": "sin_resultados"}
        
        if self.consulta_tipo == "proyectos":
            todos_proyectos = {}
            
            for chunk in self.resultados_chunks:
                if "proyectos" in chunk:
                    for proyecto in chunk["proyectos"]:
                        nombre = proyecto.get("nombre", "")
                        if nombre:
                            if nombre not in todos_proyectos:
                                todos_proyectos[nombre] = proyecto.copy()
                                todos_proyectos[nombre]["documentos"] = set()
                            
                            docs_proyecto = proyecto.get("documentos", [])
                            if isinstance(docs_proyecto, list):
                                todos_proyectos[nombre]["documentos"].update(docs_proyecto)
            
            for proyecto in todos_proyectos.values():
                proyecto["documentos"] = list(proyecto["documentos"])
                proyecto["menciones"] = len(proyecto["documentos"])
            
            return {
                "proyectos": list(todos_proyectos.values()),
                "total_proyectos": len(todos_proyectos)
            }
        
        return {
            "consulta": self.consulta_tipo,
            "chunks_procesados": len(self.resultados_chunks),
            "resultados": self.resultados_chunks
        }

def main():
    if len(sys.argv) < 2:
        print("""
CONSULTOR SECIHTI v31 - EXTRACCIÓN MASIVA

USO:
  python consultorsecihtyextractor.py consulta [opciones]

EJEMPLOS:
  python consultorsecihtyextractor.py proyectos
  python consultorsecihtyextractor.py personas
  python consultorsecihtyextractor.py instituciones

OPCIONES:
  --limpiar    Limpia el cache
  --estado     Muestra estado del sistema
  --probar N   Prueba con N documentos
""")
        return
    
    comando = sys.argv[1]
    
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
    
    import glob
    pdf_paths = glob.glob("/home/roger/Downloads/Comunicados Secihti/*.pdf")
    
    if not pdf_paths:
        print("No se encontraron PDFs en la ruta especificada")
        return
    
    consulta_tipo = comando
    
    max_docs = None
    if "--probar" in sys.argv:
        for arg in sys.argv:
            if arg.isdigit():
                max_docs = int(arg)
                break
        max_docs = max_docs or 5
        print(f"Modo prueba activado: {max_docs} documentos")
    
    print(f"\nCONSULTA: {consulta_tipo}")
    print("=" * 60)
    
    procesador = ProcesadorDocumentos(consulta_tipo)
    resultados = procesador.procesar_documentos(pdf_paths, max_docs)
    
    print(f"\n{'='*60}")
    print(f"RESULTADOS FINALES")
    print(f"{'='*60}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_resultados = f"resultados_{consulta_tipo}_{timestamp}.json"
    
    with open(archivo_resultados, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    
    print(f"Resultados guardados en: {archivo_resultados}")
    
    if "proyectos" in resultados:
        proyectos = resultados["proyectos"]
        print(f"\nPROYECTOS ENCONTRADOS: {len(proyectos)}")
        
        proyectos.sort(key=lambda x: x.get("menciones", 0), reverse=True)
        
        for i, proyecto in enumerate(proyectos[:10], 1):
            nombre = proyecto.get("nombre", "")
            desc = proyecto.get("descripcion", "")
            menciones = proyecto.get("menciones", 0)
            
            print(f"\n{i:2d}. {nombre}")
            if desc:
                print(f"    {desc[:70]}...")
            print(f"    Menciones: {menciones} documentos")

if __name__ == "__main__":
    try:
        import pdfplumber
        import requests
    except ImportError:
        print("ERROR: Dependencias faltantes\nInstala: pip install pdfplumber requests")
        sys.exit(1)
    
    main()
