# ============================================================
# dashboard/theme.py — Intelligence Workbench Design System
# Dark "ops-center" theme: deep void canvas, hairline grid,
# monospace data layer, corner-bracket panels, single-signal
# accent (teal) reserved for risk semantics (red/amber/violet/green).
# ============================================================

# ── Palette (keep in sync with the Python color constants in app.py:
#    CHART_COLORS / RISK_COLORS / COMMUNITY_PALETTE / TYPE_COLORS) ──
PALETTE = {
    "bg":        "#0b0c0a",
    "surface":   "#13140f",
    "surface2":  "#1a1c16",
    "ink":       "#e8eae2",
    "muted":     "#868c7e",
    "line":      "#2a2d24",
    "line_br":   "#3d4134",
    "teal":      "#2bd4b8",
    "teal_dim":  "#1f8a78",
    "red":       "#ff5a5f",
    "amber":     "#ffb648",
    "violet":    "#b48cf0",
    "green":     "#4fd67a",
    "blue":      "#4fc3f7",
}

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Azeret+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
    --bg: #0b0c0a;
    --surface: #13140f;
    --surface-2: #1a1c16;
    --ink: #e8eae2;
    --muted: #868c7e;
    --line: #2a2d24;
    --line-bright: #3d4134;

    --teal: #2bd4b8;
    --teal-dim: #1f8a78;
    --red: #ff5a5f;
    --amber: #ffb648;
    --violet: #b48cf0;
    --green: #4fd67a;
    --blue: #4fc3f7;

    --teal-rgb: 43, 212, 184;
    --red-rgb: 255, 90, 95;
    --amber-rgb: 255, 182, 72;
    --violet-rgb: 180, 140, 240;
    --green-rgb: 79, 214, 122;
    --blue-rgb: 79, 195, 247;

    --mono: 'Azeret Mono', monospace;
    --mono-dense: 'IBM Plex Mono', monospace;
    --sans: 'IBM Plex Sans', sans-serif;
}

* { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: var(--sans);
    color: var(--ink);
}

:focus-visible {
    outline: 2px solid var(--teal) !important;
    outline-offset: 2px !important;
}

.stApp {
    background:
        radial-gradient(ellipse 1200px 700px at 50% -10%, rgba(43, 212, 184, 0.05), transparent 60%),
        repeating-linear-gradient(90deg, rgba(232, 234, 226, 0.035) 0 1px, transparent 1px 64px),
        repeating-linear-gradient(0deg, rgba(232, 234, 226, 0.025) 0 1px, transparent 1px 64px),
        var(--bg);
}

.block-container,
div[data-testid="stMainBlockContainer"] {
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1480px !important;
}

/* ── Kill Streamlit's stock chrome ────────────────────────────
   The default header bar (Deploy button, hamburger menu) floats
   on top of the page and was clipping section titles on scroll.
   This is boilerplate Streamlit furniture, not part of the
   workbench's own UI, so it's removed outright rather than just
   pushed out of the way — full custom chrome, no stock overlay. */
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu,
.stDeployButton,
footer {
    display: none !important;
    height: 0 !important;
    visibility: hidden !important;
}

/* ── Sidebar / Ops Rail ───────────────────────────────────── */
[data-testid="stSidebar"] {
    background:
        repeating-linear-gradient(180deg, rgba(232, 234, 226, 0.02) 0 1px, transparent 1px 52px),
        linear-gradient(180deg, rgba(6, 7, 5, 0.97), rgba(10, 11, 9, 0.99)),
        #060705 !important;
    border-right: 1px solid var(--line);
}

[data-testid="stSidebar"] * {
    color: var(--ink) !important;
}

/* Verified against Streamlit 1.58's own source (Sidebar/styled-components.ts):
   stSidebarHeader is a hard-coded 3.75rem-tall row with a 1rem bottom
   margin, ALWAYS reserved to hold the collapse arrow / mobile close (X)
   control — even with no st.logo() set, so it renders as dead empty
   space above whatever content comes next. That row, not padding on the
   content below it, was the real source of the gap. Shrunk to a
   touch-friendly minimum (44px, the standard min tap-target size) rather
   than removed outright, since removing it would make the control too
   small to tap reliably on mobile. stSidebarContent/UserContent get no
   added padding-top — their real default is already 0 here (only
   nonzero when Streamlit's native multi-page nav is in play, which this
   app doesn't use), so adding our own on top of them was the bug. */
