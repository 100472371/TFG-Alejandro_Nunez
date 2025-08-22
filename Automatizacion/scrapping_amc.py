import os
import glob
import time
import random
import sys
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import undetected_chromedriver as uc
import os
from logging.handlers import TimedRotatingFileHandler
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import logging
import time
import random
import json
from seleniumbase import Driver
import shutil


def borrar_todas_las_downloaded_files():
    carpetas_encontradas = set()

    # Buscar hacia abajo (subcarpetas)
    for dirpath, dirnames, _ in os.walk("."):
        for nombre in dirnames:
            if nombre.startswith("downloaded_files"):
                ruta = os.path.abspath(os.path.join(dirpath, nombre))
                carpetas_encontradas.add(ruta)

    # Buscar hacia arriba (carpetas padre)
    ruta_actual = os.path.abspath(os.getcwd())
    while True:
        for nombre in os.listdir(ruta_actual):
            full_path = os.path.join(ruta_actual, nombre)
            if os.path.isdir(full_path) and nombre.startswith("downloaded_files"):
                carpetas_encontradas.add(full_path)
        padre = os.path.dirname(ruta_actual)
        if padre == ruta_actual:
            break  # Raíz del sistema
        ruta_actual = padre

    # Eliminar las carpetas encontradas
    if not carpetas_encontradas:
        logging.info("No se encontraron carpetas 'downloaded_files*' en ningún nivel.")
        return

    for carpeta in carpetas_encontradas:
        try:
            shutil.rmtree(carpeta)
            logging.info(f"Carpeta eliminada: {carpeta}")
        except Exception as e:
            logging.warning(f"No se pudo eliminar {carpeta}: {e}")

    logging.info(f"{len(carpetas_encontradas)} carpeta(s) 'downloaded_files*' eliminadas.")



# ========== RUTAS ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
borrar_todas_las_downloaded_files()

CARPETA_DESCARGAS = os.path.abspath("../Automatizacion/descargas_acm")
os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
logging.info(f"Carpeta de descargas creada: {CARPETA_DESCARGAS}")

# ========== LIMPIEZA PREVIA ==========


chrome_options = Options()
prefs = {"download.default_directory": CARPETA_DESCARGAS}
chrome_options.add_experimental_option("prefs", prefs)

# ========== INICIALIZAR DRIVER BASE ==========
driver = Driver(uc=True, headless=False)

logging.info("Driver de SeleniumBase inicializado con undetected_chromedriver.")

# ========== NAVEGACIÓN Y CAPTCHA ==========
url = "https://dl.acm.org/sig/sigchi"
driver.uc_open_with_reconnect(url, 4)
#driver.uc_gui_click_captcha()
time.sleep(10)

print("Driver listo y CAPTCHA gestionado")


print("Página abierta correctamente")
# =============================
# FUNCIONES AUXILIARES
# =============================

def cerrar_banner_cookies(driver):
    """Cierra el banner de cookies (Cookiebot) si está visible.
    Espera hasta 10 s a que el botón 'Allow all' sea clicable y lo pulsa.
    Deja traza en el log tanto si lo cierra como si no aparece.
    """
    try:
        boton = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"))
        )
        boton.click()
        logging.info("Banner de cookies cerrado correctamente")
    except TimeoutException:
        logging.info("No se encontró el botón de cookies o ya estaba cerrado.")

busquedas_realizadas = 0  # Contador global al inicio del script

def realizar_busqueda(driver, consulta):
    """Realiza una búsqueda en ACM DL (SIGCHI) respetando el placeholder de la primera vez.
    Lógica:
    - Si es la primera búsqueda (busquedas_realizadas == 0), usa el input con
      placeholder "Search within SIGCHI".
    - En búsquedas posteriores, usa el input con placeholder "Search".
    Limpia la caja, escribe la consulta, envía ENTER y aumenta el contador global.
    """
    global busquedas_realizadas

    try:
        if busquedas_realizadas == 0:
            logging.info("Primera búsqueda, detectando caja inicial...")
            xpath_caja = '//input[@class="auto-complete quick-search__input" and @placeholder="Search within SIGCHI"]'
        else:
            logging.info("Búsqueda posterior, detectando caja genérica...")
            xpath_caja = '//input[@class="auto-complete quick-search__input" and @placeholder="Search"]'

        caja = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath_caja)))
        caja.clear()
        caja.send_keys(consulta)
        caja.send_keys(Keys.ENTER)

        busquedas_realizadas += 1
        logging.info(f"Búsqueda '{consulta}' lanzada. Total búsquedas: {busquedas_realizadas}")
        time.sleep(5)

    except TimeoutException:
        logging.error("No se pudo realizar la búsqueda.")


