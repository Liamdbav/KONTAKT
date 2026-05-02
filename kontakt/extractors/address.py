"""Extraction d'adresses postales depuis le HTML."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Patterns ordonnés du plus spécifique au moins spécifique.
# Quand un pattern plus spécifique matche une région du texte, les patterns
# génériques qui s'y superposent sont ignorés (span tracking).
_POSTAL_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # UK : SW1A 2AA / NW1 6XE — alphanumérique, non-ambigu
    (re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s+\d[A-Z]{2}\b"), "UK", 0.85),
    # US : DC 20500 / CA 90210 — code d'état 2 lettres suivi du zip
    (re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"), "US", 0.80),
    # FR : 75001 / 69001 — 5 chiffres dans la plage 01000–95999
    (re.compile(r"\b(?:0[1-9]|[1-8]\d|9[0-5])\d{3}\b"), "FR", 0.80),
    # DE : 10115 / 80331 — 5 chiffres restants (01000–99999)
    (re.compile(r"\b(?:0[1-9]|[1-9]\d)\d{3}\b"), "DE", 0.75),
]

_WHITESPACE_RE = re.compile(r"\s+")


def extract_addresses(html: str, base_url: str) -> list[dict]:
    """Extrait les adresses postales depuis le HTML.

    Priorité :
    1. Balises ``<address>`` (HTML sémantique)
    2. Microdata schema.org ``PostalAddress``
    3. Regex sur le texte brut — du pattern le plus spécifique (UK, US) au
       plus générique (FR, DE) ; une région déjà matchée par un pattern
       précis n'est plus capturée par un pattern plus générique.

    Args:
        html: Contenu HTML brut de la page.
        base_url: URL de la page (non utilisée directement).

    Returns:
        Liste de dicts ``{"value", "country", "source", "confidence"}``.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: list[dict] = []
    seen: set[str] = set()

    # --- 1. Balises <address> ---
    for tag in soup.find_all("address"):
        text = _clean(tag.get_text(" "))
        if text and text not in seen:
            seen.add(text)
            found.append({
                "value": text,
                "country": None,
                "source": "address-tag",
                "confidence": 0.90,
            })

    # --- 2. Microdata schema.org PostalAddress ---
    for tag in soup.find_all(itemtype=re.compile(r"PostalAddress", re.IGNORECASE)):
        text = _clean(tag.get_text(" "))
        if text and text not in seen:
            seen.add(text)
            found.append({
                "value": text,
                "country": _schema_country(tag),
                "source": "schema.org",
                "confidence": 0.92,
            })

    # --- 3. Regex sur le texte brut avec suivi de régions ---
    full_text = soup.get_text(" ")
    matched_spans: list[tuple[int, int]] = []

    for pattern, country, confidence in _POSTAL_PATTERNS:
        for match in pattern.finditer(full_text):
            ms, me = match.start(), match.end()
            # Ignorer si ce match est contenu dans une région déjà capturée
            # par un pattern plus spécifique (qui a tourné avant).
            if any(s <= ms and me <= e for s, e in matched_spans):
                continue
            matched_spans.append((ms, me))
            context = _extract_context(full_text, ms, me)
            if context and context not in seen:
                seen.add(context)
                found.append({
                    "value": context,
                    "country": country,
                    "source": "regex",
                    "confidence": confidence,
                })

    return found


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _extract_context(text: str, start: int, end: int, window: int = 120) -> str:
    """Retourne une fenêtre de texte centrée autour d'un match de code postal."""
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    left = text.rfind("\n", ctx_start, start)
    right = text.find("\n", end, ctx_end)
    if left != -1:
        ctx_start = left + 1
    if right != -1:
        ctx_end = right
    return _clean(text[ctx_start:ctx_end])


def _schema_country(tag) -> str | None:
    country_tag = tag.find(itemprop="addressCountry")
    if country_tag:
        return _clean(country_tag.get_text(" ")) or None
    return None
