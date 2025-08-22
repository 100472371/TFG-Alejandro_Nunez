import psycopg2
import json
from collections import Counter, defaultdict
from psycopg2.extras import RealDictCursor
from typing import List


DB_PARAMS = {
    'dbname': 'alejandro_db',
    'user': 'alejandro',
    'password': 'alejandro*',
    'host': 'localhost',
    'port': 5432
}

def get_connection():
    return psycopg2.connect(**DB_PARAMS)

# 1. Ranking general de autores
def ranking_autores(year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()
    query = '''
        SELECT a.full_name, COUNT(p.id) AS total
        FROM authors a
        JOIN paper_authors pa ON a.id = pa.author_id
        JOIN papers p ON pa.paper_id = p.id
        JOIN conference_editions ce ON p.edition_id = ce.id
    '''
    filtros, params = [], []
    if year_start:
        filtros.append('ce.year >= %s')
        params.append(year_start)
    if year_end:
        filtros.append('ce.year <= %s')
        params.append(year_end)
    if filtros:
        query += ' WHERE ' + ' AND '.join(filtros)
    query += ' GROUP BY a.full_name ORDER BY total DESC LIMIT 20'
    cur.execute(query, tuple(params))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data

def obtener_ids_papers_por_autor(nombre):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT p.id
        FROM papers p
        JOIN paper_authors pa ON pa.paper_id = p.id
        JOIN authors a ON a.id = pa.author_id
        WHERE a.full_name = %s
    """, (nombre,))
    ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return ids


# 2. Ranking autores por conferencia
def ranking_por_conferencia(conferencia, year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = '''
            SELECT a.full_name, COUNT(p.id) AS total
            FROM authors a
            JOIN paper_authors pa ON a.id = pa.author_id
            JOIN papers p ON pa.paper_id = p.id
            JOIN conference_editions ce ON p.edition_id = ce.id
            JOIN conferences c ON ce.conference_id = c.id
            WHERE c.name ILIKE %s
        '''
        params = [f"{conferencia} %"] 

        if year_start:
            query += ' AND ce.year >= %s'
            params.append(year_start)
        if year_end:
            query += ' AND ce.year <= %s'
            params.append(year_end)

        query += ' GROUP BY a.full_name ORDER BY total DESC LIMIT 20'

        cur.execute(query, tuple(params))
        data = cur.fetchall()
        return data

    except Exception as e:
        print("ERROR en ranking_por_conferencia:", e)
        raise
    finally:
        cur.close()
        conn.close()

def get_paper_ids_from_authors_conferencia(authors, conferencia, year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = '''
            SELECT DISTINCT p.id
            FROM papers p
            JOIN paper_authors pa ON p.id = pa.paper_id
            JOIN authors a ON pa.author_id = a.id
            JOIN conference_editions ce ON p.edition_id = ce.id
            JOIN conferences c ON ce.conference_id = c.id
            WHERE a.full_name = ANY(%s)
              AND c.name ILIKE %s
        '''
        params = [authors, f"{conferencia} %"]

        if year_start:
            query += ' AND ce.year >= %s'
            params.append(year_start)
        if year_end:
            query += ' AND ce.year <= %s'
            params.append(year_end)

        cur.execute(query, tuple(params))
        return [row[0] for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

# 3. Palabras clave más usadas
def palabras_clave_mas_usadas(year_start=None, year_end=None, top_n=None, return_total=False):
    conn = get_connection()
    cur = conn.cursor()
    
    query = '''
        SELECT p.keywords FROM papers p
        JOIN conference_editions ce ON p.edition_id = ce.id
    '''
    filtros, params = [], []
    if year_start:
        filtros.append('ce.year >= %s')
        params.append(year_start)
    if year_end:
        filtros.append('ce.year <= %s')
        params.append(year_end)
    if filtros:
        query += ' WHERE ' + ' AND '.join(filtros)

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    all_keywords = []
    for row in rows:
        if row[0]:
            keywords = [kw.strip().lower() for kw in row[0].split(',') if kw.strip()]
            all_keywords.extend(keywords)

    count = Counter(all_keywords)
    total = sum(count.values())

    if return_total:
        return count.most_common(top_n), total
    else:
        return count.most_common(top_n)

def obtener_ids_papers_por_keywords(lista_keywords: List[str]):
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ' OR '.join(["p.keywords ILIKE %s" for _ in lista_keywords])
    query = f"""
        SELECT DISTINCT p.id
        FROM papers p
        JOIN conference_editions ce ON p.edition_id = ce.id
        WHERE {placeholders}
    """
    params = [f"%{kw}%" for kw in lista_keywords]
    cur.execute(query, tuple(params))
    ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return ids

# 4. Estadísticas de publicaciones españolas
def publicaciones_espanolas_por_anio(year_start=None, year_end=None):
    import json
    with open("../Automatizacion/estadisticas_resultados.txt", "r") as f:
        data = json.load(f)

    resultados = []
    for k, v in data.items():
        year = int(k)
        if (year_start is not None and year < year_start) or (year_end is not None and year > year_end):
            continue
        resultados.append({"year": year, "total": v["total"], "espanolas": v["espanolas"]})
    
    return sorted(resultados, key=lambda x: x["year"])


# 5. Evolución de un autor
def evolucion_autor(full_name, year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()

    query = '''
        SELECT ce.year, COUNT(p.id)
        FROM authors a
        JOIN paper_authors pa ON a.id = pa.author_id
        JOIN papers p ON pa.paper_id = p.id
        JOIN conference_editions ce ON p.edition_id = ce.id
        WHERE a.full_name = %s
    '''
    params = [full_name]

    if year_start is not None:
        query += ' AND ce.year >= %s'
        params.append(year_start)
    if year_end is not None:
        query += ' AND ce.year <= %s'
        params.append(year_end)

    query += ' GROUP BY ce.year ORDER BY ce.year'

    cur.execute(query, params)
    data = cur.fetchall()
    cur.close()
    conn.close()

    return [{"year": r[0], "total": r[1]} for r in data]

# 6. Pares de co-autores con más papers
def top_coauthor_pairs(year_start=None, year_end=None, top_n=20, min_papers=1):
    conn = get_connection()
    cur = conn.cursor()
    query = '''
        SELECT
            LEAST(a1.full_name, a2.full_name) AS autor1,
            GREATEST(a1.full_name, a2.full_name) AS autor2,
            COUNT(DISTINCT p.id) AS total
        FROM paper_authors pa1
        JOIN paper_authors pa2
             ON pa1.paper_id = pa2.paper_id AND pa1.author_id < pa2.author_id
        JOIN authors a1 ON a1.id = pa1.author_id
        JOIN authors a2 ON a2.id = pa2.author_id
        JOIN papers p   ON p.id   = pa1.paper_id
        JOIN conference_editions ce ON ce.id = p.edition_id
        WHERE TRUE
    '''
    params = []
    if year_start is not None:
        query += ' AND ce.year >= %s'
        params.append(year_start)
    if year_end is not None:
        query += ' AND ce.year <= %s'
        params.append(year_end)

    query += '''
        GROUP BY autor1, autor2
        HAVING COUNT(DISTINCT p.id) >= %s
        ORDER BY total DESC, autor1, autor2
        LIMIT %s
    '''
    params.extend([min_papers, top_n])

    cur.execute(query, tuple(params))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data 


def get_paper_ids_por_pares(pairs, year_start=None, year_end=None):
    """
    pairs: lista de tuplas (autor1, autor2) ya normalizadas (autor1 <= autor2).
    """
    conn = get_connection()
    cur = conn.cursor()
    paper_ids = set()

    base = '''
        SELECT DISTINCT p.id
        FROM papers p
        JOIN paper_authors pa1 ON pa1.paper_id = p.id
        JOIN paper_authors pa2 ON pa2.paper_id = p.id AND pa1.author_id <> pa2.author_id
        JOIN authors a1 ON a1.id = pa1.author_id
        JOIN authors a2 ON a2.id = pa2.author_id
        JOIN conference_editions ce ON ce.id = p.edition_id
        WHERE LEAST(a1.full_name, a2.full_name) = %s
          AND GREATEST(a1.full_name, a2.full_name) = %s
    '''
    for (a1, a2) in pairs:
        q = base
        params = [a1, a2]
        if year_start is not None:
            q += ' AND ce.year >= %s'
            params.append(year_start)
        if year_end is not None:
            q += ' AND ce.year <= %s'
            params.append(year_end)

        cur.execute(q, tuple(params))
        paper_ids.update([row[0] for row in cur.fetchall()])

    cur.close()
    conn.close()
    return list(paper_ids)


def obtener_paper_completo(paper_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.pages, p.publisher, p.abstract, p.doi, p.url, p.isbn, p.keywords,
               ce.year, ce.booktitle, c.name AS conference_name, e.name AS editorial, c.location
        FROM papers p
        JOIN conference_editions ce ON p.edition_id = ce.id
        JOIN conferences c ON ce.conference_id = c.id
        JOIN editorials e ON c.editorial_id = e.id
        WHERE p.id = %s
    """, (paper_id,))
    paper = cur.fetchone()

    cur.execute("""
        SELECT a.full_name FROM authors a
        JOIN paper_authors pa ON pa.author_id = a.id
        WHERE pa.paper_id = %s
    """, (paper_id,))
    autores = [r[0] for r in cur.fetchall()]

    cur.close()
    conn.close()
    return paper, autores


