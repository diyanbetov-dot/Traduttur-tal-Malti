"""
legacy/tests/test_legacy_basics.py

Representative regression tests for the legacy (v1) translator.
These tests document known outputs and protect against accidental regressions
when the legacy engine is preserved alongside v2.

Run with:
    python -m pytest legacy/tests/test_legacy_basics.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure the engine is not swapped during test runs
os.environ.setdefault("TRANSLATOR_ENGINE", "legacy")

from Essentials.translator import MalteseTranslator  # noqa: E402

FINALDICS_DIR = Path(__file__).resolve().parents[2] / "Essentials" / "finaldics"


@pytest.fixture(scope="module")
def tr() -> MalteseTranslator:
    return MalteseTranslator(FINALDICS_DIR)


def translate(tr: MalteseTranslator, text: str) -> str:
    return tr.translate(text, direction="en-mt").translated_text


# ---------------------------------------------------------------------------
# Basic vocabulary
# ---------------------------------------------------------------------------

def test_cow(tr):
    result = translate(tr, "That is a cow.")
    assert "baqra" in result.lower(), f"Expected 'baqra' in: {result!r}"


def test_forest(tr):
    result = translate(tr, "This is a forest.")
    assert "bosk" in result.lower() or "foresta" in result.lower(), f"Expected forest in: {result!r}"


# ---------------------------------------------------------------------------
# Pronouns and copula
# ---------------------------------------------------------------------------

def test_i_love_music(tr):
    result = translate(tr, "I like music.")
    assert "inħobb" in result or "nħobb" in result, f"Expected love verb in: {result!r}"
    assert "mużika" in result, f"Expected mużika in: {result!r}"


# ---------------------------------------------------------------------------
# Negation
# ---------------------------------------------------------------------------

def test_he_doesnt_know(tr):
    result = translate(tr, "He doesn't know.")
    assert "ma" in result.lower() and ("jafx" in result or "nafx" in result or "jaf" in result), (
        f"Expected negated know in: {result!r}"
    )


def test_they_cannot_go(tr):
    result = translate(tr, "They can't go.")
    assert "ma" in result.lower() or "stgħux" in result.lower() or "nistgħux" in result.lower(), (
        f"Expected negated can in: {result!r}"
    )


# ---------------------------------------------------------------------------
# Progressive
# ---------------------------------------------------------------------------

def test_she_is_running(tr):
    result = translate(tr, "She is running.")
    # progressive marker or active participle
    assert "qed" in result or "tiġri" in result or "ġejja" in result, (
        f"Expected progressive in: {result!r}"
    )


def test_we_are_eating(tr):
    result = translate(tr, "We are eating.")
    assert "qed" in result or "nieklu" in result, f"Expected eating in: {result!r}"


# ---------------------------------------------------------------------------
# Must / modal
# ---------------------------------------------------------------------------

def test_you_must_listen(tr):
    result = translate(tr, "You must listen.")
    assert "trid" in result or "tisma" in result, f"Expected must/listen in: {result!r}"


def test_i_must_go(tr):
    result = translate(tr, "I must go.")
    assert "rrid" in result or "immur" in result, f"Expected must/go in: {result!r}"


# ---------------------------------------------------------------------------
# Past tense
# ---------------------------------------------------------------------------

def test_i_went_to_school(tr):
    result = translate(tr, "I went to school.")
    assert "mort" in result or "l-iskola" in result, f"Expected past/school in: {result!r}"


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def test_do_you_understand_question(tr):
    result = translate(tr, "Do you understand the question?")
    assert "tifhem" in result, f"Expected tifhem in: {result!r}"
    assert "?" in result, f"Expected question mark in: {result!r}"


def test_do_they_want_to_come(tr):
    result = translate(tr, "Do they want to come?")
    assert "jridu" in result or "jiġu" in result, f"Expected want/come in: {result!r}"


# ---------------------------------------------------------------------------
# Transitive with object
# ---------------------------------------------------------------------------

def test_she_loves_him(tr):
    result = translate(tr, "She loves him.")
    assert "tħobb" in result or "tħobbu" in result, f"Expected loves in: {result!r}"


def test_i_see_them(tr):
    result = translate(tr, "I see them.")
    assert "narahom" in result or "nara" in result, f"Expected see/them in: {result!r}"


# ---------------------------------------------------------------------------
# Can pattern
# ---------------------------------------------------------------------------

def test_we_cant_go_swimming(tr):
    result = translate(tr, "We can't go swimming.")
    assert "ma" in result.lower() and ("nistgħux" in result or "immorru" in result or "ngħumu" in result), (
        f"Expected can't/swimming in: {result!r}"
    )


# ---------------------------------------------------------------------------
# Complement chain
# ---------------------------------------------------------------------------

def test_they_decided_to_run(tr):
    result = translate(tr, "They decided to run.")
    assert "ddeċidew" in result or "jiġru" in result, f"Expected decided/run in: {result!r}"


# ---------------------------------------------------------------------------
# Copula / noun predicate
# ---------------------------------------------------------------------------

def test_that_is_a_woman(tr):
    result = translate(tr, "That is a woman.")
    assert "mara" in result, f"Expected mara in: {result!r}"


def test_we_are_friends(tr):
    result = translate(tr, "We are friends.")
    assert "ħbieb" in result, f"Expected ħbieb in: {result!r}"
