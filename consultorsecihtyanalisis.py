"""
CONSULTOR SECIHTI v32 - ANÁLISIS INTELIGENTE
"""

import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
import glob

DEEPSEEK_CONFIG = {
    "api_key": "sk-1fd02fbdb4e340ae9203c9a7258acaa6",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "max_context_tokens": 32000,
    "max_response_tokens": 4000,
}

class AnalizadorConsulta:
    @staticmethod
    def analizar(consulta_texto):
        consulta = consulta_texto.lower().strip()
        
        patrones = [
            (r'(?:de\s+qu[ée]\s+trata|qu[ée]\s+es|en\s+qu[ée]\s+consiste)\s+(?:el\s+)?(proyecto)?\s*(?:["\'])?([^"\'\?]+)(?:["\'])?\s*\??', 
             'info_proyecto', lambda m: {"proyecto": m.group(2).strip()}),
            
            (r'(?:es\s+(?:verdad|mentira|cierto|falso)|verdad\s+o\s+mentira)[\s:,]*(.+)', 
             'verificar', lambda m: {"afirmacion": m.group(1).strip()}),
            
            (r'(?:en\s+qu[ée]\s+documentos|d[óo]nde\s+aparece)[\s:,]+(.+)', 
             'buscar_documentos', lambda m: {"busqueda": m.group(1).strip()}),
            
            (r'^(?:dame|muestra|lista|extrae)\s+(?:los\s+)?(proyectos|personas|instituciones)', 
             'lista_simple', lambda m: {"tipo": m.group(1)}),
            
            (r'^proyectos$', 'proyectos', lambda m: {}),
            (r'^personas$', 'personas', lambda m: {}),
            (r'^instituciones$', 'instituciones', lambda m: {}),
            
            (r'(.+\?)', 'pregunta_general', lambda m: {"pregunta": m.group(1)}),
        ]
        
        for patron, tipo, extractor in patrones:
            match = re.match(patron, consulta, re.IGNORECASE)
            if match:
                return {
                    "tipo": tipo,
                    "parametros": extractor(match),
                    "consulta_original": consulta_texto,
                    "accion": AnalizadorConsulta._determinar_accion(tipo)
                }
        
        return {
            "tipo": "busqueda_general",
            "parametros": {"texto": consulta_texto},
            "consulta_original": consulta_texto,
            "accion": "buscar_informacion"
        }
    
    @staticmethod
    def _determinar_accion(tipo):
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