def establecer_resultados_por_pagina(driver):
    """Configura la vista para mostrar 50 resultados por página."""
    try:
        WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH,
            '//*[@id="skip-to-main-content"]/main/div[1]/div/div[2]/div/div[3]/div[2]/div[1]/ul/li[3]/a'))).click()
        logging.info("Vista ajustada a 50 resultados por página.")
    except TimeoutException:
        logging.warning("No se pudo ajustar el número de resultados por página.")

def hay_resultados(driver):
    """Indica si hay resultados en la búsqueda actual.
    Evalúa la presencia de mensajes de “sin resultados” en varios idiomas. Si
    detecta alguno, devuelve False; en caso contrario, asume que sí hay resultados.
    """

    mensajes = [
        '//*[@class="search-result__no-result"]',
        '//*[contains(text(), "Your search did not return any results")]',
        '//*[contains(text(), "Tu búsqueda no produjo ningún resultado")]',
        '//*[contains(text(), "A sua pesquisa não retornou nenhum resultado")]',
        '//*[contains(text(), "Ihre Suche ergab keine Ergebnisse")]',
        '//*[contains(text(), "Aucune correspondance pour votre recherche")]'
    ]
    for xpath in mensajes:
        try:
            WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
            logging.info("No hay resultados para este filtro.")
            return False
        except TimeoutException:
            continue
    logging.info("Hay resultados.")
    return True

def limpiar_filtro_anual(driver, año):
    """Elimina el filtro activo correspondiente al año proporcionado.

    Localiza el chip/badge del filtro cuyo texto contiene el año y hace clic en
    la acción 'Remove filter'. Se usa ejecución JavaScript para asegurar el clic."""

    try:
        xpath = f'//li[span[contains(text(), "{año}")]]/a[contains(@title, "Remove filter")]'
        boton = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].click();", boton)
        logging.info(f"Filtro del año {año} eliminado.")
        time.sleep(2)
    except TimeoutException:
        logging.warning(f"No se encontró el filtro del año {año}.")



def combinar_archivos_bibtex(carpeta_destino, nombre_final="resultados_completos.bib"):
    ruta_salida = os.path.join(carpeta_destino, nombre_final)

    # 1. Detectar TODAS las carpetas llamadas downloaded_files* en cualquier nivel
    carpetas_sbase = glob.glob("**/downloaded_files*", recursive=True)

    # 2. Buscar archivos .bib en carpeta_destino y en todas las carpetas encontradas
    archivos = []

    # Añadir .bib desde carpeta destino
    archivos += glob.glob(os.path.join(carpeta_destino, "*.bib"))

    # Añadir .bib desde carpetas downloaded_files*
    for carpeta in carpetas_sbase:
        archivos += glob.glob(os.path.join(carpeta, "*.bib"))

    # 3. Ignorar archivo de salida si ya existe
    archivos = [f for f in archivos if os.path.abspath(f) != os.path.abspath(ruta_salida)]

    if archivos:
        with open(ruta_salida, "w", encoding="utf-8") as salida:
            for archivo in archivos:
                with open(archivo, "r", encoding="utf-8") as entrada:
                    salida.write(entrada.read() + "\n\n")
                logging.info(f"Incluido: {archivo}")
                os.remove(archivo)
                logging.info(f"Eliminado: {archivo}")
        logging.info(f"Archivos combinados en: {ruta_salida}")
    else:
        logging.warning("No hay archivos .bib para combinar.")

    # 4. Eliminar carpetas downloaded_files* si están vacías
    for carpeta in carpetas_sbase:
        try:
            if os.path.isdir(carpeta) and not os.listdir(carpeta):
                shutil.rmtree(carpeta)
                logging.info(f"Carpeta eliminada: {carpeta}")
        except Exception as e:
            logging.warning(f"No se pudo eliminar la carpeta {carpeta}: {e}")



def obtener_limites_acm(driver):
    """Detecta los límites reales de años permitidos leyendo los mensajes de error."""
    min_val = None
    max_val = None
    try:
        msg = driver.find_element(By.CLASS_NAME, "start-date-error").text
        min_val = int(msg.split("minimum value is")[1].strip())
        logging.info(f"Mínimo permitido detectado: {min_val}")
    except:
        pass
    try:
        msg = driver.find_element(By.CLASS_NAME, "end-date-error").text
        max_val = int(msg.split("maximum value is")[1].strip())
        logging.info(f"Máximo permitido detectado: {max_val}")
    except:
        pass
    return min_val, max_val



