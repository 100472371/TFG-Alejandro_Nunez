from fastapi import FastAPI, Query, Body, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional, List
from fastapi import Depends
import io
import csv
import psycopg2
from datetime import date
import subprocess
import json
from fastapi import Body


from db_manager import (
    ranking_autores,
    obtener_ids_papers_por_autor,
    get_connection,
    obtener_paper_completo,
    ranking_por_conferencia,
    evolucion_autor,
    palabras_clave_mas_usadas,
    publicaciones_espanolas_por_anio,
    obtener_ids_papers_por_editorial,
    obtener_ids_papers_por_conferencia,
    get_paper_ids_from_authors_conferencia,
    obtener_ids_papers_por_keywords,
    top_coauthor_pairs, 
    get_paper_ids_por_pares,
    mapa_paises_con_preview,
    detalle_series_por_pais,
    obtener_ids_papers_por_pais_y_series,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def raiz():
    return {"mensaje": "API de análisis bibliométrico en funcionamiento"}

@app.get("/limites/anios")
def obtener_limites_anios(db: psycopg2.extensions.connection = Depends(get_connection)):
    with db.cursor() as cur:
        cur.execute("SELECT MIN(year), MAX(year) FROM conference_editions")
        min_year, max_year = cur.fetchone()
    return {"min_year": min_year, "max_year": max_year}

# 1. Ranking general de autores
@app.get("/ranking/autores")
def endpoint_ranking_autores(year_start: Optional[int] = None, year_end: Optional[int] = None):
    data = ranking_autores(year_start, year_end)

    todos_ids = []
    for full_name, _total in data:
        ids = obtener_ids_papers_por_autor(full_name, year_start=year_start, year_end=year_end)
        todos_ids.extend(ids)

    return {
        "autores": [{"full_name": r[0], "total": r[1]} for r in data],
        "paper_ids": list(set(todos_ids))
    }



@app.post("/exportar_csv/ranking_autores", response_class=StreamingResponse)
def exportar_csv_ranking_autores(year_start: Optional[int] = None, year_end: Optional[int] = None):
    ranking = ranking_autores(year_start, year_end)
    if not ranking:
        raise HTTPException(status_code=404, detail="No hay autores")

    todos_ids = []
    for full_name, _total in ranking:
        ids = obtener_ids_papers_por_autor(full_name, year_start=year_start, year_end=year_end)
        todos_ids.extend(ids)

    return exportar_csv(list(set(todos_ids)))


# 2. Ranking autores por conferencia
@app.get("/conferencias_unicas")
def get_conferencias_unicas():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT TRIM(SPLIT_PART(name, '''', 1))
            FROM conferences
            WHERE name IS NOT NULL AND name LIKE '%''%'
            ORDER BY 1
        """)
        data = [row[0] for row in cur.fetchall()]
        return data
    finally:
        cur.close()
        conn.close()


@app.get("/ranking/conferencia")
def endpoint_ranking_conferencia(conferencia: str, year_start: Optional[int] = None, year_end: Optional[int] = None):
    data = ranking_por_conferencia(conferencia, year_start, year_end)
    authors = [r[0] for r in data]
    paper_ids = get_paper_ids_from_authors_conferencia(authors, conferencia, year_start, year_end)

    return {
        "autores": [{"full_name": r[0], "total": r[1]} for r in data],
        "paper_ids": paper_ids
    }


@app.post("/exportar_csv/ranking_conferencia")
def exportar_csv_ranking_conferencia(conferencia: str, year_start: Optional[int] = None, year_end: Optional[int] = None):
    data = ranking_por_conferencia(conferencia, year_start, year_end)
    authors = [r[0] for r in data]
    paper_ids = get_paper_ids_from_authors_conferencia(authors, conferencia, year_start, year_end)
    return exportar_csv(paper_ids)


# 3. Palabras más usada en ciertos años
@app.get("/estadisticas/palabras_clave")
def endpoint_palabras_clave(year_start: Optional[int] = None, year_end: Optional[int] = None, top: int = 20):
    top_keywords, total_count = palabras_clave_mas_usadas(year_start, year_end, top_n=top, return_total=True)
    return {
        "top_keywords": [{"keyword": k, "count": v} for k, v in top_keywords],
        "total_count": total_count
    }
@app.post("/exportar_csv/palabras_clave", response_class=StreamingResponse)
def exportar_csv_palabras_clave(year_start: Optional[int] = None, year_end: Optional[int] = None, top: int = 20):
    palabras = palabras_clave_mas_usadas(year_start, year_end, top)
    keywords = [kw for kw, _ in palabras]
    paper_ids = obtener_ids_papers_por_keywords(keywords,year_start, year_end)
    return exportar_csv(paper_ids)

# 4. Estadísticas de publicaciones españolas
@app.get("/estadisticas/publicaciones_espanolas")
def endpoint_espanolas(year_start: Optional[int] = None, year_end: Optional[int] = None):
    datos = publicaciones_espanolas_por_anio()
    if year_start:
        datos = [d for d in datos if d["year"] >= year_start]
    if year_end:
        datos = [d for d in datos if d["year"] <= year_end]
    return datos

@app.post("/exportar_csv/publicaciones_espanolas", response_class=StreamingResponse)
def exportar_csv_publicaciones_espanolas(year_start: Optional[int] = None, year_end: Optional[int] = None):
    conn = get_connection()
    cur = conn.cursor()

    try:
        query = """
            SELECT DISTINCT p.id
            FROM papers p
            JOIN conference_editions ce ON p.edition_id = ce.id
            WHERE TRUE
        """
        params = []
        if year_start:
            query += " AND ce.year >= %s"
            params.append(year_start)
        if year_end:
            query += " AND ce.year <= %s"
            params.append(year_end)

        cur.execute(query, tuple(params))
        paper_ids = [row[0] for row in cur.fetchall()]

        return exportar_csv(paper_ids)

    finally:
        cur.close()
        conn.close()



# 5. Evolución de un autor
@app.get("/estadisticas/evolucion_autor")
def endpoint_evolucion_autor(autor: str, year_start: int = None, year_end: int = None):
    return evolucion_autor(autor, year_start, year_end)

@app.get("/autores/existe")
def endpoint_autor_existe(autor: str):
    ids = obtener_ids_papers_por_autor(autor)
    return {"exists": len(ids) > 0, "total_papers": len(ids)}


@app.post("/exportar_csv/evolucion_autor", response_class=StreamingResponse)
def exportar_csv_evolucion_autor(autor: str, year_start: Optional[int] = None, year_end: Optional[int] = None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Obtener los IDs del autor (sin filtrar por año)
        paper_ids = obtener_ids_papers_por_autor(autor)
        if not paper_ids:
            raise HTTPException(status_code=404, detail="No se encontraron publicaciones para este autor.")

        # Ahora filtramos por años si se indican
        if year_start is not None or year_end is not None:
            placeholders = ','.join(['%s'] * len(paper_ids))
            query = f"""
                SELECT p.id
                FROM papers p
                JOIN conference_editions ce ON p.edition_id = ce.id
                WHERE p.id IN ({placeholders})
            """
            params = paper_ids
            if year_start is not None:
                query += " AND ce.year >= %s"
                params.append(year_start)
            if year_end is not None:
                query += " AND ce.year <= %s"
                params.append(year_end)

            cur.execute(query, tuple(params))
            filtered_ids = [row[0] for row in cur.fetchall()]
        else:
            filtered_ids = paper_ids

        if not filtered_ids:
            raise HTTPException(status_code=404, detail="No hay publicaciones en el rango de años seleccionado.")

        return exportar_csv(filtered_ids)

    finally:
        cur.close()
        conn.close()

# 6. Top de coautores
@app.get("/estadisticas/coautorias")
def endpoint_coautorias(
    year_start: Optional[int] = None,
    year_end:   Optional[int] = None,
    top:        int = 20,
    min_papers: int = 2
):
    data = top_coauthor_pairs(year_start, year_end, top_n=top, min_papers=min_papers)
    pairs = [(r[0], r[1]) for r in data]
    paper_ids = get_paper_ids_por_pares(pairs, year_start, year_end)

    return {
        "pairs": [{"autor1": r[0], "autor2": r[1], "total": r[2]} for r in data],
        "paper_ids": paper_ids
    }


@app.post("/exportar_csv/coautorias", response_class=StreamingResponse)
def exportar_csv_coautorias(
    year_start: Optional[int] = None,
    year_end:   Optional[int] = None,
    top:        int = 20,
    min_papers: int = 2
):
    data = top_coauthor_pairs(year_start, year_end, top_n=top, min_papers=min_papers)
    if not data:
        raise HTTPException(status_code=404, detail="No hay coautorías con esos filtros.")

    pairs = [(r[0], r[1]) for r in data]
    paper_ids = get_paper_ids_por_pares(pairs, year_start, year_end)
    if not paper_ids:
        raise HTTPException(status_code=404, detail="No hay publicaciones para las parejas seleccionadas.")

    return exportar_csv(paper_ids)

@app.post("/exportar_csv", response_class=StreamingResponse)
def exportar_csv(ids: List[int] = Body(...)):
    publicaciones = []
    for pid in ids:
        paper, autores = obtener_paper_completo(pid)
        if not paper:
            continue
        autores_bib = " and ".join(autor.strip() for autor in autores)
        publicaciones.append({
            "id": paper[0],
            "author": autores_bib,
            "title": paper[1],
            "year": paper[9],
            "isbn": paper[7] or "",
            "publisher": paper[3] or "",
            "address": paper[13] or "",
            "url": paper[6] or "",
            "doi": paper[5] or "",
            "abstract": paper[4] or "",
            "booktitle": paper[10] or "",
            "pages": paper[2] or "",
            "keywords": paper[8] or "",
            "series": paper[11] or ""
        })

    if not publicaciones:
        raise HTTPException(status_code=404, detail="No se encontraron publicaciones.")

    output = io.StringIO()
    fieldnames = ["id", "author", "title", "year", "isbn", "publisher", "address", "url", "doi", "abstract", "booktitle", "pages", "keywords", "series"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(publicaciones)

    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=publicaciones.csv"})
router = APIRouter()

def ejecutar_y_mostrar(comando):
    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    for linea in proceso.stdout:
        print(linea, end='') 
    proceso.wait()
    if proceso.returncode != 0:
        raise subprocess.CalledProcessError(proceso.returncode, comando)

@app.post("/actualizar_datos/")
def actualizar_datos(ano_inicio: int, ano_fin: int):
    min_year_valido = 1994
    año_actual = date.today().year

    if ano_inicio < min_year_valido:
        raise HTTPException(status_code=400, detail=f"El año de inicio no puede ser menor que {min_year_valido}.")
    if ano_fin > año_actual:
        raise HTTPException(status_code=400, detail=f"El año de fin no puede ser mayor que el actual ({año_actual}).")
    if ano_inicio > ano_fin:
        raise HTTPException(status_code=400, detail="El año de inicio no puede ser mayor que el año de fin.")

    try:
        # # 1. Ejecutar scraping 
        ejecutar_y_mostrar([
            "python", "../Automatizacion/scrapping_amc.py",
            str(ano_inicio), str(ano_fin)
        ])

        # 2. Ejecutar importador 
        ejecutar_y_mostrar([
            "python", "../importar_bibtex.py",
            "--ano_inicio", str(ano_inicio),
            "--ano_fin", str(ano_fin)
        ])

        # 3. Leer estadísticas
        with open("../Automatizacion/estadisticas_resultados.txt", "r") as f:
            data = json.load(f)

        años_validos = [int(a) for a, v in data.items() if v["espanolas"] > 0]
        if not años_validos:
            raise HTTPException(status_code=500, detail="No hay años con publicaciones españolas.")

        min_year = min(años_validos)
        max_year = max(años_validos)

        # 4. Guardar estado en la base de datos
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM sistema_estado")
        cur.execute(
            "INSERT INTO sistema_estado (ultima_actualizacion, min_year, max_year) VALUES (%s, %s, %s)",
            (date.today(), min_year, max_year)
        )
        conn.commit()
        cur.close()
        conn.close()

        return {
            "mensaje": f"Actualización completada de {ano_inicio} a {ano_fin}",
            "min": min_year,
            "max": max_year
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al ejecutar {' '.join(e.cmd)} (código {e.returncode})"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/estado/ultima_actualizacion")
def estado_ultima_actualizacion():
    import json

    try:
        # 1. Leer valores desde BD
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ultima_actualizacion, min_year, max_year FROM sistema_estado LIMIT 1")
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return {"estado": "no_data"}

        fecha, min_year, max_year = row

        # 2. Leer estadisticas_resultados.txt
        with open("../Automatizacion/estadisticas_resultados.txt", "r") as f:
            data = json.load(f)

        # 3. Comprobar años faltantes
        años_faltantes = []
        for y in range(min_year, max_year + 1):
            y_str = str(y)
            if y_str not in data or data[y_str].get("espanolas", 0) == 0:
                años_faltantes.append(y)

        return {
            "ultima_actualizacion": fecha.strftime("%d/%m/%Y"),
            "min_year": min_year,
            "max_year": max_year,
            "años_faltantes": años_faltantes
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar el estado: {str(e)}")



@app.get("/map/paises")
def endpoint_mapa_paises(
    year_start: Optional[int] = None,
    year_end:   Optional[int] = None,
    serie:      Optional[str] = None,
):
    rows = mapa_paises_con_preview(year_start, year_end, serie)
    items = [{
        "country": r["country"],
        "total_papers": int(r["total_papers"]),
        "total_authors": int(r["total_authors"]),
        "num_series": int(r["num_series"]),
        "series_preview": r["series_preview"],  # lista corta (top-5) para tooltip
    } for r in rows]
    return {"items": items, "params": {"year_start": year_start, "year_end": year_end, "serie": serie}}

@app.get("/map/paises/detalle")
def endpoint_detalle_pais(
    country: str,
    year_start: Optional[int] = None,
    year_end:   Optional[int] = None,
    serie:      Optional[str] = None,
):
    rows = detalle_series_por_pais(country, year_start, year_end, serie)
    items = [{
        "serie": r["serie"],
        "total_papers": int(r["total_papers"]),
        "total_authors": int(r["total_authors"]),
        "years": r["years"],  # array de años
    } for r in rows]
    return {"country": country, "items": items, "params": {"year_start": year_start, "year_end": year_end, "serie": serie}}


@app.post("/exportar_csv/mapa_paises_detalle", response_class=StreamingResponse)
def exportar_csv_mapa_paises_detalle(
    country: str = Body(...),
    series:  Optional[List[str]] = Body(default=None),
    year_start: Optional[int] = None,
    year_end:   Optional[int] = None,
):
    ids = obtener_ids_papers_por_pais_y_series(country, series, year_start, year_end)
    if not ids:
        raise HTTPException(status_code=404, detail="No hay publicaciones para los filtros indicados.")
    return exportar_csv(ids)
