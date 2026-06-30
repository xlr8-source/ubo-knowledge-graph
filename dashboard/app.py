# ============================================================
# dashboard/app.py – Corporate Ownership Intelligence Platform
# ============================================================
import sys
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components
from neo4j import GraphDatabase, exceptions as neo4j_exc
from pyvis.network import Network

# Add parent directory to system path for loading config.py
sys.path.append(str(Path(__file__).resolve().parent.parent))

import config
from theme import (
    THEME_CSS,
    SVG_ICONS,
    render_icon_title,
    render_composition_html,
    render_intel_badge_html,
    render_status_line,
)
from scoring_engine import (
    calculate_influence_score,
    calculate_control_score,
    calculate_investigation_priority,
    get_risk_tier
)
from network_analytics import NetworkAnalyticsEngine
from risk_engine import RiskIntelligenceEngine
from workspace_manager import WorkspaceManager

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Must be the very first Streamlit call. Its absence was the real cause
# of the title sitting low on the page: with no layout set, Streamlit
# runs in "centered" mode, which caps content width AND reserves a large
# default top margin meant to clear the stock header — on top of which
# our own .block-container padding was then stacking. Wide mode removes
# both problems at the source instead of patching around them with CSS.
st.set_page_config(
    page_title="VEIL · Ownership Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom global CSS and Google Fonts
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner="Verifying Secure Node Connection...")
def get_driver():
    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
        )
        driver.verify_connectivity()
        return driver
    except neo4j_exc.AuthError:
        st.error("Authentication Error. Verify NEO4J_USERNAME & NEO4J_PASSWORD values in .env")
        st.stop()
    except Exception as exc:
        st.error(f"Cannot resolve node database: {exc}")
        st.stop()

driver = get_driver()

# Session State Persistence
if "workspace" not in st.session_state:
    st.session_state["workspace"] = WorkspaceManager()

if "analytics_engine" not in st.session_state:
    with st.spinner("Syncing graph database and computing analytics..."):
        analytics = NetworkAnalyticsEngine(driver)
        analytics.sync_graph()
        analytics.run_analytics()
        st.session_state["analytics_engine"] = analytics

risk_engine = RiskIntelligenceEngine(driver)
workspace = st.session_state["workspace"]
analytics_engine = st.session_state["analytics_engine"]

# NOTE: literal hex below must stay in sync with theme.py's :root CSS vars.
# Altair (Vega-Lite) and pyvis (vis.js) render in isolated contexts that
# cannot resolve CSS custom properties, so these constants are the single
# source of truth for chart/graph color — everything else in the app reads
# color from var(--token) directly in theme.py.
RISK_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
RISK_COLORS = {
    "CRITICAL": "#ff5a5f",
    "HIGH": "#ffb648",
    "MEDIUM": "#b48cf0",
    "LOW": "#4fd67a",
}
# Reserved separately from RISK_COLORS so generic categorical charts never
# borrow risk-red/amber and accidentally imply a severity that isn't there.
CHART_COLORS = ["#2bd4b8", "#b48cf0", "#ffb648", "#4fc3f7", "#4fd67a", "#e8eae2"]
TYPE_COLORS = {"Company": "#2bd4b8", "Officer": "#b48cf0", "PSC": "#ffb648"}
TYPE_BORDER_COLORS = {"Company": "#16877a", "Officer": "#7c5cc4", "PSC": "#c98a1f"}
COMMUNITY_PALETTE = [
    "#2bd4b8", "#ffb648", "#ff5a5f", "#b48cf0",
    "#4fc3f7", "#4fd67a", "#f06292", "#ffd54f",
    "#7986cb", "#4db6ac", "#ff8a65", "#aed581",
]
GRAPH_BG = "#0d0f0c"
GRAPH_FONT = "#d8dbd2"
GRAPH_EDGE_MUTED = "#5a5f54"
CROSS_LINK_COLOR = "#4fc3f7"


@st.cache_data(ttl=300, show_spinner=False)
def get_high_risk_entities_cached() -> list[dict]:
    return RiskIntelligenceEngine(get_driver()).get_high_risk_entities()


@st.cache_data(ttl=180, show_spinner=False)
def get_company_names_cached() -> list[str]:
    rows = run_query("MATCH (c:Company) RETURN c.name AS name ORDER BY name LIMIT 1000")
    return [row["name"] for row in rows if row.get("name")]


@st.cache_data(ttl=180, show_spinner=False)
def get_people_names_cached() -> list[str]:
    officers = run_query("MATCH (o:Officer) RETURN o.name AS name LIMIT 1000")
    pscs = run_query("MATCH (p:PSC) RETURN p.name AS name LIMIT 1000")
    return sorted({row["name"] for row in officers + pscs if row.get("name")})


@st.cache_data(ttl=300, show_spinner=False)
def get_graph_stats_cached() -> dict:
    stats = run_query("""
        MATCH (c:Company) WITH count(c) AS companies
        MATCH (o:Officer) WITH companies, count(o) AS officers
        MATCH (p:PSC) WITH companies, officers, count(p) AS pscs
        MATCH ()-[r]->() WITH companies, officers, pscs, count(r) AS rels
        RETURN companies, officers, pscs, rels
    """)
    return stats[0] if stats else {"companies": 0, "officers": 0, "pscs": 0, "rels": 0}


@st.cache_data(ttl=300, show_spinner=False)
def get_company_segment_stats_cached() -> dict:
    """
    Company-only aggregates for the Entity Explorer landing panel — answers
    'what does the company population look like' before a single company
    has been picked, instead of opening on a blank search box.
    """
    status_rows = run_query(
        "MATCH (c:Company) RETURN coalesce(c.status, 'unknown') AS status, count(c) AS count "
        "ORDER BY count DESC"
    )
    type_rows = run_query(
        "MATCH (c:Company) RETURN coalesce(c.company_type, 'unknown') AS company_type, count(c) AS count "
        "ORDER BY count DESC LIMIT 6"
    )
    sic_rows = run_query(
        "MATCH (c:Company) WHERE size(c.sic_codes) > 0 UNWIND c.sic_codes AS sic "
        "RETURN sic, count(*) AS count ORDER BY count DESC LIMIT 6"
    )
    coverage = run_query("""
        MATCH (c:Company)
        OPTIONAL MATCH (c)-[:HAS_OFFICER]->(o:Officer)
        WITH c, count(o) AS officer_count
        OPTIONAL MATCH (c)-[:HAS_PSC]->(p:PSC)
        WITH c, officer_count, count(p) AS psc_count
        RETURN
            count(c) AS total,
            avg(officer_count) AS avg_officers,
            sum(CASE WHEN officer_count = 0 THEN 1 ELSE 0 END) AS no_officer_companies,
            sum(CASE WHEN psc_count = 0 THEN 1 ELSE 0 END) AS no_psc_companies
    """)
    cov = coverage[0] if coverage else {}
    return {
        "status": status_rows,
        "type": type_rows,
        "sic": sic_rows,
        "total": cov.get("total", 0) or 0,
        "avg_officers": cov.get("avg_officers", 0.0) or 0.0,
        "no_officer_companies": cov.get("no_officer_companies", 0) or 0,
        "no_psc_companies": cov.get("no_psc_companies", 0) or 0,
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_people_segment_stats_cached() -> dict:
    """
    Person-only aggregates for the People Intelligence landing panel —
    surfaces officer-role mix, PSC control-kind mix, and multi-company
    officers (the same nominee/control-concentration signal the risk
    engine flags at 5+ companies) before any single name is searched.
    """
    role_rows = run_query(
        "MATCH (:Company)-[:HAS_OFFICER]->(o:Officer) "
        "RETURN coalesce(o.role, 'unknown') AS role, count(*) AS count "
        "ORDER BY count DESC LIMIT 6"
    )
    kind_rows = run_query(
        "MATCH (:Company)-[:HAS_PSC]->(p:PSC) "
        "RETURN coalesce(p.kind, 'unknown') AS kind, count(*) AS count "
        "ORDER BY count DESC LIMIT 6"
    )
    multi_officers = run_query("""
        MATCH (c:Company)-[:HAS_OFFICER]->(o:Officer)
        WITH o.name AS name, count(DISTINCT c) AS company_count
        WHERE company_count >= 2
        RETURN name, company_count
        ORDER BY company_count DESC LIMIT 10
    """)
    multi_pscs = run_query("""
        MATCH (c:Company)-[:HAS_PSC]->(p:PSC)
        WITH p.name AS name, count(DISTINCT c) AS company_count
        WHERE company_count >= 2
        RETURN name, company_count
        ORDER BY company_count DESC LIMIT 10
    """)
    return {
        "role": role_rows,
        "kind": kind_rows,
        "multi_officers": multi_officers,
        "multi_pscs": multi_pscs,
    }


def render_workbench_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="workbench-hero">
            <div class="workbench-kicker">{kicker}</div>
            <div class="workbench-title">{title}</div>
            <div class="workbench-subtitle">{subtitle}</div>
            <div class="workbench-meta">SESSION {datetime.now():%Y-%m-%d %H:%M} · AURA CLUSTER LIVE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_label(text: str) -> None:
    st.markdown(f"<div class='section-label'>{text}</div>", unsafe_allow_html=True)


def style_chart(chart, height: int = 220):
    return (
        chart.properties(height=height)
        .configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#9aa093",
            titleColor="#868c7e",
            labelFont="IBM Plex Mono",
            titleFont="IBM Plex Mono",
            gridColor="rgba(232,234,226,0.07)",
            domainColor="#3d4134",
            tickColor="#3d4134",
        )
        .configure_legend(
            labelColor="#e8eae2",
            titleColor="#868c7e",
            labelFont="IBM Plex Mono",
            titleFont="IBM Plex Mono",
        )
    )