class GestorPrompts:
    PROMPTS = {
        'info_proyecto': {
            'system': "Eres un experto en proyectos de investigación mexicano. Analiza documentos oficiales y extrae información precisa. Responde en español con claridad.",
            
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
            'system': "Eres un verificador de hechos basado en documentos. Determina la veracidad usando solo evidencia documental.",
            
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
            'system': "Eres un buscador experto en documentos oficiales.",
            
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
    def obtener_prompt(cls, tipo_consulta, parametros):
        if tipo_consulta in cls.PROMPTS:
            prompt_data = cls.PROMPTS[tipo_consulta].copy()
            user_prompt = prompt_data['user']
            
            for key, value in parametros.items():
                user_prompt = user_prompt.replace(f"{{{key}}}", str(value))
            
            prompt_data['user'] = user_prompt
            return prompt_data
        
        return {
            'system': "Analiza documentos y responde preguntas.",
            'user': f"Responde a: {parametros.get('texto', '')}\n\nDocumentos:\n{{documentos}}"
        }

class ConsultorSecihtiV32:
    def __init__(self):
        self.cache_dir = Path("cache_v32")
        self.cache_dir.mkdir(exist_ok=True)
    
    def extraer_texto_pdf(self, ruta_pdf, max_paginas=3):
        try:
            import pdfplumber
            
            texto = ""
            with pdfplumber.open(ruta_pdf) as pdf:
                for i, pagina in enumerate(pdf.pages[:max_paginas]):
                    texto_pag = pagina.extract_text()
                    if texto_pag:
                        texto += texto_pag + "\n\n"
            
            return texto[:5000]
            
        except Exception as e:
            print(f"Error en {Path(ruta_pdf).name[:30]}: {str(e)[:50]}")
            return ""
    
    def consultar_deepseek(self, prompt, system_message=None):
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
    
    def procesar_consulta(self, consulta_texto, max_documentos=None):
        print(f"\nCONSULTA: {consulta_texto}")
        print("=" * 60)
        
        analisis = AnalizadorConsulta.analizar(consulta_texto)
        print(f"Tipo detectado: {analisis['tipo']}")
        
        pdf_paths = self._cargar_documentos(max_documentos)
        
        if not pdf_paths:
            return {"error": "No se encontraron documentos"}
        
        print(f"Documentos a procesar: {len(pdf_paths)}")
        
        textos_documentos = self._extraer_textos_documentos(pdf_paths)
        
        if not textos_documentos:
            return {"error": "No se pudo extraer texto de los documentos"}
        
        prompt_data = GestorPrompts.obtener_prompt(
            analisis['tipo'], 
            analisis['parametros']
        )
        
        textos_combinados = self._formatear_textos_documentos(
            textos_documentos, 
            pdf_paths
        )
        
        prompt_final = prompt_data['user'].replace("{documentos}", textos_combinados)
        
        print("Consultando a DeepSeek...")
        respuesta = self.consultar_deepseek(prompt_final, prompt_data['system'])
        
        resultado = self._procesar_respuesta(respuesta, analisis)
        self._guardar_resultado(consulta_texto, resultado)
        self._mostrar_resultado(resultado, analisis['tipo'])
        
        return resultado
    
    def _cargar_documentos(self, max_docs=None):
        pdf_paths = glob.glob("/home/roger/Downloads/Comunicados Secihti/*.pdf")
        
        if max_docs and max_docs < len(pdf_paths):
            pdf_paths = sorted(
                pdf_paths,
                key=lambda x: Path(x).name,
                reverse=True
            )[:max_docs]
        
        return pdf_paths
    
    def _extraer_textos_documentos(self, pdf_paths):
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
    
    def _formatear_textos_documentos(self, textos, rutas):
        resultado = []
        
        for nombre, texto in textos:
            resultado.append(f"--- DOCUMENTO: {nombre} ---")
            resultado.append(texto[:2000])
            resultado.append("")
        
        return "\n".join(resultado)
    
    def _procesar_respuesta(self, respuesta, analisis):
        try:
            json_match = re.search(r'\{.*\}', respuesta, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                data["consulta"] = analisis["consulta_original"]
                data["tipo_consulta"] = analisis["tipo"]
                data["timestamp"] = datetime.now().isoformat()
                return data
        except:
            pass
        
        return {
            "consulta": analisis["consulta_original"],
            "tipo_consulta": analisis["tipo"],
            "respuesta_texto": respuesta[:1000],
            "timestamp": datetime.now().isoformat(),
            "advertencia": "Respuesta no está en formato JSON estructurado"
        }
    
    def _guardar_resultado(self, consulta, resultado):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = f"resultados_v32_{timestamp}.json"
        
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump({
                "consulta": consulta,
                "fecha": datetime.now().isoformat(),
                "resultado": resultado
            }, f, ensure_ascii=False, indent=2)
        
        print(f"Resultado guardado en: {archivo}")
    
    def _mostrar_resultado(self, resultado, tipo_consulta):
        print(f"\n{'='*60}")
        print(f"RESULTADO - Tipo: {tipo_consulta}")
        print(f"{'='*60}")
        
        if "error" in resultado:
            print(f"Error: {resultado['error']}")
            return
        
        if tipo_consulta == "info_proyecto":
            self._mostrar_info_proyecto(resultado)
        elif tipo_consulta == "verificar":
            self._mostrar_verificacion(resultado)
        elif tipo_consulta == "buscar_documentos":
            self._mostrar_busqueda(resultado)
        else:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
    
    def _mostrar_info_proyecto(self, resultado):
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
    
    def _mostrar_verificacion(self, resultado):
        if "afirmacion" in resultado:
            print(f"\nAFIRMACIÓN: {resultado['afirmacion']}")
        
        if "veredicto" in resultado:
            veredicto = resultado["veredicto"]
            print(f"\nVEREDICTO: {veredicto.upper()}")
        
        if "explicacion_detallada" in resultado:
            print(f"\nEXPLICACIÓN: {resultado['explicacion_detallada'][:300]}...")
    
    def _mostrar_busqueda(self, resultado):
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

def mostrar_ayuda():
    print("""
CONSULTOR SECIHTI v32 - PREGUNTAS EN ESPAÑOL NATURAL

USO:
  python consultorsecihtyanalisis.py "tu consulta"

EJEMPLOS:

SOBRE PROYECTOS:
  python consultorsecihtyanalisis.py "De qué trata el proyecto Olinia?"
  python consultorsecihtyanalisis.py "Qué es el proyecto Kutsari?"

VERIFICACIONES:
  python consultorsecihtyanalisis.py "Es verdad que Kutsari trata sobre petróleo?"

BÚSQUEDAS:
  python consultorsecihtyanalisis.py "En qué documentos aparece el IPN?"

EXTRACCIONES:
  python consultorsecihtyanalisis.py "Dame los proyectos"
  python consultorsecihtyanalisis.py "proyectos"

OPCIONES:
  python consultorsecihtyanalisis.py --probar 5    # Probar con 5 documentos
  python consultorsecihtyanalisis.py --limpiar     # Limpiar cache
  python consultorsecihtyanalisis.py --ayuda       # Mostrar esta ayuda
""")

def limpiar_cache():
    import shutil
    cache_dir = Path("cache_v32")
    
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("Cache limpiado")
    else:
        print("No hay cache para limpiar")

def main():
    if len(sys.argv) < 2:
        mostrar_ayuda()
        return
    
    if sys.argv[1] == "--ayuda" or sys.argv[1] == "-h":
        mostrar_ayuda()
        return
    elif sys.argv[1] == "--limpiar":
        limpiar_cache()
        return
    elif sys.argv[1] == "--test":
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
            print(f"Tipo: {analisis['tipo']}")
            print(f"Parámetros: {analisis['parametros']}")
        
        return
    
    consulta_texto = " ".join(sys.argv[1:])
    
    max_docs = None
    if "--probar" in sys.argv:
        for arg in sys.argv:
            if arg.isdigit():
                max_docs = int(arg)
                break
        max_docs = max_docs or 5
        print(f"MODO PRUEBA: {max_docs} documentos")
    
    consultor = ConsultorSecihtiV32()
    
    try:
        resultado = consultor.procesar_consulta(consulta_texto, max_docs)
        
        print(f"\n{'='*60}")
        print("CONSULTA COMPLETADA")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        print("\nSUGERENCIAS:")
        print("   1. Verifica que los PDFs estén en la carpeta correcta")
        print("   2. Asegúrate de tener conexión a internet")
        print("   3. Prueba con menos documentos: --probar 3")

def verificar_dependencias():
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
            print(f"{modulo}: {comando}")
        print("\nEjecuta los comandos de instalación arriba.")
        return False
    
    return True

if __name__ == "__main__":
    print("CONSULTOR SECIHTI v32 - INICIANDO...")
    
    if not verificar_dependencias():
        sys.exit(1)
    
    main()
