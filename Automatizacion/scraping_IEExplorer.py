import os
import glob
import time
import sys
import random
import logging
import atexit
from logging.handlers import TimedRotatingFileHandler
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException
import undetected_chromedriver as uc

# =============================
# CONFIGURACIÓN DEL NAVEGADOR
# =============================


# Carpeta de logs en la raíz
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.abspath(os.path.join(BASE_DIR, "../logs"))
os.makedirs(LOG_DIR, exist_ok=True)

# Nombre del log según el script
script_name = os.path.basename(__file__).replace(".py", "")
log_path = os.path.join(LOG_DIR, f"{script_name}.log")

# Configuración de logs: consola + rotación diaria
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        TimedRotatingFileHandler(log_path, when="midnight", interval=1, backupCount=7, encoding="utf-8")
    ]
)


CARPETA_DESCARGAS = os.path.abspath("../Automatizacion/descargas_ieee")
os.makedirs(CARPETA_DESCARGAS, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.info(f"Carpeta de descargas configurada en: {CARPETA_DESCARGAS}")


# Ruta personalizada del driver y Chrome

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
driver_path = os.path.join(BASE_DIR, "../ChromeDriver/chromedriver_win64_116/chromedriver-win64/chromedriver.exe")
driver_path = os.path.abspath(driver_path)
if not os.path.exists(driver_path):
    logging.error(f"El driver no se encuentra en la ruta especificada: {driver_path}")
    sys.exit(1)
    
chrome_bin = os.path.join(BASE_DIR,"../ChromeDriver/chrome_v116/chrome-win64/chrome.exe")    
chrome_bin = os.path.abspath(chrome_bin)  
if not os.path.exists(chrome_bin):
    logging.error(f"El binario de Chrome no se encuentra en la ruta especificada: {chrome_bin}")
    sys.exit(1)

# Opciones de Chrome
opciones = uc.ChromeOptions()
opciones.binary_location = chrome_bin
opciones.add_argument("--disable-blink-features=AutomationControlled")
opciones.add_argument("--disable-infobars")
opciones.add_argument("--disable-dev-shm-usage")
opciones.add_argument("--no-sandbox")
opciones.add_argument("--disable-gpu")
opciones.add_argument("--window-size=1920,1080")
opciones.add_argument("--headless=new")  
opciones.add_argument("--start-maximized")
opciones.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

opciones.add_experimental_option("prefs", {
    "download.default_directory": CARPETA_DESCARGAS,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
})

# Lanzamos el navegador con tu driver y binario propio
driver = uc.Chrome(driver_executable_path=driver_path, options=opciones, use_subprocess=True)
driver.set_page_load_timeout(588)
wait = WebDriverWait(driver, 180)
logging.info("Navegador iniciado correctamente")
driver.get("https://ieeexplore.ieee.org/")
time.sleep(random.uniform(8, 12))

# =============================
# FUNCIONES AUXILIARES
# =============================


def esperar_carga_ieee():
    try:
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        try:
            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "OpaqueLayer")))
        except TimeoutException:
            pass
        time.sleep(5)
    except (TimeoutException, UnexpectedAlertPresentException):
        try:
            alert = driver.switch_to.alert
            alert.accept()
            logging.info("Alerta inesperada aceptada.")
        except:
            pass


def cerrar_banners(driver):
    try:
        # Primer intento: botón Osano por clase específica (más fiable)
        boton = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.osano-cm-accept-all"))
        )
        boton.click()
        logging.info("Botón 'Aceptar todo' de Osano clicado correctamente.")
    except TimeoutException:
        logging.info("No apareció el botón Osano de cookies, probando con genérico.")
        try:
            # Segundo intento: botón por texto visible (menos fiable si el render es raro)
            boton_generico = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(normalize-space(.), "Aceptar todo")]'))
            )
            boton_generico.click()
            logging.info("Banner de cookies genérico cerrado correctamente.")
        except TimeoutException:
            logging.info("No apareció ningún banner de cookies.")
    
    esperar_carga_ieee()

