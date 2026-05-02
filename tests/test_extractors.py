"""Tests unitaires pour les quatre extracteurs."""

from __future__ import annotations

import pytest

from kontakt.extractors.email import extract_emails
from kontakt.extractors.phone import extract_phones
from kontakt.extractors.forms import extract_forms
from kontakt.extractors.address import extract_addresses

BASE_URL = "https://example.com"

# ===========================================================================
# Fixtures HTML
# ===========================================================================

EMAIL_MAILTO = """
<html><body>
  <a href="mailto:contact@example.com">Nous écrire</a>
</body></html>
"""

EMAIL_TEXT = """
<html><body>
  <p>Contactez-nous à info@example.com pour toute demande.</p>
</body></html>
"""

EMAIL_DATA_ATTR = """
<html><body>
  <span data-email="sales@example.com">email caché</span>
</body></html>
"""

EMAIL_MULTIPLE = """
<html><body>
  <a href="mailto:contact@example.com">Pro</a>
  <p>Ou écrivez à john@gmail.com pour une réponse perso.</p>
</body></html>
"""

EMAIL_NOREPLY_ONLY = """
<html><body>
  <p>Envoyé depuis noreply@example.com</p>
</body></html>
"""

EMAIL_NOREPLY_WITH_REAL = """
<html><body>
  <a href="mailto:noreply@example.com">system</a>
  <a href="mailto:support@example.com">Support</a>
</body></html>
"""

EMAIL_FALSE_POSITIVE = """
<html><body>
  <img src="sprite@2x.png" alt="icon">
  <p>Asset: icon@3x.jpg</p>
  <p>Contact: real@example.com</p>
</body></html>
"""

EMAIL_DEDUP = """
<html><body>
  <a href="mailto:contact@example.com">Lien</a>
  <p>Ou : contact@example.com</p>
</body></html>
"""

# ---------------------------------------------------------------------------

PHONE_FR_LOCAL = """
<html><body><p>Appelez-nous au 01 23 45 67 89</p></body></html>
"""

PHONE_FR_INTL = """
<html><body><p>Tél : +33 1 23 45 67 89</p></body></html>
"""

PHONE_UK = """
<html><body><p>Call us: +44 20 7946 0958</p></body></html>
"""

PHONE_US = """
<html><body><p>Call us at +1 800 555 1234</p></body></html>
"""

PHONE_TEL_HREF = """
<html><body>
  <a href="tel:+33123456789">Nous appeler</a>
</body></html>
"""

PHONE_DEDUP = """
<html><body>
  <a href="tel:+33123456789">Appeler</a>
  <p>Ou composez le +33 1 23 45 67 89</p>
</body></html>
"""

# ---------------------------------------------------------------------------

FORM_CONTACT = """
<html><body>
  <form action="/contact" method="post">
    <input type="text" name="name" placeholder="Votre nom">
    <input type="email" name="email">
    <textarea name="message"></textarea>
    <button type="submit">Envoyer</button>
  </form>
</body></html>
"""

FORM_NO_CONTACT = """
<html><body>
  <form action="/search" method="get">
    <input type="text" name="q">
    <button>Rechercher</button>
  </form>
</body></html>
"""

FORM_IMPLICIT = """
<html><body>
  <form method="post">
    <input type="email" name="email">
    <textarea name="message"></textarea>
    <button>Envoyer</button>
  </form>
</body></html>
"""

FORM_RELATIVE_ACTION = """
<html><body>
  <form action="send-message" method="post">
    <input type="email">
    <textarea name="body"></textarea>
    <input type="submit">
  </form>
</body></html>
"""

FORM_MULTIPLE = """
<html><body>
  <form action="/contact">
    <input type="email"><textarea name="message"></textarea>
  </form>
  <form action="/search">
    <input type="text" name="q">
  </form>
</body></html>
"""

# ---------------------------------------------------------------------------

ADDRESS_TAG = """
<html><body>
  <address>
    42 rue de la Paix<br>
    75002 Paris<br>
    France
  </address>
</body></html>
"""

ADDRESS_SCHEMA = """
<html><body>
  <div itemscope itemtype="https://schema.org/PostalAddress">
    <span itemprop="streetAddress">10 Downing Street</span>
    <span itemprop="addressLocality">London</span>
    <span itemprop="addressCountry">UK</span>
  </div>
</body></html>
"""

ADDRESS_FR_REGEX = """
<html><body>
  <p>Notre siège : 15 avenue Victor Hugo, 69001 Lyon, France</p>
</body></html>
"""

ADDRESS_UK_REGEX = """
<html><body>
  <p>Find us at 221B Baker Street, London NW1 6XE, UK</p>
</body></html>
"""

ADDRESS_US_REGEX = """
<html><body>
  <p>Visit us: 1600 Pennsylvania Ave, Washington DC 20500</p>
</body></html>
"""

