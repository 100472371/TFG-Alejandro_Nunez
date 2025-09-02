import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import streamlit.components.v1 as components
import time
import io
from plotly import graph_objects as go
import re
from pathlib import Path


# Lourdes me propuso que en algunas comparativas gráficas se estire la escala del eje Y
# para que se vea mejor la diferencia entre los valores. Sin embargo streamlit no permite
# modificar la escala de los ejes de los gráficos de Plotly, así que lo hago con estas funciones

# === Escala por tramos (0–corte estirado) ===
CORTE_ESCALA = 250      # hasta dónde estiras
FACTOR_BAJO  = 6.0       # cuánto estiras el 0–corte 

def escalar_tramo(y, corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO):
    """
    Escala piecewise:
    - De 0 a 'corte': estirado 'factor_bajo' veces.
    - De 'corte' en adelante: escala normal continua.
    """
    if y <= corte:
        return factor_bajo * y
    else:
        return factor_bajo * corte + (y - corte)  # mantiene continuidad en el punto de corte


def transformar_serie(serie, corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO):
    """Aplica la transformación por tramos a una serie pandas."""
    return serie.apply(lambda v: escalar_tramo(v, corte, factor_bajo))


def generar_ticks(maximo, corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO):
    """
    Genera ticks:
    - Solo 0 y 'corte' (ej. 250).
    - Después múltiplos de 1000.
    """
    ticks_reales = [0, corte] if corte <= maximo else [0, maximo]
    mayores = list(range(1000, int(maximo)+1, 1000))
    ticks_reales += [v for v in mayores if v <= maximo]

    # Mapeo a la escala transformada para que el eje muestre lo correcto
    tickvals = [escalar_tramo(v, corte, factor_bajo) for v in ticks_reales]
    ticktext = [str(v) for v in ticks_reales]

    max_transformado = escalar_tramo(maximo, corte, factor_bajo)
    return tickvals, ticktext, max_transformado