def establecer_resultados_por_pagina(driver):
    try:
        # 1. Click en el botón "Items Per Page"
        boton_items = wait.until(
            EC.element_to_be_clickable((By.ID, "dropdownPerPageLabel"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", boton_items)
        boton_items.click()
        logging.info("Menú 'Items Per Page' abierto.")
        esperar_carga_ieee()

        # 2. Esperar al dropdown visible con aria-labelledby
        contenedor_dropdown = wait.until(
            EC.presence_of_element_located((
                By.XPATH,
                '//div[@aria-labelledby="dropdownPerPageLabel" and contains(@class, "dropdown-menu")]'
            ))
        )
        logging.info("Contenedor de opciones detectado.")

        # 3. Obtener todos los botones dentro del dropdown
        botones = contenedor_dropdown.find_elements(By.XPATH, './/button[contains(@class, "filter-popover-option")]')
        valores_disponibles = []

        for boton in botones:
            try:
                valor = int(boton.text.strip())
                valores_disponibles.append((valor, boton))
            except ValueError:
                continue  # ignorar si el texto no es un número

        if not valores_disponibles:
            logging.warning("No se encontraron opciones numéricas para resultados por página.")
            return

        # 4. Seleccionar el botón con el valor más alto
        max_valor, boton_max = max(valores_disponibles, key=lambda x: x[0])
        driver.execute_script("arguments[0].scrollIntoView(true);", boton_max)
        driver.execute_script("arguments[0].click();", boton_max)
        logging.info(f"Cambiado a {max_valor} resultados por página.")
        time.sleep(5)

    except TimeoutException:
        logging.warning("No se pudo cambiar a más resultados por página.")


def realizar_busqueda_ieee(driver, consulta='("Author Affiliations":Spain)'):
    try:
        caja = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input.Typeahead-input[aria-label="main"]'))
        )
        caja.clear()
        caja.send_keys(consulta)
        esperar_carga_ieee()
        caja.send_keys(Keys.ENTER)
        logging.info(f"Búsqueda lanzada con consulta: {consulta}")
        esperar_carga_ieee()
    except TimeoutException:
        logging.warning("No se encontró el campo de búsqueda de IEEE.")

def seleccionar_filtro_tipo(driver, tipo="Conferences"):
    checkbox_id = f"refinement-ContentType:{tipo}"
    try:
        WebDriverWait(driver,15).until(EC.presence_of_element_located((By.ID, checkbox_id)))
        return True
    except TimeoutException:
        return False

def cancelar_filtro_anio(driver):
    try:
        botones = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'i.fa-times.Breadcrumb-close.js-close'))
        )
        for boton in botones:
            tipo = boton.get_attribute("data-type")
            if tipo == "refinement":
                driver.execute_script("arguments[0].click();", boton)
                logging.info("Filtro de año cancelado correctamente.")
                time.sleep(3)
                esperar_carga_ieee()
                return
        logging.warning("No se encontró filtro de año con data-type='refinement'.")
    except TimeoutException:
        logging.warning("Timeout al intentar cancelar el filtro de año.")

def cancelar_filtro_conferencias(driver):
    try:
        boton = WebDriverWait(driver,15).until(
            EC.presence_of_element_located((By.ID, 'ContentType:Conferences'))
        )
        tipo = boton.get_attribute("data-type")
        if tipo == "refinement":
            driver.execute_script("arguments[0].click();", boton)
            logging.info("Filtro de 'Conferences' cancelado correctamente.")
            time.sleep(3)
        else:
            logging.warning("El botón encontrado no tiene data-type='refinement'.")
    except TimeoutException:
        logging.warning("No se encontró el botón para cancelar el filtro de 'Conferences'.")