def establecer_rango_anual(driver, año):
    """Establece un filtro anual fijando el mismo año como inicio y fin."""

    try:
        for intento in range(3):
            try:
                input_inicio = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="range-slider-start"]'))
                )
                input_fin = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="range-slider-end"]'))
                )

                for campo in [input_inicio, input_fin]:
                    campo.clear()
                    time.sleep(0.5)
                    campo.send_keys(str(año))
                    time.sleep(0.5)

                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, 'facet-publication-date-apply'))
                ).click()

                logging.info("Filtro de año aplicado.")
                time.sleep(5)
                return
            except StaleElementReferenceException:
                logging.warning(f"Intento {intento + 1}: campo obsoleto, reintentando...")
                time.sleep(2)
    except TimeoutException:
        logging.warning("Timeout al establecer el filtro de año.")


def obtener_total_publicaciones(driver):
    """Devuelve el número total de publicaciones mostradas en los resultados.

    Flujo:
      - Si no hay resultados (hay_resultados(driver) == False), retorna 0.
      - Localiza el elemento con clase 'hitsLength' y extrae el número.
      - Normaliza separadores de miles (',') y convierte a int.
    """

    if not hay_resultados(driver):
        logging.info("Total publicaciones: 0 (sin resultados)")
        return 0
    try:
        total_texto = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "hitsLength"))).text
        return int(total_texto.replace(",", "").strip())
    except TimeoutException:
        logging.warning("No se pudo obtener el número total de publicaciones.")
        return 0

def estadisticas_por_ano(driver, año_inicio, año_fin):
    """Calcula y persiste estadísticas anuales (total y españolas) en ACM DL (SIGCHI).

    Descripción:
        Realiza dos pasadas sobre el intervalo [año_inicio, año_fin]:
          1) Conteo total de publicaciones por año.
          2) Conteo de publicaciones con afiliación en España por año
             (consulta: affiliation:"Spain"), incluyendo descarga de BibTeX
             por año cuando el conteo > 0.
    """
    ruta_estadisticas = "estadisticas_resultados.txt"
    datos_actuales = {}

    # === Cargar archivo existente o crear uno nuevo vacío ===
    if os.path.exists(ruta_estadisticas):
        try:
            with open(ruta_estadisticas, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                if contenido:
                    datos_actuales = json.loads(contenido)
                    logging.info("Archivo estadisticas_resultados.txt cargado correctamente.")
                else:
                    logging.warning("El archivo estaba vacío. Iniciando con diccionario vacío.")
        except Exception as e:
            logging.warning(f"No se pudo leer el archivo existente: {e}")
    else:
        with open(ruta_estadisticas, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
        logging.info("Archivo estadisticas_resultados.txt no existía. Se ha creado vacío.")

    # === Inicializar diccionario actual de trabajo ===
    datos = {}

    # Copiar todo lo que ya había
    for año, valores in datos_actuales.items():
        datos[año] = {
            "total": valores.get("total", 0),
            "espanolas": valores.get("espanolas", 0)
        }

    realizar_busqueda(driver, "*")
    establecer_rango_anual(driver, 1900)
    time.sleep(2)
    min_detectado, max_detectado = obtener_limites_acm(driver)

    if min_detectado and año_inicio < min_detectado:
        logging.warning(f"Ajustando año de inicio: {año_inicio} → {min_detectado}")
        año_inicio = min_detectado
    if max_detectado and año_fin > max_detectado:
        logging.warning(f"Ajustando año de fin: {año_fin} → {max_detectado}")
        año_fin = max_detectado
    if año_inicio > año_fin:
        logging.error("Rango de años inválido, no se procesará nada.")
        return datos

    # === Total publicaciones por año ===
    for año in range(año_inicio, año_fin + 1):
        establecer_rango_anual(driver, año)
        total = obtener_total_publicaciones(driver)

        # Crear entrada si no existe
        datos[str(año)] = datos.get(str(año), {"total": 0, "espanolas": 0})

        if datos[str(año)]["total"] != total:
            logging.info(f"[{año}] Total actualizado: {datos[str(año)]['total']} → {total}")
            print(f"Año {año} - Nuevo total: {total}")
            datos[str(año)]["total"] = total
        else:
            print(f"Año {año} - Total sin cambios ({total})")

        limpiar_filtro_anual(driver, año)

        # Guardar tras cada año
        with open(ruta_estadisticas, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4)

    # === Segunda búsqueda: publicaciones españolas ===
    realizar_busqueda(driver, 'affiliation:"Spain"')
    establecer_resultados_por_pagina(driver)

    establecer_rango_anual(driver, 1900)
    time.sleep(2)
    min_detectado, max_detectado = obtener_limites_acm(driver)
    if min_detectado and año_inicio < min_detectado:
        año_inicio = min_detectado
    if max_detectado and año_fin > max_detectado:
        año_fin = max_detectado
    if año_inicio > año_fin:
        logging.error("Rango de años inválido, no se procesará nada.")
        return datos

    for año in range(año_inicio, año_fin + 1):
        establecer_rango_anual(driver, año)
        esp = obtener_total_publicaciones(driver)

        # Asegurar entrada segura
        datos[str(año)] = datos.get(str(año), {"total": 0, "espanolas": 0})

        if datos[str(año)]["espanolas"] != esp:
            logging.info(f"[{año}] Españolas actualizado: {datos[str(año)]['espanolas']} → {esp}")
            print(f"Año {año} - Nuevas españolas: {esp}")
            datos[str(año)]["espanolas"] = esp
            
        else:
            print(f"Año {año} - Españolas sin cambios ({esp})")

        if esp > 0:
            descargar_por_ano(driver, CARPETA_DESCARGAS, año, año)

        limpiar_filtro_anual(driver, año)

        # Guardar tras cada año
        with open(ruta_estadisticas, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4)

    logging.info("Estadísticas guardadas en 'estadisticas_resultados.txt'")
    return datos

    
def descargar_por_ano(driver, carpeta_descargas, año_inicial, año_final):
    """Exporta citas (BibTeX) año a año navegando por todas las páginas de resultados."""
    
    for año in range(año_inicial, año_final + 1):
        logging.info(f"Año {año}...")
        establecer_rango_anual(driver, año)
        if not hay_resultados(driver):
            limpiar_filtro_anual(driver,año_inicial)
            continue
        pagina = 1
        while True:
            logging.info(f"Página {pagina} del año {año}...")
            try:
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH,
                    '//*[@id="skip-to-main-content"]/main/div[1]/div/div[2]/div/div[3]/div[1]/div[2]/div[1]'))).click()
                logging.info("'Select All' marcado.")
            except TimeoutException:
                logging.warning("No se pudo marcar 'Select All'.")

            try:
                WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH,
                    '//*[@id="skip-to-main-content"]/main/div[1]/div/div[2]/div/div[3]/div[1]/div[2]/div[3]/a[1]'))).click()
                logging.info("'Export Citations' clickeado.")
            except TimeoutException:
                logging.warning("Botón de exportación no disponible.")

            time.sleep(3)

            try:
                xpath = '//*[@id="selectedTab"]/div/div[2]/ul/li[1]/a'
                WebDriverWait(driver, 10).until(lambda d: "disabled" not in d.find_element(By.XPATH, xpath).get_attribute("class"))
                driver.find_element(By.XPATH, xpath).click()
                logging.info("Descarga BibTeX iniciada.")
            except TimeoutException:
                logging.warning("Botón de descarga no disponible.")

            time.sleep(8)

            try:
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
                    (By.XPATH, '//*[@id="exportCitation"]/div/div[1]/button/i'))).click()
                logging.info("Popup cerrado.")
            except Exception as e:
                logging.warning(f"No se pudo cerrar popup: {e}")

            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//a[@title="Next Page"]'))).click()
                pagina += 1
                time.sleep(5)
            except TimeoutException:
                logging.info(f"Fin del año {año}.")
                break
        limpiar_filtro_anual(driver,año_inicial)

