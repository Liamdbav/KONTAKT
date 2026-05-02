"""Formatage et affichage des résultats."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from typing import Literal

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()

OutputFormat = Literal["table", "json", "csv"]

_TYPE_STYLE: dict[str, tuple[str, str]] = {
    "email":   ("blue",    "📧"),
    "phone":   ("green",   "📞"),
    "form":    ("yellow",  "📋"),
    "address": ("cyan",    "📍"),
}

_CSV_FIELDS = ["type", "value", "confidence", "source_url"]


@dataclass
class ScanResult:
    """Résultat agrégé d'un crawl + extraction."""

    url: str
    contacts: list[dict]
    pages_crawled: int


def render(result: ScanResult, *, fmt: OutputFormat = "table") -> None:
    """Affiche les résultats dans le format demandé.

    Args:
        result: Résultat agrégé.
        fmt: "table" (rich), "json", ou "csv".
    """
    match fmt:
        case "table":
            _render_table(result)
        case "json":
            _render_json(result)
        case "csv":
            _render_csv(result)


# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------

def _render_table(result: ScanResult) -> None:
    console.print(
        f"\n[bold]kontakt[/bold] · [dim]{result.url}[/dim] "
        f"([dim]{result.pages_crawled} page(s) crawlée(s)[/dim])\n"
    )

    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        expand=False,
        padding=(0, 1),
    )
    table.add_column("Type",      style="bold", width=10, no_wrap=True)
    table.add_column("Valeur",    min_width=30, max_width=60)
    table.add_column("Confiance", justify="right", width=10, no_wrap=True)
    table.add_column("Source URL", style="dim",  min_width=20, max_width=50)

    for c in result.contacts:
        table.add_row(
            _type_cell(c["type"]),
            _value_cell(c),
            _confidence_cell(c["confidence"]),
            _truncate(c.get("source_url", ""), 50),
        )

    console.print(table)
    console.print(
        f"[dim]{len(result.contacts)} résultat(s)[/dim]\n"
    )


def _render_json(result: ScanResult) -> None:
    payload = {
        "url": result.url,
        "pages_crawled": result.pages_crawled,
        "total": len(result.contacts),
        "contacts": result.contacts,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _render_csv(result: ScanResult) -> None:
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=_CSV_FIELDS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for c in result.contacts:
        writer.writerow({
            "type":       c["type"],
            "value":      c["value"],
            "confidence": f"{c['confidence']:.2f}",
            "source_url": c.get("source_url", ""),
        })


# ---------------------------------------------------------------------------
# Helpers de rendu
# ---------------------------------------------------------------------------

def _type_cell(kind: str) -> Text:
    style, icon = _TYPE_STYLE.get(kind, ("white", "·"))
    t = Text()
    t.append(icon + " ", style="default")
    t.append(kind, style=style)
    return t


def _value_cell(contact: dict) -> Text:
    t = Text(contact["value"], overflow="ellipsis")
    kind = contact["type"]
    if kind == "email":
        t.append(f"  ({contact.get('email_type', '')})", style="dim")
    elif kind == "phone" and contact.get("country"):
        t.append(f"  {contact['country']}", style="dim")
    elif kind == "form" and contact.get("fields"):
        fields_str = ", ".join(contact["fields"][:4])
        t.append(f"  [{fields_str}]", style="dim")
    elif kind == "address" and contact.get("country"):
        t.append(f"  {contact['country']}", style="dim")
    return t


def _confidence_cell(score: float) -> Text:
    pct = f"{score:.0%}"
    if score >= 0.85:
        style = "green"
    elif score >= 0.70:
        style = "yellow"
    else:
        style = "red"
    return Text(pct, style=style, justify="right")


def _truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[: max_len - 1] + "…"
