# Resource Inventory — Maltese Translator

All paths relative to project root: `c:\Users\diyan\OneDrive\New folder\Desktop\Traduttur tal-Malti\`

---

## Maltese Finaldics (`Essentials/finaldics/`)

### `verbmt_semitic.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/verbmt_semitic.dic` |
| Purpose | Full conjugation paradigm for Semitic-root Maltese verbs |
| Format | `surface/T-root-[FN-]TENSE-PERSON-gloss[-N]` |
| Encoding | UTF-8 with BOM (read as `utf-8-sig`) |
| Lines | 130,756 |
| Schema | Semitic verb paradigm |
| Source | Generated (spellchecker source) |
| Parser | `parse_verb_payload()` in `dictionary_meanings.py` |
| Runtime consumer | `MalteseTranslator._load_verb_dictionary_files()` → `verb_by_gloss` |
| Migration safety | Safe to import non-destructively; do not alter roots |
| Notes | Includes both positive and negative (`-N`) forms |

### `verbmt_nonsemitic.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/verbmt_nonsemitic.dic` |
| Purpose | Full conjugation paradigm for non-Semitic (Romance/loan) Maltese verbs |
| Format | `surface/AS-stem-TENSE-PERSON-gloss[-N]` |
| Encoding | UTF-8 with BOM |
| Lines | 73,223 |
| Schema | Non-semitic verb paradigm |
| Source | Generated |
| Parser | `parse_verb_payload()` |
| Runtime consumer | `MalteseTranslator._load_verb_dictionary_files()` → `verb_by_gloss` |
| Migration safety | Safe; keep stem separated from semitic roots |

### `fixednouns.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/fixednouns.dic` |
| Purpose | Maltese noun lexicon (singular, plural, collective, dual forms) |
| Format | `surface/POS_TAG-gloss` |
| Encoding | UTF-8 with BOM |
| Lines | 11,429 (line 1 is a count header: `11432`) |
| POS tags | `SINGNOUNM`, `SINGNOUNF`, `PLUNOUN`, `PAUCNOUN`, `COLLNOUN`, `DUALNOUN` |
| Source | Generated |
| Parser | `extract_meaning_from_line()` |
| Runtime consumer | `MalteseTranslator._load_dictionary_files()` → `en_to_mt`, `lex_by_gloss` |
| Migration safety | Safe; note: line 1 count header must be skipped |

### `maltese_adjectives.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/maltese_adjectives.dic` |
| Purpose | Maltese adjective lexicon (masculine, feminine, plural forms) |
| Format | `surface/POS_TAG-gloss` |
| Encoding | UTF-8 with BOM |
| Lines | ~3,792 |
| POS tags | `SINGADJM`, `SINGADJF`, `PLUADJ`, `SINGADJM+SINGNOUN` |
| Source | Generated |
| Parser | `extract_meaning_from_line()` |
| Runtime consumer | `_load_dictionary_files()` → `en_to_mt`, `lex_by_gloss` |
| Migration safety | Safe |

### `maltese_adverbs.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/maltese_adverbs.dic` |
| Purpose | Maltese adverb lexicon |
| Format | `surface/ADVERB[-NSPEC]-gloss` |
| Encoding | UTF-8 with BOM |
| Lines | ~400 |
| Parser | `extract_meaning_from_line()` |
| Runtime consumer | `_load_dictionary_files()` |
| Migration safety | Safe |

### `participles.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/participles.dic` |
| Purpose | Active and passive participles of Maltese verbs |
| Format | `surface/POS_TAG-gloss` (uses SINGADJM/F, PLUADJ tags) |
| Encoding | UTF-8 with BOM |
| Lines | ~2,000 |
| Parser | `extract_meaning_from_line()` |
| Runtime consumer | `_load_dictionary_files()` |
| Migration safety | Safe; participles are also adjectives grammatically |

### `prepositions.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/prepositions.dic` |
| Purpose | Maltese prepositions including fused and clitic forms |
| Format | `surface/PREP-gloss` or `surface/DEFPREP-gloss` or `surface/SHORTPREP-gloss` |
| Encoding | UTF-8 with BOM |
| Lines | ~300 |
| Parser | `extract_meaning_from_line()` |
| Runtime consumer | `_load_dictionary_files()` |
| Migration safety | Safe; fused forms (fil-, għal-...) are separate entries |

### `maltese_pronouns.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/maltese_pronouns.dic` |
| Purpose | Personal, demonstrative and other pronouns |
| Format | `surface/PRON[-NSPEC]-gloss` |
| Encoding | UTF-8 with BOM |
| Lines | ~40 |
| Parser | `extract_meaning_from_line()` |
| Runtime consumer | `_load_dictionary_files()` |
| Migration safety | Safe; small file |

### `maltese_articles.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/maltese_articles.dic` |
| Purpose | Maltese definite article forms |
| Encoding | UTF-8 |
| Lines | 1–2 |
| Migration safety | Safe |

### `places.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/places.dic` |
| Purpose | Maltese place names |
| Format | `surface/PLACE-gloss` |
| Encoding | UTF-8 with BOM |
| Lines | ~20,000 |
| Source | Generated |
| Parser | `extract_meaning_from_line()` |
| Runtime consumer | **Skipped** in `_load_dictionary_files()` (excluded by name) |
| Migration safety | Safe to import but keep separate from common lexicon |

### `eu_countries.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/eu_countries.dic` |
| Purpose | EU country names (Maltese) — likely intermediate/legacy |
| Format | `surface/TAG-gloss` |
| Lines | ~1,000 |
| Runtime consumer | Possibly unused; `eu_countries.json` is the primary source |
| Migration safety | Cross-check against JSON; do not merge automatically |

### `eu_countries.json`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/eu_countries.json` |
| Purpose | Structured EU country name pairs with official Maltese forms |
| Format | JSON: `{"records": [{"english", "maltese", "maltese_official"}, ...]}` |
| Lines | ~58 KB |
| Parser | `json.loads()` in `_load_country_json()` |
| Runtime consumer | `MalteseTranslator._load_country_json()` → `en_to_mt` |
| Migration safety | Safe; structured, well-formed |

