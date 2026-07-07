# Current Architecture — Maltese Translator

## 1. Request-to-Response Translation Flow (en-mt)

```
HTTP POST /translate  {text, direction}
  │
  ▼
Essentials/app.py :: translate()
  │  Input validation (empty, too long)
  │
  ▼
MalteseTranslator.translate(text, direction)
  │
  ├─ [if direction == mt-en] → _translate_lookup() → return
  │
  ├─ tag_sentence(text)           ← AI API call (Gemini/OpenAI), optional
  │    if empty → _tag_sentence_locally(text)   ← suffix heuristics
  │
  ▼
_translate_en_mt(text, ai_tags)
  │
  ├── normalize_text(text)
  │
  ├── _translate_pronoun_ambiguity()      regex: pronoun + copula ambiguity
  ├── _translate_transitive_object_pattern()  regex: SUBJ VERB OBJ
  ├── _translate_need_to_pattern()        regex: SUBJ need/want to VERB
  ├── _translate_must_pattern()           regex: SUBJ must/have to VERB
  ├── _translate_modal_transfer_pattern() regex: SUBJ modal VERB
  ├── _translate_connector_clause()       regex: CLAUSE so CLAUSE
  ├── _translate_complement_chain_pattern() regex: SUBJ VERB [OBJ] to VERB
  ├── _translate_do_want_pattern()        regex: do you want to VERB
  ├── _translate_understand_object_question() regex: do you understand X
  ├── _translate_like_pattern()           regex: SUBJ like/love NOUN/VERB
  ├── _translate_can_pattern()            regex: SUBJ can/cannot VERB
  ├── _translate_progressive_pattern()    regex: SUBJ be VERB-ing
  ├── _translate_past_narrative_compound() regex: past tense narrative
  ├── _translate_noun_phrase()            (1st call) noun phrase detection
  ├── _translate_clause_pattern()         regex: simple clause
  ├── _translate_clause_frame_pattern()   regex: clause with frame
  ├── _translate_transfer_clause()        full clause transfer (uses ai_tags)
  ├── _translate_np_subject_transfer_clause()  NP subject + verb clause
  ├── _translate_noun_phrase()            (2nd call — redundant)
  ├── _translate_multi_adjective_noun_phrase() adj+noun phrase
  ├── _translate_lexical_phrase()         single-word/phrase dict lookup
  ├── _preserve_unknown_noun_phrase()     preserve unknown proper nouns
  ├── _translate_story_narrative()        narrative paragraph detection
  ├── _translate_ai_route()               AI API routing call (optional)
  ├── _translate_manual_sentence()        manual sentence list
  ├── en_to_mt direct dict lookup
  ├── translate_text() AI API fallback (optional)
  └── _translate_word_by_word()           token substitution fallback
  │
  ▼
_with_source_punctuation()
  │
  ▼
_with_ai_backup()    ← AI API review + optional repair (optional)
  │
  ▼
TranslationResult{input, direction, translated_text, candidates, suggestions, highlights, notes}
  │
  ▼
JSON response
```

---

## 2. Important Classes and Functions

### `MalteseTranslator` (`Essentials/translator.py`, line 116)

The single class that owns all translation logic.

**Constructor**: `__init__(finaldics_dir: Path)`
- Calls `_load_dictionary_files()` — loads all non-verb .dic files into `en_to_mt` and `mt_to_en`
- Calls `_load_verb_dictionary_files()` — loads `verbmt_semitic.dic`, `verbmt_nonsemitic.dic`, `dev_extra.dic` into `verb_by_gloss`
- Calls `_load_country_json()` — loads `eu_countries.json`
- Calls `_load_manual_entries()` — hardcoded phrase tables loaded into `en_to_mt`
- Calls `_load_english_dictionaries()` — loads `english_dics/*.dic` into `english_pos`

**Core data structures**:
- `en_to_mt: dict[str, list[TranslationCandidate]]` — English gloss → Maltese surface forms
- `mt_to_en: dict[str, list[TranslationCandidate]]` — Maltese surface → English glosses
- `verb_by_gloss: dict[str, list[VerbTranslationRecord]]` — English verb gloss → all conjugated Maltese forms
- `lex_by_gloss: dict[str, list[LexicalRecord]]` — English gloss → Maltese forms with POS/gender/number
- `english_pos: dict[str, set[str]]` — English word → set of POS tags (NOUN/VERB/ADJ/ADV/PREP...)

