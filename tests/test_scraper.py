"""Tests unitaires pour kontakt.scraper — HTTP mocké avec respx."""

from __future__ import annotations

import pytest
import respx
import httpx
from bs4 import BeautifulSoup

from kontakt.scraper import (
    fetch_pages,
    _normalize_url,
    _is_contact_candidate,
    _discover_links,
)

# ---------------------------------------------------------------------------
# Helpers HTML
# ---------------------------------------------------------------------------

def _html(*links: tuple[str, str]) -> str:
    """Génère un HTML minimal avec les paires (href, texte) données."""
    anchors = "".join(f'<a href="{href}">{text}</a>' for href, text in links)
    return f"<html><body>{anchors}</body></html>"


SIMPLE_PAGE = "<html><body><p>Hello world</p></body></html>"

# httpx normalise les domaines nus en ajoutant un slash pour l'envoi de la requête :
# https://example.com → https://example.com/ (ce que respx intercepte).
# Mais str(response.url) retourne l'URL sans slash final (valeur stockée dans les résultats).
ROOT_MOCK = "https://example.com/"   # URL à enregistrer dans respx
ROOT_URL  = "https://example.com"    # URL retournée par str(response.url)
ROOT = ROOT_MOCK  # alias de commodité pour les mocks
ROOT_WITH_CONTACT = _html(
    ("/contact", "Contact Us"),
    ("/about", "About"),
    ("/products", "Products"),
    ("https://external.com/page", "External"),
)

# ---------------------------------------------------------------------------
# _normalize_url
# ---------------------------------------------------------------------------

def test_normalize_url_adds_https_when_no_scheme():
    assert _normalize_url("example.com") == "https://example.com"

def test_normalize_url_preserves_https():
    assert _normalize_url("https://example.com") == "https://example.com"

def test_normalize_url_preserves_http():
    assert _normalize_url("http://example.com") == "http://example.com"

def test_normalize_url_strips_whitespace():
    assert _normalize_url("  example.com  ") == "https://example.com"

# ---------------------------------------------------------------------------
# _is_contact_candidate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("href,text", [
    ("/contact", ""),
    ("/about-us", ""),
    ("/team", ""),
    ("/equipe", ""),
    ("/nous-contacter", ""),
    ("/impressum", ""),
    ("/imprint", ""),
    ("/mentions-legales", ""),
    ("/legal", ""),
    ("/irrelevant", "Contact the team"),
    ("/irrelevant", "About our company"),
])
def test_is_contact_candidate_matches(href: str, text: str):
    assert _is_contact_candidate(href, text) is True

@pytest.mark.parametrize("href,text", [
    ("/products", "Products"),
    ("/blog", "Latest news"),
    ("/shop", "Buy now"),
    ("/faq", "FAQ"),
])
def test_is_contact_candidate_no_match(href: str, text: str):
    assert _is_contact_candidate(href, text) is False

# ---------------------------------------------------------------------------
# _discover_links
# ---------------------------------------------------------------------------

def test_discover_links_prioritizes_contact_pages():
    html = _html(
        ("/products", "Products"),
        ("/contact", "Contact"),
        ("/blog", "Blog"),
        ("/about", "About"),
    )
    soup = BeautifulSoup(html, "html.parser")
    links = _discover_links(soup, "https://example.com/", "example.com")

    contact_idx  = next(i for i, l in enumerate(links) if "/contact" in l)
    about_idx    = next(i for i, l in enumerate(links) if "/about" in l)
    products_idx = next(i for i, l in enumerate(links) if "/products" in l)

    assert contact_idx < products_idx
    assert about_idx < products_idx

def test_discover_links_excludes_external_domains():
    html = _html(
        ("/internal", "Internal"),
        ("https://other.com/page", "External"),
    )
    soup = BeautifulSoup(html, "html.parser")
    links = _discover_links(soup, "https://example.com/", "example.com")

    assert all("example.com" in l for l in links)
    assert not any("other.com" in l for l in links)

def test_discover_links_deduplicates():
    html = _html(("/contact", "Link 1"), ("/contact", "Link 2"))
    soup = BeautifulSoup(html, "html.parser")
    links = _discover_links(soup, "https://example.com/", "example.com")

    assert links.count("https://example.com/contact") == 1

def test_discover_links_ignores_anchors_and_js():
    html = _html(
        ("#section", "Anchor"),
        ("javascript:void(0)", "JS"),
        ("mailto:a@b.com", "Mail"),
        ("tel:+33123456789", "Phone"),
    )
    soup = BeautifulSoup(html, "html.parser")
    links = _discover_links(soup, "https://example.com/", "example.com")

    assert links == []

def test_discover_links_resolves_relative_urls():
    html = _html(("../contact", "Contact"))
    soup = BeautifulSoup(html, "html.parser")
    links = _discover_links(soup, "https://example.com/sub/page", "example.com")

    assert "https://example.com/contact" in links

def test_discover_links_strips_fragments():
    html = _html(("/contact#form", "Contact form"))
    soup = BeautifulSoup(html, "html.parser")
    links = _discover_links(soup, "https://example.com/", "example.com")

    assert "https://example.com/contact" in links
    assert all("#" not in l for l in links)