def obtener_ids_papers_por_editorial(year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()
    query = '''
        SELECT DISTINCT p.id
        FROM papers p
        JOIN conference_editions ce ON p.edition_id = ce.id
        JOIN conferences c ON ce.conference_id = c.id
        JOIN editorials e ON c.editorial_id = e.id
    '''
    filtros, params = [], []
    if year_start:
        filtros.append('ce.year >= %s')
        params.append(year_start)
    if year_end:
        filtros.append('ce.year <= %s')
        params.append(year_end)
    if filtros:
        query += ' WHERE ' + ' AND '.join(filtros)
    cur.execute(query, tuple(params))
    ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return ids

def obtener_ids_papers_por_conferencia(year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()
    query = '''
        SELECT DISTINCT p.id
        FROM papers p
        JOIN conference_editions ce ON p.edition_id = ce.id
    '''
    filtros, params = [], []
    if year_start:
        filtros.append('ce.year >= %s')
        params.append(year_start)
    if year_end:
        filtros.append('ce.year <= %s')
        params.append(year_end)
    if filtros:
        query += ' WHERE ' + ' AND '.join(filtros)
    cur.execute(query, tuple(params))
    ids = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return ids

def autores_por_conferencia(conferencia, year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()
    query = '''
        SELECT DISTINCT a.full_name
        FROM authors a
        JOIN paper_authors pa ON a.id = pa.author_id
        JOIN papers p ON pa.paper_id = p.id
        JOIN conference_editions ce ON p.edition_id = ce.id
        JOIN conferences c ON ce.conference_id = c.id
        WHERE c.name ILIKE %s
    '''
    params = [f"%{conferencia}%"]
    if year_start:
        query += ' AND ce.year >= %s'
        params.append(year_start)
    if year_end:
        query += ' AND ce.year <= %s'
        params.append(year_end)
    cur.execute(query, tuple(params))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in data]

def ranking_por_conferencia(conferencia, year_start=None, year_end=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = '''
            SELECT a.full_name, COUNT(p.id) AS total
            FROM authors a
            JOIN paper_authors pa ON a.id = pa.author_id
            JOIN papers p ON pa.paper_id = p.id
            JOIN conference_editions ce ON p.edition_id = ce.id
            JOIN conferences c ON ce.conference_id = c.id
            WHERE c.name ILIKE %s
        '''
        params = [f"{conferencia} %"] 

        if year_start:
            query += ' AND ce.year >= %s'
            params.append(year_start)
        if year_end:
            query += ' AND ce.year <= %s'
            params.append(year_end)

        query += ' GROUP BY a.full_name ORDER BY total DESC LIMIT 20'

        cur.execute(query, tuple(params))
        data = cur.fetchall()
        return data

    except Exception as e:
        print("ERROR en ranking_por_conferencia:", e)
        raise
    finally:
        cur.close()
        conn.close()


def autores_consistentes(year_start: int, year_end: int):
    conn = get_connection()
    cur = conn.cursor()
    query = '''
        SELECT a.full_name, MIN(ce.year) as first_year, MAX(ce.year) as last_year, COUNT(DISTINCT ce.year) as num_years
        FROM authors a
        JOIN paper_authors pa ON a.id = pa.author_id
        JOIN papers p ON pa.paper_id = p.id
        JOIN conference_editions ce ON p.edition_id = ce.id
        WHERE ce.year BETWEEN %s AND %s
        GROUP BY a.full_name
        HAVING COUNT(DISTINCT ce.year) = %s
        ORDER BY a.full_name
    '''
    cur.execute(query, (year_start, year_end, year_end - year_start + 1))
    autores = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "full_name": r[0],
            "first_year": r[1],
            "last_year": r[2],
            "num_years": r[3]
        } for r in autores
    ]