ADDRESS_NONE = """
<html><body><p>Hello world, no address here.</p></body></html>
"""

# ===========================================================================
# Tests — extract_emails
# ===========================================================================

class TestExtractEmails:

    def test_detects_mailto_link(self):
        results = extract_emails(EMAIL_MAILTO, BASE_URL)
        values = [r["value"] for r in results]
        assert "contact@example.com" in values

    def test_mailto_has_high_confidence(self):
        results = extract_emails(EMAIL_MAILTO, BASE_URL)
        r = next(r for r in results if r["value"] == "contact@example.com")
        assert r["confidence"] >= 0.90

    def test_detects_email_in_text(self):
        results = extract_emails(EMAIL_TEXT, BASE_URL)
        values = [r["value"] for r in results]
        assert "info@example.com" in values

    def test_detects_data_email_attribute(self):
        results = extract_emails(EMAIL_DATA_ATTR, BASE_URL)
        values = [r["value"] for r in results]
        assert "sales@example.com" in values

    def test_classifies_pro_email(self):
        results = extract_emails(EMAIL_MAILTO, BASE_URL)
        r = next(r for r in results if r["value"] == "contact@example.com")
        assert r["type"] == "pro"

    def test_classifies_perso_email(self):
        results = extract_emails(EMAIL_MULTIPLE, BASE_URL)
        r = next(r for r in results if r["value"] == "john@gmail.com")
        assert r["type"] == "perso"

    def test_deduplicates_same_email(self):
        results = extract_emails(EMAIL_DEDUP, BASE_URL)
        values = [r["value"] for r in results]
        assert values.count("contact@example.com") == 1

    def test_dedup_keeps_highest_confidence(self):
        results = extract_emails(EMAIL_DEDUP, BASE_URL)
        r = next(r for r in results if r["value"] == "contact@example.com")
        assert r["source"] == "mailto"

    def test_excludes_image_false_positives(self):
        results = extract_emails(EMAIL_FALSE_POSITIVE, BASE_URL)
        values = [r["value"] for r in results]
        assert not any("png" in v or "jpg" in v for v in values)
        assert "real@example.com" in values

    def test_keeps_noreply_when_only_email(self):
        results = extract_emails(EMAIL_NOREPLY_ONLY, BASE_URL)
        assert len(results) >= 1

    def test_filters_noreply_when_other_emails_present(self):
        results = extract_emails(EMAIL_NOREPLY_WITH_REAL, BASE_URL)
        values = [r["value"] for r in results]
        assert "noreply@example.com" not in values
        assert "support@example.com" in values

    def test_returns_empty_on_no_emails(self):
        results = extract_emails("<html><body><p>No contact here.</p></body></html>", BASE_URL)
        assert results == []

    def test_result_has_required_keys(self):
        results = extract_emails(EMAIL_MAILTO, BASE_URL)
        for r in results:
            assert {"value", "source", "confidence", "type"}.issubset(r.keys())


# ===========================================================================
# Tests — extract_phones
# ===========================================================================

class TestExtractPhones:

    def test_detects_fr_local_format(self):
        results = extract_phones(PHONE_FR_LOCAL, BASE_URL)
        assert any("0123456789" in r["normalized"] or "+33" in r["normalized"] for r in results)

    def test_detects_fr_international_format(self):
        results = extract_phones(PHONE_FR_INTL, BASE_URL)
        assert any(r["country"] == "FR" for r in results)

    def test_fr_normalized_to_e164(self):
        results = extract_phones(PHONE_FR_LOCAL, BASE_URL)
        fr = next((r for r in results if r["country"] == "FR"), None)
        assert fr is not None
        assert fr["normalized"].startswith("+33")

    def test_detects_uk_number(self):
        results = extract_phones(PHONE_UK, BASE_URL)
        assert any(r["country"] == "UK" for r in results)

    def test_uk_normalized_to_e164(self):
        results = extract_phones(PHONE_UK, BASE_URL)
        uk = next(r for r in results if r["country"] == "UK")
        assert uk["normalized"].startswith("+44")

    def test_detects_us_number(self):
        results = extract_phones(PHONE_US, BASE_URL)
        assert any(r["country"] == "US" for r in results)

    def test_us_normalized_to_e164(self):
        results = extract_phones(PHONE_US, BASE_URL)
        us = next(r for r in results if r["country"] == "US")
        assert us["normalized"].startswith("+1")

    def test_detects_tel_href(self):
        results = extract_phones(PHONE_TEL_HREF, BASE_URL)
        assert len(results) >= 1
        assert any(r["source"] == "tel-href" for r in results)

    def test_tel_href_high_confidence(self):
        results = extract_phones(PHONE_TEL_HREF, BASE_URL)
        r = next(r for r in results if r["source"] == "tel-href")
        assert r["confidence"] >= 0.90

    def test_deduplicates_same_number(self):
        results = extract_phones(PHONE_DEDUP, BASE_URL)
        normalized_list = [r["normalized"] for r in results]
        assert len(normalized_list) == len(set(normalized_list))

    def test_dedup_prefers_tel_href(self):
        results = extract_phones(PHONE_DEDUP, BASE_URL)
        assert any(r["source"] == "tel-href" for r in results)
        assert not any(r["source"] == "text" for r in results)

    def test_returns_empty_on_no_phones(self):
        results = extract_phones("<html><body><p>No phone here.</p></body></html>", BASE_URL)
        assert results == []

    def test_result_has_required_keys(self):
        results = extract_phones(PHONE_FR_INTL, BASE_URL)
        for r in results:
            assert {"value", "normalized", "country", "source", "confidence"}.issubset(r.keys())


