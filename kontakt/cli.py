"""Point d'entrée CLI — interface Click."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console

from kontakt import __version__
from kontakt.extractors.address import extract_addresses
from kontakt.extractors.email import extract_emails
from kontakt.extractors.forms import extract_forms
from kontakt.extractors.phone import extract_phones
from kontakt.output import ScanResult, render
from kontakt.scraper import fetch_pages

console = Console(stderr=True)


@click.command()
@click.version_option(__version__, prog_name="kontakt")
@click.argument("url")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Format de sortie.",
)
@click.option(
    "--max-pages",
    default=10,
    show_default=True,
    help="Nombre maximum de pages à explorer.",
)
@click.option(
    "--timeout",
    default=10,
    show_default=True,
    help="Timeout HTTP en secondes.",
)
def main(url: str, fmt: str, max_pages: int, timeout: int) -> None:
    """Extrait les canaux de contact publics d'un site web.

    URL est l'adresse du site à analyser (ex: https://example.com).
    """
    try:
        pages = asyncio.run(fetch_pages(url, max_pages=max_pages, timeout=timeout))
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Erreur réseau fatale :[/red] {exc}")
        sys.exit(2)

    if not pages:
        console.print(
            f"[red]Impossible de joindre[/red] [bold]{url}[/bold] "
            "(vérifiez l'URL et votre connexion)"
        )
        sys.exit(2)

    contacts = _aggregate(pages)

    if not contacts:
        console.print(
            f"[yellow]Aucun contact trouvé[/yellow] sur [bold]{url}[/bold] "
            f"({len(pages)} page(s) crawlée(s))"
        )
        sys.exit(1)

    result = ScanResult(
        url=url,
        contacts=contacts,
        pages_crawled=len(pages),
    )
    render(result, fmt=fmt)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Agrégation et déduplication
# ---------------------------------------------------------------------------

def _aggregate(pages: list[dict]) -> list[dict]:
    """Passe chaque page dans les 4 extracteurs et dédoublonne les résultats.

    La déduplication utilise la clé ``(type, value)`` en gardant l'entrée
    de plus haute confiance. Pour les téléphones, ``normalized`` (E.164) sert
    de valeur canonique afin que "01 23 45 67 89" et "+33123456789" fusionnent.

    Returns:
        Contacts triés par confiance décroissante, puis par type.
    """
    seen: dict[tuple[str, str], dict] = {}

    for page in pages:
        html: str = page["html"]
        source_url: str = page["url"]

        for raw in extract_emails(html, source_url):
            _merge(seen, ("email", raw["value"]), {
                "type": "email",
                "value": raw["value"],
                "confidence": raw["confidence"],
                "source_url": source_url,
                "email_type": raw.get("type", ""),
            })

        for raw in extract_phones(html, source_url):
            canonical = raw.get("normalized") or raw["value"]
            _merge(seen, ("phone", canonical), {
                "type": "phone",
                "value": canonical,
                "confidence": raw["confidence"],
                "source_url": source_url,
                "country": raw.get("country"),
            })

        for raw in extract_forms(html, source_url):
            _merge(seen, ("form", raw["value"]), {
                "type": "form",
                "value": raw["value"],
                "confidence": raw["confidence"],
                "source_url": source_url,
                "fields": raw.get("fields", []),
            })

        for raw in extract_addresses(html, source_url):
            _merge(seen, ("address", raw["value"]), {
                "type": "address",
                "value": raw["value"],
                "confidence": raw["confidence"],
                "source_url": source_url,
                "country": raw.get("country"),
            })

    return sorted(
        seen.values(),
        key=lambda c: (-c["confidence"], c["type"], c["value"]),
    )


def _merge(seen: dict, key: tuple[str, str], contact: dict) -> None:
    if key not in seen or contact["confidence"] > seen[key]["confidence"]:
        seen[key] = contact
