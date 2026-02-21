import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword mapping  (macro, branch) → list of keywords
# ---------------------------------------------------------------------------
KEYWORD_MAP: Dict[Tuple[str, str], List[str]] = {
    ("Ingegneria", "Elettronica"): [
        "electronics", "semiconductor", "chip", "circuit", "pcb",
        "microcontroller", "fpga", "transistor", "diode", "oscilloscope",
        "elettronica", "circuito", "microchip", "sensore", "sensor",
    ],
    ("Ingegneria", "Meccanica"): [
        "mechanical", "meccanica", "meccanico", "engine", "turbine",
        "gear", "shaft", "bearing", "hydraulic", "pneumatic", "stress",
        "manufacturing", "cnc", "machining", "welding", "casting",
        "3d print", "additive manufacturing",
    ],
    ("Ingegneria", "Biotecnologie"): [
        "biotech", "biotechnology", "biomedical", "genetic", "genome",
        "crispr", "protein", "enzyme", "tissue", "clinical",
        "pharmaceutical", "drug discovery", "biotecnologie", "farmaceutico",
        "biologia molecolare",
    ],
    ("Ingegneria", "Nanoelettronica"): [
        "nano", "nanotechnology", "quantum", "nanoscale", "nanoparticle",
        "graphene", "quantum dot", "spintronics", "nanoelectronics",
        "nanotecnologia", "quantum computing", "qubit", "2d material",
    ],
    ("Ingegneria", "Automazione"): [
        "robot", "automation", "automazione", "autonomous", "self-driving",
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "computer vision", "iot", "industry 4.0",
        "plc", "scada", "drone", "intelligenza artificiale",
    ],
    ("Finanza", "Mercati"): [
        "stock", "stock market", "market cap", "equity", "nasdaq",
        "dow jones", "s&p 500", "trading", "borse", "mercato azionario",
        "azione", "bond", "treasury", "commodity", "oil price", "gold",
    ],
    ("Finanza", "Investimenti"): [
        "investment", "investimento", "portfolio", "asset management",
        "fund", "etf", "hedge fund", "venture capital", "startup funding",
        "ipo", "merger", "acquisition", "fintech", "risparmio", "dividend",
    ],
    ("Finanza", "Criptovalute"): [
        "crypto", "bitcoin", "btc", "ethereum", "eth", "blockchain",
        "defi", "nft", "web3", "altcoin", "stablecoin", "wallet",
        "mining", "criptovalute", "decentralized", "solana", "binance",
    ],
    ("Politica", "Internazionale"): [
        "international", "global", "united nations", "nato", "g7", "g20",
        "treaty", "diplomacy", "sanction", "geopolit", "war", "conflict",
        "internazionale", "mondiale", "guerra", "diplomazia",
    ],
    ("Politica", "Locale"): [
        "election", "elezioni", "parlamento", "government", "governo",
        "senate", "congress", "parliament", "mayor", "city council",
        "municipale", "regione", "regionale", "comune", "sindaco",
        "referendum",
    ],
    ("Politica", "Europea"): [
        "european union", " eu ", "eurozone", "european commission",
        "european parliament", "europeo", "europea", "bruxelles",
        "brussels", "schengen", " euro ",
    ],
}

# ---------------------------------------------------------------------------
# Category descriptions for embeddings similarity
# ---------------------------------------------------------------------------
CATEGORY_DESCRIPTIONS: Dict[Tuple[str, str], str] = {
    ("Ingegneria", "Elettronica"):
        "electronics semiconductors chips circuits microcontrollers sensors",
    ("Ingegneria", "Meccanica"):
        "mechanical engineering engines manufacturing turbines gears",
    ("Ingegneria", "Biotecnologie"):
        "biotechnology biomedical genetic pharmaceutical clinical research",
    ("Ingegneria", "Nanoelettronica"):
        "nanotechnology quantum computing nanoscale graphene quantum dots",
    ("Ingegneria", "Automazione"):
        "automation robotics artificial intelligence machine learning autonomous systems",
    ("Finanza", "Mercati"):
        "stock market trading equity shares bonds commodities prices",
    ("Finanza", "Investimenti"):
        "investment portfolio funds venture capital IPO mergers acquisitions",
    ("Finanza", "Criptovalute"):
        "cryptocurrency bitcoin blockchain ethereum DeFi tokens NFT",
    ("Politica", "Internazionale"):
        "international politics global diplomacy war sanctions geopolitics",
    ("Politica", "Locale"):
        "local politics elections government parliament local governance",
    ("Politica", "Europea"):
        "European Union EU eurozone commission parliament Brussels policy",
}

# ---------------------------------------------------------------------------
# Embeddings state
# ---------------------------------------------------------------------------
_embeddings_enabled: bool = os.getenv("USE_EMBEDDINGS", "1").lower() not in ("0", "false", "no")
_model = None
_category_embeddings = None


def _load_model() -> bool:
    global _model, _category_embeddings
    if _model is not None:
        return True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        import numpy as np  # type: ignore

        _model = SentenceTransformer("all-MiniLM-L6-v2")
        descriptions = list(CATEGORY_DESCRIPTIONS.values())
        _category_embeddings = _model.encode(descriptions, convert_to_numpy=True)
        logger.info("Embeddings model loaded (%d categories).", len(descriptions))
        return True
    except Exception as exc:
        logger.warning(
            "Embeddings model unavailable (%s). Using keyword matching.", exc
        )
        return False


def _classify_embeddings(title: str) -> Optional[Tuple[str, str]]:
    try:
        import numpy as np  # type: ignore

        emb = _model.encode([title], convert_to_numpy=True)
        sims = (_category_embeddings @ emb.T).flatten()
        best_idx = int(np.argmax(sims))
        if float(sims[best_idx]) < 0.25:
            return None
        return list(CATEGORY_DESCRIPTIONS.keys())[best_idx]
    except Exception as exc:
        logger.debug("Embeddings classify error: %s", exc)
        return None


def _classify_keywords(title: str) -> Optional[Tuple[str, str]]:
    title_lower = title.lower()
    for (macro, branch), keywords in KEYWORD_MAP.items():
        if any(kw in title_lower for kw in keywords):
            return macro, branch
    return None


# Pre-load model at import time (non-blocking; failure is handled gracefully)
if _embeddings_enabled:
    _load_model()


def classify_article(title: str) -> Tuple[str, str]:
    """Return (macro, branch) for *title*. Falls back to ('Generale', 'Altro')."""
    if not title:
        return "Generale", "Altro"

    if _embeddings_enabled and _model is not None:
        result = _classify_embeddings(title)
        if result:
            return result

    result = _classify_keywords(title)
    if result:
        return result

    return "Generale", "Altro"