# ===========================================================================
# Tests — extract_forms
# ===========================================================================

class TestExtractForms:

    def test_detects_contact_form(self):
        results = extract_forms(FORM_CONTACT, BASE_URL)
        assert len(results) >= 1

    def test_contact_form_action_url(self):
        results = extract_forms(FORM_CONTACT, BASE_URL)
        assert any("contact" in r["value"] for r in results)

    def test_contact_form_fields_listed(self):
        results = extract_forms(FORM_CONTACT, BASE_URL)
        r = results[0]
        assert "email" in r["fields"]
        assert "message" in r["fields"]

    def test_ignores_search_form(self):
        results = extract_forms(FORM_NO_CONTACT, BASE_URL)
        assert results == []

    def test_detects_form_without_explicit_action(self):
        results = extract_forms(FORM_IMPLICIT, BASE_URL)
        assert len(results) >= 1

    def test_resolves_relative_action(self):
        results = extract_forms(FORM_RELATIVE_ACTION, BASE_URL)
        assert len(results) >= 1
        assert results[0]["value"].startswith("https://")

    def test_confidence_is_float_between_0_and_1(self):
        results = extract_forms(FORM_CONTACT, BASE_URL)
        for r in results:
            assert 0.0 < r["confidence"] <= 1.0

    def test_multiple_forms_only_contact_returned(self):
        results = extract_forms(FORM_MULTIPLE, BASE_URL)
        assert len(results) == 1
        assert "contact" in results[0]["value"]

    def test_result_has_required_keys(self):
        results = extract_forms(FORM_CONTACT, BASE_URL)
        for r in results:
            assert {"value", "fields", "source", "confidence"}.issubset(r.keys())


# ===========================================================================
# Tests — extract_addresses
# ===========================================================================

class TestExtractAddresses:

    def test_detects_address_tag(self):
        results = extract_addresses(ADDRESS_TAG, BASE_URL)
        assert len(results) >= 1
        assert any(r["source"] == "address-tag" for r in results)

    def test_address_tag_high_confidence(self):
        results = extract_addresses(ADDRESS_TAG, BASE_URL)
        r = next(r for r in results if r["source"] == "address-tag")
        assert r["confidence"] >= 0.85

    def test_address_tag_contains_content(self):
        results = extract_addresses(ADDRESS_TAG, BASE_URL)
        r = next(r for r in results if r["source"] == "address-tag")
        assert "Paris" in r["value"] or "75002" in r["value"]

    def test_detects_schema_org(self):
        results = extract_addresses(ADDRESS_SCHEMA, BASE_URL)
        assert any(r["source"] == "schema.org" for r in results)

    def test_schema_org_extracts_country(self):
        results = extract_addresses(ADDRESS_SCHEMA, BASE_URL)
        r = next(r for r in results if r["source"] == "schema.org")
        assert r["country"] == "UK"

    def test_detects_fr_postal_code_in_text(self):
        results = extract_addresses(ADDRESS_FR_REGEX, BASE_URL)
        assert any(r["country"] == "FR" for r in results)
        assert any("Lyon" in r["value"] or "69001" in r["value"] for r in results)

    def test_detects_uk_postal_code_in_text(self):
        results = extract_addresses(ADDRESS_UK_REGEX, BASE_URL)
        assert any(r["country"] == "UK" for r in results)

    def test_detects_us_postal_code_in_text(self):
        results = extract_addresses(ADDRESS_US_REGEX, BASE_URL)
        assert any(r["country"] == "US" for r in results)

    def test_returns_empty_when_no_address(self):
        results = extract_addresses(ADDRESS_NONE, BASE_URL)
        assert results == []

    def test_deduplicates_same_address(self):
        html = ADDRESS_TAG + ADDRESS_TAG
        results = extract_addresses(html, BASE_URL)
        values = [r["value"] for r in results]
        assert len(values) == len(set(values))

    def test_result_has_required_keys(self):
        results = extract_addresses(ADDRESS_TAG, BASE_URL)
        for r in results:
            assert {"value", "country", "source", "confidence"}.issubset(r.keys())