### `dev_extra.dic`
| Field | Value |
|---|---|
| Path | `Essentials/finaldics/dev_extra.dic` |
| Purpose | Developer/experimental extra verb entries |
| Format | Same as verb paradigm files |
| Lines | ~200 |
| Source | Manually maintained |
| Parser | `parse_verb_payload()` |
| Runtime consumer | `_load_verb_dictionary_files()` |
| Migration safety | Review manually before migrating; may contain experimental data |

---

## English POS Files (`Essentials/english_dics/`)

All files generated by `Essentials/generate_english_dics.py` from the Maltese finaldics glosses.
Format: `gloss/POS_TAG` (most lines) — e.g. `abandon/VERB`
Secondary format in some files: `gloss:extra` — only the key before `:` is used.

### `verbs.dic`
| Lines | ~6,348 | Consumer | `_load_english_dictionaries()` → `english_pos[word].add("VERB")` |

### `nouns.dic`
| Lines | ~10,699 | Consumer | `english_pos[word].add("NOUN")` |

### `adjectives.dic`
| Lines | ~1,200 | Consumer | `english_pos[word].add("ADJ")` |

### `adverbs.dic`
| Lines | ~400 | Consumer | `english_pos[word].add("ADV")` |

### `prepositions.dic`
| Lines | ~50 | Consumer | `english_pos[word].add("PREP")` |

### `determiners.dic`
| Lines | ~20 | Consumer | `english_pos[word].add("DET")` |

### `numbers.dic`
| Lines | ~30 | Consumer | `english_pos[word].add("NUM")` |

### `phrases.dic`
| Lines | ~40 | Consumer | `english_pos[phrase].add("PHRASE")` |

**Important note**: These files are derived from Maltese dictionary glosses, not from a standardised English wordlist. Glosses like `"a neckband"` or `"344 imperial square yards"` appear as "verbs" because they were listed as glosses for Maltese verbs. They should not be used as authoritative English POS data.

---

## Source Code Files

### `Essentials/translator.py`
| Lines | 4,259 | Purpose | Main translation engine — single monolithic class |
| Key classes | `MalteseTranslator`, `TranslationResult`, `TranslationCandidate`, `VerbTranslationRecord`, `LexicalRecord`, `TransferClause`, `TransferNounPhrase` |

### `Essentials/dictionary_meanings.py`
| Lines | 709 | Purpose | Low-level .dic file parsers |
| Key functions | `extract_meaning_from_line()`, `parse_verb_payload()`, `split_dictionary_line()` |
| Reuse | Import directly in v2 — no changes needed |

### `Essentials/ai_assist.py`
| Lines | 205 | Purpose | Gemini/OpenAI API wrappers |
| Key functions | `tag_sentence()`, `route_translation()`, `review_translation()`, `translate_text()` |

### `Essentials/app.py`
| Lines | 111 | Purpose | Flask routes |

### `Essentials/generate_english_dics.py`
| Lines | 152 | Purpose | Script to regenerate `english_dics/` from finaldics |
| Status | Run manually when finaldics change |

### `Essentials/devtoy.js`
| Size | 36 KB | Purpose | Frontend dev tools (gated by `ENABLE_DEV_TOOLS`) |

### `Essentials/index.html`
| Size | 27 KB | Purpose | Main frontend |

---

## Migration Safety Summary

| File | Auto-migration safe? | Notes |
|---|---|---|
| `verbmt_semitic.dic` | Yes | Import non-destructively; verify record counts |
| `verbmt_nonsemitic.dic` | Yes | Keep separate from semitic |
| `fixednouns.dic` | Yes | Skip line 1 count header |
| `maltese_adjectives.dic` | Yes | |
| `maltese_adverbs.dic` | Yes | |
| `participles.dic` | Yes | |
| `prepositions.dic` | Yes | |
| `maltese_pronouns.dic` | Yes | |
| `places.dic` | Yes (separately) | Keep isolated from main lexicon |
| `eu_countries.json` | Yes | Well-structured |
| `eu_countries.dic` | Verify first | Cross-check with JSON |
| `dev_extra.dic` | Manual review | May contain experimental data |
| `english_dics/*.dic` | Do not migrate as authoritative | Use spaCy instead for English POS |
