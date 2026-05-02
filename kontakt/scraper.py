"""Logique de scraping HTTP — crawl et extraction."""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Mots-clés qui qualifient une page comme candidate au contact.
_CONTACT_KEYWORDS = frozenset([
    "contact", "about", "team", "equipe", "nous",
    "imprint", "impressum", "mentions", "legal",
])

_MAX_PAGES = 10
_TIMEOUT = 10.0


def _normalize_url(url: str) -> str:
    """Ajoute le schéma https:// si absent et supprime les espaces."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _base_domain(url: str) -> str:
    """Retourne le netloc (host[:port]) d'une URL."""
    return urlparse(url).netloc


def _is_contact_candidate(href: str, link_text: str) -> bool:
    """Retourne True si l'URL ou le texte du lien contient un mot-clé contact."""
    combined = (href + " " + link_text).lower()
    return any(kw in combined for kw in _CONTACT_KEYWORDS)


async def fetch_pages(
    url: str,
    *,
    max_pages: int = _MAX_PAGES,
    timeout: int = int(_TIMEOUT),
) -> list[dict]:
    """Crawl un site et retourne les pages candidates au contact.

    Fetche la page racine puis suit automatiquement les liens internes dont
    l'URL ou le texte contient un mot-clé de contact. Les pages en erreur
    (timeout, SSL, 4xx/5xx) sont ignorées avec un log warning.

    Args:
        url: URL du site à analyser. Le schéma https:// est ajouté si absent.
        max_pages: Nombre maximum de pages à visiter (défaut : 10).
        timeout: Timeout HTTP en secondes (défaut : 10).

    Returns:
        Liste de dicts ``{"url": str, "html": str, "status": int}``,
        dans l'ordre de visite, limitée à ``max_pages`` entrées.
    """
    url = _normalize_url(url)
    domain = _base_domain(url)

    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(float(timeout)),
    ) as client:
        visited: set[str] = set()
        results: list[dict] = []
        # Les liens contact sont mis en tête de file dans _discover_links.
        queue: list[str] = [url]

        while queue and len(results) < max_pages:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            fetched = await _fetch(client, current)
            if fetched is None:
                continue

            final_url, html, status = fetched
            results.append({"url": final_url, "html": html, "status": status})

            soup = BeautifulSoup(html, "html.parser")
            for link in _discover_links(soup, final_url, domain):
                if link not in visited:
                    queue.append(link)

        return results


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[str, str, int] | None:
    """Télécharge une URL et retourne (url_finale, html, status_code).

    Returns:
        Tuple ou None si la requête échoue ou retourne un code >= 400.
    """
    try:
        response = await client.get(url)
        if response.status_code >= 400:
            logger.warning("HTTP %d — %s ignorée", response.status_code, url)
            return None
        return str(response.url), response.text, response.status_code
    except httpx.TimeoutException:
        logger.warning("Timeout — %s ignorée", url)
        return None
    except httpx.RequestError as exc:
        logger.warning("Erreur réseau — %s ignorée (%s)", url, exc)
        return None


def _discover_links(soup: BeautifulSoup, page_url: str, domain: str) -> list[str]:
    """Extrait les liens internes d'une page, pages de contact en priorité.

    Args:
        soup: Document HTML parsé.
        page_url: URL de la page courante, pour résoudre les liens relatifs.
        domain: Domaine de base (netloc) — les liens externes sont ignorés.

    Returns:
        URLs internes dédupliquées : pages contact en tête, autres ensuite.
    """
    priority: list[str] = []
    others: list[str] = []
    seen: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href: str = tag["href"].strip()
        text: str = tag.get_text(strip=True)

        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        absolute = urljoin(page_url, href).split("#")[0]

        if urlparse(absolute).netloc != domain:
            continue

        if absolute in seen:
            continue
        seen.add(absolute)

        if _is_contact_candidate(absolute, text):
            priority.append(absolute)
        else:
            others.append(absolute)

    return priority + others
