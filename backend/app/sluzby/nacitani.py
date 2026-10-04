# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import aktivni_model, nastaveni
from app.jadro.embeddingy import spravce_embeddingu

logger = logging.getLogger(__name__)

_zamek = threading.Lock()
_nacitane: set[str] = set()
_chyby: dict[str, str] = {}


def _klient():
    from ollama import Client

    return Client(host=nastaveni().ollama_url)


def _nacti_llm(model: str) -> None:
    konfigurace = nastaveni()
    try:
        _klient().generate(
            model=model,
            prompt="",
            keep_alive=konfigurace.udrzet_model_v_pameti,
            options={"num_ctx": konfigurace.kontext_modelu},
        )
        _chyby.pop(model, None)
        logger.info("Jazykový model %s načten do paměti.", model)
    except Exception as chyba:
        _chyby[model] = str(chyba)
        logger.warning("Jazykový model %s se nepodařilo načíst: %s", model, chyba)
    finally:
        with _zamek:
            _nacitane.discard(model)


def predehrej_llm(model: str | None = None, v_pozadi: bool = True) -> None:
    nazev = model or aktivni_model()
    with _zamek:
        if nazev in _nacitane:
            return
        _nacitane.add(nazev)
    if v_pozadi:
        threading.Thread(target=_nacti_llm, args=(nazev,), daemon=True).start()
    else:
        _nacti_llm(nazev)


def _nacti_embeddingy() -> None:
    try:
        spravce_embeddingu().nacti_model()
    except Exception as chyba:
        logger.warning("Embedding model se nepodařilo načíst: %s", chyba)


def predehrej_embeddingy() -> None:
    threading.Thread(target=_nacti_embeddingy, daemon=True).start()


def predehrej_vse() -> None:
    if not nastaveni().predehrat_modely:
        return
    predehrej_llm()
    predehrej_embeddingy()


def _modely_v_pameti() -> set[str] | None:
    try:
        odpoved = _klient().ps()
    except Exception:
        return None
    return {
        str(m.get("model") or m.get("name"))
        for m in odpoved.get("models", [])
        if m.get("model") or m.get("name")
    }


def stav_nacitani() -> dict[str, Any]:
    model = aktivni_model()
    with _zamek:
        nacita = model in _nacitane
    v_pameti = _modely_v_pameti()

    if nacita:
        stav_llm = "nacita"
    elif v_pameti is None:
        stav_llm = "nedostupny"
    elif model in v_pameti:
        stav_llm = "pripraven"
    else:
        stav_llm = "nenacten"

    return {
        "llm": {"model": model, "stav": stav_llm, "chyba": _chyby.get(model)},
        "embedding": {
            "model": nastaveni().model_embeddingu,
            "stav": spravce_embeddingu().stav,
        },
    }
