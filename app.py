import hashlib
import io
import math
import re
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


st.set_page_config(
    page_title="Vibra/Suape | Painel de Compras",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)


TRUCK_COMPARTMENT_LITERS = 5000
DATA_VERSION = "pdf-litragem-2026-06-18-vmd-17dias"
PRODUCTS = [
    "Gasolina Comum",
    "Etanol Comum",
    "Gasolina Aditivada",
    "Etanol Aditivado",
    "Gasolina Podium",
    "Diesel Comum",
    "Diesel Aditivado",
]
PRODUCT_COLORS = {
    "Gasolina Comum": "#2dd4bf",
    "Etanol Comum": "#84cc16",
    "Gasolina Aditivada": "#38bdf8",
    "Etanol Aditivado": "#22c55e",
    "Gasolina Podium": "#a78bfa",
    "Diesel Comum": "#f59e0b",
    "Diesel Aditivado": "#fb7185",
}

USERS = {
    "socio": {
        "name": "Sócio Administrador",
        "role": "Sócio",
        "password_hash": hashlib.sha256("suape2026".encode()).hexdigest(),
        "station": None,
    },
    "gerente_recife": {
        "name": "Gerente Casa Caiada",
        "role": "Gerente",
        "password_hash": hashlib.sha256("recife123".encode()).hexdigest(),
        "station": "AP Casa Caiada",
    },
    "gerente_olinda": {
        "name": "Gerente VIP",
        "role": "Gerente",
        "password_hash": hashlib.sha256("olinda123".encode()).hexdigest(),
        "station": "Posto VIP",
    },
}