def resultados_invalidos(driver):
    """
    Detecta si aparece un mensaje de error de búsqueda, como "We were unable to find results".
    """
    try:
        wait.until(
            EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "We were unable to find results")]'))
        )
        logging.warning("IEEE indica que no se encontraron resultados (error general).")
        esperar_carga_ieee()
        return True
    except TimeoutException:
        return False


def establecer_rango_anual_ieee(driver, año=None):
    try:
        # Seleccionamos los dos campos del rango
        input_inicio = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[aria-label="Enter start year of range"]'))
        )
        input_fin = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[aria-label="Enter end year of range"]'))
        )

        # Limpiamos y escribimos en ambos campos el mismo año
        for campo in [input_inicio, input_fin]:
            campo.clear()
            campo.send_keys(Keys.CONTROL + "a")
            campo.send_keys(Keys.DELETE)
            campo.send_keys(str(año))
            driver.execute_script("""
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, campo)
            time.sleep(0.3)

        logging.info(f"Filtro por rango: {año} - {año}")

        # Click en botón "Apply"
        boton = wait.until(
            EC.element_to_be_clickable((By.ID, "Year-apply-btn"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", boton)
        time.sleep(3)
        boton.click()
        logging.info("Filtro aplicado correctamente.")
        time.sleep(5)
        esperar_carga_ieee()

    except TimeoutException:
        logging.warning("No se pudo establecer el filtro de año por rango.")

def exportar_bibtex_ieee(driver):
    try:
        archivos_previos = set(os.listdir(CARPETA_DESCARGAS))

        check = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.results-actions-selectall-checkbox")))
        driver.execute_script("arguments[0].scrollIntoView(true);", check)
        esperar_carga_ieee()
        check.click()
        logging.info("'Select All on Page' marcado.")

        exportar = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"Export")]')))
        exportar.click()
        logging.info("Botón 'Export' clicado.")
        esperar_carga_ieee()

        pestaña = wait.until(EC.element_to_be_clickable((By.XPATH, '//a[contains(text(), "Citations")]')))
        pestaña.click()
        logging.info("Pestaña 'Citations' abierta.")
        esperar_carga_ieee()

        span_bibtex = wait.until(EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "BibTeX")]')))
        input_bibtex = span_bibtex.find_element(By.XPATH, './ancestor::label//input')
        driver.execute_script("arguments[0].scrollIntoView(true);", input_bibtex)
        driver.execute_script("arguments[0].click();", input_bibtex)
        logging.info("Input 'BibTeX' seleccionado.")
        esperar_carga_ieee()

        span_abstract = wait.until(EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "Citation and Abstract")]')))
        input_abstract = span_abstract.find_element(By.XPATH, './ancestor::label//input')
        driver.execute_script("arguments[0].scrollIntoView(true);", input_abstract)
        driver.execute_script("arguments[0].click();", input_abstract)
        logging.info("Input 'Citation and Abstract' seleccionado.")
        esperar_carga_ieee()

        descargar = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(text(),"Download")]')))
        descargar.click()
        logging.info("Descarga iniciada.")
        esperar_carga_ieee()

        cerrar_div = wait.until(EC.element_to_be_clickable((By.XPATH, '//div[contains(@class, "pe-3 cursor-pointer d-flex align-items-center")]')))
        driver.execute_script("arguments[0].click();", cerrar_div)
        cerrar_div.click()
        logging.info("Popup cerrado.")
        esperar_carga_ieee()

        # Esperar a que aparezca un nuevo archivo
        max_espera = 60
        inicio = time.time()
        while True:
            archivos_actuales = set(os.listdir(CARPETA_DESCARGAS))
            nuevos = archivos_actuales - archivos_previos
            if any(f.endswith('.bib') for f in nuevos):
                logging.info("Nuevo archivo .bib detectado, descarga completada.")
                break
            if time.time() - inicio > max_espera:
                logging.warning("Timeout esperando archivo .bib, posible fallo de descarga.")
                break
            time.sleep(1)

    except TimeoutException:
        logging.warning("Fallo durante el proceso de exportación BibTeX.")


def combinar_archivos_bibtex(carpeta, nombre_final="ieee_resultados_completos.bib"):
    salida = os.path.join(carpeta, nombre_final)
    archivos = [
        f for f in glob.glob(os.path.join(carpeta, "*.bib"))
        if os.path.abspath(f) != os.path.abspath(salida)
    ]

    if archivos:
        with open(salida, "w", encoding="utf-8") as out:
            for f in archivos:
                with open(f, "r", encoding="utf-8") as entrada:
                    out.write(entrada.read() + "\n\n")
        logging.info(f"Archivos .bib combinados en: {salida}")
        for f in archivos:
            os.remove(f)
            logging.info(f"Eliminado archivo: {f}")
    else:
        logging.warning("No se encontraron archivos .bib para combinar.")


def descargar_por_ano_ieee(driver, año_inicio, año_fin):
    for año in range(año_inicio, año_fin + 1):
        logging.info(f"Analizando año {año}...")
        establecer_rango_anual_ieee(driver, año)

        # Comprobación 1: error general
        if resultados_invalidos(driver):
            logging.info(f"Año {año} inválido por error de búsqueda. Cancelando filtro.")
            cancelar_filtro_anio(driver)
            continue

        # Comprobación 2: no hay opción "Conferences"
        if not seleccionar_filtro_tipo(driver, "Conferences"):
            logging.info(f"No hay 'Conferences' en {año}, se cancela filtro.")
            cancelar_filtro_conferencias(driver)
            continue

        try:
            WebDriverWait(driver,15).until(
                EC.element_to_be_clickable((By.ID, "refinement-ContentType:Conferences"))
            ).click()
            logging.info("Filtro 'Conferences' aplicado.")

            # Aplicar botón Apply
            boton_apply_tipo = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH, '//button[contains(@class, "xpl-btn-primary") and text()="Apply"]'
                ))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", boton_apply_tipo)
            time.sleep(0.3)
            boton_apply_tipo.click()
            logging.info("Botón 'Apply' de tipo aplicado correctamente.")
            time.sleep(5)
        except TimeoutException:
            logging.warning("No se pudo aplicar el filtro de tipo.")

        esperar_carga_ieee()

        establecer_resultados_por_pagina(driver)

        pagina = 1
        while True:
            logging.info(f"Exportando página {pagina} del año {año}...")
            exportar_bibtex_ieee(driver)

            # Buscar botón ">" para ir a la siguiente página
            try:
                boton_next = wait.until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        '//li[contains(@class, "next-btn")]/button'
                    ))
                )
                if boton_next.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView(true);", boton_next)
                    driver.execute_script("arguments[0].click();", boton_next)
                    logging.info("Pasando a la siguiente página...")
                    pagina += 1
                    esperar_carga_ieee()
                else:
                    raise TimeoutException("Botón '>' desactivado.")
            except TimeoutException:
                logging.info(f"Fin de resultados para el año {año} tras {pagina} página(s).")
                cancelar_filtro_conferencias(driver)
                cancelar_filtro_anio(driver)
                break



# =============================
# EJECUCIÓN PRINCIPAL
# =============================

try:
    cerrar_banners(driver)
    realizar_busqueda_ieee(driver)

    if len(sys.argv) != 3:
        logging.error("Debes indicar el año de inicio y fin. Ejemplo: python scraping_IEExplorer.py 2010 2024")
        driver.quit()
        exit(1)

    año_inicio = int(sys.argv[1])
    año_fin = int(sys.argv[2])

    descargar_por_ano_ieee(driver, año_inicio, año_fin)
    combinar_archivos_bibtex(CARPETA_DESCARGAS)
except Exception as e:
    logging.error(f"Error inesperado: {e}")
finally:
    logging.info("Navegador cerrado.")
    driver8.quit()
    logging.info("Proceso completado.")