**Key verb selection**:
- `_select_verb(lemma, tense, person, negative) → VerbTranslationRecord | None`
- `_attach_direct_object_suffix(verb_surface, object_person) → str`
- `_negate_suffixed_verb(surface) → str`
- `_generate_transfer_clause(clause: TransferClause) → str`

**Key morphology**:
- `_definite_noun(surface: str) → str` — applies `il-`, `l-`, assimilation rules
- `_fused_in_surface(noun_surface) → str` — fuses `f'` with definite article
- `_apply_possessive_suffix(noun_mt, pronoun_eng) → str`
- `_generate_noun_phrase(phrase: TransferNounPhrase) → str`

**Key utilities**:
- `normalize_text(value: str) → str` — NFC, casefold, strip special chars
- `split_glosses(value: str) → list[str]` — splits `;`, `,`, `or`, `/`
- `_lemmatize_word(key: str) → tuple[str, str]` — type: `english|maltese|omit`, value: lemma
- `_is_past_english_verb(word: str) → bool` — suffix heuristic + hardcoded list
- `_subject_person(subject: str) → str` — pronoun → person tag (1S, 2S, 3SM...)
- `_candidate_payload_obj(candidate) → dict` — formats candidate for JSON response

---

## 3. English Analysis Method

**POS tagging** (called at entry point):
1. `tag_sentence(text)` — calls Gemini/OpenAI API if `TRANSLATOR_AI_ENABLED=1`; returns list of `{word, lemma, pos, tense, person}` dicts
2. If AI unavailable: `_tag_sentence_locally(text)` — phrase lookup in `english_pos`, then suffix heuristics:
   - `-ing` → verb; `-ly` → adverb; otherwise → noun
   - Previous-token context (e.g., subject pronoun before word → verb)

**Lemmatization** (`_lemmatize_word`):
- Hardcoded irregular map: `{went→go, came→come, ran→run, ...}`
- Suffix stripping: `-ed`, `-ing`, `-s`, `-es`, `-ies`, `-ied`
- If result found in `verb_by_gloss` → type `english`
- If result found in `en_to_mt` → type `english`
- Known Maltese words → type `maltese`
- Known omit words (articles, common function words) → type `omit`

**Tense detection**:
- Regex auxiliary in full-sentence patterns: `did`, `was/were`, `has/have`
- `_is_past_english_verb()`: hardcoded list + `-ed` suffix

---

## 4. Sentence-Pattern Logic

All sentence patterns are tried sequentially in `_translate_en_mt()`.
Each pattern returns `TranslationResult | None`; first non-None wins.

Key patterns:
- `_translate_transfer_clause`: Matches `(did)? PRONOUN (NEG)? VERB (TAIL)?` with a full regex. Constructs Maltese via `_generate_transfer_clause()`.
- `_translate_complement_chain_pattern`: Matches `SUBJ VERB [OBJ] to VERB TAIL` for modal complement chains.
- `_translate_progressive_pattern`: Detects `is/am/are VERB-ing` and routes to `qed` + MPERF form.
- `_translate_can_pattern`: Detects `can/cannot + VERB`, routes to `nista'/ma nistax` + MPERF.
- `_translate_like_pattern`: Detects `like/love + NOUN/VERB`, routes to `jogħġbu/inħobb` constructions.
- `_translate_clause_pattern`: Detects simple `SUBJ is/are NOUN/ADJ` patterns → copula construction.

---

## 5. Hardcoded Constructions

**Class-level constants** (lines 117–240):
- `SUBJECT_JUST_FORMS`: dict mapping English pronouns to Maltese "just did" constructions
- `JUST_ACTION_FORMS`: dict mapping action verbs × pronouns to Maltese past forms
- `ACTION_ALIASES`: irregular verb surface → canonical action key
- `MANUAL_PHRASES`: exact phrase → exact Maltese phrase (very small, e.g. "One day,")
- `WATER_CONTEXT`: set of words triggering masculine adjective form for "cold"
- `PREFERRED_VERB_SURFACES`, `PREFERRED_NOUN_SURFACES`, `PREFERRED_ADJECTIVE_SURFACES`: priority-ranked surface forms

