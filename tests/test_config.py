#!/usr/bin/env python3
"""
Prueba de configuración básica del sistema.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_import_config():
    try:
        import config
        print("Configuración importada correctamente")
        return True
    except Exception as e:
        print(f"Error importando config: {e}")
        return False

def test_pdf_directory():
    import config
    import os
    
    if hasattr(config, 'PDF_DIRECTORY'):
        pdf_dir = config.PDF_DIRECTORY
        exists = os.path.exists(pdf_dir)
        print(f"Directorio PDF: {pdf_dir}")
        print(f"Existe: {exists}")
        return exists
    else:
        print("PDF_DIRECTORY no definido en config.py")
        return False

def test_api_key():
    import config
    
    if hasattr(config, 'API_KEY'):
        key = config.API_KEY
        if key and len(key) > 10:
            print(f"API Key configurada")
            return bool(key)
        else:
            print("API Key muy corta o vacía")
            return False
    else:
        print("API_KEY no definida en config.py")
        return False

def test_pdf_files():
    import config
    
    try:
        if hasattr(config, 'PDF_FILES'):
            pdfs = config.PDF_FILES
            count = len(pdfs)
            print(f"PDFs encontrados: {count}")
            
            if count > 0:
                print(f"Primer archivo: {pdfs[0].name}")
                return True
            else:
                print("No se encontraron archivos PDF")
                return False
        else:
            print("PDF_FILES no definido en config.py")
            return False
    except Exception as e:
        print(f"Error listando PDFs: {e}")
        return False

def main():
    print("EJECUTANDO PRUEBAS DE CONFIGURACIÓN")
    
    pruebas = [
        ("Importar configuración", test_import_config),
        ("Directorio PDF", test_pdf_directory),
        ("API Key", test_api_key),
        ("Archivos PDF", test_pdf_files),
    ]
    
    resultados = []
    
    for nombre, funcion in pruebas:
        print(f"\n{nombre}:")
        try:
            resultado = funcion()
            resultados.append(resultado)
            estado = "PASÓ" if resultado else "FALLÓ"
            print(f"{estado}")
        except Exception as e:
            print(f"ERROR: {e}")
            resultados.append(False)
    
    print(f"\nRESULTADO: {sum(resultados)}/{len(resultados)} pruebas pasaron")
    
    if sum(resultados) == len(resultados):
        print("Todas las pruebas pasaron - Sistema listo")
        return 0
    else:
        print("Algunas pruebas fallaron - Revisar configuración")
        return 1

if __name__ == "__main__":
    sys.exit(main())