[data-testid="stSidebarHeader"] {
    height: 2.75rem !important;
    min-height: 0 !important;
    margin-bottom: 0.6rem !important;
}

/* The collapse/close (X) control ships as a bare gray Material icon with
   no relationship to this theme — that mismatch, not just proximity, is
   why it read as an awkward stray mark sitting on the brand box. Give it
   an actual designed treatment: a bordered chip matching the sidebar's
   own button language, with the same teal hover state used everywhere
   else, so it reads as an intentional control rather than leftover chrome. */
[data-testid="stSidebarCollapseButton"] button {
    border: 1px solid var(--line) !important;
    border-radius: 3px !important;
    background: var(--surface) !important;
    width: 1.9rem !important;
    height: 1.9rem !important;
    transition: border-color 140ms ease, background 140ms ease !important;
}

[data-testid="stSidebarCollapseButton"] button:hover {
    border-color: var(--teal) !important;
    background: var(--surface-2) !important;
}

[data-testid="stSidebarCollapseButton"] svg {
    color: var(--muted) !important;
    fill: var(--muted) !important;
}

[data-testid="stSidebarCollapseButton"] button:hover svg {
    color: var(--teal) !important;
    fill: var(--teal) !important;
}

[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {
    padding-top: 0 !important;
}

.stRadio label, .stSelectbox label, .stTextArea label, .stTextInput label {
    font-size: 0.74rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted) !important;
}

.stRadio [role="radiogroup"] { gap: 0.15rem; }

.stRadio [role="radio"] {
    position: relative;
    padding: 0.55rem 0.6rem 0.55rem 0.7rem;
    border-radius: 2px;
    border-left: 2px solid transparent;
    transition: background 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
}

.stRadio [role="radio"] p {
    font-family: var(--mono-dense) !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.03em;
}

.stRadio [role="radio"]:hover {
    background: rgba(43, 212, 184, 0.06);
    border-left-color: var(--line-bright);
}

/* Active row gets real visual weight — a filled gradient, a bright
   left rail, an inset glow, and a bold readout — not just a faint
   background tint, so "which page am I on" is unmistakable at a glance. */
.stRadio [role="radio"][aria-checked="true"] {
    background: linear-gradient(90deg, rgba(43, 212, 184, 0.16), rgba(43, 212, 184, 0.02) 85%);
    border-left: 2px solid var(--teal);
    box-shadow: inset 0 0 0 1px rgba(43, 212, 184, 0.18);
}

.stRadio [role="radio"][aria-checked="true"] p {
    color: var(--teal) !important;
    font-weight: 700 !important;
}

/* ── Sidebar brand block (corner-bracket frame, matches intelligence-card) */
.sidebar-brand {
    position: relative;
    text-align: center;
    padding: 18px 10px 15px;
    margin: 2px 2px 14px;
    border: 1px solid var(--line);
    border-radius: 3px;
    background: rgba(43, 212, 184, 0.035);
}

.sidebar-brand::before,
.sidebar-brand::after {
    content: "";
    position: absolute;
    width: 10px;
    height: 10px;
    pointer-events: none;
}

.sidebar-brand::before { top: -1px; left: -1px; border-top: 2px solid var(--teal); border-left: 2px solid var(--teal); }
.sidebar-brand::after { bottom: -1px; right: -1px; border-bottom: 2px solid var(--teal); border-right: 2px solid var(--teal); }

.sidebar-brand-name {
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--teal);
    font-family: var(--mono-dense);
    letter-spacing: 0.2em;
}

.sidebar-brand-tag {
    font-size: 0.64rem;
    color: var(--muted);
    margin-top: 5px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
}

/* ── Sidebar live stat strip ─────────────────────────────────── */
.sidebar-stat-strip {
    display: flex;
    justify-content: space-between;
    gap: 2px;
    margin: 0 2px 18px;
    padding: 11px 2px 13px;
    border-bottom: 1px solid var(--line);
}

.sidebar-stat {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
}

.sidebar-stat .v {
    font-family: var(--mono);
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--ink);
}

.sidebar-stat .l {
    font-size: 0.58rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 3px;
}