**`_load_manual_entries()`** (lines 403–472):
- ~30 hardcoded phrase pairs (wake up, feel like, at all, really, morning, yesterday, today, tomorrow, etc.)
- ~15 lexical overrides (meadow, grass, little, small, large, green, fresh, home, work, job, etc.)

**Pattern function completeness** varies: some use `re.fullmatch()` with very specific patterns (anchored to exact pronoun lists), others are more general noun-phrase parsers.

---

## 6. Dictionary Formats

### Maltese verb paradigm files (`verbmt_semitic.dic`, `verbmt_nonsemitic.dic`)
```
surface/TYPE-root_or_stem-[FORMCLASS-]TENSE-PERSON-gloss[-N]
```
Examples:
- `jaf/T-''f-F1-MPERF-3SM-to know or be aware`
- `kisirx/T-ksr-PERF-3SM-to not break or not divert-N`
- `abbanduna/AS-abbandun-IMP-2S-to abandon or neglect`

Types: `T` = Semitic, `Q` = Quadriliteral, `S` = Stem, `AS` = Allomorphic Stem, `IS` = Irregular Stem
Tenses: `IMP`, `PERF`, `MPERF`, `ACTPAR`
Person tags: `1S`, `2S`, `3SM`, `3SF`, `1P`, `2P`, `3P`, `12S`, `12P`
Negative marker: trailing `-N`

Parsed by: `parse_verb_payload()` in `dictionary_meanings.py`

### Maltese lexical files (`fixednouns.dic`, `maltese_adjectives.dic`, etc.)
```
surface/POS_TAG-gloss
```
POS tags: `SINGNOUNM`, `SINGNOUNF`, `PLUNOUN`, `SINGADJM`, `SINGADJF`, `PLUADJ`, `ADVERB`, `PREP`, `PRON`, `CONJ`, `DET`, `CARDNUM`, etc.

Parsed by: `extract_meaning_from_line()` in `dictionary_meanings.py`

### English POS files (`english_dics/verbs.dic`, `nouns.dic`, etc.)
Two formats found:
1. `gloss/POS_TAG` (most lines) — e.g. `abandon/VERB`
2. `gloss:extra_info` (some lines) — e.g. `word:definition`

Generated by: `Essentials/generate_english_dics.py` from the Maltese finaldics glosses.
Consumer: `_load_english_dictionaries()` → `english_pos` dict.

### Country data (`eu_countries.json`)
```json
{"records": [{"english": "Malta", "maltese": "Malta", "maltese_official": "ir-Repubblika ta' Malta"}, ...]}
```

---

## 7. Morphology Logic

### Definite article (`_definite_noun`)
Applies Maltese phonological assimilation:
- Solar consonants (n, t, d, s, z, ċ, ż, r, x, ġ) → assimilated article prefix: `in-`, `it-`, etc.
- Otherwise: `il-` (most), `l-` (before vowel)
- Special: `l-` before h + vowel

### Possessive suffixes (`_apply_possessive_suffix`, `NOUN_POSSESSIVE_SUFFIXES`)
- Hardcoded for ~20 common body parts, family members, house
- Fallback: suffix rules based on final phoneme of noun stem

### Fused prepositions (`_fused_in_surface`)
- `f'` + `il-X` → `fil-X`
- `f'` + `l-X` → `fl-X`
- Assimilated forms for `in-`, `is-`, `it-`, `iċ-`, `iż-`

### Verb clitic suffixes (`_attach_direct_object_suffix`)
Appends direct object pronoun suffixes to verb surface forms.
Rules vary by verb ending.

### Negation (`_negate_suffixed_verb`)
Wraps verb in `ma ... x` pattern with phonological adjustments.

---

## 8. AI Review System

Three optional AI integration points, all gated by env vars:

| Function | Env var | Purpose |
|---|---|---|
| `tag_sentence()` | `TRANSLATOR_AI_ENABLED` | POS tagging and lemmatization |
| `route_translation()` | `TRANSLATOR_AI_ENABLED` | Route transitive verb+object patterns |
| `review_translation()` | `TRANSLATOR_AI_REVIEW_ENABLED` | Post-hoc review; suggest corrections |
| `translate_text()` | `TRANSLATOR_AI_ENABLED` | Full AI fallback when all rules fail |