# ---------------------------------------------------------------------------
# fetch_pages — tests d'intégration avec respx
#
# Important : respx.mock() crée une nouvelle instance de routeur.
# Les routes DOIVENT être enregistrées via la variable `mock` retournée par
# le context manager (et non via `respx.get()`), sans quoi elles atterrissent
# sur le routeur global et ne sont pas interceptées.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_pages_returns_root():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))

        pages = await fetch_pages("https://example.com")

        assert len(pages) >= 1
        assert pages[0]["url"] == ROOT_URL
        assert pages[0]["status"] == 200
        assert "Hello world" in pages[0]["html"]


@pytest.mark.asyncio
async def test_fetch_pages_normalizes_url():
    """Le schéma https:// est ajouté automatiquement."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))

        pages = await fetch_pages("example.com")

        assert len(pages) >= 1


@pytest.mark.asyncio
async def test_fetch_pages_follows_contact_links():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(return_value=httpx.Response(200, text=ROOT_WITH_CONTACT))
        mock.get("https://example.com/contact").mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))
        mock.get("https://example.com/about").mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))
        mock.get("https://example.com/products").mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))

        pages = await fetch_pages("https://example.com")
        urls = [p["url"] for p in pages]

        assert ROOT_URL in urls
        assert "https://example.com/contact" in urls
        assert "https://example.com/about" in urls
        assert not any("external.com" in u for u in urls)


@pytest.mark.asyncio
async def test_fetch_pages_contact_links_fetched_before_others():
    """Les pages contact sont visitées avant les autres pages internes."""
    html = _html(
        ("/products", "Products"),
        ("/blog", "Blog"),
        ("/contact", "Contact"),
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(return_value=httpx.Response(200, text=html))
        mock.get("https://example.com/contact").mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))
        mock.get("https://example.com/products").mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))
        mock.get("https://example.com/blog").mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))

        pages = await fetch_pages("https://example.com")
        urls = [p["url"] for p in pages]

        contact_idx  = urls.index("https://example.com/contact")
        products_idx = urls.index("https://example.com/products")
        assert contact_idx < products_idx


@pytest.mark.asyncio
async def test_fetch_pages_skips_404():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(
            return_value=httpx.Response(200, text=_html(("/missing", "Gone")))
        )
        mock.get("https://example.com/missing").mock(return_value=httpx.Response(404, text="Not Found"))

        pages = await fetch_pages("https://example.com")
        urls = [p["url"] for p in pages]

        assert ROOT_URL in urls
        assert "https://example.com/missing" not in urls


@pytest.mark.asyncio
async def test_fetch_pages_skips_500():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(
            return_value=httpx.Response(200, text=_html(("/error", "Error page")))
        )
        mock.get("https://example.com/error").mock(return_value=httpx.Response(500, text="Server Error"))

        pages = await fetch_pages("https://example.com")
        urls = [p["url"] for p in pages]

        assert "https://example.com/error" not in urls


@pytest.mark.asyncio
async def test_fetch_pages_skips_timeout():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(
            return_value=httpx.Response(200, text=_html(("/slow", "Slow page")))
        )
        mock.get("https://example.com/slow").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        pages = await fetch_pages("https://example.com")
        urls = [p["url"] for p in pages]

        assert "https://example.com/slow" not in urls


@pytest.mark.asyncio
async def test_fetch_pages_skips_ssl_error():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(side_effect=httpx.RequestError("SSL error"))

        pages = await fetch_pages("https://example.com")

        assert pages == []


@pytest.mark.asyncio
async def test_fetch_pages_respects_max_pages():
    """Ne crawle pas plus de _MAX_PAGES (10) pages."""
    many_links = _html(*[(f"/{i}", f"Page {i}") for i in range(15)])

    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(return_value=httpx.Response(200, text=many_links))
        for i in range(15):
            mock.get(f"https://example.com/{i}").mock(
                return_value=httpx.Response(200, text=SIMPLE_PAGE)
            )

        pages = await fetch_pages("https://example.com")

        assert len(pages) <= 10


@pytest.mark.asyncio
async def test_fetch_pages_deduplicates_visits():
    """Une même URL n'est visitée qu'une seule fois, pas de boucle infinie."""
    html_a = _html(("/b", "B"))
    html_b = _html(("/", "Home"), ("/b", "B again"))

    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(return_value=httpx.Response(200, text=html_a))
        mock.get("https://example.com/b").mock(return_value=httpx.Response(200, text=html_b))

        pages = await fetch_pages("https://example.com")
        urls = [p["url"] for p in pages]

        assert urls.count(ROOT_URL) == 1
        assert urls.count("https://example.com/b") == 1


@pytest.mark.asyncio
async def test_fetch_pages_does_not_follow_external_links():
    html = _html(
        ("https://external.com/contact", "External contact"),
        ("/internal", "Internal"),
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get(ROOT).mock(return_value=httpx.Response(200, text=html))
        mock.get("https://example.com/internal").mock(return_value=httpx.Response(200, text=SIMPLE_PAGE))

        pages = await fetch_pages("https://example.com")
        urls = [p["url"] for p in pages]

        assert not any("external.com" in u for u in urls)
