# pages/00_User_Manual.py
import streamlit as st

# ---- Config ----
st.set_page_config(
    page_title="User Manual — Bibliometric Explorer",
    layout="wide",
)

# ---- Estilos  ----
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');

html, body, .main, .block-container, header, .stApp {
    background-color: #0e1117 !important;
    color: white !important;
    font-family: 'Montserrat', sans-serif;
}

/* Tipografías y colores */
h1, h2, h3, h4, h5, h6 { color: #f8fafc !important; }
p, li, label, .stMarkdown { color: #e2e8f0 !important; }

/* Tabs en modo oscuro */
div[data-baseweb="tab-list"] { border-bottom: 1px solid #263242 !important; }
div[data-baseweb="tab"] { color: #cbd5e1 !important; }
div[data-baseweb="tab"][aria-selected="true"] {
    color: #60a5fa !important;
    border-color: #60a5fa !important;
}

/* Expanders */
.streamlit-expanderHeader p { color:#e2e8f0 !important; }
details > summary { color:#e2e8f0 !important; }

/* Enlaces */
a, a:visited { color:#60a5fa !important; text-decoration: none; }
a:hover { text-decoration: underline; }

/* Separadores y contenedor */
.block-container { padding-top: 2.0rem; }
hr { border: none; border-top: 1px solid #263242; margin: 1.2rem 0; }

/* Chips/etiquetas usadas en el texto */
.tag {
  background:#0b1220;
  border:1px solid #243244;
  border-radius:6px;
  padding:2px 6px;
  margin-right:6px;
  color:#93c5fd;
  white-space: nowrap;
}
.note { color:#cbd5e1; }
.ok { color:#34d399; }
.warn { color:#fbbf24; }
.bad { color:#f87171; }
.kbd {
  background:#0b1220;
  border:1px solid #243244;
  border-radius:4px;
  padding:0 6px;
}
</style>
""", unsafe_allow_html=True)

# ---- Título ----
st.title("User Manual")
st.caption("How to use the Bibliometric Explorer")

# ---- Enlace de vuelta ----
col_left, col_sp, col_right = st.columns([1, 8, 3])
with col_left:
    try:
        st.page_link("app.py", label="Back to Explorer")
    except Exception:
        if hasattr(st, "switch_page"):
            if st.button("Back to Explorer"):
                st.switch_page("app.py")
        else:
            st.markdown("[Back to Explorer](/)", unsafe_allow_html=True)

with col_right:
    st.caption("v1.0 — Manual for the current UI")

st.markdown("---")

# ---- Índice en pestañas ----
tab_overview, tab_filters, tab_actions, tab_charts, tab_csv, tab_kpis, tab_faq = st.tabs(
    ["Overview", "Global Filters", "Actions", "Charts & Controls", "CSV Export", "KPIs", "FAQ & Troubleshooting"]
)

# ========== OVERVIEW ==========
with tab_overview:
    st.subheader("What is this?")
    st.write(
        "This dashboard lets you explore bibliographic data (authors, keywords, "
        "Spanish publications, author evolution, and co-author pairs) using a clean set of filters "
        "and interactive charts."
    )
    st.markdown(
        """
        **Workflow**  
        1. Set the time window with **Start Year** and **End year**.  
        2. Choose an **Action** (type of analysis).  
        3. Click **SEARCH**.  
        4. Use any **post-search controls** (e.g., Top N, chart type).  
        5. Download results as **CSV** if needed.
        """
    )
    st.info("Tip: Narrow the year range to speed up queries and focus your analysis.")

# ========== FILTERS ==========
with tab_filters:
    st.subheader("Global Filters (top of the page)")
    st.markdown(
        """
        - **Start Year / End year**: limits the time window for all analyses.  
          - End year cannot exceed the current year.  
          - Start Year must be ≤ End year.
        - **Action**: selects the analysis to run.
        - **SEARCH**: executes the query with the selected filters.
        """
    )
    st.markdown(
        """
        **Contextual input fields**  
        - *Author Evolution*: you must type the **full author name** before pressing **SEARCH**.  
        - *Author Ranking*: optional **conference** filter (dropdown) before **SEARCH**.
        """
    )

# ========== ACTIONS ==========
with tab_actions:
    st.subheader("Available Actions")

    with st.expander("Author Ranking", expanded=True):
        st.markdown(
            """
            Lists top authors by number of publications within the selected year range.  
            - Optional **conference** filter.  
            - **Outputs**: table + bar charts (horizontal/vertical) + CSV.
            """
        )

    with st.expander("Most Frequent Keywords", expanded=True):
        st.markdown(
            """
            Shows the most common keywords and their distribution.  
            - **Post-search controls**:  
              <span class="tag">Number of keywords (Top N)</span>
              <span class="tag">Chart type (Pie / Horizontal bars)</span>  
            - **Outputs**: pie & bar charts + CSV.  
            - The dashboard also shows percentage distribution (including *Others*).
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Spanish Publications Statistics", expanded=True):
        st.markdown(
            """
            Year-by-year totals vs. Spanish publications.  
            - **Chart types**: Dual Lines, Grouped Bars, Stacked Areas, Donut per Year, Bubbles.  
            - **Outputs**: interactive charts + CSV.
            """
        )

    with st.expander("Author Evolution", expanded=True):
        st.markdown(
            """
            Enter a **full author name** and press **SEARCH** to see their yearly output.  
            - **Views**: Yearly totals and Cumulative totals.  
            - **Outputs**: line charts + CSV.  
            - The KPI *Conferences/Publishers* lists conference/booktitle names found in the author's CSV.
            """
        )

    with st.expander("Frequent Co-author Pairs", expanded=True):
        st.markdown(
            """
            Finds the **most frequent** co-author pairs in the selected period.  
            - **Post-search controls**:  
              <span class="tag">Max. top pairs (5–35)</span>
              <span class="tag">Chart type (Horizontal bars / Lollipop / Dot plot)</span>  
            - **Outputs**: interactive chart + CSV.
            """,
            unsafe_allow_html=True,
        )

# ========== CHARTS ==========
with tab_charts:
    st.subheader("Charts and Post-search Controls")
    st.markdown(
        """
        - Hover any point/bar to see exact values.  
        - Legends let you show/hide series where applicable.  
        - Bars and dots usually display the value as a label for quick reading.
        """
    )
    st.markdown(
        """
        **Special chart types**  
        - **Lollipop** (Co-author Pairs): a line from 0 to the value with a dot at the end.  
        - **Donut per Year** (Spanish stats): a pie-with-hole for each year.  
        - **Bubbles**: circle size encodes totals; position encodes percentage over time.
        """
    )

# ========== CSV ==========
with tab_csv:
    st.subheader("CSV Export")
    st.markdown(
        """
        After each query, a **Download CSV** button appears under the charts.  
        **Naming convention**:
        - `ranking_autores_<start>_<end>.csv` (or `ranking_conferencia_...` if filtered)
        - `most_frequent_keywords_<start>_<end>.csv`
        - `spanish_publications_<start>_<end>.csv`
        - `evolucion_de_<author>_<start>_<end>.csv`
        - `frequent_coauthor_pairs_<start>_<end>.csv`
        """
    )
    st.markdown(
        """
        **Columns vary** by action (e.g., IDs, author list, conference/booktitle, counts).  
        Use the CSV to reproduce calculations, pivot additional views, or join with external datasets.
        """
    )

# ========== KPIs ==========
with tab_kpis:
    st.subheader("KPIs")
    st.markdown(
        """
        - **Publications**: number of unique papers in the current result.  
        - **Unique Authors**: unique authors appearing in the result (or `1` for single-author evolution).  
        - **Conferences / Publishers**: count of distinct venues (or comma-separated names for Author Evolution).
        """
    )
    st.markdown(
        """
        **Banner “Last update …”**  
        Shows data coverage in the database plus any missing years detected by the backend.
        """
    )

# ========== FAQ ==========
with tab_faq:
    st.subheader("FAQ and Troubleshooting")
    st.markdown(
        """
        **Nothing appears after clicking SEARCH**  
        - Check that **Start Year ≤ End year** and **End year ≤ current year**.  
        - If the banner shows missing data for certain years, adjust the range.

        **404 / backend error**  
        - Ensure the backend API is running and reachable from the machine where Streamlit runs.  
        - Verify the IP/port configured in the frontend (`API_BASE`).

        **Author Evolution returns empty**  
        - Make sure the **full name** matches the database exactly (case and spacing).  
        - Try a wider year range.

        **Manual link does nothing**  
        - This page includes fallbacks, but if your Streamlit version is very old, update it.

        **Performance tips**  
        - Reduce the year span and raise Top N only when needed.  
        - Use CSV to iterate offline-heavy analysis.
        """
    )

st.markdown("---")
st.caption("© Bibliometric Explorer")
