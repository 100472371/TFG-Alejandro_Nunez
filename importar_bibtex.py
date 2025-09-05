import os
import time
import sys
import argparse
import unicodedata
import re
import psycopg2
import bibtexparser
import logging
import subprocess
import socket
from difflib import SequenceMatcher
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import homogenize_latex_encoding, convert_to_unicode
from seleniumbase import Driver
import shutil


# Evitar problemas de bloqueos de IP
def lanzar_tor_en_segundo_plano():
    tor_path = os.path.join(BASE_DIR, "tor-browser", "Browser", "TorBrowser", "Tor", "tor")
    logging.info("Lanzando Tor en segundo plano...")

    try:
        tor_process = subprocess.Popen(
            [tor_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        logging.error(f"No se pudo lanzar Tor: {e}")
        sys.exit(1)

    # Esperar a que el puerto 9050 esté abierto
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", 9050), timeout=1):
                logging.info("Tor conectado en 127.0.0.1:9050")
                return tor_process
        except Exception:
            time.sleep(1)

    logging.error("Tor no respondió en el puerto 9050 tras 30 segundos.")
    tor_process.terminate()
    sys.exit(1)





# ================================
# LIMPIEZA Y CONFIGURACIÓN RUTAS
# ================================

def borrar_todas_las_downloaded_files():
    carpetas_encontradas = set()

    for dirpath, dirnames, _ in os.walk("."):
        for nombre in dirnames:
            if nombre.startswith("downloaded_files"):
                ruta = os.path.abspath(os.path.join(dirpath, nombre))
                carpetas_encontradas.add(ruta)

    ruta_actual = os.path.abspath(os.getcwd())
    while True:
        for nombre in os.listdir(ruta_actual):
            full_path = os.path.join(ruta_actual, nombre)
            if os.path.isdir(full_path) and nombre.startswith("downloaded_files"):
                carpetas_encontradas.add(full_path)
        padre = os.path.dirname(ruta_actual)
        if padre == ruta_actual:
            break
        ruta_actual = padre

    for carpeta in carpetas_encontradas:
        try:
            shutil.rmtree(carpeta)
            logging.info(f"🧹 Carpeta eliminada: {carpeta}")
        except Exception as e:
            logging.warning(f"No se pudo eliminar {carpeta}: {e}")
    logging.info(f"{len(carpetas_encontradas)} carpeta(s) 'downloaded_files*' eliminadas.")

borrar_todas_las_downloaded_files()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configurar logging para que se vea en consola al lanzarlo desde subprocess
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


# Argumentos
parser = argparse.ArgumentParser()
parser.add_argument('--ano_inicio', type=int, default=None)
parser.add_argument('--ano_fin', type=int, default=None)
args = parser.parse_args()

# Paths personalizados para driver y chrome bin
driver_path = os.path.abspath(os.path.join(BASE_DIR, "ChromeDriver", "chromedriver-linux64", "chromedriver"))
chrome_bin = os.path.abspath(os.path.join(BASE_DIR, "ChromeDriver", "chrome-linux64", "chrome"))

if not os.path.exists(driver_path):
    logging.error(f"No se encontró ChromeDriver en: {driver_path}")
    sys.exit(1)
if not os.path.exists(chrome_bin):
    logging.error(f"No se encontró chrome en: {chrome_bin}")
    sys.exit(1)

# ========== INICIALIZAR DRIVER BASE ==========
tor_process = lanzar_tor_en_segundo_plano()

driver = Driver(
    uc=True,
    headless=False,
    undetected=True,
    proxy="socks5://127.0.0.1:9050"
)
logging.info("Driver de SeleniumBase inicializado con undetected_chromedriver.")
wait = WebDriverWait(driver, 60)

# PARÁMETROS DE BASE DE DATOS
DB_PARAMS = {
    'dbname': 'alejandro_db',
    'user': 'alejandro',
    'password': 'alejandro*',
    'host': 'localhost',
    'port': 5432
}

BIBTEX_DIRS = [os.path.join(BASE_DIR, "Automatizacion", "descargas_acm")]

# FUNCIONES AUXILIARES
def limpiar_nombre(nombre):
    nombre = re.sub(r'[\'"\\\-]', ' ', nombre)
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', nombre).strip()

def split_authors(author_field):
    autores = [a.strip() for a in author_field.replace('\n', ' ').split(' and ')]
    normalizados = []
    for a in autores:
        if ',' in a:
            last, first = a.split(',', 1)
            normalizados.append(f"{first.strip()} {last.strip()}")
        else:
            normalizados.append(a.strip())
    return normalizados

def obtener_autores_dblp(titulo, year):
    try:
        print(f"Iniciando búsqueda en DBLP: '{titulo}' para el año {year}")
        url = "https://dblp.org/search/publ"
        print("Abriendo URL en el navegador...")
        driver.uc_open_with_reconnect(url, 4)

        print("Esperando resolución del CAPTCHA...")
        # driver.uc_gui_click_captcha()
        time.sleep(10)
        print("Driver listo y CAPTCHA gestionado correctamente.")

        print("Verificando que la página está correctamente cargada...")
        print("Página abierta correctamente")
        time.sleep(3)

        print("Esperando campo de búsqueda...")
        campo = wait.until(EC.presence_of_element_located((By.NAME, "q")))
        print("Campo de búsqueda localizado. Enviando título...")
        campo.clear()
        campo.send_keys(titulo)
        time.sleep(10)
        campo.send_keys(Keys.RETURN)
        print("Consulta enviada.")
        time.sleep(10)

        print("Buscando bloques de resultados...")
        bloques = driver.find_elements(By.CSS_SELECTOR, "li.entry.inproceedings.toc.marked, li.entry.informal.toc.marked")
        print(f"{len(bloques)} bloques encontrados en la página de resultados.")

        titulo_normalizado = limpiar_nombre(titulo).lower()
        mejor_sim = 0
        mejores_autores = []
        mejor_titulo = ""
        mejor_ano = None

        for idx, bloque in enumerate(bloques):
            try:
                bloque_text = bloque.text
                print(f"Procesando bloque {idx + 1}: {bloque_text[:100]}...")

                if year and str(year) not in bloque_text:
                    print(f"Bloque {idx + 1} descartado (no contiene año {year})")
                    continue

                cite = bloque.find_element(By.CSS_SELECTOR, "cite")
                titulo_dblp = cite.find_element(By.CSS_SELECTOR, 'span.title').text.strip()
                titulo_dblp_limpio = limpiar_nombre(titulo_dblp).lower()

                sim = 1.0 if titulo_dblp_limpio == titulo_normalizado else SequenceMatcher(None, titulo_normalizado, titulo_dblp_limpio).ratio()
                print(f"Bloque {idx + 1}: '{titulo_dblp}' (similitud: {sim:.2f})")

                if sim > mejor_sim:
                    spans = cite.find_elements(By.CSS_SELECTOR, 'span[itemprop="name"]')
                    mejores_autores = [s.text.strip() for s in spans]
                    mejor_sim = sim
                    mejor_titulo = titulo_dblp
                    mejor_ano = year
                    print(f"Nuevo mejor resultado con similitud {sim:.2f}: '{titulo_dblp}'")
            except Exception as e:
                print(f"Error procesando bloque {idx + 1}: {e}")
                continue

        if mejores_autores:
            print(f"Título más similar encontrado (similitud {mejor_sim:.2f}): '{mejor_titulo}'")
            print(f"Autores extraídos desde DBLP: {mejores_autores}")
            return mejores_autores

    except Exception as e:
        logging.exception(f"Excepción general durante la búsqueda en DBLP: {e}")

    logging.warning("No se encontró ningún título válido en DBLP.")
    return []


# FUNCIÓN PRINCIPAL
def importar_bibtex():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    inserted_papers = 0
    skipped_no_doi = 0

    for folder in BIBTEX_DIRS:
        for filename in os.listdir(folder):
            if filename.endswith('.bib'):
                with open(os.path.join(folder, filename), 'r', encoding='utf-8') as bibfile:
                    parser = BibTexParser()
                    parser.customization = lambda record: convert_to_unicode(homogenize_latex_encoding(record))
                    bib_database = bibtexparser.load(bibfile, parser=parser)

                    for entry in bib_database.entries:
                        doi = entry.get('doi')
                        if not doi:
                            skipped_no_doi += 1
                            continue

                        year = int(entry.get('year')) if entry.get('year') else None
                        if args.ano_inicio and args.ano_fin and (year is None or not (args.ano_inicio <= year <= args.ano_fin)):
                            continue

                        autores_dblp = obtener_autores_dblp(entry.get('title', ''), year) if year else []
                        autores_finales = []
                        for author in split_authors(entry.get('author', '')):
                            limpio = limpiar_nombre(author)
                            if autores_dblp:
                                mejor = max(autores_dblp, key=lambda x: SequenceMatcher(None, limpiar_nombre(x), limpio).ratio())
                                sim = SequenceMatcher(None, limpiar_nombre(mejor), limpio).ratio()
                                if sim > 0.5:
                                    print(f"Autor '{author}' reemplazado por '{mejor}' (similitud: {sim:.2f})")
                                    limpio = limpiar_nombre(mejor)
                                else:
                                    print(f"Autor '{author}' mantenido como '{limpio}' (similitud máxima: {sim:.2f})")
                            autores_finales.append(limpio.title())

                        authors_str = ', '.join(autores_finales)

                        editorial = entry.get('publisher', '').strip()
                        cur.execute("SELECT id FROM editorials WHERE name = %s", (editorial,))
                        row = cur.fetchone()
                        if row:
                            editorial_id = row[0]
                        else:
                            cur.execute("INSERT INTO editorials (name) VALUES (%s) RETURNING id", (editorial,))
                            editorial_id = cur.fetchone()[0]

                        serie = entry.get('series', '').strip()
                        location = entry.get('location', '').strip()
                        cur.execute("SELECT id FROM conferences WHERE name = %s", (serie,))
                        row = cur.fetchone()
                        if row:
                            conf_id = row[0]
                        else:
                            cur.execute("INSERT INTO conferences (name, location, editorial_id) VALUES (%s,%s,%s) RETURNING id", (serie, location, editorial_id))
                            conf_id = cur.fetchone()[0]

                        booktitle = entry.get('booktitle', '').strip()
                        cur.execute("SELECT id FROM conference_editions WHERE conference_id = %s AND year = %s", (conf_id, year))
                        row = cur.fetchone()
                        if row:
                            edition_id = row[0]
                        else:
                            cur.execute("INSERT INTO conference_editions (conference_id, year, booktitle) VALUES (%s,%s,%s) RETURNING id", (conf_id, year, booktitle))
                            edition_id = cur.fetchone()[0]

                        cur.execute("SELECT id FROM papers WHERE doi = %s", (doi,))
                        row = cur.fetchone()
                        nuevo_paper = False
                        if row:
                            paper_id = row[0]
                        else:
                            cur.execute("""
                                INSERT INTO papers (edition_id, authors, title, pages, publisher, abstract, doi, url, isbn, keywords)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                            """, (
                                edition_id,
                                authors_str,
                                entry.get('title'),
                                entry.get('pages'),
                                entry.get('publisher'),
                                entry.get('abstract'),
                                doi,
                                entry.get('url'),
                                entry.get('isbn'),
                                entry.get('keywords')
                            ))
                            paper_id = cur.fetchone()[0]
                            inserted_papers += 1
                            nuevo_paper = True

                        for nombre in autores_finales:
                            cur.execute("SELECT id, publication_count, first_publication_year, last_publication_year FROM authors WHERE full_name = %s", (nombre,))
                            row = cur.fetchone()
                            if row:
                                author_id, pub_count, first_pub, last_pub = row
                                if nuevo_paper:
                                    pub_count += 1
                                    first_pub = min(first_pub or year, year)
                                    last_pub = max(last_pub or year, year)
                                    cur.execute("UPDATE authors SET publication_count = %s, first_publication_year = %s, last_publication_year = %s WHERE id = %s", (pub_count, first_pub, last_pub, author_id))
                            else:
                                cur.execute("INSERT INTO authors (full_name, publication_count, first_publication_year, last_publication_year) VALUES (%s, %s, %s, %s) RETURNING id", (nombre, 1, year, year))
                                author_id = cur.fetchone()[0]

                            cur.execute("INSERT INTO paper_authors (paper_id, author_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (paper_id, author_id))

                            cur.execute("""
                                SELECT c.name, COUNT(*) FROM paper_authors pa
                                JOIN papers p ON pa.paper_id = p.id
                                JOIN conference_editions ce ON p.edition_id = ce.id
                                JOIN conferences c ON ce.conference_id = c.id
                                WHERE pa.author_id = %s
                                GROUP BY c.name ORDER BY COUNT(*) DESC LIMIT 1
                            """, (author_id,))
                            res = cur.fetchone()
                            if res:
                                cur.execute("UPDATE authors SET most_common_conference = %s WHERE id = %s", (res[0], author_id))

    conn.commit()
    cur.close()
    conn.close()
    driver.quit()
    logging.info("Importación finalizada.")
    logging.info(f"Artículos insertados: {inserted_papers}")
    logging.info(f"Entradas BibTeX sin DOI: {skipped_no_doi}")


if __name__ == "__main__":
    importar_bibtex()
    if tor_process:
        tor_process.terminate()
        logging.info("Proceso Tor finalizado.")