.sidebar-stat.alert .v { color: var(--red); }

.status-line {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    color: var(--muted);
    font-size: 0.7rem;
    text-align: center;
    font-family: var(--mono-dense);
    letter-spacing: 0.08em;
    margin-top: 28px;
}

.status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 0 0 rgba(var(--green-rgb), 0.6);
    animation: pulse-dot 2.2s infinite;
    flex-shrink: 0;
}

@keyframes pulse-dot {
    0%   { box-shadow: 0 0 0 0 rgba(var(--green-rgb), 0.55); }
    70%  { box-shadow: 0 0 0 6px rgba(var(--green-rgb), 0); }
    100% { box-shadow: 0 0 0 0 rgba(var(--green-rgb), 0); }
}

/* ── Page header ──────────────────────────────────────────── */
.workbench-hero {
    border-top: 2px solid var(--teal);
    border-bottom: 1px solid var(--line);
    padding: 16px 0 14px 0;
    margin-bottom: 20px;
    animation: reveal 420ms ease both;
}

.workbench-kicker {
    font-family: var(--mono-dense);
    color: var(--muted);
    text-transform: uppercase;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.14em;
}

.workbench-title {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.08;
    margin-top: 6px;
    color: var(--ink);
    font-family: var(--sans);
}

.workbench-subtitle {
    color: var(--muted);
    max-width: 920px;
    margin-top: 8px;
    font-size: 0.96rem;
}

.workbench-meta {
    margin-top: 10px;
    font-family: var(--mono-dense);
    font-size: 0.68rem;
    color: var(--teal-dim);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* ── Intelligence panels (corner-bracket signature) ──────────── */
.intelligence-card {
    position: relative;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 18px;
    margin-bottom: 18px;
    box-shadow: 0 18px 36px rgba(0, 0, 0, 0.35);
    animation: reveal 360ms ease both;
}

.intelligence-card::before,
.intelligence-card::after {
    content: "";
    position: absolute;
    width: 11px;
    height: 11px;
    pointer-events: none;
}

.intelligence-card::before {
    top: -1px; left: -1px;
    border-top: 2px solid var(--teal);
    border-left: 2px solid var(--teal);
}

.intelligence-card::after {
    bottom: -1px; right: -1px;
    border-bottom: 2px solid var(--teal);
    border-right: 2px solid var(--teal);
}

.panel-title {
    font-family: var(--mono-dense);
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--ink);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--line);
    padding-bottom: 9px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.panel-title svg { color: var(--teal); }

.section-label {
    font-family: var(--mono-dense);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 10px 0 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.section-label::before {
    content: "";
    width: 6px;
    height: 6px;
    background: var(--teal-dim);
}

/* ── Metrics ──────────────────────────────────────────────── */
[data-testid="stMetric"] {
    position: relative;
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 3px !important;
    padding: 13px 15px !important;
    box-shadow: 0 10px 22px rgba(0, 0, 0, 0.3) !important;
    transition: border-color 160ms ease, box-shadow 160ms ease !important;
}

[data-testid="stMetric"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 2px;
    background: var(--teal-dim);
}

[data-testid="stMetric"]:hover {
    border-color: var(--line-bright) !important;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.4) !important;
}

[data-testid="stMetric"]:hover::before { background: var(--teal); }

[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em;
    font-weight: 600 !important;
}

[data-testid="stMetricValue"] {
    color: var(--ink) !important;
    font-size: 1.7rem !important;
    font-weight: 600 !important;
    font-family: var(--mono) !important;
}

/* ── Buttons / inputs ─────────────────────────────────────── */
.stButton > button,
.stDownloadButton > button {
    background: var(--surface-2) !important;
    color: var(--ink) !important;
    border: 1px solid var(--line-bright) !important;
    border-radius: 2px !important;
    font-weight: 600 !important;
    font-family: var(--mono-dense) !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.02em;
    min-height: 2.3rem;
    transition: border-color 140ms ease, color 140ms ease, box-shadow 140ms ease !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    border-color: var(--teal) !important;
    color: var(--teal) !important;
    box-shadow: 0 0 0 1px rgba(var(--teal-rgb), 0.25) !important;
}

button[kind="primary"] {
    background: var(--teal) !important;
    border: 1px solid var(--teal) !important;
    color: #06140f !important;
}