def inject_css():
    st.markdown(
        """
        <style>
            :root {
                --bg: #0b1120;
                --panel: #111827;
                --panel-soft: #172033;
                --line: rgba(148, 163, 184, 0.22);
                --text: #e5e7eb;
                --muted: #94a3b8;
                --blue: #38bdf8;
                --green: #22c55e;
                --yellow: #f59e0b;
                --red: #ef4444;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(56, 189, 248, .10), transparent 30%),
                    linear-gradient(180deg, #07111f 0%, #0b1120 100%);
                color: var(--text);
            }

            [data-testid="stSidebar"] {
                background: #070d19;
                border-right: 1px solid var(--line);
            }

            h1, h2, h3 {
                letter-spacing: 0;
            }

            .top-title {
                padding: 18px 0 6px 0;
            }

            .subtitle {
                color: var(--muted);
                font-size: 1rem;
                margin-top: -8px;
                margin-bottom: 22px;
            }

            .glass-card {
                background: linear-gradient(180deg, rgba(17, 24, 39, .94), rgba(15, 23, 42, .94));
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 18px;
                box-shadow: 0 18px 60px rgba(0, 0, 0, .22);
            }

            .signal-card {
                border-radius: 8px;
                padding: 18px 20px;
                border: 1px solid rgba(255,255,255,.12);
                margin: 10px 0 18px 0;
            }

            .signal-up {
                background: linear-gradient(135deg, rgba(34, 197, 94, .22), rgba(20, 83, 45, .42));
                border-color: rgba(34, 197, 94, .38);
            }

            .signal-down {
                background: linear-gradient(135deg, rgba(14, 165, 233, .20), rgba(245, 158, 11, .18));
                border-color: rgba(245, 158, 11, .34);
            }

            .signal-neutral {
                background: linear-gradient(135deg, rgba(148, 163, 184, .18), rgba(51, 65, 85, .34));
                border-color: rgba(148, 163, 184, .32);
            }

            .signal-title {
                font-size: 1.12rem;
                font-weight: 700;
                margin-bottom: 4px;
            }

            .signal-text {
                color: #d1d5db;
                margin: 0;
            }

            .small-muted {
                color: var(--muted);
                font-size: .88rem;
            }

            div[data-testid="stMetric"] {
                background: linear-gradient(180deg, rgba(17, 24, 39, .92), rgba(15, 23, 42, .92));
                border: 1px solid var(--line);
                padding: 16px;
                border-radius: 8px;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid var(--line);
                border-radius: 8px;
                overflow: hidden;
            }

            .stButton > button {
                border-radius: 8px;
                border: 1px solid rgba(56, 189, 248, .35);
                background: #0f172a;
                color: #e5e7eb;
                font-weight: 650;
            }

            .stButton > button:hover {
                border-color: rgba(56, 189, 248, .8);
                color: #ffffff;
            }

            .risk-high {
                color: #fecaca;
                font-weight: 700;
            }

            .risk-ok {
                color: #bbf7d0;
                font-weight: 700;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def money(value, decimals=2):
    if value is None:
        return "Indisponível"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def liters(value):
    return f"{float(value):,.0f} L".replace(",", ".")


def normalize_product(value):
    raw = str(value or "").strip().upper()
    raw = re.sub(r"\s+", " ", raw)
    raw = raw.replace(".", "")
    raw = raw.replace(" A PRAZO", "")
    raw = raw.replace(" GRID", "")
    raw = raw.replace(" PETROBRAS PO", "")
    raw = raw.replace(" PETROBRAS PODIUM", "")
    raw = raw.replace(" C ADIT", "")
    aliases = {
        "GASOLINA": "Gasolina Comum",
        "GASOLINA COMUM": "Gasolina Comum",
        "GC": "Gasolina Comum",
        "ETANOL": "Etanol Comum",
        "ETANOL COMUM": "Etanol Comum",
        "ALCOOL": "Etanol Comum",
        "ÁLCOOL": "Etanol Comum",
        "GASOLINA ADITIVADA": "Gasolina Aditivada",
        "GAS ADITIVADA": "Gasolina Aditivada",
        "ETANOL ADITIVADO": "Etanol Aditivado",
        "GASOLINA PODIUM": "Gasolina Podium",
        "PODIUM": "Gasolina Podium",
        "DIESEL": "Diesel Comum",
        "DIESEL S10": "Diesel Comum",
        "DIESEL COMUM": "Diesel Comum",
        "DIESEL S10 COMUM": "Diesel Comum",
        "S500": "Diesel Comum",
        "S10": "Diesel Aditivado",
        "DIESEL B S10 ADITIVADO": "Diesel Aditivado",
        "DIESEL ADITIVADO": "Diesel Aditivado",
        "GASOLINA PREMIUM": "Gasolina Podium",
        "GASOLINA PREMIUM PODIUM": "Gasolina Podium",
    }
    return aliases.get(raw, str(value or "").strip().title())


def round_to_truck_compartment(volume, headroom):
    if volume <= 0 or headroom < TRUCK_COMPARTMENT_LITERS:
        return 0
    rounded = math.ceil(volume / TRUCK_COMPARTMENT_LITERS) * TRUCK_COMPARTMENT_LITERS
    max_load = math.floor(headroom / TRUCK_COMPARTMENT_LITERS) * TRUCK_COMPARTMENT_LITERS
    return max(0, min(rounded, max_load))


def normalize_station_name(value):
    name = re.sub(r"\s+", " ", str(value or "").strip())
    upper = name.upper()
    aliases = {
        "AP CASA CAIADA": "AP Casa Caiada",
        "POSTO DOZE FILIAL II": "Posto Doze Filial II",
        "POSTO ENSEADA DO NORTE": "Posto Enseada do Norte",
        "POSTO VIP": "Posto VIP",
    }
    return aliases.get(upper, name.title())


def default_network():
    return {
        "AP Casa Caiada": {
            "city": "Olinda",
            "tanks": {
                "Etanol Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 974.97},
                "Gasolina Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 1980.89},
            },
        },
        "Posto Doze Filial II": {
            "city": "Pernambuco",
            "tanks": {
                "Gasolina Aditivada": {"capacity": 15000.0, "stock": 0.0, "vmd": 273.69},
                "Diesel Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 810.59},
                "Etanol Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 1893.59},
                "Gasolina Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 3250.70},
            },
        },
        "Posto Enseada do Norte": {
            "city": "Pernambuco",
            "tanks": {
                "Gasolina Podium": {"capacity": 15000.0, "stock": 0.0, "vmd": 214.11},
                "Diesel Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 374.59},
                "Gasolina Aditivada": {"capacity": 15000.0, "stock": 0.0, "vmd": 385.87},
                "Etanol Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 2068.20},
                "Gasolina Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 3889.52},
            },
        },
        "Posto VIP": {
            "city": "Pernambuco",
            "tanks": {
                "Diesel Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 141.79},
                "Gasolina Aditivada": {"capacity": 15000.0, "stock": 0.0, "vmd": 212.77},
                "Etanol Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 1986.53},
                "Gasolina Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 3435.59},
            },
        },
    }


def init_state():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    if st.session_state.get("data_version") != DATA_VERSION:
        st.session_state.network = default_network()
        st.session_state.data_version = DATA_VERSION
    st.session_state.setdefault("network", default_network())
    st.session_state.setdefault("market_cache", None)
    st.session_state.setdefault("last_market_update", None)


def login_screen():
    inject_css()
    left, mid, right = st.columns([1.2, 1, 1.2])
    with mid:
        st.markdown('<div class="top-title">', unsafe_allow_html=True)
        st.title("⛽ Vibra/Suape")
        st.markdown(
            '<p class="subtitle">Painel corporativo para decisão de compras, estoque e autonomia da rede.</p>',
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Usuário", placeholder="socio")
            password = st.text_input("Senha", type="password", placeholder="suape2026")
            submitted = st.form_submit_button("Entrar no painel", use_container_width=True)

        if submitted:
            user = USERS.get(username.strip())
            if user and user["password_hash"] == hash_password(password):
                st.session_state.authenticated = True
                st.session_state.user = {"username": username.strip(), **user}
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")


def network_records(station_filter=None):
    rows = []
    for station, payload in st.session_state.network.items():
        if station_filter and station != station_filter:
            continue
        for product, tank in payload["tanks"].items():
            capacity = max(float(tank.get("capacity", 0)), 0)
            stock = max(float(tank.get("stock", 0)), 0)
            vmd = max(float(tank.get("vmd", 0)), 0)
            autonomy = stock / vmd if vmd > 0 else 0
            occupancy = stock / capacity if capacity > 0 else 0
            rows.append(
                {
                    "Posto": station,
                    "Cidade": payload.get("city", ""),
                    "Produto": product,
                    "Capacidade (L)": capacity,
                    "Estoque Atual (L)": stock,
                    "VMD (L/dia)": vmd,
                    "Dias de Autonomia": autonomy,
                    "Ocupação": occupancy,
                }
            )
    return pd.DataFrame(rows)


def fetch_market_data():
    if yf is None:
        return {
            "usd": None,
            "brent": None,
            "usd_delta": 0,
            "brent_delta": 0,
            "trend": "NEUTRA",
            "source": "Biblioteca yfinance não instalada.",
        }

    tickers = {"usd": "USDBRL=X", "brent": "BZ=F"}
    output = {}
    deltas = []

    for key, ticker in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="7d", interval="1d")
            if hist.empty or len(hist["Close"].dropna()) < 2:
                output[key] = None
                output[f"{key}_delta"] = 0
                continue
            closes = hist["Close"].dropna()
            last = float(closes.iloc[-1])
            previous = float(closes.iloc[-2])
            delta = ((last - previous) / previous) * 100 if previous else 0
            output[key] = last
            output[f"{key}_delta"] = delta
            deltas.append(delta)
        except Exception:
            output[key] = None
            output[f"{key}_delta"] = 0

    weighted_delta = sum(deltas) / len(deltas) if deltas else 0
    if weighted_delta >= 0.35:
        trend = "ALTA"
    elif weighted_delta <= -0.35:
        trend = "BAIXA"
    else:
        trend = "NEUTRA"

    output["trend"] = trend
    output["source"] = "Yahoo Finance via yfinance"
    return output


def get_market_data(force=False):
    if force or st.session_state.market_cache is None:
        st.session_state.market_cache = fetch_market_data()
        st.session_state.last_market_update = datetime.now().strftime("%d/%m/%Y %H:%M")
    return st.session_state.market_cache


def purchase_recommendation(row, trend):
    capacity = float(row["Capacidade (L)"])
    stock = float(row["Estoque Atual (L)"])
    vmd = float(row["VMD (L/dia)"])
    headroom = max(capacity - stock, 0)
    critical_volume = max((vmd * 3) - stock, 0)

    if trend == "ALTA":
        volume = headroom
        action = "Comprar imediato: completar tanque"
    elif trend == "BAIXA":
        volume = min(headroom, critical_volume)
        action = "Adiar: comprar só segurança" if volume > 0 else "Adiar pedido"
    else:
        target_stock = min(capacity, vmd * 5)
        volume = max(target_stock - stock, 0)
        action = "Comprar moderado: manter 5 dias"

    autonomy = float(row["Dias de Autonomia"])
    if autonomy < 2:
        action = "Crítico: comprar hoje"
        volume = max(volume, min(headroom, (vmd * 3) - stock))

    rounded_volume = round_to_truck_compartment(max(volume, 0), headroom)
    if rounded_volume == 0 and volume > 0:
        action = "Aguardar: não fecha 5.000 L"
    return rounded_volume, action


def weekly_priority(autonomy, volume):
    if autonomy < 2:
        return "Comprar hoje"
    if autonomy < 4:
        return "Comprar na semana"
    if volume >= TRUCK_COMPARTMENT_LITERS:
        return "Planejar compra"
    return "Sem compra"


def next_receiving_days(days=7):
    start = datetime.now().date() + timedelta(days=1)
    labels = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        weekday = day.weekday()
        weekday_names = [
            "Segunda-feira",
            "Terça-feira",
            "Quarta-feira",
            "Quinta-feira",
            "Sexta-feira",
            "Sábado",
            "Domingo",
        ]
        labels.append(
            {
                "date": day,
                "label": f"{weekday_names[weekday]} {day.strftime('%d/%m')}",
                "operates": weekday != 6,
            }
        )
    return labels


def build_weekly_receiving_schedule(exec_df):
    days = next_receiving_days()
    operational_days = [day for day in days if day["operates"]]
    candidates = exec_df[
        (exec_df["Volume Recomendado para Compra (L)"] >= TRUCK_COMPARTMENT_LITERS)
        & (exec_df["Prioridade da Semana"].isin(["Comprar hoje", "Comprar na semana", "Planejar compra"]))
    ].copy()

    priority_order = {"Comprar hoje": 0, "Comprar na semana": 1, "Planejar compra": 2}
    candidates["Ordem"] = candidates["Prioridade da Semana"].map(priority_order).fillna(9)
    candidates = candidates.sort_values(["Ordem", "Dias de Autonomia", "Posto", "Produto"])

    rows = []
    for i, (_, item) in enumerate(candidates.iterrows()):
        day = operational_days[i % len(operational_days)] if operational_days else days[0]
        rows.append(
            {
                "Chegada Prevista": day["label"],
                "Data": day["date"].strftime("%d/%m/%Y"),
                "Posto": item["Posto"],
                "Produto": item["Produto"],
                "Comprar (L)": item["Volume Recomendado para Compra (L)"],
                "Compartimentos": int(item["Volume Recomendado para Compra (L)"] / TRUCK_COMPARTMENT_LITERS),
                "Autonomia Atual": item["Dias de Autonomia"],
                "Prioridade": item["Prioridade da Semana"],
                "Observação": item["Ação Requerida"],
            }
        )

    schedule = pd.DataFrame(rows)
    calendar = pd.DataFrame(
        [
            {
                "Dia": day["label"],
                "Data": day["date"].strftime("%d/%m/%Y"),
                "Status Base": "Sem operação" if not day["operates"] else "Operando",
            }
            for day in days
        ]
    )
    return schedule, calendar


def build_executive_table(df, trend):
    if df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in df.iterrows():
        volume, action = purchase_recommendation(row, trend)
        rows.append(
            {
                "Posto": row["Posto"],
                "Produto": row["Produto"],
                "Dias de Autonomia": round(float(row["Dias de Autonomia"]), 1),
                "Volume Recomendado para Compra (L)": round(volume, 0),
                "Múltiplo Caminhão": f"{TRUCK_COMPARTMENT_LITERS:,} L".replace(",", "."),
                "Prioridade da Semana": weekly_priority(float(row["Dias de Autonomia"]), volume),
                "Ação Requerida": action,
            }
        )
    return pd.DataFrame(rows).sort_values(["Dias de Autonomia", "Posto", "Produto"])


def donut_chart(station, station_df):
    fig = go.Figure()
    for _, row in station_df.iterrows():
        occupancy = min(max(float(row["Ocupação"]), 0), 1)
        fig.add_trace(
            go.Pie(
                labels=[row["Produto"], "Livre"],
                values=[occupancy, 1 - occupancy],
                hole=0.68,
                marker_colors=[PRODUCT_COLORS.get(row["Produto"], "#38bdf8"), "#1f2937"],
                textinfo="none",
                name=row["Produto"],
                domain={"row": 0, "column": list(station_df["Produto"]).index(row["Produto"])},
            )
        )

    fig.update_layout(
        title={"text": station, "font": {"color": "#e5e7eb", "size": 18}},
        grid={"rows": 1, "columns": len(station_df), "pattern": "independent"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=250,
        margin=dict(l=10, r=10, t=42, b=10),
        showlegend=False,
        annotations=[
            dict(
                text=f"{int(min(max(row['Ocupação'], 0), 1) * 100)}%<br>{row['Produto'][:3]}",
                x=(i + 0.5) / len(station_df),
                y=0.5,
                font=dict(size=14, color="#e5e7eb"),
                showarrow=False,
            )
            for i, (_, row) in enumerate(station_df.iterrows())
        ],
    )
    return fig


def extract_text_from_upload(uploaded_file):
    suffix = uploaded_file.name.lower().split(".")[-1]
    data = uploaded_file.getvalue()
    if suffix == "txt":
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Não consegui ler o TXT. Salve em UTF-8 e tente novamente.")
    if suffix == "pdf":
        if PdfReader is None:
            raise ValueError("A biblioteca pypdf não está instalada. Confira o requirements.txt.")
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    raise ValueError("Envie um arquivo TXT ou PDF.")


def parse_station_import_text(text):
    stations = {}
    current_station = None
    current_city = "Pernambuco"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        clean = re.sub(r"\s+", " ", line)
        upper = clean.upper()

        station_match = re.match(r"^(POSTO|UNIDADE)\s*[:\-]?\s+(.+)$", clean, flags=re.I)
        city_match = re.match(r"^(CIDADE|MUNICIPIO|MUNICÍPIO)\s*[:\-]?\s+(.+)$", clean, flags=re.I)
        product_match = re.match(
            r"^([A-ZÁÉÍÓÚÂÊÔÃÕÇ\s]+?)\s+([\d\.,]+)\s*(L|LTS|LITROS)?(?:\s+VMD\s+([\d\.,]+))?$",
            upper,
            flags=re.I,
        )

        if station_match:
            current_station = station_match.group(2).strip().title()
            current_city = "Pernambuco"
            stations.setdefault(current_station, {"city": current_city, "tanks": {}})
            continue
        if city_match and current_station:
            current_city = city_match.group(2).strip().title()
            stations[current_station]["city"] = current_city
            continue
        if product_match and current_station:
            product = normalize_product(product_match.group(1))
            capacity = float(product_match.group(2).replace(".", "").replace(",", "."))
            vmd = (
                float(product_match.group(4).replace(".", "").replace(",", "."))
                if product_match.group(4)
                else max(capacity / 6, 1)
            )
            if product in PRODUCTS:
                stations[current_station]["tanks"][product] = {
                    "capacity": capacity,
                    "stock": 0.0,
                    "vmd": vmd,
                }
            continue

    return {name: payload for name, payload in stations.items() if payload["tanks"]}


def merge_imported_stations(imported):
    for station, payload in imported.items():
        st.session_state.network.setdefault(station, {"city": payload["city"], "tanks": {}})
        st.session_state.network[station]["city"] = payload["city"]
        for product, tank in payload["tanks"].items():
            existing = st.session_state.network[station]["tanks"].get(product, {})
            st.session_state.network[station]["tanks"][product] = {
                "capacity": float(tank["capacity"]),
                "stock": float(existing.get("stock", 0)),
                "vmd": float(tank["vmd"]),
            }


def parse_brazilian_number(value):
    return float(str(value).replace(".", "").replace(",", "."))


def parse_stock_line(line):
    refs = "000004|004118|000003|000002|000222|000257|000106|000129|000132|000131|000130"
    ref_match = re.search(rf"({refs})\s+[\d,]+", line)
    if not ref_match:
        return None

    before_ref = line[: ref_match.start()].strip()
    quantity_match = re.search(r"(\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,2},\d{2})$", before_ref)
    if not quantity_match:
        return None

    quantity_text = quantity_match.group(1)
    integer_part = quantity_text.split(",", 1)[0]
    if "." in integer_part and len(integer_part.split(".", 1)[0]) == 3:
        quantity_text = quantity_text[1:]
    elif "." not in integer_part and len(integer_part) == 2 and quantity_match.start() > 0:
        quantity_text = quantity_text[1:]

    before_quantity = before_ref[: quantity_match.start()].strip()
    product_part = re.split(r"\s+\d[\d\.]*,\d{2,4}\s+", before_quantity, maxsplit=1)[0].strip()
    if not product_part:
        return None

    product = normalize_product(product_part)
    if product not in PRODUCTS:
        return None

    return product, parse_brazilian_number(quantity_text)


def parse_stock_import_text(text):
    stocks = {}
    current_station = None
    pending_line = ""

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line.strip())
        if not line:
            continue

        station_match = re.match(r"^(.+?)Filial:$", line)
        if station_match:
            current_station = normalize_station_name(station_match.group(1))
            stocks.setdefault(current_station, {})
            pending_line = ""
            continue

        if not current_station:
            continue

        upper = line.upper()
        if (
            "PRODUTO CUSTO" in upper
            or "TOTAL" in upper
            or "USUÁRIO" in upper
            or "RELATÓRIO" in upper
            or "GRUPO DE PRODUTO" in upper
        ):
            pending_line = ""
            continue

        candidate = f"{pending_line} {line}".strip() if pending_line else line
        parsed = parse_stock_line(candidate)
        if parsed:
            product, quantity = parsed
            stocks[current_station][product] = stocks[current_station].get(product, 0.0) + quantity
            pending_line = ""
        elif re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9\s\.]+$", upper):
            pending_line = candidate
        else:
            pending_line = ""

    return {station: payload for station, payload in stocks.items() if payload}


def apply_stock_import(stocks):
    updated = 0
    ignored = []
    for station, products in stocks.items():
        if station not in st.session_state.network:
            ignored.append(f"{station} / posto não cadastrado")
            continue
        for product, stock in products.items():
            if product not in st.session_state.network[station]["tanks"]:
                ignored.append(f"{station} / {product}")
                continue
            capacity = st.session_state.network[station]["tanks"][product]["capacity"]
            st.session_state.network[station]["tanks"][product]["stock"] = min(max(float(stock), 0), capacity)
            updated += 1
    return updated, ignored


def highlight_priority(row):
    priority = row.get("Prioridade da Semana", "")
    if priority == "Comprar hoje":
        return ["background-color: rgba(239, 68, 68, .28); color: #fee2e2; font-weight: 700"] * len(row)
    if priority == "Comprar na semana":
        return ["background-color: rgba(245, 158, 11, .24); color: #fef3c7; font-weight: 700"] * len(row)
    if priority == "Planejar compra":
        return ["background-color: rgba(56, 189, 248, .18); color: #dbeafe"] * len(row)
    return [""] * len(row)


def filter_table(df, key, label="Filtros da planilha"):
    if df.empty:
        return df

    filtered = df.copy()
    with st.expander(label, expanded=False):
        selected_columns = st.multiselect(
            "Colunas para filtrar",
            list(filtered.columns),
            default=[],
            key=f"{key}_columns",
        )

        for column in selected_columns:
            series = filtered[column]
            if pd.api.types.is_numeric_dtype(series):
                min_value = float(series.min())
                max_value = float(series.max())
                if min_value == max_value:
                    st.caption(f"{column}: todos os registros têm valor {min_value:g}.")
                    continue
                selected_range = st.slider(
                    column,
                    min_value=min_value,
                    max_value=max_value,
                    value=(min_value, max_value),
                    key=f"{key}_{column}_range",
                )
                filtered = filtered[filtered[column].between(selected_range[0], selected_range[1])]
            else:
                values = sorted([str(value) for value in series.dropna().unique()])
                selected_values = st.multiselect(
                    column,
                    values,
                    default=values,
                    key=f"{key}_{column}_values",
                )
                filtered = filtered[filtered[column].astype(str).isin(selected_values)]

    return filtered


def header(title, subtitle):
    st.markdown('<div class="top-title">', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="subtitle">{subtitle}</p>', unsafe_allow_html=True)


def allowed_station():
    user = st.session_state.user
    if user["role"] == "Gerente":
        return user["station"]
    return None


def render_sidebar():
    user = st.session_state.user
    st.sidebar.title("⛽ Suprimento PE")
    st.sidebar.caption(f"{user['name']} | {user['role']}")

    if user["role"] == "Sócio":
        pages = [
            "Painel de Compras",
            "Cadastro de Postos e Tanques",
            "Configurações e Vendas",
        ]
    else:
        pages = ["Painel de Consulta"]

    page = st.sidebar.radio("Navegação", pages, label_visibility="collapsed")
    st.sidebar.divider()
    st.sidebar.caption("Usuários internos")
    st.sidebar.code("socio / suape2026\n gerentes: recife123, olinda123", language="text")

    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()

    return page


def render_market_signal(market):
    trend = market["trend"]
    if trend == "ALTA":
        css = "signal-up"
        title = "📈 Tendência de ALTA: compra imediata recomendada"
        text = "Complete os tanques com o volume máximo suportado para travar preço antes de novo repasse em Suape."
    elif trend == "BAIXA":
        css = "signal-down"
        title = "📉 Tendência de BAIXA: adiar pedido quando possível"
        text = "Compre apenas o volume crítico de segurança: 2 dias de lead-time Vibra mais 1 dia de margem operacional."
    else:
        css = "signal-neutral"
        title = "➖ Tendência NEUTRA: manter disciplina de cobertura"
        text = "Sem sinal macro forte. A recomendação usa alvo operacional moderado de 5 dias de cobertura."

    st.markdown(
        f"""
        <div class="signal-card {css}">
            <div class="signal-title">{title}</div>
            <p class="signal-text">{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_main_panel(read_only=False):
    station_filter = allowed_station() if read_only else None
    title = "📊 Painel de Consulta" if read_only else "📊 Painel de Compras Inteligente"
    subtitle = (
        "Visão operacional do posto, autonomia e risco de ruptura."
        if read_only
        else "Visão de sócio para decisão rápida de compra, preço e cobertura da rede."
    )
    header(title, subtitle)

    df = network_records(station_filter)
    market = get_market_data()
    trend = market["trend"]

    total_stock = df["Estoque Atual (L)"].sum() if not df.empty else 0
    avg_autonomy = df["Dias de Autonomia"].mean() if not df.empty else 0
    risk_count = int((df["Dias de Autonomia"] < 3).sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🛢️ Estoque Total", liters(total_stock))
    c2.metric("📆 Cobertura Média", f"{avg_autonomy:.1f} dias")
    c3.metric("⚠️ Alertas de Risco", risk_count)
    c4.metric("🌎 Tendência Macro", trend)

    with st.expander("Medição física do dia", expanded=not read_only):
        if read_only:
            st.caption("Perfil de consulta. Medições e compras são editadas pelo sócio.")
        edit_df = df[["Posto", "Produto", "Estoque Atual (L)", "Capacidade (L)", "VMD (L/dia)"]].copy()
        edited = st.data_editor(
            edit_df,
            hide_index=True,
            use_container_width=True,
            disabled=read_only,
            column_config={
                "Estoque Atual (L)": st.column_config.NumberColumn(min_value=0, step=100, format="%.0f"),
                "Capacidade (L)": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                "VMD (L/dia)": st.column_config.NumberColumn(disabled=True, format="%.0f"),
            },
        )
        if not read_only and st.button("Salvar medições", type="primary"):
            for _, row in edited.iterrows():
                station = row["Posto"]
                product = row["Produto"]
                capacity = st.session_state.network[station]["tanks"][product]["capacity"]
                st.session_state.network[station]["tanks"][product]["stock"] = min(
                    max(float(row["Estoque Atual (L)"]), 0), capacity
                )
            st.success("Medições atualizadas.")
            st.rerun()

    st.subheader("Mercado online")
    m1, m2, m3, m4 = st.columns([1, 1, 1, 1.1])
    m1.metric("💵 Dólar USD/BRL", money(market.get("usd")), f"{market.get('usd_delta', 0):.2f}%")
    m2.metric("🛢️ Brent", money(market.get("brent")), f"{market.get('brent_delta', 0):.2f}%")
    m3.metric("Sinal", trend)
    if m4.button("Atualizar mercado", use_container_width=True):
        get_market_data(force=True)
        st.rerun()
    st.caption(f"Fonte: {market['source']} | Última atualização: {st.session_state.last_market_update or 'não executada'}")
    render_market_signal(market)

    st.subheader("Ocupação física dos tanques")
    for station in df["Posto"].drop_duplicates().tolist():
        station_df = df[df["Posto"] == station].reset_index(drop=True)
        st.plotly_chart(donut_chart(station, station_df), use_container_width=True)

    st.subheader("Saída executiva de compra")
    exec_df = build_executive_table(df, trend)
    weekly_schedule, base_calendar = build_weekly_receiving_schedule(exec_df)

    st.markdown("#### Programação semanal de recebimento")
    st.caption("Janela móvel de 7 dias a partir de amanhã. Domingo aparece como sem operação da base.")
    st.dataframe(
        base_calendar,
        hide_index=True,
        use_container_width=True,
    )
    if weekly_schedule.empty:
        st.info("Nenhuma compra programada na semana com volume mínimo de 5.000 L.", icon="✅")
    else:
        weekly_schedule_view = filter_table(weekly_schedule, "weekly_schedule", "Filtros da programação semanal")
        st.dataframe(
            weekly_schedule_view,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Comprar (L)": st.column_config.NumberColumn(format="%.0f"),
                "Autonomia Atual": st.column_config.NumberColumn(format="%.1f"),
            },
        )

    week_df = exec_df[
        exec_df["Prioridade da Semana"].isin(["Comprar hoje", "Comprar na semana"])
        & (exec_df["Volume Recomendado para Compra (L)"] >= TRUCK_COMPARTMENT_LITERS)
    ].copy()
    if not week_df.empty:
        st.markdown("#### Ênfase da semana")
        for _, row in week_df.head(8).iterrows():
            st.markdown(
                f"""
                <div class="signal-card signal-up">
                    <div class="signal-title">{row['Prioridade da Semana']} · {row['Posto']} · {row['Produto']}</div>
                    <p class="signal-text">Comprar <b>{liters(row['Volume Recomendado para Compra (L)'])}</b> em múltiplos de {TRUCK_COMPARTMENT_LITERS:,} L. Autonomia atual: {row['Dias de Autonomia']:.1f} dias.</p>
                </div>
                """.replace(",", "."),
                unsafe_allow_html=True,
            )
    else:
        st.info("Nenhum produto fecha compra mínima de 5.000 L com prioridade nesta semana.", icon="✅")

    exec_df_view = filter_table(exec_df, "executive_table", "Filtros da saída executiva")
    st.dataframe(
        exec_df_view.style.apply(highlight_priority, axis=1),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Dias de Autonomia": st.column_config.NumberColumn(format="%.1f"),
            "Volume Recomendado para Compra (L)": st.column_config.NumberColumn(format="%.0f"),
        },
    )


def render_network_admin():
    header(
        "🏪 Cadastro de Postos e Tanques",
        "Gerencie a rede, capacidades, estoque inicial e venda média diária por produto.",
    )

    with st.expander("Cadastrar novo posto", expanded=True):
        with st.form("new_station_form"):
            name = st.text_input("Nome do posto", placeholder="Posto Pina")
            city = st.text_input("Cidade", placeholder="Recife")
            selected_products = st.multiselect(
                "Produtos vendidos neste posto",
                PRODUCTS,
                default=["Gasolina Comum", "Etanol Comum"],
            )
            cols = st.columns(2)
            capacities = {}
            vmds = {}
            for i, product in enumerate(selected_products):
                with cols[i % 2]:
                    capacities[product] = st.number_input(
                        f"Capacidade {product} (L)", min_value=0.0, value=30000.0, step=1000.0
                    )
                    vmds[product] = st.number_input(
                        f"VMD {product} (L/dia)", min_value=0.0, value=2500.0, step=100.0
                    )
            submitted = st.form_submit_button("Cadastrar posto", type="primary")

        if submitted:
            clean_name = name.strip()
            if not clean_name:
                st.error("Informe o nome do posto.")
            elif clean_name in st.session_state.network:
                st.error("Já existe um posto com esse nome.")
            elif not selected_products:
                st.error("Selecione pelo menos um produto.")
            else:
                st.session_state.network[clean_name] = {
                    "city": city.strip() or "Pernambuco",
                    "tanks": {
                        product: {
                            "capacity": float(capacities[product]),
                            "stock": 0.0,
                            "vmd": float(vmds[product]),
                        }
                        for product in PRODUCTS
                    },
                }
                st.success("Posto cadastrado.")
                st.rerun()

    with st.expander("Importar cadastro por TXT ou PDF", expanded=False):
        st.caption(
            "Formato simples: `POSTO Casa Caiada`, `CIDADE Olinda`, e uma linha por produto, "
            "exemplo `GASOLINA 30000 VMD 2500`. Se não informar VMD, o app estima pela capacidade."
        )
        st.code(
            "POSTO Casa Caiada\n"
            "CIDADE Olinda\n"
            "GASOLINA 30000 VMD 2500\n"
            "ETANOL 20000 VMD 1600\n"
            "\n"
            "POSTO Piedade\n"
            "GASOLINA ADITIVADA 15000 VMD 900\n"
            "DIESEL ADITIVADO 25000 VMD 1800",
            language="text",
        )
        upload_network = st.file_uploader("Arquivo de cadastro TXT ou PDF", type=["txt", "pdf"], key="network_import")
        if upload_network is not None:
            try:
                text = extract_text_from_upload(upload_network)
                imported = parse_station_import_text(text)
                if not imported:
                    st.warning("Não encontrei postos/produtos válidos no arquivo.")
                else:
                    preview_rows = []
                    for station, payload in imported.items():
                        for product, tank in payload["tanks"].items():
                            preview_rows.append(
                                {
                                    "Posto": station,
                                    "Cidade": payload["city"],
                                    "Produto": product,
                                    "Capacidade (L)": tank["capacity"],
                                    "VMD (L/dia)": tank["vmd"],
                                }
                            )
                    st.dataframe(pd.DataFrame(preview_rows), hide_index=True, use_container_width=True)
                    if st.button("Importar cadastro para a rede", type="primary"):
                        merge_imported_stations(imported)
                        st.success("Cadastro importado.")
                        st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível importar o cadastro: {exc}")

    st.subheader("Editar capacidades, estoque e VMD")
    df = network_records()
    edited = st.data_editor(
        df[["Posto", "Cidade", "Produto", "Capacidade (L)", "Estoque Atual (L)", "VMD (L/dia)"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Capacidade (L)": st.column_config.NumberColumn(min_value=0, step=1000, format="%.0f"),
            "Estoque Atual (L)": st.column_config.NumberColumn(min_value=0, step=100, format="%.0f"),
            "VMD (L/dia)": st.column_config.NumberColumn(min_value=0, step=100, format="%.0f"),
        },
    )

    if st.button("Salvar alterações da rede", type="primary"):
        new_network = {}
        for _, row in edited.iterrows():
            station = str(row["Posto"]).strip()
            product = str(row["Produto"]).strip()
            if product not in PRODUCTS or not station:
                continue
            new_network.setdefault(station, {"city": str(row["Cidade"]).strip(), "tanks": {}})
            capacity = max(float(row["Capacidade (L)"]), 0)
            stock = min(max(float(row["Estoque Atual (L)"]), 0), capacity)
            vmd = max(float(row["VMD (L/dia)"]), 0)
            new_network[station]["tanks"][product] = {
                "capacity": capacity,
                "stock": stock,
                "vmd": vmd,
            }

        st.session_state.network = new_network
        st.success("Rede atualizada.")
        st.rerun()


def read_sales_file(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Formato não suportado. Envie CSV, XLSX ou XLS.")


def normalize_sales_columns(df):
    lower_map = {str(col).strip().lower(): col for col in df.columns}
    station_col = lower_map.get("posto") or lower_map.get("station")
    product_col = lower_map.get("produto") or lower_map.get("product")
    liters_col = (
        lower_map.get("litros")
        or lower_map.get("volume")
        or lower_map.get("volume_litros")
        or lower_map.get("venda_litros")
    )
    date_col = lower_map.get("data") or lower_map.get("date")
    missing = []
    if not station_col:
        missing.append("Posto")
    if not product_col:
        missing.append("Produto")
    if not liters_col:
        missing.append("Litros/Volume")
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(missing)}.")

    out = df.rename(
        columns={
            station_col: "Posto",
            product_col: "Produto",
            liters_col: "Litros",
            **({date_col: "Data"} if date_col else {}),
        }
    ).copy()
    out["Litros"] = pd.to_numeric(out["Litros"], errors="coerce").fillna(0)
    out["Produto"] = out["Produto"].apply(normalize_product)
    out["Posto"] = out["Posto"].astype(str).str.strip()
    if "Data" in out.columns:
        out["Data"] = pd.to_datetime(out["Data"], errors="coerce")
    return out


def apply_sales_upload(df, last_30_days=True):
    if last_30_days and "Data" in df.columns and df["Data"].notna().any():
        latest = df["Data"].max()
        cutoff = latest - pd.Timedelta(days=29)
        df = df[df["Data"].between(cutoff, latest)].copy()

    if "Data" in df.columns and df["Data"].notna().any():
        days = df.groupby(["Posto", "Produto"])["Data"].nunique().reset_index(name="dias")
        volume = df.groupby(["Posto", "Produto"])["Litros"].sum().reset_index(name="litros")
        grouped = volume.merge(days, on=["Posto", "Produto"], how="left")
        grouped["vmd"] = grouped["litros"] / grouped["dias"].clip(lower=1)
    else:
        grouped = df.groupby(["Posto", "Produto"])["Litros"].mean().reset_index(name="vmd")

    updated = 0
    ignored = []
    for _, row in grouped.iterrows():
        station = row["Posto"]
        product = row["Produto"]
        if station in st.session_state.network and product in st.session_state.network[station]["tanks"]:
            st.session_state.network[station]["tanks"][product]["vmd"] = max(float(row["vmd"]), 0)
            updated += 1
        else:
            ignored.append(f"{station} / {product}")
    return updated, ignored, grouped


def render_settings_sales():
    header(
        "⚙️ Configurações e Vendas",
        "Importe relatórios de vendas, recalcule VMD e consulte os acessos internos.",
    )

    st.subheader("Upload de relatórios")
    st.caption("Formato esperado: colunas `Posto`, `Produto`, `Litros` ou `Volume`, e opcionalmente `Data`.")
    last_30_days = st.toggle("Usar somente os últimos 30 dias do relatório", value=True)
    uploaded = st.file_uploader("Arraste um CSV ou Excel de vendas", type=["csv", "xlsx", "xls"])
    if uploaded is not None:
        try:
            raw = read_sales_file(uploaded)
            normalized = normalize_sales_columns(raw)
            updated, ignored, grouped = apply_sales_upload(normalized, last_30_days=last_30_days)
            st.success(f"VMD recalculada para {updated} combinação(ões) de posto/produto.")
            if ignored:
                st.warning("Linhas ignoradas por posto/produto não cadastrado: " + "; ".join(ignored[:8]))
            st.dataframe(grouped, hide_index=True, use_container_width=True)
        except Exception as exc:
            st.error(f"Não foi possível processar o arquivo: {exc}")

    st.divider()
    st.subheader("Importar estoque atual")
    st.caption(
        "Envie a Relação de Estoque em PDF ou TXT. O app atualiza somente os produtos já cadastrados em cada posto "
        "e limita o estoque à capacidade do tanque."
    )
    stock_upload = st.file_uploader("Arquivo de estoque atual", type=["pdf", "txt"], key="stock_import")
    if stock_upload is not None:
        try:
            stock_text = extract_text_from_upload(stock_upload)
            stocks = parse_stock_import_text(stock_text)
            if not stocks:
                st.warning("Não encontrei estoques válidos no arquivo.")
            else:
                stock_rows = []
                for station, products in stocks.items():
                    for product, quantity in products.items():
                        stock_rows.append(
                            {
                                "Posto": station,
                                "Produto": product,
                                "Estoque Atual do Arquivo (L)": quantity,
                            }
                        )
                st.dataframe(pd.DataFrame(stock_rows), hide_index=True, use_container_width=True)
                if st.button("Atualizar estoque atual", type="primary"):
                    updated, ignored = apply_stock_import(stocks)
                    st.success(f"Estoque atualizado para {updated} produto(s).")
                    if ignored:
                        st.warning("Itens ignorados: " + "; ".join(ignored[:12]))
                    st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível importar o estoque: {exc}")

    st.divider()
    st.subheader("Gestão de usuários")
    users_df = pd.DataFrame(
        [
            {
                "Usuário": username,
                "Nome": payload["name"],
                "Perfil": payload["role"],
                "Posto vinculado": payload["station"] or "Todos",
            }
            for username, payload in USERS.items()
        ]
    )
    st.dataframe(users_df, hide_index=True, use_container_width=True)
    st.info(
        "Para produção, troque as senhas padrão e prefira Streamlit Secrets ou banco externo. "
        "Neste protótipo, os hashes ficam em dicionário interno conforme solicitado.",
        icon="🔐",
    )


def main():
    init_state()
    inject_css()

    if not st.session_state.authenticated:
        login_screen()
        return

    page = render_sidebar()
    if page == "Painel de Compras":
        render_main_panel(read_only=False)
    elif page == "Cadastro de Postos e Tanques":
        render_network_admin()
    elif page == "Configurações e Vendas":
        render_settings_sales()
    else:
        render_main_panel(read_only=True)


if __name__ == "__main__":
    main()