# =============================
# EJECUCIÓN PRINCIPAL CON TRY
# =============================

try:
    cerrar_banner_cookies(driver)

    if len(sys.argv) != 3:
        logging.error("Debes indicar el año de inicio y fin. Ejemplo: python scraping_IEExplorer.py 2010 2024")
        driver.quit()
        exit(1)

    año_inicio = int(sys.argv[1])
    año_fin = int(sys.argv[2])

    estadisticas_por_ano(driver, año_inicio, año_fin)
    logging.info("Estadísticas por año obtenidas correctamente.")
    combinar_archivos_bibtex(CARPETA_DESCARGAS)

    # === Reordenar archivo de estadísticas por año ===
    try:
        with open("estadisticas_resultados.txt", "r", encoding="utf-8") as f:
            datos = json.load(f)
        datos_ordenados = dict(sorted(datos.items(), key=lambda x: int(x[0])))
        with open("estadisticas_resultados.txt", "w", encoding="utf-8") as f:
            json.dump(datos_ordenados, f, indent=4)
        logging.info("Archivo estadisticas_resultados.txt reordenado por año correctamente.")
    except Exception as e:
        logging.warning(f"No se pudo reordenar el archivo de estadísticas: {e}")

except Exception as e:
    logging.error(f"Error inesperado durante la ejecución: {e}")
finally:
    driver.quit()
    logging.info("Navegador cerrado correctamente.")