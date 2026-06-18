import hashlib
import html as html_lib
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
TRUCK_CAPACITY_LITERS = 25000
AVAILABLE_TRUCKS_PER_DAY = 2
DAILY_DELIVERY_CAPACITY_LITERS = TRUCK_CAPACITY_LITERS * AVAILABLE_TRUCKS_PER_DAY
MARKET_REFRESH_HOURS = 3
DATA_VERSION = "pdf-litragem-2026-06-18-vmd-17dias-prazo-logistica"
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
        "stations": [],
        "active": True,
    },
    "gerente_recife": {
        "name": "Gerente Casa Caiada",
        "role": "Gerente",
        "password_hash": hashlib.sha256("recife123".encode()).hexdigest(),
        "stations": ["AP Casa Caiada"],
        "active": True,
    },
    "gerente_olinda": {
        "name": "Gerente VIP",
        "role": "Gerente",
        "password_hash": hashlib.sha256("olinda123".encode()).hexdigest(),
        "stations": ["Posto VIP"],
        "active": True,
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

            .mobile-card-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 12px;
                margin: 10px 0 18px 0;
            }

            .mobile-summary-card {
                background: rgba(15, 23, 42, .92);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 14px;
            }

            .mobile-summary-card h4 {
                margin: 0 0 8px 0;
                font-size: 1rem;
            }

            .mobile-summary-card p {
                margin: 4px 0;
                color: #d1d5db;
                font-size: .9rem;
            }

            @media (max-width: 640px) {
                .block-container {
                    padding-left: .75rem;
                    padding-right: .75rem;
                    padding-top: 1rem;
                }

                h1 {
                    font-size: 1.55rem;
                    line-height: 1.2;
                }

                h2, h3 {
                    font-size: 1.15rem;
                }

                .subtitle {
                    font-size: .9rem;
                    margin-bottom: 12px;
                }

                .signal-card {
                    padding: 12px;
                    margin: 8px 0 12px 0;
                }

                .signal-title {
                    font-size: .98rem;
                }

                .signal-text {
                    font-size: .88rem;
                }

                div[data-testid="stMetric"] {
                    padding: 10px;
                }

                div[data-testid="stMetricValue"] {
                    font-size: 1.25rem;
                }

                div[data-testid="stDataFrame"] {
                    max-height: 430px;
                }

                [data-testid="stSidebar"] {
                    border-right: 0;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def default_users():
    return {username: payload.copy() for username, payload in USERS.items()}


def migrate_users():
    migrated = {}
    for username, payload in st.session_state.users.items():
        user = payload.copy()
        if "stations" not in user:
            station = user.pop("station", None)
            user["stations"] = [station] if station else []
        user.setdefault("active", True)
        user.setdefault("role", "Gerente")
        user.setdefault("name", username)
        migrated[username] = user
    st.session_state.users = migrated


def current_user_payload(username):
    user = st.session_state.users.get(username)
    if not user:
        return None
    return {"username": username, **user}


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
            "payment_term_days": 7,
            "tanks": {
                "Etanol Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 974.97},
                "Gasolina Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 1980.89},
            },
        },
        "Posto Doze Filial II": {
            "city": "Pernambuco",
            "payment_term_days": 7,
            "tanks": {
                "Gasolina Aditivada": {"capacity": 15000.0, "stock": 0.0, "vmd": 273.69},
                "Diesel Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 810.59},
                "Etanol Aditivado": {"capacity": 15000.0, "stock": 0.0, "vmd": 1893.59},
                "Gasolina Comum": {"capacity": 15000.0, "stock": 0.0, "vmd": 3250.70},
            },
        },
        "Posto Enseada do Norte": {
            "city": "Pernambuco",
            "payment_term_days": 14,
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
            "payment_term_days": 7,
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
    st.session_state.setdefault("users", default_users())
    if st.session_state.get("data_version") != DATA_VERSION:
        st.session_state.network = default_network()
        st.session_state.data_version = DATA_VERSION
    st.session_state.setdefault("network", default_network())
    st.session_state.setdefault("market_cache", None)
    st.session_state.setdefault("last_market_update", None)
    st.session_state.setdefault("sales_trends", {})
    st.session_state.setdefault("decision_history", [])
    migrate_users()


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
            clean_username = username.strip()
            user = st.session_state.users.get(clean_username)
            if user and user.get("active", True) and user["password_hash"] == hash_password(password):
                st.session_state.authenticated = True
                st.session_state.user = current_user_payload(clean_username)
                st.rerun()
            elif user and not user.get("active", True):
                st.error("Usuário inativo. Procure o administrador.")
            else:
                st.error("Usuário ou senha inválidos.")


def network_records(station_filter=None):
    rows = []
    for station, payload in st.session_state.network.items():
        if station_filter and station not in station_filter:
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
                    "Prazo Financeiro (dias)": int(payload.get("payment_term_days", 0)),
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
    output["trend_label"] = {"ALTA": "Alta", "BAIXA": "Queda", "NEUTRA": "Estável"}[trend]
    output["source"] = "Yahoo Finance via yfinance"
    output["source_detail"] = "Brent (BZ=F) e dólar USD/BRL (USDBRL=X). ANP, Petrobras e fornecedores locais ficam como fontes recomendadas para futura integração."
    return output


def get_market_data(force=False):
    last_update = st.session_state.get("last_market_update_dt")
    expired = True
    if last_update:
        expired = datetime.now() - last_update >= timedelta(hours=MARKET_REFRESH_HOURS)

    if force or expired or st.session_state.market_cache is None:
        st.session_state.market_cache = fetch_market_data()
        st.session_state.last_market_update_dt = datetime.now()
        st.session_state.last_market_update = datetime.now().strftime("%d/%m/%Y %H:%M")
    return st.session_state.market_cache


def consumption_trend_for(row):
    trends = st.session_state.get("sales_trends", {})
    return trends.get((row["Posto"], row["Produto"]), "Estável")


def trend_factor(consumption_trend):
    if consumption_trend == "Alta":
        return 1.15
    if consumption_trend == "Queda":
        return 0.90
    return 1.00


def stock_strategy(coverage, adjusted_vmd, capacity):
    if adjusted_vmd <= 0:
        return "🟡 Estoque normal"
    giro = adjusted_vmd / capacity if capacity else 0
    if coverage < 3 or giro >= 0.22:
        return "🔴 Estoque alto"
    if coverage > 7 and giro <= 0.10:
        return "🟢 Estoque baixo"
    return "🟡 Estoque normal"


def strategy_target_days(strategy, consumption_trend):
    if "alto" in strategy:
        return 6 if consumption_trend == "Alta" else 5
    if "baixo" in strategy:
        return 3
    return 4


def delivery_window(stock, capacity, adjusted_vmd, volume):
    if adjusted_vmd <= 0 or volume <= 0:
        return {
            "can_fit_in_days": 0,
            "runout_in_days": 999,
            "window": "Sem janela calculável",
            "latest_day": 0,
        }
    headroom = max(capacity - stock, 0)
    can_fit_in_days = max(math.ceil((volume - headroom) / adjusted_vmd), 0)
    runout_in_days = max(stock / adjusted_vmd, 0)
    latest_day = max(math.floor(runout_in_days - 0.5), 0)
    if can_fit_in_days > latest_day:
        text = f"Crítica: cabe em {can_fit_in_days} dia(s), mas falta em {runout_in_days:.1f} dia(s)"
    else:
        text = f"Pode entregar entre D+{can_fit_in_days} e D+{latest_day}; depois disso pode faltar"
    return {
        "can_fit_in_days": can_fit_in_days,
        "runout_in_days": runout_in_days,
        "window": text,
        "latest_day": latest_day,
    }


def proportional_target_days(row, adjusted_vmd, base_target_days):
    station = row["Posto"]
    records = network_records([station])
    coverages = []
    for _, item in records.iterrows():
        item_vmd = float(item["VMD (L/dia)"]) * trend_factor(consumption_trend_for(item))
        if item_vmd > 0:
            coverages.append(float(item["Estoque Atual (L)"]) / item_vmd)
    if not coverages:
        return base_target_days
    station_average = sum(coverages) / len(coverages)
    return max(base_target_days, min(max(station_average + 1.5, 3), 7))


def purchase_score(coverage, reorder_point_days, trend, reason, payment_term_days, volume):
    risk_score = max(0, min(45, ((reorder_point_days + 1 - coverage) / max(reorder_point_days + 1, 1)) * 45))
    price_score = 0
    if trend == "ALTA":
        price_score = 25
    elif trend == "BAIXA":
        price_score = 5 if reason in ("Risco de falta", "Comprar mínimo e aguardar baixa") else 0
    else:
        price_score = 10
    logistics_score = 15 if volume >= TRUCK_COMPARTMENT_LITERS else 0
    finance_score = min(max(payment_term_days, 0), 30) / 30 * 15
    return round(min(risk_score + price_score + logistics_score + finance_score, 100), 0)


def purchase_recommendation(row, trend=None):
    capacity = float(row["Capacidade (L)"])
    stock = float(row["Estoque Atual (L)"])
    vmd = float(row["VMD (L/dia)"])
    headroom = max(capacity - stock, 0)
    payment_term_days = int(row.get("Prazo Financeiro (dias)", 0))
    consumption_trend = consumption_trend_for(row)
    adjusted_vmd = max(vmd * trend_factor(consumption_trend), 0)
    coverage = stock / adjusted_vmd if adjusted_vmd > 0 else 999
    lead_time_days = 2
    safety_days = 1.5 if consumption_trend == "Alta" else 1.0
    reorder_point_days = lead_time_days + safety_days
    strategy = stock_strategy(coverage, adjusted_vmd, capacity)
    target_days = strategy_target_days(strategy, consumption_trend)
    if trend == "ALTA":
        target_days = min(max(target_days + 2, 5), 7)
    elif trend == "BAIXA":
        target_days = max(target_days - 1, 3)
    days_until_buy = max(math.floor(coverage - reorder_point_days), 0)

    shortage_risk = coverage <= reorder_point_days
    price_opportunity = trend == "ALTA" and coverage <= target_days + 1 and headroom >= TRUCK_COMPARTMENT_LITERS
    should_buy = shortage_risk or price_opportunity
    if not should_buy:
        finance_note = f" Prazo financeiro: {payment_term_days} dia(s)." if payment_term_days else ""
        if trend == "BAIXA":
            action = (
                f"Aguardar provável baixa de preço; cobertura suficiente para {coverage:.1f} dia(s). "
                f"Reavaliar em {days_until_buy} dia(s).{finance_note}"
            )
            reason = "Aguardar baixa provável"
        else:
            action = f"Não comprar agora; cobertura suficiente. Reavaliar em {days_until_buy} dia(s).{finance_note}"
            reason = "Cobertura suficiente"
        return {
            "volume": 0,
            "action": action,
            "coverage": coverage,
            "trend": consumption_trend,
            "strategy": strategy,
            "should_buy": "Não",
            "when": f"Em {days_until_buy} dia(s)",
            "reason": reason,
            "window": "Sem compra agora; cobertura permite aguardar",
            "score": purchase_score(coverage, reorder_point_days, trend, reason, payment_term_days, 0),
        }

    balanced_target_days = proportional_target_days(row, adjusted_vmd, target_days)
    if trend == "BAIXA" and shortage_risk:
        target_stock = min(capacity, adjusted_vmd * reorder_point_days)
    else:
        target_stock = min(capacity, adjusted_vmd * balanced_target_days)
    raw_volume = max(target_stock - stock, 0)
    rounded_volume = round_to_truck_compartment(raw_volume, headroom)
    window = delivery_window(stock, capacity, adjusted_vmd, rounded_volume)
    if rounded_volume == 0:
        return {
            "volume": 0,
            "action": "Não comprar; volume necessário não fecha 5.000 L ou não há espaço.",
            "coverage": coverage,
            "trend": consumption_trend,
            "strategy": strategy,
            "should_buy": "Não",
            "when": "Reavaliar",
            "reason": "Sem lote logístico",
            "window": "Sem compra programada",
            "score": purchase_score(coverage, reorder_point_days, trend, "Sem lote logístico", payment_term_days, 0),
        }

    if shortage_risk and trend == "BAIXA":
        reason = "Comprar mínimo e aguardar baixa"
    elif shortage_risk:
        reason = "Risco de falta"
    else:
        reason = "Alta prevista: comprar antes do aumento"
    finance_note = f" Prazo financeiro: {payment_term_days} dia(s)." if payment_term_days else ""
    if reason == "Comprar mínimo e aguardar baixa":
        action = f"{reason}. Comprar só segurança logística para não faltar e esperar preço melhor.{finance_note}"
    else:
        action = f"{reason}. Comprar para repor até {target_days} dia(s) de cobertura ajustada.{finance_note}"
    return {
        "volume": rounded_volume,
        "action": action,
        "coverage": coverage,
        "trend": consumption_trend,
        "strategy": strategy,
        "should_buy": "Sim",
        "when": "Hoje",
        "reason": reason,
        "window": window["window"],
        "score": purchase_score(coverage, reorder_point_days, trend, reason, payment_term_days, rounded_volume),
    }


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
    remaining_capacity = {day["date"]: DAILY_DELIVERY_CAPACITY_LITERS for day in operational_days}
    candidates = exec_df[
        (exec_df["Volume"] >= TRUCK_COMPARTMENT_LITERS)
        & (exec_df["Comprar?"] == "Sim")
    ].copy()

    reason_order = {
        "Risco de falta": 0,
        "Comprar mínimo e aguardar baixa": 1,
        "Alta prevista: comprar antes do aumento": 2,
    }
    candidates["Ordem Motivo"] = candidates["Motivo"].map(reason_order).fillna(5)
    candidates = candidates.sort_values(
        ["Ordem Motivo", "Score", "Cobertura (dias)", "Prazo Financeiro (dias)", "Posto", "Produto"],
        ascending=[True, False, True, False, True, True],
    )

    rows = []
    for _, item in candidates.iterrows():
        volume = float(item["Volume"])
        day = None
        for candidate_day in operational_days:
            if remaining_capacity[candidate_day["date"]] >= volume:
                day = candidate_day
                remaining_capacity[candidate_day["date"]] -= volume
                break
        if day is None:
            day = operational_days[-1] if operational_days else days[0]
        rows.append(
            {
                "Chegada Prevista": day["label"],
                "Data": day["date"].strftime("%d/%m/%Y"),
                "Posto": item["Posto"],
                "Produto": item["Produto"],
                "Comprar (L)": volume,
                "Compartimentos": int(volume / TRUCK_COMPARTMENT_LITERS),
                "Autonomia Atual": item["Cobertura (dias)"],
                "Score": item["Score"],
                "Prazo Financeiro (dias)": item["Prazo Financeiro (dias)"],
                "Prioridade": item["Estratégia de Estoque"],
                "Motivo": item["Motivo"],
                "Janela de Entrega": item["Janela de Entrega"],
                "Observação": item["Recomendação"],
            }
        )

    schedule = pd.DataFrame(rows)
    calendar = pd.DataFrame(
        [
            {
                "Dia": day["label"],
                "Data": day["date"].strftime("%d/%m/%Y"),
                "Status Base": "Sem operação" if not day["operates"] else "Operando",
                "Capacidade Logística": "0 L" if not day["operates"] else liters(DAILY_DELIVERY_CAPACITY_LITERS),
                "Caminhões": 0 if not day["operates"] else AVAILABLE_TRUCKS_PER_DAY,
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
        recommendation = purchase_recommendation(row, trend)
        rows.append(
            {
                "Posto": row["Posto"],
                "Produto": row["Produto"],
                "Estoque Atual": round(float(row["Estoque Atual (L)"]), 0),
                "Consumo Diário": round(float(row["VMD (L/dia)"]), 1),
                "Cobertura (dias)": round(float(recommendation["coverage"]), 1),
                "Tendência Consumo": recommendation["trend"],
                "Tendência Preço": {"ALTA": "Alta", "BAIXA": "Queda", "NEUTRA": "Estável"}.get(trend, "Estável"),
                "Estratégia de Estoque": recommendation["strategy"],
                "Prazo Financeiro (dias)": int(row.get("Prazo Financeiro (dias)", 0)),
                "Score": recommendation["score"],
                "Motivo": recommendation["reason"],
                "Janela de Entrega": recommendation["window"],
                "Recomendação": recommendation["action"],
                "Comprar?": recommendation["should_buy"],
                "Quando": recommendation["when"],
                "Volume": round(recommendation["volume"], 0),
            }
        )
    return pd.DataFrame(rows).sort_values(["Comprar?", "Cobertura (dias)", "Posto", "Produto"], ascending=[False, True, True, True])


def build_financial_schedule(weekly_schedule, price_delta):
    if weekly_schedule.empty:
        return pd.DataFrame()
    rows = []
    for _, row in weekly_schedule.iterrows():
        arrival = datetime.strptime(row["Data"], "%d/%m/%Y").date()
        term = int(row.get("Prazo Financeiro (dias)", 0))
        due_date = arrival + timedelta(days=term)
        volume = float(row["Comprar (L)"])
        rows.append(
            {
                "Posto": row["Posto"],
                "Produto": row["Produto"],
                "Chegada": row["Data"],
                "Volume (L)": volume,
                "Prazo (dias)": term,
                "Vencimento Boleto": due_date.strftime("%d/%m/%Y"),
                "Impacto Caixa Simulado": round(volume * price_delta, 2),
                "Melhor Dia para Faturar": row["Data"],
            }
        )
    return pd.DataFrame(rows)


def render_price_simulator(exec_df, weekly_schedule):
    with st.expander("Simulador de preço e ganho potencial", expanded=False):
        c1, c2 = st.columns([1, 2])
        price_delta = c1.number_input(
            "Variação prevista por litro (R$)",
            min_value=-2.0,
            max_value=2.0,
            value=0.08,
            step=0.01,
            format="%.2f",
            help="Use valor positivo para alta esperada e negativo para baixa esperada.",
        )
        scheduled_volume = weekly_schedule["Comprar (L)"].sum() if not weekly_schedule.empty else 0
        c2.metric("Resultado potencial da programação", f"R$ {money(scheduled_volume * price_delta)}")
        if price_delta > 0:
            st.success("Alta simulada: comprar antes pode proteger margem.")
        elif price_delta < 0:
            st.warning("Baixa simulada: se houver cobertura, esperar reduz custo de compra.")
        else:
            st.info("Sem variação simulada.")

        sim_df = exec_df[exec_df["Comprar?"] == "Sim"].copy()
        if not sim_df.empty:
            sim_df["Resultado Potencial"] = sim_df["Volume"] * price_delta
            st.dataframe(
                sim_df[["Posto", "Produto", "Volume", "Tendência Preço", "Motivo", "Resultado Potencial"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Volume": st.column_config.NumberColumn(format="%.0f"),
                    "Resultado Potencial": st.column_config.NumberColumn(format="R$ %.2f"),
                },
            )
    return price_delta


def render_financial_control(weekly_schedule, price_delta):
    st.markdown("#### Controle financeiro")
    finance_df = build_financial_schedule(weekly_schedule, price_delta)
    if finance_df.empty:
        st.info("Sem compras programadas para projetar boletos e caixa.", icon="💳")
        return
    st.dataframe(
        finance_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Volume (L)": st.column_config.NumberColumn(format="%.0f"),
            "Impacto Caixa Simulado": st.column_config.NumberColumn(format="R$ %.2f"),
        },
    )


def render_decision_history(exec_df, weekly_schedule, price_delta):
    st.markdown("#### Histórico de decisões")
    c1, c2 = st.columns([1, 3])
    decision = c1.selectbox("Decisão tomada", ["Aprovar recomendação", "Aguardar", "Comprar parcial", "Revisar manualmente"])
    notes = c2.text_input("Observação", placeholder="Ex: aguardando tabela Vibra/Suape")
    if st.button("Registrar decisão da rodada", type="primary"):
        approved = exec_df[exec_df["Comprar?"] == "Sim"].copy()
        total_volume = float(approved["Volume"].sum()) if not approved.empty else 0
        potential_result = total_volume * price_delta
        st.session_state.decision_history.append(
            {
                "Data/Hora": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Usuário": st.session_state.user.get("username", ""),
                "Decisão": decision,
                "Volume Total (L)": total_volume,
                "Pedidos Programados": len(weekly_schedule),
                "Resultado Simulado": round(potential_result, 2),
                "Observação": notes,
            }
        )
        st.success("Decisão registrada no histórico.")

    if st.session_state.decision_history:
        history_df = pd.DataFrame(st.session_state.decision_history)
        st.dataframe(
            history_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Volume Total (L)": st.column_config.NumberColumn(format="%.0f"),
                "Resultado Simulado": st.column_config.NumberColumn(format="R$ %.2f"),
            },
        )
    else:
        st.info("Nenhuma decisão registrada nesta sessão.", icon="🧾")


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
            stations.setdefault(current_station, {"city": current_city, "payment_term_days": 7, "tanks": {}})
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
        st.session_state.network.setdefault(
            station,
            {"city": payload["city"], "payment_term_days": payload.get("payment_term_days", 7), "tanks": {}},
        )
        st.session_state.network[station]["city"] = payload["city"]
        st.session_state.network[station]["payment_term_days"] = payload.get(
            "payment_term_days",
            st.session_state.network[station].get("payment_term_days", 7),
        )
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
    should_buy = row.get("Comprar?", "")
    strategy = row.get("Estratégia de Estoque", "")
    if should_buy == "Sim" and "alto" in strategy:
        return ["background-color: rgba(239, 68, 68, .28); color: #fee2e2; font-weight: 700"] * len(row)
    if should_buy == "Sim":
        return ["background-color: rgba(245, 158, 11, .24); color: #fef3c7; font-weight: 700"] * len(row)
    if "baixo" in strategy:
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


def filter_weekly_schedule(schedule):
    if schedule.empty:
        return schedule

    filtered = schedule.copy()
    filtered["_DataFiltro"] = pd.to_datetime(filtered["Data"], format="%d/%m/%Y", errors="coerce")
    start = datetime.now().date() + timedelta(days=1)
    end = start + timedelta(days=2)
    filtered = filtered[
        filtered["_DataFiltro"].dt.date.between(start, end)
    ].copy()

    st.markdown("##### Filtros rápidos")
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    station_options = sorted(filtered["Posto"].dropna().unique().tolist())
    product_options = sorted(filtered["Produto"].dropna().unique().tolist())
    selected_stations = c1.multiselect("Postos", station_options, default=station_options, key="quick_schedule_stations")
    selected_products = c2.multiselect("Produtos", product_options, default=product_options, key="quick_schedule_products")

    if not filtered.empty:
        min_qty = int(filtered["Comprar (L)"].min())
        max_qty = int(filtered["Comprar (L)"].max())
    else:
        min_qty = max_qty = 0
    if min_qty == max_qty:
        qty_range = (min_qty, max_qty)
        c3.caption(f"Quantidade: {liters(min_qty)}")
    else:
        qty_range = c3.slider(
            "Quantidade (L)",
            min_value=min_qty,
            max_value=max_qty,
            value=(min_qty, max_qty),
            step=TRUCK_COMPARTMENT_LITERS,
            key="quick_schedule_qty",
        )

    filtered = filtered[
        filtered["Posto"].isin(selected_stations)
        & filtered["Produto"].isin(selected_products)
        & filtered["Comprar (L)"].between(qty_range[0], qty_range[1])
    ].copy()
    return filtered.drop(columns=["_DataFiltro"], errors="ignore")


def short_weekday(date_text):
    try:
        day = datetime.strptime(date_text, "%d/%m/%Y")
    except Exception:
        return ""
    names = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
    return names[day.weekday()]


def product_transport_code(product):
    codes = {
        "Gasolina Comum": "GC",
        "Etanol Comum": "ET",
        "Gasolina Aditivada": "GA",
        "Etanol Aditivado": "EA",
        "Gasolina Podium": "PODIUM",
        "Diesel Comum": "DC",
        "Diesel Aditivado": "DA",
    }
    return codes.get(product, product)


def render_transport_order(schedule):
    st.markdown("#### Ordem para transporte")
    if schedule.empty:
        st.info("Sem programação de transporte para exibir.", icon="🚚")
        return

    source = schedule.copy()
    station_options = sorted(source["Posto"].dropna().unique().tolist())
    c1, c2 = st.columns([1.2, 1])
    selected_station = c1.selectbox("Posto para transporte", station_options, key="transport_station")
    days_ahead = c2.slider("Dias para enviar", min_value=1, max_value=7, value=3, step=1, key="transport_days")

    start = datetime.now().date()
    end = start + timedelta(days=days_ahead - 1)
    source["_DataFiltro"] = pd.to_datetime(source["Data"], format="%d/%m/%Y", errors="coerce")
    view = source[
        (source["Posto"] == selected_station)
        & source["_DataFiltro"].dt.date.between(start, end)
    ].copy()

    if view.empty:
        st.warning("Esse posto não tem entrega programada dentro do período selecionado.")
        return

    transport_rows = []
    text_lines = [selected_station.upper(), ""]
    for date_text, day_df in view.sort_values(["_DataFiltro", "Produto"]).groupby("Data", sort=False):
        header = f"> {short_weekday(date_text)} - {date_text[:5]}"
        text_lines.append(header)
        for _, row in day_df.iterrows():
            code = product_transport_code(row["Produto"])
            volume = int(row["Comprar (L)"])
            text_lines.append(f"{code} {volume}")
            transport_rows.append(
                {
                    "Posto": selected_station,
                    "Dia": short_weekday(date_text),
                    "Data": date_text,
                    "Produto": row["Produto"],
                    "Código": code,
                    "Volume (L)": volume,
                    "Compartimentos": int(row["Compartimentos"]),
                }
            )
        text_lines.append("")
        text_lines.append("----------------")

    st.dataframe(
        pd.DataFrame(transport_rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Volume (L)": st.column_config.NumberColumn(format="%.0f"),
            "Compartimentos": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.text_area("Mensagem para transportador", "\n".join(text_lines).strip(), height=220)


def render_mobile_recommendation_cards(exec_df, weekly_schedule):
    st.markdown("#### Resumo rápido")
    source = exec_df[exec_df["Comprar?"] == "Sim"].copy()
    if source.empty:
        source = exec_df.sort_values(["Score", "Cobertura (dias)"], ascending=[False, True]).head(6)
    else:
        source = source.sort_values(["Score", "Cobertura (dias)"], ascending=[False, True]).head(6)

    if source.empty:
        st.info("Sem dados para exibir no resumo.", icon="📱")
        return

    schedule_lookup = {}
    if not weekly_schedule.empty:
        for _, item in weekly_schedule.iterrows():
            schedule_lookup[(item["Posto"], item["Produto"])] = {
                "label": item.get("Chegada Prevista", "-"),
                "date": item.get("Data", "-"),
            }

    html_parts = ['<div class="mobile-card-grid">']
    for _, row in source.iterrows():
        arrival = schedule_lookup.get((row["Posto"], row["Produto"]), {"label": row.get("Quando", "-"), "date": "-"})
        volume = liters(row["Volume"]) if float(row["Volume"]) > 0 else "0 L"
        title = html_lib.escape(f"{row['Posto']} · {row['Produto']}")
        buy = html_lib.escape(str(row["Comprar?"]))
        arrival_text = html_lib.escape(f"{arrival['date']} · {arrival['label']}")
        reason = html_lib.escape(str(row["Motivo"]))
        html_parts.append(
            '<div class="mobile-summary-card">'
            f"<h4>{title}</h4>"
            f"<p><b>Comprar?</b> {buy} · <b>Volume:</b> {volume}</p>"
            f"<p><b>Cobertura:</b> {row['Cobertura (dias)']:.1f} dias · <b>Score:</b> {row['Score']:.0f}</p>"
            f"<p><b>Chegada:</b> {arrival_text}</p>"
            f"<p><b>Motivo:</b> {reason}</p>"
            "</div>"
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def header(title, subtitle):
    st.markdown('<div class="top-title">', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="subtitle">{subtitle}</p>', unsafe_allow_html=True)


def allowed_station():
    user = st.session_state.user
    if user["role"] == "Gerente":
        return user.get("stations", [])
    return None


def render_sidebar():
    user = st.session_state.user
    market = get_market_data()
    st.sidebar.title("⛽ FuelGuard")
    st.sidebar.caption("Trader inteligente de combustível")
    st.sidebar.divider()
    st.sidebar.markdown(f"**{user['name']}**")
    st.sidebar.caption(f"Perfil: {user['role']}")

    if user["role"] == "Gerente":
        stations = user.get("stations", [])
        st.sidebar.caption("Postos liberados:")
        st.sidebar.write(", ".join(stations) if stations else "Nenhum posto vinculado")
    else:
        st.sidebar.caption(f"Rede: {len(st.session_state.network)} posto(s)")

    if user["role"] == "Sócio":
        page_labels = {
            "📊 Painel de Compras": "Painel de Compras",
            "🏪 Postos e Tanques": "Cadastro de Postos e Tanques",
            "⚙️ Configurações": "Configurações e Vendas",
        }
    else:
        page_labels = {"📊 Painel de Consulta": "Painel de Consulta"}

    st.sidebar.divider()
    selected_label = st.sidebar.radio("Menu", list(page_labels.keys()), label_visibility="collapsed")

    st.sidebar.divider()
    st.sidebar.markdown("**Mercado**")
    st.sidebar.metric("Tendência preço", market.get("trend_label", market["trend"]))
    st.sidebar.caption(f"Atualizado: {st.session_state.last_market_update or 'pendente'}")
    st.sidebar.caption(f"Atualização automática: {MARKET_REFRESH_HOURS}h")
    if st.sidebar.button("Atualizar mercado", use_container_width=True):
        get_market_data(force=True)
        st.rerun()

    st.sidebar.divider()
    st.sidebar.markdown("**Logística**")
    st.sidebar.caption(f"{AVAILABLE_TRUCKS_PER_DAY} caminhões/dia")
    st.sidebar.caption(f"{liters(TRUCK_CAPACITY_LITERS)} por caminhão")
    st.sidebar.caption(f"Capacidade diária: {liters(DAILY_DELIVERY_CAPACITY_LITERS)}")

    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()

    return page_labels[selected_label]


def render_market_signal(market):
    trend = market["trend"]
    if trend == "ALTA":
        css = "signal-up"
        title = "📈 Tendência de ALTA: avaliar compra antes do aumento"
        text = "Antecipe somente os produtos com cobertura dentro da janela econômica ou risco de falta, respeitando espaço de tanque e logística."
    elif trend == "BAIXA":
        css = "signal-down"
        title = "📉 Tendência de BAIXA: esperar quando houver cobertura"
        text = "Se a cobertura permitir, adie para capturar preço menor. Se houver risco de falta, compre só o mínimo de segurança."
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


def render_market_radar(market):
    st.markdown("#### Radar de mercado")
    radar_rows = [
        {
            "Fonte": "Brent",
            "Status": "Automático",
            "Sinal": market.get("trend_label", "Estável"),
            "Valor/Delta": f"{money(market.get('brent'))} | {market.get('brent_delta', 0):.2f}%",
            "Uso na decisão": "Custo internacional",
        },
        {
            "Fonte": "Dólar",
            "Status": "Automático",
            "Sinal": market.get("trend_label", "Estável"),
            "Valor/Delta": f"{money(market.get('usd'))} | {market.get('usd_delta', 0):.2f}%",
            "Uso na decisão": "Câmbio de combustíveis",
        },
        {
            "Fonte": "ANP",
            "Status": "Manual / próxima integração",
            "Sinal": "Acompanhar semanal",
            "Valor/Delta": "Pesquisa de preços",
            "Uso na decisão": "Referência regional",
        },
        {
            "Fonte": "Petrobras",
            "Status": "Manual / próxima integração",
            "Sinal": "Acompanhar reajustes",
            "Valor/Delta": "Comunicados",
            "Uso na decisão": "Probabilidade de repasse",
        },
        {
            "Fonte": "Vibra/Suape",
            "Status": "Manual / fornecedor",
            "Sinal": "Conferir tabela",
            "Valor/Delta": "Preço de faturamento",
            "Uso na decisão": "Compra real",
        },
        {
            "Fonte": "Notícias",
            "Status": "Manual / próxima integração",
            "Sinal": "Monitorar",
            "Valor/Delta": "Eventos e política",
            "Uso na decisão": "Risco de alta/baixa",
        },
    ]
    st.dataframe(pd.DataFrame(radar_rows), hide_index=True, use_container_width=True)


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

    with st.expander("Medição física do dia", expanded=False):
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
    st.caption(
        f"Fonte: {market['source']} | Última atualização: {st.session_state.last_market_update or 'não executada'} | "
        f"Atualização automática a cada {MARKET_REFRESH_HOURS}h"
    )
    st.caption(market.get("source_detail", ""))
    render_market_signal(market)
    with st.expander("Radar de mercado", expanded=False):
        render_market_radar(market)

    with st.expander("Ocupação física dos tanques", expanded=False):
        for station in df["Posto"].drop_duplicates().tolist():
            station_df = df[df["Posto"] == station].reset_index(drop=True)
            st.plotly_chart(donut_chart(station, station_df), use_container_width=True)

    st.subheader("Saída executiva de compra")
    exec_df = build_executive_table(df, trend)
    weekly_schedule, base_calendar = build_weekly_receiving_schedule(exec_df)
    price_delta = render_price_simulator(exec_df, weekly_schedule)
    render_mobile_recommendation_cards(exec_df, weekly_schedule)

    st.markdown("#### Programação semanal de recebimento")
    st.caption(
        f"Janela móvel de 7 dias a partir de amanhã. Domingo não opera. "
        f"Capacidade planejada: {AVAILABLE_TRUCKS_PER_DAY} caminhões de {liters(TRUCK_CAPACITY_LITERS)} por dia."
    )
    with st.expander("Calendário e capacidade da base", expanded=False):
        st.dataframe(
            base_calendar,
            hide_index=True,
            use_container_width=True,
        )
    if weekly_schedule.empty:
        st.info("Nenhuma compra programada na semana com volume mínimo de 5.000 L.", icon="✅")
    else:
        st.caption("Mostrando por padrão os próximos 3 dias, com filtros por posto, produto e quantidade.")
        weekly_schedule_view = filter_weekly_schedule(weekly_schedule)
        st.dataframe(
            weekly_schedule_view,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Comprar (L)": st.column_config.NumberColumn(format="%.0f"),
                "Autonomia Atual": st.column_config.NumberColumn(format="%.1f"),
                "Score": st.column_config.NumberColumn(format="%.0f"),
                "Prazo Financeiro (dias)": st.column_config.NumberColumn(format="%d"),
            },
        )
        render_transport_order(weekly_schedule)

    week_df = exec_df[
        (exec_df["Comprar?"] == "Sim")
        & (exec_df["Volume"] >= TRUCK_COMPARTMENT_LITERS)
    ].copy()
    if not week_df.empty:
        st.markdown("#### Ênfase da semana")
        for _, row in week_df.head(8).iterrows():
            st.markdown(
                f"""
                <div class="signal-card signal-up">
                    <div class="signal-title">{row['Posto']} · {row['Produto']}</div>
                    <p class="signal-text">Comprar <b>{liters(row['Volume'])}</b> uma vez nesta programação. Cobertura atual: {row['Cobertura (dias)']:.1f} dias. {row['Recomendação']}</p>
                </div>
                """.replace(",", "."),
                unsafe_allow_html=True,
            )
    else:
        st.info("Nenhum produto fecha compra mínima de 5.000 L com prioridade nesta semana.", icon="✅")

    with st.expander("Tabela executiva completa", expanded=False):
        exec_df_view = filter_table(exec_df, "executive_table", "Filtros da saída executiva")
        st.dataframe(
            exec_df_view.style.apply(highlight_priority, axis=1),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Estoque Atual": st.column_config.NumberColumn(format="%.0f"),
                "Consumo Diário": st.column_config.NumberColumn(format="%.1f"),
                "Cobertura (dias)": st.column_config.NumberColumn(format="%.1f"),
                "Volume": st.column_config.NumberColumn(format="%.0f"),
                "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                "Prazo Financeiro (dias)": st.column_config.NumberColumn(format="%d"),
            },
        )
    with st.expander("Financeiro e histórico", expanded=False):
        render_financial_control(weekly_schedule, price_delta)
        render_decision_history(exec_df, weekly_schedule, price_delta)


def render_network_admin():
    header(
        "🏪 Cadastro de Postos e Tanques",
        "Gerencie a rede, capacidades, estoque inicial e venda média diária por produto.",
    )

    with st.expander("Cadastrar novo posto", expanded=True):
        with st.form("new_station_form"):
            name = st.text_input("Nome do posto", placeholder="Posto Pina")
            city = st.text_input("Cidade", placeholder="Recife")
            payment_term_days = st.number_input(
                "Prazo financeiro padrão do posto (dias)",
                min_value=0,
                max_value=90,
                value=7,
                step=1,
            )
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
                    "payment_term_days": int(payment_term_days),
                    "tanks": {
                        product: {
                            "capacity": float(capacities[product]),
                            "stock": 0.0,
                            "vmd": float(vmds[product]),
                        }
                        for product in selected_products
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
        df[["Posto", "Cidade", "Prazo Financeiro (dias)", "Produto", "Capacidade (L)", "Estoque Atual (L)", "VMD (L/dia)"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Prazo Financeiro (dias)": st.column_config.NumberColumn(min_value=0, max_value=90, step=1, format="%d"),
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
            new_network.setdefault(
                station,
                {
                    "city": str(row["Cidade"]).strip(),
                    "payment_term_days": int(row.get("Prazo Financeiro (dias)", 0)),
                    "tanks": {},
                },
            )
            new_network[station]["payment_term_days"] = int(row.get("Prazo Financeiro (dias)", 0))
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
        latest = df["Data"].max()
        last_7_start = latest - pd.Timedelta(days=6)
        prev_7_start = latest - pd.Timedelta(days=13)
        recent = df[df["Data"].between(last_7_start, latest)].groupby(["Posto", "Produto"])["Litros"].sum()
        previous = df[df["Data"].between(prev_7_start, last_7_start - pd.Timedelta(days=1))].groupby(["Posto", "Produto"])["Litros"].sum()
        trends = {}
        for key in set(recent.index).union(set(previous.index)):
            recent_avg = float(recent.get(key, 0)) / 7
            previous_avg = float(previous.get(key, 0)) / 7
            if previous_avg <= 0:
                trend = "Estável"
            else:
                change = (recent_avg - previous_avg) / previous_avg
                if change >= 0.12:
                    trend = "Alta"
                elif change <= -0.12:
                    trend = "Queda"
                else:
                    trend = "Estável"
            trends[key] = trend
        st.session_state.sales_trends.update(trends)

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


def user_rows():
    rows = []
    for username, payload in st.session_state.users.items():
        stations = payload.get("stations", [])
        rows.append(
            {
                "Usuário": username,
                "Nome": payload.get("name", ""),
                "Perfil": payload.get("role", ""),
                "Postos administrados": "Todos" if payload.get("role") == "Sócio" else ", ".join(stations),
                "Status": "Ativo" if payload.get("active", True) else "Inativo",
            }
        )
    return pd.DataFrame(rows).sort_values(["Perfil", "Usuário"])


def render_user_crud():
    st.dataframe(user_rows(), hide_index=True, use_container_width=True)

    tabs = st.tabs(["Criar usuário", "Editar acessos", "Senha e exclusão"])
    station_options = list(st.session_state.network.keys())

    with tabs[0]:
        with st.form("create_user_form"):
            c1, c2 = st.columns(2)
            username = c1.text_input("Usuário de login", placeholder="gerente_enseada")
            name = c2.text_input("Nome completo", placeholder="Gerente Enseada")
            role = c1.selectbox("Perfil", ["Gerente", "Sócio"], key="create_user_role")
            password = c2.text_input("Senha inicial", type="password")
            stations = st.multiselect(
                "Postos que este usuário pode administrar",
                station_options,
                disabled=role == "Sócio",
                help="Sócio tem acesso administrativo a todos os postos.",
            )
            active = st.checkbox("Usuário ativo", value=True)
            submitted = st.form_submit_button("Criar usuário", type="primary")

        if submitted:
            clean_username = re.sub(r"\s+", "_", username.strip().lower())
            if not clean_username or not name.strip() or not password:
                st.error("Informe usuário, nome e senha inicial.")
            elif clean_username in st.session_state.users:
                st.error("Já existe um usuário com esse login.")
            elif role == "Gerente" and not stations:
                st.error("Gerente precisa administrar pelo menos um posto.")
            else:
                st.session_state.users[clean_username] = {
                    "name": name.strip(),
                    "role": role,
                    "password_hash": hash_password(password),
                    "stations": [] if role == "Sócio" else stations,
                    "active": active,
                }
                st.success("Usuário criado.")
                st.rerun()

    with tabs[1]:
        if not st.session_state.users:
            st.info("Nenhum usuário cadastrado.")
        else:
            selected = st.selectbox("Usuário", sorted(st.session_state.users.keys()), key="edit_user_select")
            payload = st.session_state.users[selected]
            with st.form("edit_user_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Nome", value=payload.get("name", ""))
                role = c2.selectbox(
                    "Perfil",
                    ["Gerente", "Sócio"],
                    index=0 if payload.get("role") == "Gerente" else 1,
                    key="edit_role",
                )
                stations = st.multiselect(
                    "Postos administrados",
                    station_options,
                    default=[station for station in payload.get("stations", []) if station in station_options],
                    disabled=role == "Sócio",
                )
                can_disable = selected != st.session_state.user.get("username")
                active = st.checkbox(
                    "Usuário ativo",
                    value=payload.get("active", True),
                    disabled=not can_disable,
                    help="Você não pode desativar o próprio usuário logado.",
                )
                submitted = st.form_submit_button("Salvar alterações", type="primary")

            if submitted:
                if role == "Gerente" and not stations:
                    st.error("Gerente precisa administrar pelo menos um posto.")
                else:
                    st.session_state.users[selected].update(
                        {
                            "name": name.strip() or selected,
                            "role": role,
                            "stations": [] if role == "Sócio" else stations,
                            "active": active,
                        }
                    )
                    if selected == st.session_state.user.get("username"):
                        st.session_state.user = current_user_payload(selected)
                    st.success("Usuário atualizado.")
                    st.rerun()

    with tabs[2]:
        selected = st.selectbox("Selecionar usuário", sorted(st.session_state.users.keys()), key="security_user_select")
        c1, c2 = st.columns(2)
        with c1:
            with st.form("reset_password_form"):
                new_password = st.text_input("Nova senha", type="password")
                confirm_password = st.text_input("Confirmar nova senha", type="password")
                submitted = st.form_submit_button("Resetar senha", type="primary")
            if submitted:
                if not new_password or new_password != confirm_password:
                    st.error("As senhas não conferem.")
                else:
                    st.session_state.users[selected]["password_hash"] = hash_password(new_password)
                    st.success("Senha atualizada.")

        with c2:
            st.warning("Excluir usuário remove o acesso imediatamente nesta sessão.")
            confirm_delete = st.text_input("Digite EXCLUIR para confirmar", key="delete_confirm")
            if st.button("Excluir usuário", disabled=selected == st.session_state.user.get("username")):
                if confirm_delete.strip().upper() != "EXCLUIR":
                    st.error("Confirmação inválida.")
                else:
                    del st.session_state.users[selected]
                    st.success("Usuário excluído.")
                    st.rerun()


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
    render_user_crud()
    st.info(
        "Os usuários ficam em memória durante a sessão do Streamlit. Para ambiente definitivo, o próximo passo é persistir em banco ou Streamlit Secrets.",
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