button[kind="primary"]:hover {
    background: var(--teal-dim) !important;
    border-color: var(--teal-dim) !important;
    color: #06140f !important;
    box-shadow: 0 0 0 1px rgba(var(--teal-rgb), 0.4) !important;
}

.stTextInput > div > div > input,
.stSelectbox > div > div,
.stTextArea textarea,
.stNumberInput input {
    background-color: var(--surface-2) !important;
    color: var(--ink) !important;
    border: 1px solid var(--line) !important;
    border-radius: 2px !important;
    font-family: var(--mono-dense) !important;
    font-size: 0.86rem !important;
}

.stTextInput > div > div > input:focus,
.stSelectbox > div > div:focus-within,
.stTextArea textarea:focus {
    border-color: var(--teal) !important;
    box-shadow: 0 0 0 1px var(--teal) !important;
}

[data-baseweb="popover"], [data-baseweb="menu"], ul[data-testid="stSelectboxVirtualDropdown"] {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--line-bright) !important;
}

[data-baseweb="menu"] li, [role="option"] {
    color: var(--ink) !important;
    font-family: var(--mono-dense) !important;
    font-size: 0.84rem !important;
}

[data-baseweb="menu"] li:hover, [role="option"]:hover {
    background: rgba(43, 212, 184, 0.1) !important;
}

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 1px solid var(--line);
    margin-bottom: 18px;
    flex-wrap: wrap;
}

.stTabs [data-baseweb="tab"] {
    position: relative;
    background: var(--surface);
    border: 1px solid var(--line);
    border-bottom: none;
    border-radius: 3px 3px 0 0;
    color: var(--muted);
    font-family: var(--mono-dense);
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    padding: 10px 18px !important;
    transition: color 140ms ease, background 140ms ease;
}

.stTabs [data-baseweb="tab"]:hover {
    color: var(--ink);
    background: var(--surface-2);
}

.stTabs [aria-selected="true"] {
    background: var(--surface-2) !important;
    color: var(--teal) !important;
    border-color: var(--line-bright);
}

.stTabs [aria-selected="true"]::before {
    content: "";
    position: absolute;
    top: -1px; left: -1px; right: -1px;
    height: 2px;
    background: var(--teal);
}

.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ── Risk indicators ──────────────────────────────────────── */
.risk-indicator {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 2px;
    font-size: 0.66rem;
    font-weight: 700;
    font-family: var(--mono-dense);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.risk-critical, .risk-cri { background: rgba(var(--red-rgb), 0.14); color: var(--red); border: 1px solid rgba(var(--red-rgb), 0.4); }
.risk-high { background: rgba(var(--amber-rgb), 0.14); color: var(--amber); border: 1px solid rgba(var(--amber-rgb), 0.4); }
.risk-medium, .risk-med { background: rgba(var(--violet-rgb), 0.14); color: var(--violet); border: 1px solid rgba(var(--violet-rgb), 0.4); }
.risk-low { background: rgba(var(--green-rgb), 0.14); color: var(--green); border: 1px solid rgba(var(--green-rgb), 0.4); }

/* ── Audit log ────────────────────────────────────────────── */
.audit-entry {
    border-left: 2px solid var(--line);
    padding-left: 12px;
    margin-bottom: 12px;
    font-size: 0.86rem;
    color: var(--ink);
}

.audit-entry:hover {
    border-left-color: var(--teal);
    background: rgba(43, 212, 184, 0.04);
}

.audit-time {
    font-family: var(--mono-dense);
    color: var(--muted);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}

/* ── Alerts (st.info / warning / success / error) ────────────── */
[data-testid="stAlert"] {
    background: var(--surface) !important;
    border: 1px solid var(--line) !important;
    border-radius: 2px !important;
}

[data-testid="stAlert"] p { color: var(--ink) !important; font-size: 0.88rem !important; }

/* ── Tables / dataframes ──────────────────────────────────── */
div[data-testid="stDataFrame"],
div[data-testid="stTable"] {
    border: 1px solid var(--line);
    border-radius: 3px;
    overflow: hidden;
}

/* ── Composition ratio bars (replaces pie/donut charts) ──────── */
.ratio-bar {
    display: flex;
    width: 100%;
    height: 9px;
    background: var(--line);
    border-radius: 1px;
    overflow: hidden;
    margin-bottom: 10px;
}

.ratio-seg { height: 100%; }

.ratio-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-bottom: 4px;
}

