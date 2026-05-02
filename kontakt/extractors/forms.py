"""Extraction de formulaires de contact depuis le HTML."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

# Mots-clés dans l'action ou l'id/class du form qui suggèrent un contact.
_ACTION_KEYWORDS = re.compile(
    r"contact|send|message|submit|mail|inquiry|enquiry|support",
    re.IGNORECASE,
)

# Noms/ids/placeholders typiques d'un formulaire de contact.
_FIELD_SCORES: dict[str, int] = {
    "email": 3,
    "message": 3,
    "name": 2,
    "subject": 2,
    "phone": 1,
    "company": 1,
    "body": 2,
    "content": 1,
    "comment": 2,
    "nom": 2,
    "prenom": 1,
    "sujet": 2,
    "objet": 2,
    "texte": 1,
}


def extract_forms(html: str, base_url: str) -> list[dict]:
    """Détecte les formulaires de contact dans le HTML.

    Combine plusieurs heuristiques :
    - mots-clés dans l'action, l'id ou la classe du formulaire
    - présence de champs typiques (email, message, name, subject…)
    Un score de pertinence donne la confidence finale.

    Args:
        html: Contenu HTML brut de la page.
        base_url: URL de la page, pour résoudre les actions relatives.

    Returns:
        Liste de dicts ``{"value", "fields", "source", "confidence"}``.
        ``value`` contient l'URL absolue de l'action (ou ``base_url`` si vide).
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for form in soup.find_all("form"):
        score, fields = _score_form(form)
        if score == 0:
            continue

        action = form.get("action", "") or ""
        action_url = urljoin(base_url, action) if action else base_url

        confidence = min(0.95, 0.40 + score * 0.08)
        results.append({
            "value": action_url,
            "fields": fields,
            "source": "form",
            "confidence": round(confidence, 2),
        })

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_form(form: Tag) -> tuple[int, list[str]]:
    """Retourne (score, liste des champs détectés) pour un <form>."""
    score = 0
    detected_fields: list[str] = []

    # Bonus si l'action/id/class du form contient un mot-clé contact.
    action = form.get("action", "") or ""
    form_id = form.get("id", "") or ""
    form_class = " ".join(form.get("class", []))
    if _ACTION_KEYWORDS.search(action + " " + form_id + " " + form_class):
        score += 3

    # Analyse des champs.
    for tag in form.find_all(["input", "textarea", "select"]):
        field_hints = " ".join(filter(None, [
            tag.get("name", ""),
            tag.get("id", ""),
            tag.get("placeholder", ""),
            tag.get("type", ""),
            tag.get("autocomplete", ""),
        ])).lower()

        # input type="email" est un indicateur fort indépendamment du nom.
        if tag.get("type", "").lower() == "email":
            if "email" not in detected_fields:
                detected_fields.append("email")
                score += _FIELD_SCORES["email"]
            continue

        for keyword, points in _FIELD_SCORES.items():
            if keyword in field_hints and keyword not in detected_fields:
                detected_fields.append(keyword)
                score += points
                break

    return score, detected_fields
