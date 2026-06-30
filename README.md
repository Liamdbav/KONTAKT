# kontakt · CLI

> Découvrez les canaux de contact publics d'un site web à partir de son URL.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![httpx](https://img.shields.io/badge/httpx-async-009688?style=flat-square)
![BeautifulSoup4](https://img.shields.io/badge/BeautifulSoup4-HTML_parsing-43A047?style=flat-square)
![Click](https://img.shields.io/badge/Click-CLI-EF6C00?style=flat-square)
![Rich](https://img.shields.io/badge/Rich-terminal_UI-7B1FA2?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

---

## Aperçu

```
$ kontakt https://stripe.com

 URL             https://stripe.com
 Pages visitées  8

 Type       Valeur                          Source
 ─────────────────────────────────────────────────────────────────
 Contact    contact@stripe.com              /contact
 Sales      sales@stripe.com                /contact/sales
 Privacy    privacy@stripe.com              /privacy
 Support    support@stripe.com              /support
```

---

## Installation

```bash
pip install -e .
```

---

## Usage

```bash
kontakt https://example.com

# Sortie JSON
kontakt https://example.com --format json

# Export CSV
kontakt https://example.com --format csv

# Crawler plus large avec timeout étendu
kontakt https://example.com --max-pages 20 --timeout 15
```

---

## Options

| Option | Défaut | Description |
|---|---|---|
| `--format` | `table` | Format de sortie : `table`, `json`, `csv` |
| `--max-pages` | `10` | Nombre maximum de pages à explorer |
| `--timeout` | `10` | Timeout HTTP en secondes |

---

## Structure du projet

```
kontakt/
├── cli.py              # Point d'entrée Click, agrégation des résultats
├── scraper.py          # Crawl HTTP (fetch_pages), découverte de liens
├── output.py           # Rendu table / JSON / CSV
└── extractors/
    ├── email.py        # Emails (mailto:, data-email, texte brut)
    ├── phone.py        # Téléphones FR/UK/US/INTL, normalisation E.164
    ├── forms.py        # Formulaires de contact (scoring heuristique)
    └── address.py      # Adresses postales FR/UK/US/DE
```

---

## Développement

**Prérequis** : Python 3.12+

```bash
# Installer avec les dépendances de développement
pip install -e ".[dev]"

# Lancer la suite de tests
pytest

# Un seul module
pytest tests/test_extractors.py -v

# Avec couverture
pytest --cov=kontakt --cov-report=term-missing
```

### Ajouter un extracteur

1. Créer `kontakt/extractors/mon_extracteur.py` :
   ```python
   def extract_xxx(html: str, base_url: str) -> list[dict]:
       # retourne des dicts avec au minimum : value, source, confidence
   ```
2. Importer et appeler l'extracteur dans `cli.py::_aggregate()`.
3. Ajouter les tests dans `tests/test_extractors.py`.

---

## Nettoyage

```bash
# Supprimer les caches Python
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name "*.egg-info" -exec rm -rf {} +
find . -type d -name ".pytest_cache" -exec rm -rf {} +
find . -name "*.pyc" -delete

# Désinstaller le paquet
pip uninstall kontakt
```

---

<div align="center">

Fait avec soin par **Liam** - License MIT — voir [LICENSE](LICENSE)

</div>