.ratio-chip {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 0.8rem;
    font-family: var(--sans);
    color: var(--ink);
}

.ratio-chip .swatch {
    width: 8px;
    height: 8px;
    border-radius: 1px;
    flex-shrink: 0;
}

.ratio-chip .val {
    font-family: var(--mono-dense);
    color: var(--muted);
    font-size: 0.78rem;
}

/* ── Single-signal badge (replaces single-bar / single-slice charts) ── */
.intel-badge {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    background: var(--surface-2);
    border: 1px solid var(--line);
    border-left: 3px solid var(--teal);
    border-radius: 2px;
    padding: 12px 16px;
    margin-bottom: 10px;
}

.intel-badge .label {
    font-size: 0.82rem;
    color: var(--ink);
    font-weight: 500;
}

.intel-badge .sub {
    font-size: 0.72rem;
    color: var(--muted);
    margin-top: 2px;
}

.intel-badge .value {
    font-family: var(--mono);
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--teal);
    flex-shrink: 0;
}

@keyframes reveal {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
    .intelligence-card, .workbench-hero, .status-dot { animation: none !important; }
}
</style>
"""

SVG_ICONS = {
    "dashboard": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="10" rx="1"/><rect width="7" height="5" x="3" y="15" rx="1"/></svg>""",
    "search": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>""",
    "people": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>""",
    "network": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>""",
    "shield": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 9.7a1 1 0 0 1-.68 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 .76-.97l8-2a1 1 0 0 1 .48 0l8 2A1 1 0 0 1 20 6z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>""",
    "analytics": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>""",
    "workspace": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/></svg>""",
    "terminal": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/></svg>""",
    "heart": """<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>""",
}


def render_icon_title(icon_name: str, title: str) -> str:
    svg = SVG_ICONS.get(icon_name, "")
    return f"""
    <div class="panel-title">
        <span style="display:inline-flex; align-items:center;">{svg}</span>
        <span>{title}</span>
    </div>
    """


def render_status_line(label: str, online: bool = True) -> str:
    color = "var(--green)" if online else "var(--red)"
    return f"""
    <div class="status-line">
        <span class="status-dot" style="background:{color};"></span>
        <span>{label}</span>
    </div>
    """


def render_composition_html(items: list, unit_label: str = "") -> str:
    """
    Render a parts-of-a-whole breakdown as a slim ratio bar + legend chips —
    the Palantir-style replacement for pie/donut charts.

    items: [{"label": str, "count": number, "color": "#hex"}, ...]
    Returns "" if there is no usable data (<=0 total), so the caller can
    fall back to an empty-state panel.
    Falls back to a single intel-badge when only one category has signal —
    a pie/bar chart with one slice conveys nothing a number doesn't.
    """
    clean = [it for it in items if (it.get("count") or 0) > 0]
    total = sum(it["count"] for it in clean)
    if total <= 0:
        return ""

    if len(clean) == 1:
        only = clean[0]
        return render_intel_badge_html(
            label=only["label"],
            value=f"{only['count']:,}{(' ' + unit_label) if unit_label else ''}",
            sub="100% of records — no further breakdown to chart",
        )

    segs, chips = [], []
    for it in clean:
        pct = (it["count"] / total) * 100
        segs.append(f'<div class="ratio-seg" style="width:{pct:.3f}%; background:{it["color"]};"></div>')
        chips.append(
            f'<div class="ratio-chip"><span class="swatch" style="background:{it["color"]};"></span>'
            f'<span>{it["label"]}</span><span class="val">{it["count"]:,} · {pct:.0f}%</span></div>'
        )

    return f"""
    <div class="ratio-bar">{''.join(segs)}</div>
    <div class="ratio-legend">{''.join(chips)}</div>
    """


def render_intel_badge_html(label: str, value: str, sub: str = "") -> str:
    """Single-signal badge: used as the composition fallback for one-category
    data, and for any other place a one-bar chart would otherwise appear."""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f"""
    <div class="intel-badge">
        <div><div class="label">{label}</div>{sub_html}</div>
        <div class="value">{value}</div>
    </div>
    """