AI provider: Gemini (via `GEMINI_API_KEY`) or OpenAI (via `OPENAI_API_KEY`).
Model configurable via `GEMINI_MODEL` or `OPENAI_MODEL`.

`_with_ai_backup()`:
- If `TRANSLATOR_AI_APPLY_REPAIRS=1`, the AI suggested translation *replaces* the rule output.
- Otherwise, it is added as a candidate.

---

## 9. Frontend → Backend

- Frontend: `Essentials/index.html` + `Essentials/devtoy.js`
- API call: `POST /translate` with JSON `{text, direction}`
- Response fields consumed by frontend: `input`, `direction`, `translated_text`, `candidates`, `suggestions`, `highlights`, `notes`
- Dev tools (gated by `ENABLE_DEV_TOOLS=True` in `Essentials/app.py`): exposed via `/devtoy.js`

---

## 10. Reusable Components

| Component | Location | Reuse Plan |
|---|---|---|
| `extract_meaning_from_line` | `dictionary_meanings.py` | Import directly in v2 importers |
| `parse_verb_payload` | `dictionary_meanings.py` | Import directly in v2 morphology |
| `split_dictionary_line` | `dictionary_meanings.py` | Import directly in v2 importers |
| `_definite_noun` | `translator.py:~2400` | Extract to `translator_v2/maltese/morphology/articles.py` |
| `_fused_in_surface` | `translator.py:~1145` | Extract to `translator_v2/maltese/morphology/prepositions.py` |
| `_apply_possessive_suffix` | `translator.py:~614` | Extract to `translator_v2/maltese/morphology/nouns.py` |
| `_attach_direct_object_suffix` | `translator.py` | Extract to `translator_v2/maltese/morphology/clitics.py` |
| `_select_verb` | `translator.py` | Wrap in `translator_v2/maltese/morphology/verbs.py` |
| `verb_by_gloss` data | `.dic` files | Re-imported non-destructively in v2 |
| `eu_countries.json` | `finaldics/` | Re-imported in v2 terminology |
| `PREFERRED_NOUN_SURFACES` etc. | `translator.py` | Migrate to terminology module |
| `NOUN_POSSESSIVE_SUFFIXES` | `translator.py` | Migrate to morphology module |

---

## 11. Components to Retire (Gradually)

| Component | Reason | Stage |
|---|---|---|
| `_tag_sentence_locally()` | Suffix heuristics, poor POS accuracy | Stage 5: replace with spaCy |
| `tag_sentence()` AI call | Latency, cost, cloud dependency | Stage 5: retire |
| 20+ pattern functions in `_translate_en_mt()` | Hardcoded surface patterns, poor generalisation | Stage 4–8: superseded by pipeline |
| `_translate_word_by_word()` | Token substitution, no sense disambiguation | Stage 8: becomes lowest-priority candidate |
| `route_translation()` AI call | Replaced by spaCy dependency parsing | Stage 5–6 |
| `review_translation()` AI call | Replaced by deterministic validation | Stage 12 |

---

## 12. Major Risks and Technical Debt

1. **Pattern order sensitivity**: The 20-function waterfall means any new pattern can silently shadow an existing one. Adding a new pattern requires testing all prior cases.
2. **Duplicate `_translate_noun_phrase()` call**: Called at lines ~749 and ~770 — one call is wasted. Indicates the pipeline grew by accretion.
3. **Verb paradigm coverage vs. use**: The paradigm files have 130k+ entries but most are only used for lookup; no round-trip analysis or morphological validation is done.
4. **AI as primary tagger**: When AI tagging is enabled, every request makes a cloud API call before any local logic runs. Latency depends on API response time.
5. **No lexical sense separation**: `run` (move on foot) and `run` (manage a company) resolve to the same Maltese verb.
6. **No validation of neural output**: Currently no mechanism to check if a Maltese string is morphologically valid.
7. **Large monolith**: `translator.py` is 4,259 lines. Hard to test individual components in isolation.
8. **English dics generated from Maltese glosses**: `english_dics/` are reverse-engineered from Maltese dictionary glosses, so they inherit whatever glosses were written by the Maltese dictionary authors (which may not be standardised English lemmas).