def risk_tier_frame(high_risks: list[dict]) -> pd.DataFrame:
    counts = {tier: 0 for tier in RISK_ORDER}
    for entity in high_risks:
        tier = entity.get("risk_tier", "LOW")
        counts[tier] = counts.get(tier, 0) + 1
    return pd.DataFrame(
        [{"Tier": tier, "Count": counts.get(tier, 0), "Color": RISK_COLORS[tier]} for tier in RISK_ORDER]
    )


def flag_frequency_frame(high_risks: list[dict], limit: int = 8) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for entity in high_risks:
        for flag in entity.get("flags", []):
            title = flag.get("title", "Unknown flag")
            counts[title] = counts.get(title, 0) + 1
    rows = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    return pd.DataFrame([{"Flag": title, "Count": count} for title, count in rows])


@st.cache_data(ttl=300, show_spinner=False)
def relationship_mix_frame() -> pd.DataFrame:
    rows = run_query("MATCH ()-[r]->() RETURN type(r) AS relationship, count(r) AS count ORDER BY count DESC")
    return pd.DataFrame(rows)


def render_empty_panel(message: str) -> None:
    st.info(message)


def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    try:
        with driver.session() as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]
    except Exception as exc:
        st.error(f"Database Query Error: {exc}")
        return []

def fmt_number(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def harden_graph_html(html: str, bg_hex: str = GRAPH_BG) -> str:
    """
    Post-process raw pyvis/vis.js output before it goes into components.html().

    Every embedded topology graph in this app was opening "zoomed into a
    void" — vis.js computes its initial camera position from the iframe's
    layout at construction time, before Streamlit's iframe has finished
    sizing itself and before physics has settled, so the first paint can
    land anywhere. Fix: hide the canvas, force `network.fit()` once
    stabilization actually finishes (with a hard timeout fallback in case
    that event never fires), then reveal — the camera is always centered
    on the graph before the user sees it. Also swaps pyvis's default
    light-grey container border for the workbench's own dark border, since
    that iframe has its own isolated DOM and can't see theme.py's CSS.
    """
    html = html.replace(
        "border: 1px solid lightgray;",
        f"border: 1px solid #2a2d24; border-radius: 6px; background-color: {bg_hex};",
    )
    fit_script = """
    <style>#mynetwork { opacity: 0; transition: opacity 0.4s ease; }</style>
    <script type="text/javascript">
    (function () {
        function settle() {
            if (typeof network !== "undefined" && network) {
                try { network.fit({ animation: false }); } catch (e) {}
            }
            var c = document.getElementById("mynetwork");
            if (c) { c.style.opacity = "1"; }
        }
        function bind() {
            if (typeof network !== "undefined" && network) {
                network.once("stabilizationIterationsDone", settle);
                network.once("afterDrawing", settle);
            }
            setTimeout(settle, 900);   // hard fallback regardless of events
        }
        setTimeout(bind, 30);          // let drawGraph() assign `network` first
    })();
    </script>
    """
    return html.replace("</body>", fit_script + "</body>")


def generate_intelligence_narrative(company_node: dict, officers: list, pscs: list, risk_report: dict) -> str:
    """Build a concise analyst briefing for the selected company."""
    company_name = company_node.get("name", "Unknown company")
    company_number = company_node.get("company_number", "N/A")
    status = (company_node.get("status") or "unknown").upper()
    company_type = company_node.get("company_type", "N/A")
    incorporation_date = company_node.get("incorporation_date", "N/A")
    address = company_node.get("address", "N/A")
    sic_codes = company_node.get("sic_codes", []) or []
    risk_score = float(risk_report.get("risk_score", 0.0))
    risk_tier = risk_report.get("risk_tier", "LOW")
    flags = risk_report.get("flags_triggered", []) or []

    active_officers = [o for o in officers if not o.get("resigned_date")]
    resigned_officers = [o for o in officers if o.get("resigned_date")]

    lines = [
        f"## Intelligence Brief: {company_name}",
        "",
        f"- Company Number: `{company_number}`",
        f"- Status: `{status}`",
        f"- Risk Profile: **{risk_tier}** ({risk_score:.1f}%)",
        f"- Company Type: `{company_type}`",
        f"- Incorporation Date: `{incorporation_date}`",
        f"- Registered Address: {address}",
        f"- SIC Codes: {', '.join(sic_codes) if sic_codes else 'N/A'}",
        "",
        "### Structure Snapshot",
        f"- Active officers: {len(active_officers)}",
        f"- Former officers: {len(resigned_officers)}",
        f"- PSC records: {len(pscs)}",
        "",
        "### Risk Summary",
    ]

    if flags:
        for flag in flags:
            severity = flag.get("severity", "INFO")
            title = flag.get("title", "Unnamed risk flag")
            description = flag.get("description", "")
            lines.append(f"- **[{severity}] {title}**: {description}")
    else:
        lines.append("- No risk flags were triggered for this entity.")

    lines.extend([
        "",
        "### Officers",
    ])
    if officers:
        for officer in officers[:10]:
            role = officer.get("role") or "N/A"
            resigned_date = officer.get("resigned_date")
            status_text = f"resigned {resigned_date}" if resigned_date else "active"
            lines.append(f"- {officer.get('name', 'Unnamed officer')} | {role} | {status_text}")
    else:
        lines.append("- No officers on record.")

    lines.extend([
        "",
        "### PSCs",
    ])
    if pscs:
        for psc in pscs[:10]:
            noc = psc.get("nature_of_control") or "N/A"
            nationality = psc.get("nationality") or "N/A"
            lines.append(f"- {psc.get('name', 'Unnamed PSC')} | {noc} | {nationality}")
    else:
        lines.append("- No PSC records on file.")

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════
# SIDEBAR NAVIGATION
# ═══════════════════════════════════════════════════════════════
NAV_PAGES = [
    "Overview",
    "Entity Explorer",
    "People Intelligence",
    "Risk & Analytics",
    "Workspace",
    "Query Studio",
]

with st.sidebar:
    sidebar_stats = get_graph_stats_cached()
    sidebar_alerts = len(get_high_risk_entities_cached())

    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-brand-name">VEIL</div>
            <div class="sidebar-brand-tag">Ownership Intelligence</div>
        </div>
        <div class="sidebar-stat-strip">
            <div class="sidebar-stat"><span class="v">{fmt_number(sidebar_stats['companies'])}</span><span class="l">Companies</span></div>
            <div class="sidebar-stat"><span class="v">{fmt_number(sidebar_stats['officers'])}</span><span class="l">Officers</span></div>
            <div class="sidebar-stat"><span class="v">{fmt_number(sidebar_stats['pscs'])}</span><span class="l">PSCs</span></div>
            <div class="sidebar-stat alert"><span class="v">{fmt_number(sidebar_alerts)}</span><span class="l">Alerts</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Numbered ops-rail navigation — the sequence is a real investigative
    # workflow (triage & topology → drilldown → compliance → export), so
    # the index prefix carries information rather than decorating it.
    nav_choice = st.radio(
        "Navigation",
        [f"{i+1:02d} · {label}" for i, label in enumerate(NAV_PAGES)],
        label_visibility="collapsed",
    )
    page = nav_choice.split("· ", 1)[-1]

    st.markdown("<br><hr style='border-color: var(--line);'><br>", unsafe_allow_html=True)

    # Sync trigger
    if st.button("Sync Graph Database"):
        with st.spinner("Re-syncing local graph..."):
            analytics_engine.sync_graph()
            analytics_engine.run_analytics()
            get_high_risk_entities_cached.clear()
            get_company_names_cached.clear()
            get_people_names_cached.clear()
            get_graph_stats_cached.clear()
            relationship_mix_frame.clear()
            get_company_segment_stats_cached.clear()
            get_people_segment_stats_cached.clear()
            st.success("Synchronised successfully!")
            st.rerun()

    st.markdown(render_status_line("GRAPH DATABASE ONLINE", online=True), unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style='color:var(--muted); font-size:0.66rem; text-align:center; margin-top:2px; font-family:var(--mono-dense); letter-spacing:0.08em;'>
            AURA PORT 7687 · {datetime.now():%Y-%m-%d %H:%M}
        </div>
        """,
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════
# PAGE 1: OVERVIEW (Rebuilt to be comprehensive & professional)
# ═══════════════════════════════════════════════════════════════
if page == "Overview":
    render_workbench_header(
        "Registry Command Center",
        "Ownership Risk Workbench",
        "Triage graph coverage, risk concentration, relationship density, and central entities before drilling into specific companies or people.",
    )

    stats_data = get_graph_stats_cached()
    num_nodes = stats_data["companies"] + stats_data["officers"] + stats_data["pscs"]
    avg_connections = stats_data["rels"] / max(num_nodes, 1)
    psc_coverage = (stats_data["pscs"] / max(stats_data["companies"], 1)) * 100

    high_risks = get_high_risk_entities_cached()
    active_alerts = len(high_risks)
    avg_risk_score = (sum(e["risk_score"] for e in high_risks) / active_alerts) if active_alerts else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Companies", fmt_number(stats_data["companies"]))
    with c2:
        st.metric("Officers", fmt_number(stats_data["officers"]))
    with c3:
        st.metric("Beneficial Owners (PSCs)", fmt_number(stats_data["pscs"]))
    with c4:
        st.metric("Total Edges", fmt_number(stats_data["rels"]))
    with c5:
        st.metric("Active Alerts", fmt_number(active_alerts))

    ranked_nodes = pd.DataFrame(analytics_engine.get_ranked_nodes(metric="degree", limit=8))

    col1, col2 = st.columns([3, 2])

    with col1:
        render_section_label("Graph Population")
        population_html = render_composition_html([
            {"label": "Companies", "count": stats_data["companies"], "color": TYPE_COLORS["Company"]},
            {"label": "Officers", "count": stats_data["officers"], "color": TYPE_COLORS["Officer"]},
            {"label": "PSCs", "count": stats_data["pscs"], "color": TYPE_COLORS["PSC"]},
        ])
        if population_html:
            st.markdown(population_html, unsafe_allow_html=True)
        else:
            render_empty_panel("No registry nodes loaded yet.")

        render_section_label("Relationship Mix")
        rel_df = relationship_mix_frame()
        if not rel_df.empty:
            total_rels = rel_df["count"].sum()
            for _, row in rel_df.iterrows():
                rel_type = row["relationship"]
                count = row["count"]
                pct = (count / total_rels) * 100
                st.markdown(
                    f"""
                    <div style="margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-family: var(--mono-dense); margin-bottom: 2px;">
                            <span>{rel_type}</span>
                            <span style="color: var(--muted);">{count:,} ({pct:.1f}%)</span>
                        </div>
                        <div style="background: var(--line); height: 6px; border-radius: 3px; overflow: hidden;">
                            <div style="background: var(--teal); width: {pct}%; height: 100%;"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            render_empty_panel("No relationships are available yet.")

        st.markdown(
            f"""
            <div class="intelligence-card">
                <div class="panel-title">Network Health Diagnostics</div>
                <div style="display:flex; justify-content:space-around; align-items:center; padding: 8px 0;">
                    <div style="text-align:center;">
                        <div style="font-family:var(--mono); font-size:1.55rem; color:var(--ink);">{avg_connections:.2f}</div>
                        <div style="font-size:0.72rem; color:var(--muted); text-transform:uppercase; margin-top:4px;">Average Degree</div>
                    </div>
                    <div style="text-align:center; border-left:1px solid var(--line); border-right:1px solid var(--line); padding:0 30px;">
                        <div style="font-family:var(--mono); font-size:1.55rem; color:var(--ink);">{fmt_number(num_nodes)}</div>
                        <div style="font-size:0.72rem; color:var(--muted); text-transform:uppercase; margin-top:4px;">Nodes in Graph</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-family:var(--mono); font-size:1.55rem; color:var(--ink);">{psc_coverage:.1f}%</div>
                        <div style="font-size:0.72rem; color:var(--muted); text-transform:uppercase; margin-top:4px;">PSC Coverage Signal</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_section_label("Most Connected Registry Nodes")
        if not ranked_nodes.empty:
            for _, row in ranked_nodes.iterrows():
                node_type = row["type"]
                color = TYPE_COLORS.get(node_type, "#5a5f54")
                st.markdown(
                    f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; background: var(--surface); border: 1px solid var(--line); border-radius: 3px; margin-bottom: 6px;">
                        <div>
                            <span style="background: {color}20; color: {color}; border: 1px solid {color}40; padding: 2px 6px; border-radius: 2px; font-size: 0.65rem; font-family: var(--mono-dense); font-weight: bold; text-transform: uppercase;">{node_type}</span>
                            &nbsp;<span style="font-size: 0.82rem; font-family: var(--sans); font-weight: 500;">{row['name']}</span>
                        </div>
                        <span style="font-family: var(--mono-dense); font-size: 0.8rem; color: var(--muted);">Degree: {row['score_value']:.4f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            render_empty_panel("Centrality scores are not available yet.")

    with col2:
        render_section_label("Flagged Risk Tier Distribution")
        risk_df = risk_tier_frame(high_risks)
        total_risk_entities = risk_df["Count"].sum()
        if total_risk_entities > 0:
            for _, row in risk_df.iterrows():
                tier = row["Tier"]
                count = row["Count"]
                pct = (count / total_risk_entities) * 100
                color = RISK_COLORS[tier]
                st.markdown(
                    f"""
                    <div style="margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-family: var(--mono-dense); margin-bottom: 2px;">
                            <span style="color: {color}; font-weight: bold;">{tier}</span>
                            <span style="color: var(--muted);">{count:,} ({pct:.1f}%)</span>
                        </div>
                        <div style="background: var(--line); height: 6px; border-radius: 3px; overflow: hidden;">
                            <div style="background: {color}; width: {pct}%; height: 100%;"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            render_empty_panel("No compliance risk alerts are currently flagged.")

        render_section_label("Active Risk Queue")
        if high_risks:
            for entity in high_risks[:5]:
                tier = entity["risk_tier"]
                badge_class = f"risk-{tier.lower()}"
                st.markdown(
                    f"<div style='margin-bottom: 10px; padding: 12px; background: var(--surface-2); border: 1px solid var(--line); border-radius: 3px;'>"
                    f"<span class='risk-indicator {badge_class}'>{tier}</span> &nbsp;"
                    f"<b style='font-family:var(--mono);'>{entity['name']}</b><br>"
                    f"<span style='font-size:0.8rem; color:var(--muted);'>Reference {entity['company_number']} | Score {entity['risk_score']:.1f}% | Flags {entity.get('flags_count', 0)}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            render_empty_panel("No compliance risk alerts are currently flagged.")

        st.markdown(
            f"""
            <div class="intelligence-card">
                <div class="panel-title">Database Event Log</div>
                <div class="audit-entry">
                    <span class="audit-time">REGISTRY GRAPH LOADED</span><br>
                    {fmt_number(num_nodes)} nodes and {fmt_number(stats_data["rels"])} relationships are available for analysis.
                </div>
                <div class="audit-entry">
                    <span class="audit-time">RISK QUEUE COMPILED</span><br>
                    {active_alerts} entities have active structural risk flags, averaging {avg_risk_score:.1f}% severity.
                </div>
                <div class="audit-entry">
                    <span class="audit-time">ANALYTICS READY</span><br>
                    Centrality and community scores are available from the local NetworkX graph.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="border-top:2px solid var(--teal); margin-top:32px; padding-top:18px;">
            <div class="workbench-kicker">Topology Intelligence</div>
            <div style="font-size:1.3rem; font-weight:700; color:var(--ink); margin-top:4px;">Network Analysis</div>
            <div class="workbench-subtitle" style="margin-top:6px; font-size:0.9rem;">
                Rank influential entities, inspect communities, and identify structurally important nodes in the local graph projection.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_graph, tab_metrics = st.tabs(["01 · Global Graph Topology", "02 · Topological Metrics"])
    
    with tab_metrics:
        metric_choice = st.selectbox(
            "Topological Ranking Metrics",
            ["PageRank Flow", "Degree Connections", "Betweenness Centrality", "Closeness Centrality"]
        )
        
        metric_map = {
            "PageRank Flow": "pagerank",
            "Degree Connections": "degree",
            "Betweenness Centrality": "betweenness",
            "Closeness Centrality": "closeness"
        }
        
        ranked_nodes = analytics_engine.get_ranked_nodes(metric=metric_map[metric_choice], limit=30)
        
        if ranked_nodes:
            ranked_df = pd.DataFrame(ranked_nodes)
            ranked_df["display_name"] = ranked_df["name"].astype(str).str.slice(0, 48)
            top_chart = alt.Chart(ranked_df.head(15)).mark_bar(cornerRadiusEnd=0).encode(
                x=alt.X("score_value:Q", title=metric_choice),
                y=alt.Y("display_name:N", sort="-x", title=None),
                color=alt.Color("type:N", scale=alt.Scale(range=CHART_COLORS), legend=alt.Legend(title=None)),
                tooltip=["name:N", "type:N", "score_value:Q", "community:N"],
            )
            render_section_label("Ranked Node Signal")
            st.altair_chart(style_chart(top_chart, 330), use_container_width=True)

            left, right = st.columns(2)
            with left:
                render_section_label("Class Composition")
                type_counts = ranked_df["type"].value_counts().reset_index()
                type_counts.columns = ["Class Type", "Count"]
                type_chart = alt.Chart(type_counts).mark_arc(innerRadius=58, outerRadius=95).encode(
                    theta=alt.Theta("Count:Q"),
                    color=alt.Color("Class Type:N", scale=alt.Scale(range=CHART_COLORS), legend=alt.Legend(title=None)),
                    tooltip=["Class Type:N", "Count:Q"],
                )
                st.altair_chart(style_chart(type_chart, 230), use_container_width=True)

            with right:
                render_section_label("Community Cluster Distribution")
                counts = ranked_df["community"].value_counts().reset_index()
                counts.columns = ["Community Cluster ID", "Count"]
                community_chart = alt.Chart(counts).mark_bar(cornerRadiusEnd=0).encode(
                    x=alt.X("Community Cluster ID:N", title="Community"),
                    y=alt.Y("Count:Q", title=None),
                    color=alt.value("#584873"),
                    tooltip=["Community Cluster ID:N", "Count:Q"],
                )
                st.altair_chart(style_chart(community_chart, 230), use_container_width=True)

            render_section_label("Ranked Nodes Table")
            st.dataframe(
                ranked_df.rename(columns={
                    "name": "Node Label",
                    "type": "Class Type",
                    "score_value": "Index Score",
                    "community": "Louvain Community Cluster"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            render_empty_panel("Network analytics have not been computed yet. Use Sync Graph Database from the sidebar.")

    with tab_graph:
        st.markdown(
            """
            <div style="margin-bottom: 12px; font-size: 0.88rem; color: var(--muted);">
                This interactive visualization projects the active registry network. Nodes are color-coded by their 
                <b>Louvain Community Cluster ID</b>, highlighting corporate groupings and shared control networks. 
                Use mouse wheel to zoom, click and drag to pan, and hover over nodes for details.
            </div>
            """,
            unsafe_allow_html=True
        )
        if analytics_engine.metadata:
            # Create a PyVis network
            net = Network(height="600px", width="100%", bgcolor=GRAPH_BG, font_color=GRAPH_FONT, directed=True, cdn_resources="in_line")
            net.set_options(json.dumps({
                "physics": {
                    "forceAtlas2Based": {
                        "gravitationalConstant": -45,
                        "springLength": 90,
                        "springConstant": 0.04
                    },
                    "solver": "forceAtlas2Based",
                    "stabilization": {"iterations": 120, "fit": True}
                },
                "interaction": {"hover": True, "navigationButtons": True, "tooltipDelay": 100},
                "nodes": {"font": {"size": 11, "face": "'IBM Plex Mono', monospace", "color": GRAPH_FONT}},
                "edges": {"smooth": {"type": "continuous", "roundness": 0.15}}
            }))
            
            # Map type to shape/size
            for node_id, meta in analytics_engine.metadata.items():
                node_type = meta.get("type", "Company")
                display_label = meta.get("name", "")
                if len(display_label) > 24:
                    display_label = display_label[:22] + "..."
                
                cid = analytics_engine.node_communities.get(node_id, 0)
                bg_color = COMMUNITY_PALETTE[cid % len(COMMUNITY_PALETTE)]
                
                shape = "diamond" if node_type == "Company" else "dot"
                size = 20 if node_type == "Company" else 10
                title = f"<b>{meta.get('name')}</b><br>Type: {node_type}<br>Community: {cid}"
                
                net.add_node(node_id, label=display_label, title=title,
                             color={"background": bg_color, "border": bg_color, "highlight": {"background": "#ffd54f", "border": "#c98a1f"}},
                             size=size, shape=shape)
            
            # Add all edges
            for u, v, data in analytics_engine.nx_di_graph.edges(data=True):
                rel_type = data.get("type", "")
                color = GRAPH_EDGE_MUTED if rel_type == "HAS_OFFICER" else RISK_COLORS["CRITICAL"]
                dashes = False if rel_type == "HAS_OFFICER" else True
                net.add_edge(u, v, color=color, dashes=dashes, title=rel_type, width=1.0)
            
            temp_path = None
            try:
                net_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
                net_file.close()
                net.save_graph(net_file.name)
                temp_path = Path(net_file.name)
                graph_html = harden_graph_html(temp_path.read_text(encoding="utf-8"), bg_hex=GRAPH_BG)
            finally:
                if temp_path and temp_path.exists():
                    temp_path.unlink(missing_ok=True)
            components.html(graph_html, height=620, scrolling=False)
            
            # Legend
            st.markdown(
                """
                <div style="display:flex; gap:20px; margin-top:8px; font-size:0.72rem; color:var(--muted); font-family:var(--mono-dense);">
                    <span>&#9670; Company (Diamond)</span>
                    <span>&#11044; Officer / PSC (Circle)</span>
                    <span style="color:var(--muted);">&mdash; HAS_OFFICER relationship</span>
                    <span style="color:#8f1f2c;">- - HAS_PSC (control) relationship</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            render_empty_panel("No graph metadata is available. Use Sync Graph Database from the sidebar.")

# ═══════════════════════════════════════════════════════════════
# PAGE 2: ENTITY EXPLORER
# ═══════════════════════════════════════════════════════════════
elif page == "Entity Explorer":
    render_workbench_header(
        "Entity Drilldown",
        "Corporate Entity Explorer",
        "Inspect a company through its control records, board footprint, centrality score, risk flags, and local ownership graph.",
    )

    seg = get_company_segment_stats_cached()
    render_section_label("Company Population at a Glance")
    seg_c1, seg_c2, seg_c3, seg_c4 = st.columns(4)
    with seg_c1:
        st.metric("Total Companies", fmt_number(seg["total"]))
    with seg_c2:
        st.metric("Avg Officers / Company", f"{seg['avg_officers']:.1f}")
    with seg_c3:
        st.metric("No Officers On File", fmt_number(seg["no_officer_companies"]))
    with seg_c4:
        st.metric("No PSC Filing", fmt_number(seg["no_psc_companies"]))

    seg_left, seg_right = st.columns(2)
    with seg_left:
        render_section_label("Status Mix")
        status_html = render_composition_html([
            {"label": row["status"].title(), "count": row["count"], "color": CHART_COLORS[i % len(CHART_COLORS)]}
            for i, row in enumerate(seg["status"])
        ])
        if status_html:
            st.markdown(status_html, unsafe_allow_html=True)
        else:
            render_empty_panel("No company status data on file.")

        render_section_label("Legal Form Mix")
        type_html = render_composition_html([
            {"label": row["company_type"], "count": row["count"], "color": CHART_COLORS[i % len(CHART_COLORS)]}
            for i, row in enumerate(seg["type"])
        ])
        if type_html:
            st.markdown(type_html, unsafe_allow_html=True)
        else:
            render_empty_panel("No company type data on file.")

    with seg_right:
        render_section_label("Top Sector Codes (SIC)")
        if len(seg["sic"]) >= 2:
            sic_df = pd.DataFrame(seg["sic"])
            sic_chart = alt.Chart(sic_df).mark_bar(cornerRadiusEnd=0).encode(
                x=alt.X("count:Q", title=None),
                y=alt.Y("sic:N", sort="-x", title=None),
                color=alt.value(CHART_COLORS[0]),
                tooltip=["sic:N", "count:Q"],
            )
            st.altair_chart(style_chart(sic_chart, 230), use_container_width=True)
        elif len(seg["sic"]) == 1:
            only = seg["sic"][0]
            st.markdown(
                render_intel_badge_html(f"SIC {only['sic']}", fmt_number(only["count"]), "Only sector code on file"),
                unsafe_allow_html=True,
            )
        else:
            render_empty_panel("No SIC sector data on file.")

    st.markdown("<hr style='border-color:var(--line); margin: 6px 0 18px 0;'>", unsafe_allow_html=True)

    company_options = get_company_names_cached()

    selected_company_name = st.selectbox(
        "Select Corporate Registry Target",
        options=[""] + company_options,
        index=0,
        placeholder="Type company name..."
    )

    if selected_company_name:
        workspace.log_search(selected_company_name, "Company")

        detail_res = run_query(
            "MATCH (c:Company {name: $name}) RETURN c",
            {"name": selected_company_name}
        )

        if detail_res:
            company_node = detail_res[0]["c"]
            company_number = company_node.get("company_number")

            # ── Pre-fetch ALL data upfront so every tab is instantly browsable ──
            officers = run_query(
                "MATCH (:Company {company_number: $cn})-[r:HAS_OFFICER]->(o:Officer) "
                "RETURN o.name AS name, o.role AS role, r.appointed_date AS appointed_date, "
                "r.resigned_date AS resigned_date, o.nationality AS nationality",
                {"cn": company_number}
            )
            pscs = run_query(
                "MATCH (:Company {company_number: $cn})-[r:HAS_PSC]->(p:PSC) "
                "RETURN p.name AS name, p.nature_of_control AS nature_of_control, "
                "p.kind AS kind, r.notified_on AS notified_on, p.nationality AS nationality",
                {"cn": company_number}
            )
            risk_report   = risk_engine.analyze_company_risks(company_number)
            node_key      = f"co_{company_number}"
            rank_score    = analytics_engine.pagerank_scores.get(node_key, 0.0) * 1000.0
            degree_val    = analytics_engine.nx_graph.degree(node_key) if analytics_engine.nx_graph.has_node(node_key) else 0
            inf_score     = calculate_influence_score(
                degree_val,
                max([calculate_control_score(p.get("nature_of_control", "")) for p in pscs]) if pscs else 0.0,
                len(officers)
            )
            priority_score = calculate_investigation_priority(risk_report["risk_score"], inf_score, degree_val * 10.0)
            flags          = risk_report.get("flags_triggered", []) or []
            active_officers  = [o for o in officers if not o.get("resigned_date")]
            resigned_officers = [o for o in officers if o.get("resigned_date")]

            # ── Company header ─────────────────────────────────────────────────
            col_h1, col_h2 = st.columns([5, 2])
            with col_h1:
                risk_tier = risk_report.get("risk_tier", "LOW")
                tier_color = RISK_COLORS.get(risk_tier, "#367a3c")
                status_val = company_node.get('status', 'Unknown').upper()
                st.markdown(
                    f"""
                    <div style="margin-bottom:4px;">
                        <span style="font-size:1.55rem; font-weight:700; color:var(--ink); font-family:var(--mono);">
                            {selected_company_name}
                        </span>
                        &nbsp;
                        <span class="risk-indicator risk-{risk_tier.lower()}" style="vertical-align:middle;">{risk_tier}</span>
                    </div>
                    <div style="font-size:0.78rem; color:var(--muted); font-family:var(--mono-dense); letter-spacing:0.05em;">
                        REF&nbsp;{company_number}&nbsp;&nbsp;|&nbsp;&nbsp;STATUS&nbsp;{status_val}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col_h2:
                is_bm = workspace.is_company_bookmarked(company_number)
                btn_lbl = "Unbookmark Target" if is_bm else "Bookmark Target"
                if st.button(btn_lbl):
                    added = workspace.toggle_bookmark_company(company_number, selected_company_name)
                    st.toast("Bookmark saved!" if added else "Bookmark removed!")
                    st.rerun()

            # ── Score strip ────────────────────────────────────────────────────
            st.markdown("<div style='margin-top:10px;'>", unsafe_allow_html=True)
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Risk Score", f"{risk_report['risk_score']:.1f}%")
            with sc2:
                st.metric("Influence Index", f"{inf_score:.1f}%")
            with sc3:
                st.metric("PageRank Value", f"{rank_score:.5f}")
            with sc4:
                st.metric("Priority Score", f"{priority_score:.1f}%")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<hr style='border-color:var(--line); margin: 14px 0 4px 0;'>", unsafe_allow_html=True)

            # ══════════════════════════════════════════════════════════════════
            # TABS — placed at the top so they are the primary nav mechanism
            # ══════════════════════════════════════════════════════════════════
            t_meta, t_off, t_psc, t_analytics, t_net, t_brief = st.tabs([
                "01 · Registry Profile",
                f"02 · Appointed Officers ({len(officers)})",
                f"03 · Beneficial Controls ({len(pscs)})",
                "04 · Analytics",
                "05 · Visual Structure",
                "06 · Analyst Briefing",
            ])

            # ── TAB 1: Registry Profile ────────────────────────────────────────
            with t_meta:
                sic_codes = company_node.get("sic_codes", []) or []
                address   = company_node.get("address", "N/A")
                incorp    = company_node.get("incorporation_date", "N/A")
                co_type   = company_node.get("company_type", "N/A")
                sic_str   = ", ".join(sic_codes) if sic_codes else "N/A"

                st.markdown(
                    f"""
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px;">
                        <div class="intelligence-card" style="padding:20px;">
                            <div style="font-size:0.68rem; text-transform:uppercase; letter-spacing:0.12em; color:var(--muted); margin-bottom:6px;">Corporate Classification</div>
                            <div style="font-family:var(--mono); font-size:1.15rem; color:var(--ink); font-weight:600;">{co_type}</div>
                        </div>
                        <div class="intelligence-card" style="padding:20px;">
                            <div style="font-size:0.68rem; text-transform:uppercase; letter-spacing:0.12em; color:var(--muted); margin-bottom:6px;">Sector Classification (SIC)</div>
                            <div style="font-family:var(--mono); font-size:1.05rem; color:#16756d; font-weight:600;">{sic_str}</div>
                        </div>
                        <div class="intelligence-card" style="padding:20px;">
                            <div style="font-size:0.68rem; text-transform:uppercase; letter-spacing:0.12em; color:var(--muted); margin-bottom:6px;">Incorporated Date</div>
                            <div style="font-family:var(--mono); font-size:1.15rem; color:#16756d; font-weight:600;">{incorp}</div>
                        </div>
                        <div class="intelligence-card" style="padding:20px;">
                            <div style="font-size:0.68rem; text-transform:uppercase; letter-spacing:0.12em; color:var(--muted); margin-bottom:6px;">Registered Office</div>
                            <div style="font-size:0.9rem; color:var(--ink); line-height:1.5;">{address}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown("<div style='margin-top:20px;'>", unsafe_allow_html=True)
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Active Officers", len(active_officers))
                with m2:
                    st.metric("Former Officers", len(resigned_officers))
                with m3:
                    st.metric("PSC Filings", len(pscs))
                st.markdown("</div>", unsafe_allow_html=True)

            # ── TAB 2: Appointed Officers ──────────────────────────────────────
            with t_off:
                if officers:
                    off_col1, off_col2 = st.columns([3, 1])
                    with off_col1:
                        st.dataframe(
                            pd.DataFrame(officers),
                            use_container_width=True,
                            hide_index=True
                        )
                    with off_col2:
                        render_section_label("Officer Summary")
                        officer_mix_html = render_composition_html([
                            {"label": "Active", "count": len(active_officers), "color": CHART_COLORS[0]},
                            {"label": "Former", "count": len(resigned_officers), "color": CHART_COLORS[1]},
                        ])
                        st.markdown(officer_mix_html, unsafe_allow_html=True)
                else:
                    st.info("No recorded officers.")

            # ── TAB 3: Beneficial Controls ─────────────────────────────────────
            with t_psc:
                if pscs:
                    psc_col1, psc_col2 = st.columns([3, 1])
                    with psc_col1:
                        st.dataframe(
                            pd.DataFrame(pscs),
                            use_container_width=True,
                            hide_index=True
                        )
                    with psc_col2:
                        render_section_label("Control Kinds")
                        kind_counts = pd.DataFrame(pscs)["kind"].value_counts() if pscs else pd.Series(dtype=int)
                        kind_html = render_composition_html([
                            {"label": kind, "count": int(count), "color": CHART_COLORS[i % len(CHART_COLORS)]}
                            for i, (kind, count) in enumerate(kind_counts.items())
                        ])
                        if kind_html:
                            st.markdown(kind_html, unsafe_allow_html=True)
                        else:
                            render_empty_panel("No control-kind data on file.")
                else:
                    st.info("No beneficial ownership filings detected.")

            # ── TAB 4: Analytics ───────────────────────────────────────────────
            with t_analytics:
                an_left, an_right = st.columns([3, 2])
                with an_left:
                    render_section_label("Investigation Signal Profile")
                    score_df = pd.DataFrame([
                        {"Signal": "Risk Score",             "Score": risk_report["risk_score"]},
                        {"Signal": "Influence Index",        "Score": inf_score},
                        {"Signal": "Investigation Priority", "Score": priority_score},
                        {"Signal": "Degree Pressure",        "Score": min(degree_val * 10.0, 100.0)},
                    ])
                    score_chart = alt.Chart(score_df).mark_bar(cornerRadiusEnd=0).encode(
                        x=alt.X("Score:Q", scale=alt.Scale(domain=[0, 100]), title="Score (0–100)"),
                        y=alt.Y("Signal:N", sort="-x", title=None),
                        color=alt.Color("Signal:N", scale=alt.Scale(range=CHART_COLORS), legend=None),
                        tooltip=["Signal:N", alt.Tooltip("Score:Q", format=".1f")],
                    )
                    st.altair_chart(style_chart(score_chart, 210), use_container_width=True)

                    # Officer tenure timeline
                    off_with_dates = [o for o in officers if o.get("appointed_date")]
                    if off_with_dates:
                        render_section_label("Officer Appointment Timeline")
                        off_timeline_df = pd.DataFrame([
                            {
                                "Officer": o["name"][:28],
                                "Appointed": o.get("appointed_date", ""),
                                "Status": "Former" if o.get("resigned_date") else "Active",
                            }
                            for o in off_with_dates
                        ])
                        timeline_chart = alt.Chart(off_timeline_df).mark_point(size=80, filled=True).encode(
                            x=alt.X("Appointed:T", title="Appointment Date"),
                            y=alt.Y("Officer:N", title=None),
                            color=alt.Color("Status:N", scale=alt.Scale(
                                domain=["Active", "Former"],
                                range=[CHART_COLORS[0], CHART_COLORS[1]]
                            ), legend=alt.Legend(title=None)),
                            tooltip=["Officer:N", "Appointed:T", "Status:N"],
                        )
                        st.altair_chart(style_chart(timeline_chart, 220), use_container_width=True)

                with an_right:
                    render_section_label("Risk Flag Composition")
                    if flags:
                        flag_df = pd.DataFrame([
                            {"Flag": flag.get("title", "Unknown flag"), "Severity": flag.get("severity", "INFO"), "Weight": flag.get("weight", 0)}
                            for flag in flags
                        ])
                        flag_chart = alt.Chart(flag_df).mark_bar(cornerRadiusEnd=0).encode(
                            x=alt.X("Weight:Q", title="Risk Weight"),
                            y=alt.Y("Flag:N", sort="-x", title=None),
                            color=alt.Color("Severity:N", scale=alt.Scale(
                                domain=["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
                                range=[RISK_COLORS["CRITICAL"], RISK_COLORS["HIGH"], RISK_COLORS["MEDIUM"], RISK_COLORS["LOW"], "#5a5f54"]
                            ), legend=alt.Legend(title="Severity")),
                            tooltip=["Flag:N", "Severity:N", "Weight:Q"],
                        )
                        st.altair_chart(style_chart(flag_chart, 280), use_container_width=True)
                    else:
                        render_empty_panel("No risk flags triggered for this entity.")

            # ── TAB 5: Visual Structure ────────────────────────────────────────
            with t_net:
                net_c1, net_c2, net_c3 = st.columns(3)
                with net_c1:
                    spotlight = st.checkbox("Spotlight Focus", value=True, help="Fade nodes not directly connected to this company")
                with net_c2:
                    community_color = st.checkbox("Community Coloring", value=True, help="Color nodes by Louvain community cluster")
                with net_c3:
                    cross_links = st.checkbox("Cross-Company Links", value=False, help="Show other companies that share officers or PSCs with this company")


                net = Network(height="520px", width="100%", bgcolor=GRAPH_BG, font_color=GRAPH_FONT, directed=True, cdn_resources="in_line")
                net.set_options(json.dumps({
                    "physics": {
                        "forceAtlas2Based": {
                            "gravitationalConstant": -60,
                            "springLength": 120,
                            "springConstant": 0.05
                        },
                        "solver": "forceAtlas2Based",
                        "stabilization": {"iterations": 150}
                    },
                    "interaction": {"hover": True, "navigationButtons": True, "tooltipDelay": 100},
                    "nodes": {"font": {"size": 12, "face": "'IBM Plex Mono', monospace", "color": GRAPH_FONT}},
                    "edges": {"smooth": {"type": "curvedCW", "roundness": 0.15}}
                }))

                def _community_color(node_id: str) -> str:
                    cid = analytics_engine.node_communities.get(node_id, 0)
                    return COMMUNITY_PALETTE[cid % len(COMMUNITY_PALETTE)]

                def draw_node(node_id, label, node_type, force_color=None):
                    is_neighbor = (node_id == node_key) or analytics_engine.nx_graph.has_edge(node_key, node_id)

                    if force_color:
                        bg_color = force_color
                        bd_color = force_color
                    elif community_color:
                        bg_color = _community_color(node_id)
                        bd_color = bg_color
                    else:
                        bg_color = TYPE_COLORS.get(node_type, "#5a5f54")
                        bd_color = TYPE_BORDER_COLORS.get(node_type, "#3d4134")

                    if spotlight and not is_neighbor and not force_color:
                        bg_color = "rgba(61, 65, 52, 0.55)"
                        bd_color = "rgba(61, 65, 52, 0.35)"

                    shape = "diamond" if node_type == "Company" else "dot"
                    size  = 32 if node_id == node_key else (24 if node_type == "Company" else 16)
                    title = f"<b>{label}</b><br>Type: {node_type}<br>Community: {analytics_engine.node_communities.get(node_id, 'N/A')}"
                    net.add_node(node_id, label=label, title=title,
                                 color={"background": bg_color, "border": bd_color, "highlight": {"background": "#ffd54f", "border": "#c98a1f"}},
                                 size=size, shape=shape)

                # Primary company — always rendered as diamond focal node
                draw_node(node_key, selected_company_name, "Company", force_color=TYPE_COLORS["Company"] if not community_color else None)

                for o in officers:
                    oid = f"off_{o['name']}"
                    draw_node(oid, o['name'], "Officer")
                    net.add_edge(node_key, oid, color=GRAPH_EDGE_MUTED, title="HAS_OFFICER", width=1.5)

                for p in pscs:
                    pid = f"psc_{p['name']}"
                    draw_node(pid, p['name'], "PSC")
                    net.add_edge(pid, node_key, color=RISK_COLORS["CRITICAL"], dashes=True, title="HAS_PSC (control)", width=2.0)

                # Cross-company links: other companies sharing same officers/PSCs
                if cross_links:
                    shared_cos = run_query("""
                        MATCH (c1:Company {company_number: $cn})-[:HAS_OFFICER]->(o:Officer)<-[:HAS_OFFICER]-(c2:Company)
                        WHERE c1 <> c2
                        RETURN c2.name AS name, c2.company_number AS cn2, collect(o.name)[..3] AS shared, count(o) AS cnt
                        ORDER BY cnt DESC LIMIT 8
                    """, {"cn": company_number})
                    shared_psc_cos = run_query("""
                        MATCH (c1:Company {company_number: $cn})-[:HAS_PSC]->(p:PSC)<-[:HAS_PSC]-(c2:Company)
                        WHERE c1 <> c2
                        RETURN c2.name AS name, c2.company_number AS cn2, collect(p.name)[..3] AS shared, count(p) AS cnt
                        ORDER BY cnt DESC LIMIT 5
                    """, {"cn": company_number})

                    for row in shared_cos:
                        co2_key = f"co_{row['cn2']}"
                        if co2_key not in [n for n in net.get_nodes()]:
                            draw_node(co2_key, row['name'][:32], "Company")
                        shared_labels = ", ".join(row['shared'])
                        net.add_edge(node_key, co2_key,
                                     color=CROSS_LINK_COLOR, dashes=False, width=2.5,
                                     title=f"Shared officers: {shared_labels} (+{row['cnt']} total)")

                    for row in shared_psc_cos:
                        co2_key = f"co_{row['cn2']}"
                        if co2_key not in [n for n in net.get_nodes()]:
                            draw_node(co2_key, row['name'][:32], "Company")
                        net.add_edge(node_key, co2_key,
                                     color=RISK_COLORS["HIGH"], dashes=True, width=2.5,
                                     title=f"Shared PSC: {', '.join(row['shared'])}")

                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
                        net.save_graph(f.name)
                        temp_path = Path(f.name)
                        graph_html = harden_graph_html(temp_path.read_text(encoding="utf-8"), bg_hex=GRAPH_BG)
                finally:
                    if temp_path and temp_path.exists():
                        temp_path.unlink(missing_ok=True)
                components.html(graph_html, height=540, scrolling=False)

                # Legend
                st.markdown(
                    """
                    <div style="display:flex; gap:20px; margin-top:6px; font-size:0.72rem; color:var(--muted); font-family:var(--mono-dense);">
                        <span>&#9670; Company (focal)</span>
                        <span style="color:var(--teal);">&#11044; Company</span>
                        <span style="color:var(--violet);">&#11044; Officer</span>
                        <span style="color:var(--red);">&#11044; PSC / Controller</span>
                        <span style="color:var(--blue);">&#11044; Cross-linked (shared officer)</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # ── TAB 6: Analyst Briefing ────────────────────────────────────────
            with t_brief:
                brief_text = generate_intelligence_narrative(company_node, officers, pscs, risk_report)
                st.markdown(brief_text)
                st.download_button("Export Briefing", data=brief_text, file_name=f"brief_{company_number}.txt")

# ═══════════════════════════════════════════════════════════════
# PAGE 3: PEOPLE INTELLIGENCE
# ═══════════════════════════════════════════════════════════════
elif page == "People Intelligence":
    render_workbench_header(
        "Person-Centric Triage",
        "People Intelligence",
        "Find repeat directors, beneficial owners, nominee patterns, and cross-company control footprints.",
    )

    pseg = get_people_segment_stats_cached()
    overview_stats = get_graph_stats_cached()
    render_section_label("Person & Control Population at a Glance")
    pp_c1, pp_c2, pp_c3, pp_c4 = st.columns(4)
    with pp_c1:
        st.metric("Total Officers", fmt_number(overview_stats["officers"]))
    with pp_c2:
        st.metric("Total PSCs", fmt_number(overview_stats["pscs"]))
    with pp_c3:
        st.metric("Multi-Board Officers", fmt_number(len(pseg["multi_officers"])))
    with pp_c4:
        st.metric("Repeat PSCs", fmt_number(len(pseg["multi_pscs"])))

    pp_left, pp_right = st.columns(2)
    with pp_left:
        render_section_label("Officer Role Mix")
        role_html = render_composition_html([
            {"label": row["role"].title(), "count": row["count"], "color": CHART_COLORS[i % len(CHART_COLORS)]}
            for i, row in enumerate(pseg["role"])
        ])
        if role_html:
            st.markdown(role_html, unsafe_allow_html=True)
        else:
            render_empty_panel("No officer role data on file.")

        render_section_label("PSC Control Kind Mix")
        kind_html = render_composition_html([
            {"label": row["kind"], "count": row["count"], "color": CHART_COLORS[i % len(CHART_COLORS)]}
            for i, row in enumerate(pseg["kind"])
        ])
        if kind_html:
            st.markdown(kind_html, unsafe_allow_html=True)
        else:
            render_empty_panel("No PSC control-kind data on file.")

    with pp_right:
        render_section_label("Multi-Company Officers (Nominee Signal)")
        if len(pseg["multi_officers"]) >= 2:
            mo_df = pd.DataFrame(pseg["multi_officers"])
            mo_chart = alt.Chart(mo_df).mark_bar(cornerRadiusEnd=0).encode(
                x=alt.X("company_count:Q", title="Companies"),
                y=alt.Y("name:N", sort="-x", title=None),
                color=alt.condition(
                    alt.datum.company_count >= 5,
                    alt.value(RISK_COLORS["HIGH"]),
                    alt.value(CHART_COLORS[0]),
                ),
                tooltip=["name:N", "company_count:Q"],
            )
            st.altair_chart(style_chart(mo_chart, 230), use_container_width=True)
            st.markdown(
                "<div style='font-size:0.72rem; color:var(--muted); margin-top:-6px;'>"
                "Amber bars sit at or above the 5-company nominee-risk threshold.</div>",
                unsafe_allow_html=True,
            )
        elif len(pseg["multi_officers"]) == 1:
            only = pseg["multi_officers"][0]
            st.markdown(
                render_intel_badge_html(only["name"], f"{only['company_count']} companies", "Only repeat officer on file"),
                unsafe_allow_html=True,
            )
        else:
            render_empty_panel("No officer holds more than one board seat yet.")

    st.markdown("<hr style='border-color:var(--line); margin: 6px 0 18px 0;'>", unsafe_allow_html=True)

    people_names = get_people_names_cached()
    
    selected_person = st.selectbox(
        "Select Individual Registry Target",
        options=[""] + people_names,
        index=0,
        placeholder="Type name..."
    )
    
    if selected_person:
        workspace.log_search(selected_person, "Person")
        
        roles_off = run_query(
            "MATCH (c:Company)-[r:HAS_OFFICER]->(o:Officer {name: $name}) "
            "RETURN c.name AS company, c.company_number AS cn, o.role AS role, r.appointed_date AS appointed",
            {"name": selected_person}
        )
        roles_psc = run_query(
            "MATCH (c:Company)-[r:HAS_PSC]->(p:PSC {name: $name}) "
            "RETURN c.name AS company, c.company_number AS cn, p.nature_of_control AS control, r.notified_on AS notified",
            {"name": selected_person}
        )
        
        person_risks = risk_engine.analyze_person_risks(selected_person)
        
        col1, col2 = st.columns([5, 2])
        with col1:
            st.subheader(selected_person)
            st.caption(f"Risk Rating Score: {person_risks['risk_score']:.1f}% ({person_risks['risk_tier']})")
        with col2:
            is_bm = workspace.is_person_bookmarked(selected_person)
            lbl = "Unbookmark Person" if is_bm else "Bookmark Person"
            if st.button(lbl):
                added = workspace.toggle_bookmark_person(selected_person)
                st.toast("Saved!" if added else "Removed!")
                st.rerun()

        footprint_df = pd.DataFrame([
            {"Relationship": "Board appointments", "Count": len(roles_off)},
            {"Relationship": "PSC controls", "Count": len(roles_psc)},
            {"Relationship": "Distinct companies", "Count": len({r.get("cn") for r in roles_off + roles_psc if r.get("cn")})},
            {"Relationship": "Risk flags", "Count": len(person_risks.get("flags_triggered", []))},
        ])
        render_section_label("Person Footprint")
        footprint_chart = alt.Chart(footprint_df).mark_bar(cornerRadiusEnd=0).encode(
            x=alt.X("Count:Q", title=None),
            y=alt.Y("Relationship:N", sort="-x", title=None),
            color=alt.Color("Relationship:N", scale=alt.Scale(range=CHART_COLORS), legend=None),
            tooltip=["Relationship:N", "Count:Q"],
        )
        st.altair_chart(style_chart(footprint_chart, 180), use_container_width=True)

        if person_risks.get("flags_triggered"):
            render_section_label("Person Risk Rules")
            person_flag_df = pd.DataFrame([
                {"Flag": flag.get("title", "Unknown flag"), "Weight": flag.get("weight", 0)}
                for flag in person_risks.get("flags_triggered", [])
            ])
            person_flag_chart = alt.Chart(person_flag_df).mark_bar(cornerRadiusEnd=0).encode(
                x=alt.X("Weight:Q", title="Weight"),
                y=alt.Y("Flag:N", sort="-x", title=None),
                color=alt.value("#8f1f2c"),
                tooltip=["Flag:N", "Weight:Q"],
            )
            st.altair_chart(style_chart(person_flag_chart, 140), use_container_width=True)

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            render_section_label("Board Appointments")
            if roles_off:
                st.dataframe(pd.DataFrame(roles_off), use_container_width=True, hide_index=True)
            else:
                st.info("No Officer history.")
        with col_t2:
            render_section_label("Beneficial Control Registry")
            if roles_psc:
                st.dataframe(pd.DataFrame(roles_psc), use_container_width=True, hide_index=True)
            else:
                st.info("No PSC history.")

# ═══════════════════════════════════════════════════════════════
# PAGE 4: RISK & ANALYTICS
# ═══════════════════════════════════════════════════════════════
elif page == "Risk & Analytics":
    render_workbench_header(
        "Compliance & Diagnostics",
        "Risk & Analytics",
        "Prioritize structural transparency issues and monitor registry-wide status, incorporation, and address concentration in one workbench.",
    )

    tab_risk, tab_diag = st.tabs(["01 · Compliance Queue", "02 · Graph Diagnostics"])

    with tab_risk:
        high_risks = get_high_risk_entities_cached()

        crit_count = sum(1 for e in high_risks if e["risk_tier"] == "CRITICAL")
        high_count = sum(1 for e in high_risks if e["risk_tier"] == "HIGH")
        med_count = sum(1 for e in high_risks if e["risk_tier"] == "MEDIUM")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Critical Structural Risks", crit_count)
        with c2:
            st.metric("High Compliance Alerts", high_count)
        with c3:
            st.metric("Medium Compliance Alerts", med_count)

        risk_left, risk_right = st.columns([2, 3])
        with risk_left:
            render_section_label("Risk Tier Distribution")
            risk_df = risk_tier_frame(high_risks)
            risk_chart = alt.Chart(risk_df).mark_bar(cornerRadiusEnd=0).encode(
                x=alt.X("Count:Q", title=None),
                y=alt.Y("Tier:N", sort=RISK_ORDER, title=None),
                color=alt.Color(
                    "Tier:N",
                    scale=alt.Scale(domain=RISK_ORDER, range=[RISK_COLORS[t] for t in RISK_ORDER]),
                    legend=None,
                ),
                tooltip=["Tier:N", "Count:Q"],
            )
            st.altair_chart(style_chart(risk_chart, 220), use_container_width=True)

        with risk_right:
            render_section_label("Most Frequent Risk Rules")
            flags_df = flag_frequency_frame(high_risks)
            if not flags_df.empty:
                flags_chart = alt.Chart(flags_df).mark_bar(cornerRadiusEnd=0).encode(
                    x=alt.X("Count:Q", title=None),
                    y=alt.Y("Flag:N", sort="-x", title=None),
                    color=alt.value(RISK_COLORS["CRITICAL"]),
                    tooltip=["Flag:N", "Count:Q"],
                )
                st.altair_chart(style_chart(flags_chart, 220), use_container_width=True)
            else:
                render_empty_panel("No risk rules are currently active.")

        render_section_label("Structural Risk Alert Logs")

        if high_risks:
            table_rows = []
            for e in high_risks:
                flags_str = ", ".join([f["title"] for f in e["flags"]])
                table_rows.append({
                    "Entity Name": e["name"],
                    "ID": e["company_number"],
                    "Tier": e["risk_tier"],
                    "Risk Score": f"{e['risk_score']:.1f}%",
                    "Compliance Alerts": flags_str
                })
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
        else:
            st.success("No compliance structures flagged.")

    with tab_diag:
        col1, col2 = st.columns(2)
        with col1:
            render_section_label("Company Registry Statuses")
            status_data = run_query("MATCH (c:Company) RETURN c.status AS status, count(c) AS count")
            if status_data:
                df = pd.DataFrame(status_data)
                chart = alt.Chart(df).mark_arc(innerRadius=40).encode(
                    theta="count:Q",
                    color=alt.Color("status:N", scale=alt.Scale(range=CHART_COLORS), legend=alt.Legend(title=None)),
                    tooltip=["status:N", "count:Q"],
                )
                st.altair_chart(style_chart(chart, 240), use_container_width=True)

        with col2:
            render_section_label("Timeline of Graph Incorporations")
            timeline = run_query("""
                MATCH (c:Company) WHERE c.incorporation_date <> ""
                RETURN left(c.incorporation_date, 4) AS year, count(c) AS count 
                ORDER BY year
            """)
            if timeline:
                df = pd.DataFrame(timeline)
                chart = alt.Chart(df).mark_area(
                    line={"color": "#16756d"},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="rgba(22,117,109,0.45)", offset=0),
                            alt.GradientStop(color="rgba(22,117,109,0.08)", offset=1),
                        ],
                        x1=1,
                        x2=1,
                        y1=1,
                        y2=0,
                    ),
                ).encode(
                    x=alt.X("year:O", title="Year"),
                    y=alt.Y("count:Q", title=None),
                    tooltip=["year:O", "count:Q"],
                )
                st.altair_chart(style_chart(chart, 240), use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            render_section_label("Company Type Mix")
            type_data = run_query("""
                MATCH (c:Company)
                RETURN coalesce(c.company_type, 'unknown') AS company_type, count(c) AS count
                ORDER BY count DESC LIMIT 12
            """)
            if type_data:
                type_df = pd.DataFrame(type_data)
                type_chart = alt.Chart(type_df).mark_bar(cornerRadiusEnd=0).encode(
                    x=alt.X("count:Q", title=None),
                    y=alt.Y("company_type:N", sort="-x", title=None),
                    color=alt.Color("company_type:N", scale=alt.Scale(range=CHART_COLORS), legend=None),
                    tooltip=["company_type:N", "count:Q"],
                )
                st.altair_chart(style_chart(type_chart, 260), use_container_width=True)

        with col4:
            render_section_label("Registered Address Density")
            address_data = run_query("""
                MATCH (c:Company)
                WHERE c.address <> ""
                WITH c.address AS address, count(c) AS count
                WHERE count > 1
                RETURN address, count
                ORDER BY count DESC LIMIT 10
            """)
            if address_data:
                address_df = pd.DataFrame(address_data)
                address_df["short_address"] = address_df["address"].astype(str).str.slice(0, 42)
                address_chart = alt.Chart(address_df).mark_bar(cornerRadiusEnd=0).encode(
                    x=alt.X("count:Q", title=None),
                    y=alt.Y("short_address:N", sort="-x", title=None),
                    color=alt.value(RISK_COLORS["HIGH"]),
                    tooltip=["address:N", "count:Q"],
                )
                st.altair_chart(style_chart(address_chart, 260), use_container_width=True)
            else:
                render_empty_panel("No repeated registered addresses found.")

# ═══════════════════════════════════════════════════════════════
# PAGE 5: WORKSPACE
# ═══════════════════════════════════════════════════════════════
elif page == "Workspace":
    render_workbench_header(
        "Case Workspace",
        "Investigation Workspace",
        "Keep target entities and people close, compare structures side by side, and compile exportable case evidence.",
    )
    
    t_bookmarks, t_comp = st.tabs(["01 · Active Case Bookmarks", "02 · Structure Side-by-Side Deck"])
    
    with t_bookmarks:
        bm_cos = workspace.data.get("bookmarked_companies", [])
        bm_pep = workspace.data.get("bookmarked_people", [])
        
        c1, c2 = st.columns(2)
        with c1:
            render_section_label("Bookmarked Corporations")
            if bm_cos:
                for idx, c in enumerate(bm_cos):
                    row1, row2 = st.columns([5, 2])
                    with row1:
                        st.info(f"{c['name']} (#{c['company_number']})")
                    with row2:
                        if st.button("Delete Target", key=f"del_c_{idx}"):
                            workspace.toggle_bookmark_company(c['company_number'], c['name'])
                            st.rerun()
            else:
                st.info("No bookmarked companies.")
        with c2:
            render_section_label("Bookmarked Persons")
            if bm_pep:
                for idx, p in enumerate(bm_pep):
                    row1, row2 = st.columns([5, 2])
                    with row1:
                        st.info(p)
                    with row2:
                        if st.button("Delete Person", key=f"del_p_{idx}"):
                            workspace.toggle_bookmark_person(p)
                            st.rerun()
            else:
                st.info("No bookmarked people.")
                
    with t_comp:
        bm_cos = workspace.data.get("bookmarked_companies", [])
        if len(bm_cos) < 2:
            st.warning("Select and bookmark at least two companies in Entity Explorer to activate comparison.")
        else:
            targets = [c["name"] for c in bm_cos]
            c_sel1 = st.selectbox("Compare Target A", options=targets, index=0)
            c_sel2 = st.selectbox("Compare Target B", options=targets, index=1 if len(targets) > 1 else 0)
            
            if c_sel1 and c_sel2:
                det1 = run_query("MATCH (c:Company {name: $name}) RETURN c", {"name": c_sel1})[0]["c"]
                det2 = run_query("MATCH (c:Company {name: $name}) RETURN c", {"name": c_sel2})[0]["c"]
                
                risk1 = risk_engine.analyze_company_risks(det1["company_number"])
                risk2 = risk_engine.analyze_company_risks(det2["company_number"])
                
                comp_matrix = {
                    "Registry Property": ["ID Number", "Filing Status", "Risk Metric", "Risk Profile", "Office Address"],
                    c_sel1: [det1.get("company_number"), det1.get("status"), f"{risk1['risk_score']:.1f}%", risk1['risk_tier'], det1.get("address")],
                    c_sel2: [det2.get("company_number"), det2.get("status"), f"{risk2['risk_score']:.1f}%", risk2['risk_tier'], det2.get("address")]
                }

                comparison_df = pd.DataFrame([
                    {"Target": c_sel1, "Score": risk1["risk_score"]},
                    {"Target": c_sel2, "Score": risk2["risk_score"]},
                ])
                render_section_label("Comparison Risk Signal")
                comparison_chart = alt.Chart(comparison_df).mark_bar(cornerRadiusEnd=0).encode(
                    x=alt.X("Score:Q", scale=alt.Scale(domain=[0, 100]), title="Risk score"),
                    y=alt.Y("Target:N", title=None),
                    color=alt.Color("Target:N", scale=alt.Scale(range=["#16756d", "#8f1f2c"]), legend=None),
                    tooltip=["Target:N", alt.Tooltip("Score:Q", format=".1f")],
                )
                st.altair_chart(style_chart(comparison_chart, 150), use_container_width=True)
                st.table(pd.DataFrame(comp_matrix))
                
                # Exporter dossier trigger
                st.markdown("---")
                target_exp = st.selectbox("Compile Case File Export", options=[c_sel1, c_sel2])
                exp_det = det1 if target_exp == c_sel1 else det2
                exp_risk = risk1 if target_exp == c_sel1 else risk2
                exp_off = run_query("MATCH (:Company {company_number: $cn})-[r:HAS_OFFICER]->(o:Officer) RETURN o.name AS name, o.role AS role, r.resigned_date AS resigned_date", {"cn": exp_det["company_number"]})
                exp_pscs = run_query("MATCH (:Company {company_number: $cn})-[r:HAS_PSC]->(p:PSC) RETURN p.name AS name, p.nature_of_control AS nature_of_control", {"cn": exp_det["company_number"]})
                
                evidence_text = workspace.generate_evidence_package(exp_det, exp_off, exp_pscs, exp_risk)
                st.download_button(f"📥 Export Dossier for {target_exp}", data=evidence_text, file_name=f"brief_{exp_det['company_number']}.txt")

# ═══════════════════════════════════════════════════════════════
# PAGE 6: QUERY STUDIO
# ═══════════════════════════════════════════════════════════════
elif page == "Query Studio":
    st.markdown(render_icon_title("terminal", "Neo4j Cypher Query Terminal"), unsafe_allow_html=True)

    st.markdown("**AML reference Cypher scripts:**")

    # Grouped by investigative angle rather than one flat list — each group
    # targets patterns the rule-based risk_engine doesn't already flag on
    # its own, so these are genuinely additive lenses on the same graph.
    TEMPLATE_GROUPS = {
        "Nominee & Control Patterns": {
            "Shared Board Seats Discovery (Nominee Risk)": """MATCH (c1:Company)-[:HAS_OFFICER]->(o:Officer)<-[:HAS_OFFICER]-(c2:Company)
WHERE c1.company_number < c2.company_number
RETURN c1.name AS company_a, c2.name AS company_b, collect(o.name) AS shared_officers, count(o) AS shared_count
ORDER BY shared_count DESC LIMIT 10""",

            "Shadow Control — PSC Absent From Officer Register": """MATCH (c:Company)-[:HAS_PSC]->(p:PSC)
WHERE NOT EXISTS {
    MATCH (c)-[:HAS_OFFICER]->(o:Officer) WHERE o.name = p.name
}
RETURN c.name AS company, c.company_number AS company_number, p.name AS beneficial_owner,
       p.nature_of_control AS control_basis, p.kind AS psc_kind
ORDER BY company LIMIT 10""",

            "Same-Day Mass Appointment (Possible Nominee Batch)": """MATCH (o:Officer)<-[r:HAS_OFFICER]-(c:Company)
WHERE r.appointed_date IS NOT NULL AND r.appointed_date <> ""
WITH o.name AS officer, r.appointed_date AS appointed_on, count(DISTINCT c) AS companies_same_day, collect(c.name)[..6] AS companies
WHERE companies_same_day >= 3
RETURN officer, appointed_on, companies_same_day, companies
ORDER BY companies_same_day DESC LIMIT 10""",
        },
        "Filing & Lifecycle Gaps": {
            "Missing PSC Filing Detections": """MATCH (c:Company) WHERE NOT (c)-[:HAS_PSC]->()
RETURN c.name AS Company_Name, c.company_number AS Number, c.status AS Status, c.incorporation_date AS Incorporated
ORDER BY Incorporated DESC LIMIT 10""",

            "Dissolved Companies With Unretired Control Records": """MATCH (c:Company)
WHERE toLower(c.status) IN ["dissolved", "liquidation", "wound-up", "voluntary-arrangement"]
MATCH (c)-[r:HAS_OFFICER]->(o:Officer)
WHERE r.resigned_date IS NULL OR r.resigned_date = ""
RETURN c.name AS company, c.status AS status, c.company_number AS company_number,
       count(o) AS unretired_officers, collect(o.name)[..5] AS officers
ORDER BY unretired_officers DESC LIMIT 10""",

            "Resigned Officers Still Active Elsewhere (Director Churn)": """MATCH (c1:Company)-[r1:HAS_OFFICER]->(o:Officer)
WHERE r1.resigned_date IS NOT NULL AND r1.resigned_date <> ""
MATCH (o)<-[r2:HAS_OFFICER]-(c2:Company)
WHERE c1 <> c2 AND (r2.resigned_date IS NULL OR r2.resigned_date = "")
RETURN o.name AS officer, c1.name AS resigned_from, r1.resigned_date AS resigned_on,
       c2.name AS still_active_at, c2.status AS active_company_status
ORDER BY r1.resigned_date DESC LIMIT 10""",
        },
        "Geographic & Cluster Patterns": {
            "Registered Address Farms Density": """MATCH (c:Company) WHERE c.address <> ""
WITH c.address AS address, count(c) AS count, collect(c.name)[..3] AS example_companies
WHERE count >= 5
RETURN address AS Address, count AS Density, example_companies AS Examples
ORDER BY Density DESC""",

            "Incorporation Mill Detection (Same Address, Same Day)": """MATCH (c:Company)
WHERE c.address <> "" AND c.incorporation_date <> ""
WITH c.address AS address, c.incorporation_date AS inc_date, collect(c) AS companies
WHERE size(companies) >= 3
UNWIND companies AS c2
RETURN address, inc_date AS incorporation_date, size(companies) AS companies_same_day,
       collect(c2.name)[..6] AS example_companies
ORDER BY companies_same_day DESC LIMIT 10""",

            "Foreign-Controlled PSC Concentration": """MATCH (c:Company)-[:HAS_PSC]->(p:PSC)
WHERE p.nationality IS NOT NULL AND p.nationality <> "" AND p.nationality <> "British"
WITH p.name AS controller, p.nationality AS nationality, count(DISTINCT c) AS companies_controlled, collect(c.name)[..5] AS example_companies
WHERE companies_controlled >= 2
RETURN controller, nationality, companies_controlled, example_companies
ORDER BY companies_controlled DESC LIMIT 10""",
        },
    }

    for group_name, group_templates in TEMPLATE_GROUPS.items():
        render_section_label(group_name)
        for title, cypher in group_templates.items():
            with st.expander(title):
                st.code(cypher, language="cypher")
                if st.button("Load Script", key=f"load_{title}"):
                    st.session_state["active_cypher"] = cypher

    st.markdown("<br>", unsafe_allow_html=True)
    active_cypher = st.text_area("Enter Cypher Query Block", value=st.session_state.get("active_cypher", "MATCH (c:Company) RETURN c.name LIMIT 5"))
    st.session_state["active_cypher"] = active_cypher
    
    if st.button("Execute Query", type="primary") and active_cypher.strip():
        with st.spinner("Executing on AuraDB cluster..."):
            res = run_query(active_cypher)
            if res:
                st.success(f"{len(res)} matching rows returned.")
                df = pd.DataFrame(res)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Exporter
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download Output as CSV", data=csv, file_name="cypher_export.csv", mime="text/csv")
            else:
                st.info("Query returned no records.")
