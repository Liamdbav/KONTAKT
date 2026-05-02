"""Extraction d'adresses e-mail depuis le HTML."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# RFC 5322 simplifié — couvre les cas réels sans sur-matcher.
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.ASCII,
)

# Extensions d'image qui produisent des faux positifs (ex : sprite@2x.png).
_IMAGE_SUFFIXES = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|ico|bmp|tiff?)$", re.IGNORECASE
)

# Préfixes locaux typiques des adresses "no-reply".
_NOREPLY_RE = re.compile(r"^(noreply|no[-.]?reply|donotreply)$", re.IGNORECASE)


def extract_emails(html: str, base_url: str) -> list[dict]:
    """Extrait les adresses e-mail depuis le HTML.

    Détecte les liens ``mailto:``, les attributs ``data-email``, et les
    adresses dans le texte brut. Dédoublonne, filtre les faux positifs,
    et classe chaque adresse en "pro" ou "perso" selon le domaine du site.

    Args:
        html: Contenu HTML brut de la page.
        base_url: URL de la page (utilisée pour la classification pro/perso).

    Returns:
        Liste de dicts ``{"value", "source", "confidence", "type"}``.
    """
    soup = BeautifulSoup(html, "html.parser")
    site_domain = _root_domain(urlparse(base_url).netloc)

    found: dict[str, dict] = {}  # email → best result

    # --- 1. Liens mailto: ---
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if href.lower().startswith("mailto:"):
            raw = href[7:].split("?")[0].strip()
            _add(found, raw, "mailto", 0.95, site_domain)

    # --- 2. Attributs data-email (obfuscation courante) ---
    for tag in soup.find_all(attrs={"data-email": True}):
        raw = tag["data-email"].strip()
        _add(found, raw, "data-email", 0.90, site_domain)

    # --- 3. Texte brut ---
    text = soup.get_text(" ")
    for match in _EMAIL_RE.finditer(text):
        _add(found, match.group(), "text", 0.80, site_domain)

    results = list(found.values())

    # Supprimer noreply@ seulement si d'autres emails ont été trouvés.
    non_noreply = [r for r in results if not _is_noreply(r["value"])]
    return non_noreply if non_noreply else results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add(
    found: dict[str, dict],
    raw: str,
    source: str,
    confidence: float,
    site_domain: str,
) -> None:
    """Valide et insère un email en gardant la détection de plus haute confiance."""
    if not _EMAIL_RE.fullmatch(raw):
        return
    local, domain = raw.split("@", 1)
    if _IMAGE_SUFFIXES.search(local) or _IMAGE_SUFFIXES.search(domain):
        return

    email = raw.lower()
    if email in found and found[email]["confidence"] >= confidence:
        return

    found[email] = {
        "value": email,
        "source": source,
        "confidence": confidence,
        "type": "pro" if _root_domain(email.split("@")[1]) == site_domain else "perso",
    }


def _root_domain(netloc: str) -> str:
    """Retourne les deux derniers composants du domaine (ex: example.com)."""
    parts = netloc.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc.lower()


def _is_noreply(email: str) -> bool:
    local = email.split("@")[0]
    return bool(_NOREPLY_RE.match(local))