st.set_page_config(
    page_title="Bibliometric Explorer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Si el navegador trae ?page=... desde una sesión anterior, lo limpiamos
try:
    if "page" in st.query_params:
        st.query_params.clear()
except Exception:
    pass


TOKEN_ACTUALIZACION = "token_ALEJANDRO_LOURDES"

# Para pantalla negra de manera completa mientras carga antes de todo
st.markdown("""
    <style>
    html, body, .main, .block-container, header, .stApp {
        background-color: #0e1117 !important;
        color: white !important;
    }
    header {
        background-color: #0e1117 !important;
        color: white !important;
        border-bottom: none !important;
        box-shadow: none !important;
    }
    </style>
""", unsafe_allow_html=True)

if "carga_completada" not in st.session_state:
    with st.empty():
        components.html("""<html style='margin:0;padding:0;height:100%;width:100%;background:#0e1117;'>
        <head><style>html, body {margin:0;padding:0;overflow:hidden;height:100%;width:100%;background:#0e1117;}</style></head>
        <body>
            <div style='position:fixed;top:0;left:0;width:100vw;height:100vh;background:#0e1117;display:flex;flex-direction:column;justify-content:center;align-items:center;'>
                <script src='https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js'></script>
                <lottie-player src='https://assets6.lottiefiles.com/packages/lf20_j1adxtyb.json' background='transparent' speed='1'
                  style='width: 140px; height: 140px;' loop autoplay></lottie-player>
                <h1 style='color: white; font-family: Montserrat, sans-serif; margin-top: 30px; font-size: 1.8rem;'>Loading bibliometric dashboard...</h1>
            </div>
        </body></html>""", height=1000)
        time.sleep(5)
        st.session_state.carga_completada = True
        st.rerun()

def resetear_kpis():
    # Reinicio KPIs y caches para evitar mostrar datos viejos entre búsquedas
    st.session_state["kpi_pub_total"] = "-"
    st.session_state["kpi_autores_unicos"] = "-"
    st.session_state["kpi_conf_total"] = "-"
    st.session_state.pop("df_keywords", None)
    st.session_state.pop("df_espanolas", None)
    st.session_state.pop("df_ranking", None)
    st.session_state.pop("df_pairs", None)
    st.session_state.pop("df_evolucion_autor", None)
    st.session_state.pop("csv_data", None)
    st.session_state.pop("csv_nombre", None)
    st.session_state["ocultar_kpis"] = False

def realizar_busqueda():
    st.session_state["cargando"] = True
    st.session_state["forzar_rerun"] = True  

# ---- Estilos  ----
if st.session_state.get("carga_completada"):
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');

    html, body, .main, .block-container {
        background-color: #0e1117 !important;
        color: white !important;
        font-family: 'Montserrat', sans-serif;
    }

    h1.title {
        text-align: center;
        font-size: 2.8rem;
        color: #f8fafc;
        margin-bottom: 0.5rem;
        animation: fadeInUp 0.8s ease;
    }
    .subtitle {
        font-size: 1.2rem;
        color: #94a3b8;
        margin-bottom: 1rem;
        text-align: center;
        animation: fadeInUp 1s ease;
    }

    label {
        color: #e2e8f0 !important;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.2rem;
    }

    button {
        background-color: #1f2937 !important;
        color: white !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        border: 1px solid #475569 !important;
        padding: 0.55rem 1.2rem !important;
        border-radius: 6px !important;
        transition: background-color 0.3s ease;
    }
    button:hover {
        background-color: #334155 !important;
    }
    button:focus, button:active {
        background-color: #475569 !important;
    }

    button[kind="primary"] {
        background-color: #1f2937 !important;
        border: 1px solid #334155 !important;
        color: white !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        padding: 0.55rem 1.2rem !important;
        transition: background-color 0.3s ease;
    }

    button[kind="primary"]:hover {
        background-color: #334155 !important;
    }
    button[kind="primary"]:focus, button[kind="primary"]:active {
        background-color: #475569 !important;
    }

    div[data-baseweb="select"] > div {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        color: white !important;
        font-size: 0.95rem !important;
        font-family: 'Montserrat', sans-serif;
    }

    div[data-baseweb="select"] div[role="button"] {
        padding: 0.4rem !important;
    }

    div[data-baseweb="select"] span {
        color: white !important;
    }

    .value {
        font-size: 2.3rem;
        font-weight: bold;
        color: #38bdf8;
        text-align: center;
        margin-top: 1rem;
        text-shadow: 1px 1px 2px black;
    }
    .label {
        font-size: 1rem;
        color: #cbd5e1;
        text-align: center;
    }

    div[data-testid="column"] > div {
        background: transparent;
        padding: 1rem;
        border-radius: 10px;
    }

    input[type=number], select {
        background-color: #1e293b !important;
        color: white !important;
        font-size: 0.95rem !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        padding: 0.4rem !important;
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .js-plotly-plot .plotly .main-svg {
        font-family: 'Montserrat', sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)


    st.markdown("<h1 class='title'>Bibliometric Explorer</h1>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Search Filters</div>", unsafe_allow_html=True)

    # --- Trigger del modal (no llama nada aún; solo marca un flag y rerun) ---
    top_left, top_right = st.columns([3, 1])  # antes [10, 1]
    with top_right:
        if st.button("Update data", key="btn_open_update", use_container_width=True):
            st.session_state["open_update_modal"] = True
            st.rerun()



    
    API_BASE = "http://10.117.129.37:8000"

    # Flags de estado por defecto
    if "cargando" not in st.session_state:
        st.session_state["cargando"] = False

    if "kpi_pub_total" not in st.session_state:
        resetear_kpis() # inicializo KPIs a "-"

   
    if "ocultar_kpis" not in st.session_state:
        st.session_state["ocultar_kpis"] = False


    def mostrar_kpis(pub_total, autores_unicos, conf_total):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"<div class='value'>{pub_total}</div><div class='label'>Publications</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='value'>{autores_unicos}</div><div class='label'>Unique Authors</div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='value'>{conf_total}</div><div class='label'>Conferences / Publishers</div>", unsafe_allow_html=True)

    # Pido límites válidos al backend para acotar los inputs
    limites = requests.get(f"{API_BASE}/limites/anios").json()
    min_year = limites["min_year"]
    max_year = limites["max_year"]
    year_actual = pd.Timestamp.now().year # para validar que el usuario no meta un año futuro

    col1, col2 = st.columns(2)  
    with col1:
        year_start = st.number_input("Start Year", value=min_year, min_value=min_year, max_value=max_year, step=1, format="%d", key="inicio")
    with col2:
        year_end = st.number_input("End year", value=max_year, min_value=min_year, max_value=year_actual, step=1, format="%d", key="fin")

    # Acción principal (controla qué endpoint se consulta)
    accion = st.selectbox(
        "Action",
        ["Author Ranking" , "Most Frequent Keywords", "Spanish Publications Statistics", "Author Evolution", "Frequent Co-author Pairs"],
        key="accion",
        on_change=resetear_kpis
    )

    params = {"year_start": year_start, "year_end": year_end}
    valid = True

    if year_end > year_actual:
        st.error(f"End year cannot be greater than the current year : ({year_actual}).")
        valid = False
    if year_start > year_end:
        st.error("Start year cannot be greater than end year.")
        valid = False

    conferencia_seleccionada = None

    # Si estamos en el ranking de autores, ofrezco filtro opcional por conferencia
    if accion == "Author Ranking":
        try:
            conferencias = requests.get(f"{API_BASE}/conferencias_unicas").json()
            conferencias.insert(0, "")  
            conferencia_seleccionada = st.selectbox("Filter by conference (optional)", conferencias,format_func=lambda x: "Select an option..." if x == "" else x,key="conferencia_seleccionada")

        except Exception:
            st.error("Failed to fetch conferences from backend.")
            valid = False


    if accion == "Author Evolution":
        # Estilo SOLO para el input "Enter full author name"
        st.markdown("""
        <style>
        /* 1) Caja contenedora (mismo look que los selects) */
        div[data-baseweb="base-input"]:has(> input[aria-label="Enter full author name"]) {
            background-color:#1e293b !important;
            border:1px solid #334155 !important;
            border-radius:6px !important;
            box-shadow:none !important;
        }

        /* 2) El <input> */
        input[aria-label="Enter full author name"]{
            background-color:#1e293b !important;
            color:#ffffff !important;
            border:0 !important;           /* el borde lo lleva el wrapper */
        }
        input[aria-label="Enter full author name"]::placeholder{
            color:#9ca3af !important;
        }

        /* 3) Borde al hacer foco, como el resto de controles */
        div[data-baseweb="base-input"]:has(> input[aria-label="Enter full author name"]):focus-within{
            border-color:#475569 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.text_input("Enter full author name", key="autor_input", placeholder="Full author name")



    # --- Modal de actualización con token  ---
    @st.dialog("🔒 Admin · Data update")
    def show_update_modal():
        st.write(
            "Enter the parameters to update data. "
            "This will run scraping + import on the backend."
        )

        # Defaults: usa lo que haya en los filtros actuales si existe
        default_start = int(st.session_state.get("inicio", year_start))
        default_end = int(st.session_state.get("fin", year_end))

        ano_inicio_form = st.number_input(
            "Start Year (update)",
            value=default_start,
            min_value=min_year,
            max_value=year_actual,
            step=1,
            key="upd_start",
        )

        ano_fin_form = st.number_input(
            "End Year (update)",
            value=default_end,
            min_value=min_year,
            max_value=year_actual,
            step=1,
            key="upd_end",
        )

        token_input = st.text_input(
            "Admin token", type="password", key="upd_token"
        )

        col_ok, col_cancel = st.columns(2)

        with col_ok:
            if st.button("OK", key="upd_ok"):

                # Validaciones claras
                if not token_input:
                    st.error("Token is required.")
                    st.stop()

                if token_input != TOKEN_ACTUALIZACION:
                    st.error("Invalid token.")
                    st.stop()

                if ano_inicio_form > ano_fin_form:
                    st.error("Start year cannot be greater than end year.")
                    st.stop()

                if ano_fin_form > year_actual:
                    st.error(
                        f"End year cannot be greater than the current year ({year_actual})."
                    )
                    st.stop()

                # Llamada al backend
                try:
                    with st.spinner("Running backend update..."):
                        r = requests.post(
                            f"{API_BASE}/actualizar_datos/",
                            params={
                                "ano_inicio": int(ano_inicio_form),
                                "ano_fin": int(ano_fin_form),
                            },
                            timeout=(15, 60 * 60 * 24),  # 15s conexión, hasta 1h lectura
                            # headers={"Authorization": f"Bearer {token_input}"}
                        )
                        r.raise_for_status()
                        data = r.json()

                    st.success(data.get("mensaje", "Update completed."))

                    # Cierra modal y refresca banner/estado
                    st.session_state["open_update_modal"] = False
                    st.session_state["forzar_rerun"] = True
                    st.rerun()

                except requests.exceptions.HTTPError:
                    try:
                        st.error(f"{r.status_code}: {r.json().get('detail')}")
                    except Exception:
                        st.error(f"HTTP {r.status_code}: {r.text}")

                except requests.exceptions.RequestException as e:
                    st.error("Could not reach the backend.")
                    st.exception(e)

        with col_cancel:
            if st.button("Cancel", key="upd_cancel"):
                st.session_state["open_update_modal"] = False
                st.rerun()

        # Estilos del modal
        st.markdown(
            """
            <style>
            /* 1) El contenedor del diálogo sirve de referencia para posicionar el botón */
            div[data-testid="stDialog"] {
                position: relative !important;
            }

            /* 2) Botón cerrar: recolocado arriba derecha */
            div[data-testid="stDialog"] button[aria-label="Close"] {
                position: absolute !important;
                top: 12px;
                right: 12px;
            }

            /* Ocultar icono SVG nativo para que no se duplique */
            div[data-testid="stDialog"] button[aria-label="Close"] svg {
                display: none !important;
            }

            /* 3) Insertar la X blanca manualmente */
            div[data-testid="stDialog"] button[aria-label="Close"]::after {
                content: "✕";
                color: #fff;
                font-size: 16px;
                font-weight: bold;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
            }

            /* 4) Labels del modal */
            div[data-testid="stDialog"] label,
            div[data-testid="stDialog"] .stNumberInput label,
            div[data-testid="stDialog"] .stTextInput label {
                color: #334155 !important;
                font-weight: 600;
            }

            /* 5) Overlay translúcido */
            div[data-testid="stModalOverlay"],
            div[data-testid="stDialogOverlay"],
            div[class*="stModalOverlay"],
            div[class*="stDialogOverlay"] {
                background: rgba(0, 0, 0, 0.45) !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        components.html(
            """
            <script>
            (function () {
            const poll = setInterval(() => {
                try {
                const doc = window.parent.document;
                const dialog = doc.querySelector('div[data-testid="stDialog"]');
                if (!dialog) return;

                const closeBtn = dialog.querySelector('button[aria-label="Close"]');
                const allBtns  = dialog.querySelectorAll('button');
                let cancelBtn = null;
                allBtns.forEach(b => {
                    if (!cancelBtn && b.innerText && b.innerText.trim() === 'Cancel') {
                    cancelBtn = b;
                    }
                });

                if (closeBtn && cancelBtn) {
                    clearInterval(poll);
                    if (!closeBtn.dataset._hooked) {
                    closeBtn.dataset._hooked = "1";
                    closeBtn.addEventListener('click', () => {
                        cancelBtn.click();
                    });
                    }
                }
                } catch (err) {}
            }, 250);
            })();
            </script>
            """,
            height=0,
        )

    
    # Si el flag quedó activado por el botón superior, abre el modal ahora
    if st.session_state.get("open_update_modal"):
        show_update_modal()


    # Form principal: agrupo filtros y lanzo la búsqueda con un solo botón
    with st.form("formulario_busqueda"):
        submit = st.form_submit_button("SEARCH")
        if submit:
            if accion == "Author Evolution":
                autor = st.session_state.get("autor_input", "").strip()
                if not autor:
                    st.warning("You must enter an author name.")
                    valid = False
                else:
                    params["autor"] = autor

            if accion == "Author Ranking":
                conferencia_seleccionada = st.session_state.get("conferencia_seleccionada", "")
                if conferencia_seleccionada:
                    params["conferencia"] = conferencia_seleccionada
                else:
                    params.pop("conferencia", None)
                    st.session_state["kpi_conf_total"] = "-"

            if valid:
                st.session_state["cargando"] = True



    
    if st.session_state.get("cargando"):
        with st.spinner("🔍 Querying backend..."):
            try:
                if accion == "Author Ranking":
                    if conferencia_seleccionada:
                        endpoint = "/ranking/conferencia"
                        export_endpoint = "/exportar_csv/ranking_conferencia"
                    else:
                        endpoint = "/ranking/autores"
                        export_endpoint = "/exportar_csv/ranking_autores"

                
                elif accion == "Most Frequent Keywords":
                    endpoint = "/estadisticas/palabras_clave"
                    export_endpoint = "/exportar_csv/palabras_clave"
                    if "top_n" not in st.session_state:
                        st.session_state["top_n"] = 20
                    params["top"] = st.session_state["top_n"]
                elif accion == "Spanish Publications Statistics":
                    endpoint = "/estadisticas/publicaciones_espanolas"
                    export_endpoint = "/exportar_csv/publicaciones_espanolas"
                elif accion == "Author Evolution":
                    endpoint = "/estadisticas/evolucion_autor"
                    export_endpoint = "/exportar_csv/evolucion_autor" 
                elif accion == "Frequent Co-author Pairs":
                    endpoint = "/estadisticas/coautorias"
                    export_endpoint = "/exportar_csv/coautorias"
                    st.session_state.setdefault("top_pairs", 20)
                    st.session_state.setdefault("min_papers_pairs", 2)
                    params["top"] = st.session_state["top_pairs"]
                    params["min_papers"] = st.session_state["min_papers_pairs"]



                r = requests.get(f"{API_BASE}{endpoint}", params=params)
                r.raise_for_status()
                respuesta = r.json()

                if accion == "Most Frequent Keywords":
                    st.session_state["df_keywords"] = pd.DataFrame(respuesta["top_keywords"])
                    st.session_state["total_keywords_count"] = respuesta["total_count"]
                
                elif accion == "Spanish Publications Statistics":
                    df = pd.DataFrame(respuesta)
                    st.session_state["df_espanolas"] = df
                    st.session_state["kpi_pub_total"] = df["espanolas"].sum()
                    # Extraer autores del CSV exportado (ya contiene solo papers españoles en ese rango)
                    try:
                        df_csv = pd.read_csv(io.BytesIO(
                            requests.post(f"{API_BASE}/exportar_csv/publicaciones_espanolas", params=params).content
                        ))
                        autores = set()
                        for entrada in df_csv["author"]:
                            for autor in entrada.split(" and "):
                                autores.add(autor.strip())
                        st.session_state["kpi_autores_unicos"] = len(autores)
                        pd.DataFrame(sorted(autores), columns=["autor"]).to_csv("autores_espanolas_frontend.csv", index=False)
                    except Exception as e:
                        st.session_state["kpi_autores_unicos"] = "-"
                        st.warning("Could not extract unique authors.")
                        st.exception(e)

                    st.session_state["kpi_conf_total"] = "-"
                    st.session_state["csv_data"] = requests.post(f"{API_BASE}/exportar_csv/publicaciones_espanolas", params=params).content
                    st.session_state["csv_nombre"] = f"spanish_publications_{year_start}_{year_end}.csv"

                elif accion == "Author Evolution":
                    df = pd.DataFrame(respuesta)
                    st.session_state["df_evolucion_autor"] = df
                    autor_actual = st.session_state.get("autor_input", "").strip()

                    # Por defecto: no mostramos KPIs si no hay resultados
                    if df.empty:
                        # 1) Consulto si el autor existe en la BD (independiente del rango de años)
                        exists = None
                        try:
                            check = requests.get(f"{API_BASE}/autores/existe", params={"autor": autor_actual}, timeout=15)
                            check.raise_for_status()
                            exists = check.json().get("exists", False)
                        except Exception:
                            exists = None  # si falla la comprobación, mostramos un mensaje genérico

                        # 2) Ocultar KPIs y dejar sin CSV
                        st.session_state["ocultar_kpis"] = True
                        st.session_state["kpi_pub_total"] = "-"
                        st.session_state["kpi_autores_unicos"] = "-"
                        st.session_state["kpi_conf_total"] = "-"
                        st.session_state.pop("csv_data", None)
                        st.session_state.pop("csv_nombre", None)

                        # 3) Mensaje acorde
                        if exists is False:
                            st.error("Author not found in the database. Please try another full name.")
                        elif exists is True:
                            st.info("This author exists, but has no publications within the selected years. Try expanding the year range.")
                        else:
                            st.warning("No results found. Try a different author or adjust the year range.")

                    else:
                        # Hay resultados: mostramos KPIs y generamos CSV como hasta ahora
                        st.session_state["ocultar_kpis"] = False
                        st.session_state["kpi_conf_total"] = "-"
                        st.session_state["kpi_autores_unicos"] = 1
                        st.session_state["kpi_pub_total"] = int(df["total"].sum())

                        try:
                            params_export = {
                                "autor": autor_actual,
                                "year_start": year_start,
                                "year_end": year_end
                            }
                            csv_export = requests.post(
                                f"{API_BASE}/exportar_csv/evolucion_autor",
                                params=params_export
                            ).content

                            st.session_state["csv_data"] = csv_export
                            autor_formateado = autor_actual.replace(" ", "_").lower()
                            st.session_state["csv_nombre"] = f"evolucion_de_{autor_formateado}_{year_start}_{year_end}.csv"

                            df_csv_autor = pd.read_csv(io.BytesIO(csv_export))

                            campo_conf = None
                            for posible in ["series", "booktitle"]:
                                if posible in df_csv_autor.columns:
                                    campo_conf = posible
                                    break

                            if campo_conf:
                                conferencias_unicas = sorted(set(df_csv_autor[campo_conf].dropna().unique()))
                                st.session_state["kpi_conf_total"] = ", ".join(conferencias_unicas) if conferencias_unicas else "(no conferences)"
                            else:
                                st.session_state["kpi_conf_total"] = "(field not available)"

                        except Exception as e:
                            st.session_state["kpi_conf_total"] = "-"
                            st.warning("Failed to extract conferences from CSV.")
                            st.exception(e)


                elif accion == "Frequent Co-author Pairs":
                    df_pairs = pd.DataFrame(respuesta["pairs"])  # columnas: autor1, autor2, total
                    st.session_state["df_pairs"] = df_pairs

                    # KPIs
                    st.session_state["kpi_pub_total"] = len(set(respuesta.get("paper_ids", [])))
                    autores_involucrados = set()
                    if not df_pairs.empty:
                        autores_involucrados = set(df_pairs["autor1"]).union(set(df_pairs["autor2"]))
                    st.session_state["kpi_autores_unicos"] = len(autores_involucrados)
                    st.session_state["kpi_conf_total"] = len(df_pairs)  # nº de parejas en el top

    
                else:
                    df = pd.DataFrame(respuesta.get("autores", respuesta))
                    st.session_state["df_ranking"] = df
                    st.session_state["kpi_pub_total"] = len(set(respuesta.get("paper_ids", [])))
                    st.session_state["kpi_autores_unicos"] = len(df)


                    if accion == "Author Ranking" and conferencia_seleccionada:
                        st.session_state["kpi_conf_total"] = conferencia_seleccionada

                    elif accion == "Author Ranking" and not conferencia_seleccionada:
                        try:
                            if not conferencia_seleccionada:
                                st.session_state["csv_data"] = requests.post(f"{API_BASE}/exportar_csv/ranking_autores", params=params).content
                            
                            df_csv = pd.read_csv(io.BytesIO(st.session_state["csv_data"]))

                            if "series" in df_csv.columns:
                                def limpiar_conf(nombre):
                                    if isinstance(nombre, str):
                                        return nombre.split(" '")[0].strip()
                                    return None

                                conferencias_limpias = set()
                                for conf in df_csv["series"].dropna():
                                    base = limpiar_conf(conf)
                                    if base:
                                        conferencias_limpias.add(base)

                                st.session_state["kpi_conf_total"] = len(conferencias_limpias)
                            else:
                                st.session_state["kpi_conf_total"] = "(field 'series' not available)"


                        except Exception as e:
                            st.session_state["kpi_conf_total"] = "-"
                            st.warning("Could not extract conferences for general ranking.")
                            st.exception(e)

                # Solo aquí generamos csv_data y nombre
                if export_endpoint:
                    st.session_state["csv_data"] = requests.post(f"{API_BASE}{export_endpoint}", params=params).content
                    
                    # Solo si NO es evolución de autor, generamos el nombre por defecto,
                    if accion == "Author Ranking":
                        base_nombre = "ranking_conferencia" if conferencia_seleccionada else "ranking_autores"
                        st.session_state["csv_nombre"] = f"{base_nombre}_{year_start}_{year_end}.csv"
                    elif accion != "Author Evolution":
                        st.session_state["csv_nombre"] = f"{accion.replace(' ', '_').lower()}_{year_start}_{year_end}.csv"


                #  Calculamos KPIs desde CSV si es palabras clave
                if accion == "Most Frequent Keywords":
                    try:
                        df_csv = pd.read_csv(io.BytesIO(st.session_state["csv_data"]))
                        st.session_state["kpi_pub_total"] = df_csv["id"].nunique()

                        # Autores únicos
                        autores = set()
                        for entrada in df_csv["author"]:
                            for autor in entrada.split(" and "):
                                autores.add(autor.strip())
                        st.session_state["kpi_autores_unicos"] = len(autores)
                        pd.DataFrame(sorted(autores), columns=["autor"]).to_csv("autores_frontend.csv", index=False)

                        # Contar conferencias/editoriales si hay campos válidos
                        campo_conf = None
                        for posible in ["series", "booktitle"]:
                            if posible in df_csv.columns:
                                campo_conf = posible
                                break

                        if campo_conf:
                            conferencias_unicas = sorted(set(df_csv[campo_conf].dropna().unique()))
                            st.session_state["kpi_conf_total"] = len(conferencias_unicas)
                        else:
                            st.session_state["kpi_conf_total"] = "(field not available)"

                    except Exception as e:
                        st.session_state["kpi_pub_total"] = "-"
                        st.session_state["kpi_autores_unicos"] = "-"
                        st.session_state["kpi_conf_total"] = "-"
                        st.warning("Failed to calculate KPIs for keywords.")
                        st.exception(e)

            except Exception as e:
                st.error("Failed to retrieve data from backend.")
                for k in ["df_keywords", "df_ranking", "csv_data", "csv_nombre"]:
                    st.session_state.pop(k, None)
                st.exception(e)
            finally:
                st.session_state["cargando"] = False

    try:
        r_estado = requests.get(f"{API_BASE}/estado/ultima_actualizacion")
        estado = r_estado.json()

        if "ultima_actualizacion" not in estado:
            msg = "	Last update: - | Bibliographic data from - to -"
        else:
            msg = f"Last update: {estado['ultima_actualizacion']} | Bibliographic data from {estado['min_year']} to {estado['max_year']}"

            faltantes = estado.get("años_faltantes", [])
            if faltantes:
                lista_faltantes = ", ".join(str(a) for a in sorted(faltantes))
                msg += f" | <span style='color:#facc15;'>⚠️ Missing data for {lista_faltantes}</span>"

        st.markdown(f"""
            <div style='text-align: center; font-size: 0.95rem; margin-bottom: 15px; font-family: Montserrat, sans-serif; color: #cbd5e1;'>
                {msg}
            </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error("Failed to fetch data from backend.")
        st.exception(e)




    if not st.session_state.get("ocultar_kpis", False):
        mostrar_kpis(
            st.session_state["kpi_pub_total"],
            st.session_state["kpi_autores_unicos"],
            st.session_state["kpi_conf_total"]
        )

    # === KEYWORDS ================================================================
    df_keywords = st.session_state.get("df_keywords")
    if accion == "Most Frequent Keywords" and isinstance(df_keywords, pd.DataFrame) and not df_keywords.empty:
        col0, col1, col2 = st.columns([1, 1, 1])
        with col1:
            top_n = st.selectbox("Number of keywords", [5, 10, 20, 30], key="top_n", on_change=realizar_busqueda)

        with col2:
            tipo_grafico_keywords = st.selectbox("Chart type", ["Pie chart", "Horizontal bars"], key="grafico_keywords")

        df = df_keywords.head(top_n)
        total_keywords = st.session_state.get("total_keywords_count", df_keywords["count"].sum())
        top_keywords_sum = df["count"].sum()
        otros = total_keywords - top_keywords_sum
        df_otro = df.copy()
        if otros > 0:
            df_otro = pd.concat([df_otro, pd.DataFrame([{"keyword": "Others", "count": otros}])], ignore_index=True)

        if tipo_grafico_keywords == "Pie chart":
            col1, col2 = st.columns(2)

            with col1:
                fig1 = px.pie(df, values='count', names='keyword', hole=0)
                fig1.update_traces(textinfo="label+value", textfont=dict(color="white"))
                fig1.update_layout(
                    title="<b style='color:#38bdf8;'>Top Keywords (absolute value)</b>",
                    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                    font_color="white", title_font_size=20, title_x=0.02,
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=0.99,
                        xanchor="right",
                        x=1.3,
                        font=dict(color="white")
                    )
                )
                st.plotly_chart(fig1, use_container_width=True)

            with col2:
                # Calcular porcentajes
                df_otro["percent"] = df_otro["count"] / total_keywords * 100
                df_otro["percent"] = df_otro["percent"].map(lambda x: round(x, 2))

                # Gráfico DONUT con leyenda activa
                fig2 = px.pie(
                    df_otro,
                    values="count",
                    names="keyword",
                    hole=0.5,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )

                fig2.update_traces(
                    textinfo='none',
                    hovertemplate='%{label}<br>%{percent:.3f}<extra></extra>',
                    pull=[0.05 if k.lower() == "others" else 0 for k in df_otro["keyword"]],
                    marker=dict(line=dict(color='#0e1117', width=1))
                )

                fig2.update_layout(
                    title="<b style='color:#38bdf8;'>Distribution relative to total (with 'Others')</b>",
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=0.99,
                        xanchor="right",
                        x=1.3,
                        font=dict(color="white")
                    ),
                    plot_bgcolor="#0e1117",
                    paper_bgcolor="#0e1117",
                    font_color="white",
                    title_font_size=20,
                    title_x=0.02
                )

                st.plotly_chart(fig2, use_container_width=True)

            # Tabla HTML con estilo oscuro y porcentajes
            df_tabla = df_otro[["keyword", "percent"]].sort_values("percent", ascending=False).reset_index(drop=True)
            df_tabla.columns = ["Keyword", "% of total"]

            tabla_html = df_tabla.to_html(
                index=False,
                classes="styled-table",
                justify="left"
            )

            # Estilo personalizado de tabla HTML
            st.markdown("""
            <style>
            .styled-table {
                width: 100%;
                border-collapse: collapse;
                font-family: 'Montserrat', sans-serif;
                font-size: 0.9rem;
                background-color: #0e1117;
                color: white;
            }
            .styled-table th {
                background-color: #1f2937;
                color: #60a5fa;
                text-align: left;
                padding: 8px;
            }
            .styled-table td {
                background-color: #0e1117;
                color: white;
                padding: 8px;
            }
            .styled-table tr:nth-child(even) td {
                background-color: #1a1d24;
            }
            </style>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style='text-align: center; margin-top: 40px;'>
                <h3 style='color:#60a5fa; font-family:Montserrat, sans-serif;'>Distribution table:</h3>
            </div>
            <div style='display: flex; justify-content: center;'>
                <div style='width: 70%;'>
                    """ + tabla_html + """
                </div>
            </div>
            """, unsafe_allow_html=True)
        


        elif tipo_grafico_keywords == "Horizontal bars":
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            fig = px.bar(df.sort_values("count"), x="count", y="keyword", orientation="h")
            fig.update_traces(textfont=dict(color="white"))
            fig.update_layout(
                title="<b style='color:#38bdf8;'>Top Keywords (absolute value)</b>",
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                font_color="white", title_font_size=20, title_x=0.02,
                margin=dict(l=120, r=40, t=60, b=60)
            )
            st.plotly_chart(fig, use_container_width=True)

        st.download_button("Download CSV", data=st.session_state["csv_data"], file_name=st.session_state["csv_nombre"], mime="text/csv")

    # === RANKINGS ================================================================
    df_ranking = st.session_state.get("df_ranking")
    if accion in  "Author Ranking" and isinstance(df_ranking, pd.DataFrame) and not df_ranking.empty:
        st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([3, 1, 1])
        with col3:
            tipo_grafico = st.selectbox("Chart type", ["Horizontal bars", "Vertical Bars"], key="tipo_grafico")

        df = df_ranking
        df_sorted = df.sort_values("total", ascending=True if tipo_grafico == "Horizontal bars" else False)
        df_sorted["full_name"] = df_sorted["full_name"].apply(lambda x: f"<span style='color:#38bdf8;font-weight:bold'>{x}</span>")

        if tipo_grafico == "Horizontal bars":
            fig = px.bar(df_sorted, x="total", y="full_name", orientation="h", text="total",
                         labels={"total": "Publications", "full_name": "Autor"},
                         title="<b style='color:#38bdf8;'>Top Authors by Publications</b>")
            fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=150, r=30, t=60, b=150))
        else:
            fig = px.bar(df_sorted, x="full_name", y="total", orientation="v", text="total",
                         labels={"total": "Publications", "full_name": "Autor"},
                         title="<b style='color:#38bdf8;'>Top Authors by Publications</b>")
            fig.update_layout(xaxis_tickangle=-30, margin=dict(l=60, r=30, t=60, b=60))

        fig.update_traces(textfont=dict(color="white"))
        fig.update_layout(
            plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white", title_font_size=22, title_x=0.02
        )
        st.plotly_chart(fig, use_container_width=True)
        st.download_button("Download CSV", data=st.session_state["csv_data"], file_name=st.session_state["csv_nombre"], mime="text/csv")


    # === OBRAS ESPAÑOLAS VS TOTALES ================================================================
    df_espanolas = st.session_state.get("df_espanolas")
    if accion == "Spanish Publications Statistics" and isinstance(df_espanolas, pd.DataFrame) and not df_espanolas.empty:
        st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col2:
            tipo_grafico_espanolas = st.selectbox(
                "Chart type",
                ["Dual Lines", "Grouped Bars", "Stacked Areas", "Donut per Year", "Bubbles"],
                key="tipo_grafico_espanolas"
            )

        df = df_espanolas.sort_values("year")
        if tipo_grafico_espanolas == "Dual Lines":
            df_tmp = df.copy()
            df_tmp["total_t"] = transformar_serie(df_tmp["total"], corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)
            df_tmp["espanolas_t"] = transformar_serie(df_tmp["espanolas"], corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)

            fig = px.line(
                df_tmp, x="year", y=["total_t", "espanolas_t"], markers=True,
                labels={"value": "Papers", "variable": ""}
            )

            tickvals, ticktext, ymax = generar_ticks(df["total"].max(), corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)
            fig.update_yaxes(tickvals=tickvals, ticktext=ticktext, range=[0, ymax])

            # Hovers con valores reales
            fig.data[0].name = "Total"
            fig.data[1].name = "Españolas"
            fig.data[0].customdata = df["total"]
            fig.data[1].customdata = df["espanolas"]
            for tr in fig.data:
                tr.update(hovertemplate="%{x} — %{customdata} papers")

            fig.update_layout(
                title_text="Total vs Españolas - Dual Line",
                title_font=dict(color="white", size=20),
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                legend=dict(font=dict(color="white"), title=dict(text="", font=dict(color="white")))
            )

        elif tipo_grafico_espanolas == "Grouped Bars":
            import plotly.graph_objects as go

            df_tmp = df.copy()
            df_tmp["total_t"] = transformar_serie(df_tmp["total"], corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)
            df_tmp["espanolas_t"] = transformar_serie(df_tmp["espanolas"], corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)

            tickvals, ticktext, ymax = generar_ticks(df["total"].max(), corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)

            fig = go.Figure()
            fig.add_bar(
                x=df_tmp["year"], y=df_tmp["total_t"], name="Total",
                customdata=df_tmp["total"], hovertemplate="%{x} — %{customdata} papers"
            )
            fig.add_bar(
                x=df_tmp["year"], y=df_tmp["espanolas_t"], name="Españolas",
                customdata=df_tmp["espanolas"], hovertemplate="%{x} — %{customdata} papers"
            )

            fig.update_layout(
                barmode="group",
                title="Total vs Españolas - Grouped Bars",
                title_font=dict(color="white", size=20),
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                legend=dict(font=dict(color="white"), title=dict(text="", font=dict(color="white")))
            )
            fig.update_yaxes(
                tickvals=tickvals, ticktext=ticktext, range=[0, ymax],
                gridcolor="#2b2f3a"
            )

        elif tipo_grafico_espanolas == "Stacked Areas":
            df_tmp = df.copy()
            df_tmp["otras"] = df_tmp["total"] - df_tmp["espanolas"]

            # Transformar ambas series
            df_tmp["espanolas_t"] = transformar_serie(df_tmp["espanolas"], corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)
            df_tmp["otras_t"]     = transformar_serie(df_tmp["otras"], corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)

            tickvals, ticktext, ymax = generar_ticks(df["total"].max(), corte=CORTE_ESCALA, factor_bajo=FACTOR_BAJO)

            # IMPORTANTE: primero 'espanolas_t', luego 'otras_t' (para que se apile correctamente)
            fig = px.area(
                df_tmp, x="year", y=["espanolas_t", "otras_t"],
                labels={"value": "Papers", "variable": ""},
                title="Españolas dentro del Total - Stacked Areas",
                color_discrete_map={
                    "espanolas_t": "#3b82f6",  # azul claro (Españolas)
                    "otras_t": "#1f2937"       # oscuro (Otras)
                }
            )

            # Renombrar leyendas
            fig.data[0].name = "Españolas"
            fig.data[1].name = "Otras"

            # Hovers con valores reales
            fig.data[0].customdata = df["espanolas"]
            fig.data[1].customdata = df_tmp["otras"]
            for tr in fig.data:
                tr.update(hovertemplate="%{x} — %{customdata} papers")

            # Eje Y personalizado
            fig.update_yaxes(
                tickvals=tickvals, ticktext=ticktext, range=[0, ymax],
                gridcolor="#2b2f3a"
            )
            fig.update_layout(
                title_font=dict(color="white", size=20),
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                legend=dict(font=dict(color="white"), title=dict(text="", font=dict(color="white")))
            )


        elif tipo_grafico_espanolas == "Donut per Year":
            total = len(df)
            for idx, row in enumerate(df.itertuples()):
                values = [row.espanolas, row.total - row.espanolas]
                labels = ["Spanish", "Others"]
                year = row.year

                fig = px.pie(values=values, names=labels, hole=0.5)
                fig.update_layout(
                    plot_bgcolor="#0e1117",
                    paper_bgcolor="#0e1117",
                    font_color="white",
                    showlegend=True,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=-0.1,
                        xanchor="center",
                        x=0.5,
                        font=dict(color="white")
                    )
                )
                fig.update_traces(
                    hovertemplate='%{label}<br>Value=%{value}<br>Percentage=%{percent}',
                    textinfo='percent'
                )

                if total % 2 == 1 and idx == total - 1:
                    st.markdown(f"<h4 style='text-align: center; color: white; margin-top: 40px;'>Year {year}</h4>", unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=False, width=500)

                else:
                    if idx % 2 == 0:
                        col1, col2 = st.columns(2)
                    col_actual = col1 if idx % 2 == 0 else col2
                    with col_actual:
                        st.markdown(f"<h4 style='color: white; margin-top: 30px;'>Year {year}</h4>", unsafe_allow_html=True)
                        st.plotly_chart(fig, use_container_width=True)


        elif tipo_grafico_espanolas == "Bubbles":
            df["porcentaje"] = df["espanolas"] / df["total"] * 100
            fig = px.scatter(df, x="year", y="porcentaje", size="total", color="porcentaje",
                            title="Percentage of Spanish Publications", size_max=60)
            fig.update_layout(
                title_font=dict(color="white", size=20), 
                plot_bgcolor="#0e1117", 
                paper_bgcolor="#0e1117", 
                font_color="white",   
            )

        if tipo_grafico_espanolas != "Donut per Year":
            st.plotly_chart(fig, use_container_width=True)

        st.download_button("Download CSV", data=st.session_state["csv_data"], file_name=st.session_state["csv_nombre"], mime="text/csv")

    df_evolucion_autor = st.session_state.get("df_evolucion_autor")
    if accion == "Author Evolution" and isinstance(df_evolucion_autor, pd.DataFrame) and not df_evolucion_autor.empty:
        st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col2:
            tipo_evolucion = st.selectbox("Visualization Type", ["Year", "Total"], key="tipo_evolucion_autor")

        primer_anio = df_evolucion_autor["year"].min()
        ultimo_anio = year_end

        todos_los_anios = pd.DataFrame({"year": list(range(primer_anio, ultimo_anio + 1))})
        df = todos_los_anios.merge(df_evolucion_autor, on="year", how="left").fillna(0)
        df["total"] = df["total"].astype(int)

        if tipo_evolucion == "Year":
            fig = px.line(df, x="year", y="total", markers=True)
            titulo = f"Yearly Evolution of {st.session_state.get('autor_input', '')}"

        else:
            df["acumulado"] = df["total"].cumsum()
            fig = px.line(df, x="year", y="acumulado", markers=True)
            titulo = f"Cumulative Publications of {st.session_state.get('autor_input', '')}"

        try:
            autor_actual = st.session_state.get("autor_input", "").strip()
            params_export = {
                "autor": autor_actual,
                "year_start": year_start,
                "year_end": year_end
            }
            csv_export = requests.post(f"{API_BASE}/exportar_csv/evolucion_autor", params=params_export).content
            st.session_state["csv_data"] = csv_export
            autor_formateado = st.session_state.get("autor_input", "").replace(" ", "_").lower()
            st.session_state["csv_nombre"] = f"evolucion_de_{autor_formateado}_{year_start}_{year_end}.csv"

            try:
                df_csv_autor = pd.read_csv(io.BytesIO(csv_export))

                campo_conf = None
                for posible in ["series", "booktitle"]:
                    if posible in df_csv_autor.columns:
                        campo_conf = posible
                        break

                if campo_conf:
                    conferencias_unicas = sorted(set(df_csv_autor[campo_conf].dropna().unique()))
                    st.session_state["kpi_conf_total"] = ", ".join(conferencias_unicas) if conferencias_unicas else "(no conferences)"
                else:
                    st.session_state["kpi_conf_total"] = "(field not available)"
            except Exception as e:
                st.session_state["kpi_conf_total"] = "-"
                st.warning("Failed to extract conferences from author CSV.")
                st.exception(e)
            

        except Exception as e:
            st.warning("Could not fetch author's publication CSV.")
            st.exception(e)

        fig.update_layout(
            title=f"<b style='color:#38bdf8;'>{titulo}</b>",
            plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white"
        )

        st.plotly_chart(fig, use_container_width=True)
        st.download_button("Download CSV", data=st.session_state["csv_data"], file_name=st.session_state["csv_nombre"], mime="text/csv")

    # === COAUTORÍA ================================================================
    df_pairs = st.session_state.get("df_pairs")
    if accion == "Frequent Co-author Pairs" and isinstance(df_pairs, pd.DataFrame) and not df_pairs.empty:
        st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

        # 3 columnas: 1) vacía  2) top (A)  3) tipo gráfico (B)
        col_vacia, col_a, col_b = st.columns(3)

        with col_a:
            # Desplegable para "Max. top pairs" (5..35). Cambiar relanza la búsqueda.
            opciones_top = list(range(5, 36))
            st.session_state.setdefault("top_pairs", 20)
            st.selectbox(
                "Max. top pairs",
                options=opciones_top,
                key="top_pairs",
                on_change=realizar_busqueda
            )

        with col_b:
            # Tipos de gráfica
            if "grafico_pairs" not in st.session_state:
                st.session_state["grafico_pairs"] = "Horizontal bars"
            st.selectbox(
                "Chart type",
                ["Horizontal bars", "Lollipop", "Dot plot"],
                key="grafico_pairs"
            )

        # --- Preparación datos base ---
        df_viz = df_pairs.copy()
        # Aseguramos tipos
        df_viz["total"] = pd.to_numeric(df_viz["total"], errors="coerce").fillna(0).astype(int)
        df_viz = df_viz.sort_values("total")

        # Texto de par solo para ejes/etiquetas en algunas gráficas
        df_viz["pair"] = df_viz.apply(lambda r: f"{r['autor1']} — {r['autor2']}", axis=1)

        # --- Render según tipo de gráfico ---
        tipo = st.session_state["grafico_pairs"]

        try:
            if tipo == "Horizontal bars":
                fig = px.bar(
                    df_viz, x="total", y="pair", orientation="h", text="total",
                    labels={"total": "Joint papers", "pair": "Co-author pair"},
                    title="<b style='color:#38bdf8;'>Top Co-author Pairs</b>"
                )
                fig.update_layout(
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                    title_font_size=22, title_x=0.02, margin=dict(l=180, r=30, t=60, b=60)
                )
                fig.update_traces(textfont=dict(color="white"))
                st.plotly_chart(fig, use_container_width=True)

            elif tipo == "Lollipop":
                # Lollipop = línea 0→total + marcador en el extremo
                y_vals = df_viz["pair"].tolist()
                x_vals = df_viz["total"].tolist()

                fig = go.Figure()
                # líneas
                fig.add_trace(go.Scatter(
                    x=sum(([0, x] for x in x_vals), []),
                    y=sum(([y, y] for y in y_vals), []),
                    mode="lines",
                    line=dict(width=2),
                    showlegend=False,
                    hoverinfo="skip"
                ))
                # puntos
                fig.add_trace(go.Scatter(
                    x=x_vals, y=y_vals, mode="markers+text", text=x_vals, textposition="middle right",
                    marker=dict(size=10),
                    showlegend=False
                ))
                fig.update_layout(
                    title="<b style='color:#38bdf8;'>Top Co-author Pairs — Lollipop</b>",
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                    margin=dict(l=180, r=30, t=60, b=60)
                )
                st.plotly_chart(fig, use_container_width=True)

            elif tipo == "Dot plot":
                fig = px.scatter(
                    df_viz, x="total", y="pair", size="total", size_max=18,
                    labels={"total": "Joint papers", "pair": "Co-author pair"},
                    title="<b style='color:#38bdf8;'>Top Co-author Pairs — Dot plot</b>"
                )
                fig.update_layout(
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117", font_color="white",
                    margin=dict(l=180, r=30, t=60, b=60)
                )
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.warning("We couldn't render this chart due to an error below:")
            st.exception(e)

        # Descarga CSV (igual que tienes)
        st.download_button(
            "Download CSV",
            data=st.session_state["csv_data"],
            file_name=st.session_state["csv_nombre"],
            mime="text/csv"
        )



if st.session_state.pop("forzar_rerun", False):
    st.rerun()
