"""Extraction de numéros de téléphone depuis le HTML."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# (pattern, pays, confidence_base)
# Les patterns avec indicatif explicite (+33, +44, +1) ont priorité.
_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # FR — indicatif international
    (re.compile(r"(?:\+33|0033)[\s.\-]?[1-9](?:[\s.\-]?\d{2}){4}"), "FR", 0.95),
    # FR — format local 0X XX XX XX XX
    (re.compile(r"\b0[1-9](?:[\s.\-]?\d{2}){4}\b"), "FR", 0.80),
    # UK — indicatif international
    (re.compile(r"(?:\+44|0044)[\s.\-]?\d{2,4}[\s.\-]?\d{3,4}[\s.\-]?\d{4}"), "UK", 0.95),
    # US — indicatif international
    (re.compile(r"\+1[\s.\-]?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}"), "US", 0.95),
    # US — format local (XXX) XXX-XXXX ou XXX-XXX-XXXX
    (re.compile(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}"), "US", 0.70),
    # International générique — +XX... (catch-all pour DE, ES, IT…)
    (re.compile(r"\+\d{1,3}[\s.\-]?\d{2,4}(?:[\s.\-]?\d{2,4}){2,4}"), "INTL", 0.85),
]


def extract_phones(html: str, base_url: str) -> list[dict]:
    """Extrait les numéros de téléphone depuis le HTML.

    Détecte les liens ``tel:``, puis cherche dans le texte brut avec des
    patterns couvrant les formats FR, UK, US et internationaux génériques.
    Chaque numéro est normalisé en E.164 dans le champ ``normalized``.

    Args:
        html: Contenu HTML brut de la page.
        base_url: URL de la page (non utilisée directement, présente pour cohérence).

    Returns:
        Liste de dicts ``{"value", "normalized", "country", "source", "confidence"}``.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}  # normalized → best result

    # --- 1. Liens tel: ---
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if href.lower().startswith("tel:"):
            raw = href[4:].strip()
            country, normalized = _normalize(raw)
            _add(found, raw, normalized, country, "tel-href", 0.95)

    # --- 2. Texte brut ---
    text = soup.get_text(" ")
    for pattern, country, confidence in _PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group().strip()
            _, normalized = _normalize(raw, country_hint=country)
            _add(found, raw, normalized, country, "text", confidence)

    return list(found.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(raw: str, country_hint: str = "INTL") -> tuple[str, str]:
    """Retourne (pays détecté, numéro en E.164)."""
    digits = re.sub(r"\D", "", raw)
    has_plus = raw.lstrip().startswith("+")

    if has_plus:
        if digits.startswith("33") and len(digits) == 11:
            return "FR", "+" + digits
        if digits.startswith("44"):
            return "UK", "+" + digits
        if digits.startswith("1") and len(digits) == 11:
            return "US", "+" + digits
        return "INTL", "+" + digits

    if country_hint == "FR" and digits.startswith("0") and len(digits) == 10:
        return "FR", "+33" + digits[1:]
    if country_hint == "UK" and digits.startswith("0"):
        return "UK", "+44" + digits[1:]
    if country_hint == "US" and len(digits) == 10:
        return "US", "+1" + digits

    return country_hint, digits


def _add(
    found: dict[str, dict],
    raw: str,
    normalized: str,
    country: str,
    source: str,
    confidence: float,
) -> None:
    if not normalized or len(re.sub(r"\D", "", normalized)) < 7:
        return
    key = normalized
    if key in found and found[key]["confidence"] >= confidence:
        return
    found[key] = {
        "value": raw,
        "normalized": normalized,
        "country": country,
        "source": source,
        "confidence": confidence,
    }
