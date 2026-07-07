# Maltese Data Needed — Human Review Required

This file records every linguistic question that the code cannot resolve automatically.
Do not decide these automatically. Do not fabricate rules to pass tests.

---

## Priority Legend
- 🔴 **critical** — translation will be wrong without this
- 🟡 **high** — frequent pattern, affects many sentences  
- 🟢 **medium** — less frequent, edge case

---

## MALT-001 — Verified Maltese lemma for "run" (manage sense) 🔴

**Question**: Which Maltese verb is standard for "manage a company/organisation"?
**Evidence from user**: `Tmexxi kumpanija ta' suċċess kbir.` → **tmexxa** (mexa) is the verb
**Status**: ✅ Confirmed: `mexa` (imperfect: imexxi/tmexxi/jmexxi). Mark as verified in `run.jsonl`.
**Affected module**: `translator_v2/lexical_sense/data/run.jsonl`

---

## MALT-002 — Verified Maltese lemma for "run" (movement sense) 🔴

**Question**: Which Maltese verb for physical running?
**Evidence from user**: `Tiġri kull filgħodu.` → **ġera** (imperfect: niġri/tiġri/jiġri)
**Status**: ✅ Confirmed. Mark as verified in `run.jsonl`.

---

## MALT-003 — Verified Maltese lemma for "run" (operate/function sense) 🔴

**Question**: Which Maltese verb for "a program/engine is running"?
**Evidence from user**: `Il-programm qed jaħdem` → **ħadem** (work/function, imperfect: jaħdem)
**Status**: ✅ Confirmed. Mark as verified in `run.jsonl`.

---

## MALT-004 — "run out of" (phrasal) → spiċċa + clitic construction 🔴

**Question**: How to express "run out of X" in Maltese?
**Evidence from user**: `Spiċċalhom l-ilma` — spiċċa + -lhom (dative clitic), subject X follows
**Key insight**: This is an **experiencer-possessor** construction, not a simple verb.
  The "owner" appears as indirect object suffix on the verb, subject follows.
**Status**: ✅ Documented. Need morphology module to handle: `spiċċa + IDO_suffix + subject`.
**Affected module**: `translator_v2/maltese/morphology/clitics.py`

---

## MALT-005 — "run for election" Maltese equivalent 🟡

**Question**: Which Maltese expression for "run for [office]"?
**Evidence from user**: `Ħiereġ għal president` — active participle of ħareġ (come out/emerge) + għal
**Alternative**: `Qed joħroġ għall-presidenza`
**Status**: ✅ Documented. Sense: ħareġ + għal + office.
**Affected module**: `translator_v2/lexical_sense/data/run.jsonl`

---

## MALT-006 — Location verbs + definite noun: preposition omission 🟡

**Question**: When does Maltese omit "to/in" before definite place nouns?
**Evidence from user**:
  - `Mort il-bank` (not `mort lejn il-bank` or `mort fil-bank`)
  - `immorru l-iskola` (not `immorru l-iskola`)
**Pattern**: After motion verbs (mar, ġie, telaq...), definite place nouns appear bare.
**Open question**: Is this always the case, or only for familiar/habitual places?
**Status**: ⚠️ Needs more examples. Human review needed.
**Affected module**: `translator_v2/maltese/morphology/prepositions.py`

---

## MALT-007 — Impersonal "like/please" construction (ġġarrab/jogħġob) 🔴

**Question**: How is "like" expressed in Maltese — as subject-likes-X or as X-pleases-subject?
**Evidence from user**:
  - `Ma jogħġbux il-ħaxix` — impersonal jogħġob, subject (vegetable) after verb
  - `Iħobbu jgħumu fil-baħar` — transitive ħabb, subject swims (complement)
**Key insight**: Two different verbs used for "like":
  - `ħabb` (love/like strongly) — transitive, subject is experiencer
  - `jogħġob` (please/suit) — impersonal, logical subject is theme, not experiencer
**Open question**: What governs the choice between ħabb and jogħġob?
  Tentative rule: intensity/preference (ħobb = stronger) vs. suitability (jogħġob)?
**Status**: ⚠️ Needs human clarification on register/semantic distinction.
**Affected module**: `translator_v2/lexical_sense/` (new senses needed for "like")

---

## MALT-008 — Negation strategies 🟡

**Evidence from user**:
  - `Mhux qed nifhem il-mistoqsija` — negated progressive (mhux + qed + MPERF)
  - `Ma nifhimx il-mistoqsija` — direct negation (ma + MPERF + -x suffix)
  - `Ma jistax jiġi` — modal negation (ma jistax)
  - `Ma jogħġbux il-ħaxix` — impersonal negation
**Question**: When is `mhux qed VERB` preferred over `ma VERBx`?
  Both are grammatical. Is this purely stylistic?
**Status**: ⚠️ Needs human clarification. Do not hardcode one strategy.
**Affected module**: `translator_v2/maltese/validation/agreement.py`

---

## MALT-009 — "need" construction (għandi bżonn vs. irrid) 🟡

**Evidence from user**:
  - `Għandi bżonn nibbukkja titjira` — għandi bżonn + MPERF
  - `Għandna bżonn immorru l-iskola` — same pattern
**Key insight**: Maltese "need" = għandi bżonn (I have need), NOT a modal verb.
**Open question**: Is `irrid` (I want) ever used for "need"? What distinguishes them?
**Status**: ⚠️ Document distinction. Do not map "need" to "irrid".
**Affected module**: `translator_v2/lexical_sense/` (new senses for "need")

---

## MALT-010 — Near-future "going to" → sejrin + MPERF 🟡

**Evidence from user**: `Sejrin nieklu issa` — active participle of mar (pl) + 1P MPERF
**Alternative from user**: `Qed immorru nieklu issa`
**Key insight**: `Sejrin` = plural active participle of mar (go). Used for near-future "going to".
**Open question**: Is `sejrin` always masculine/mixed plural? How does it agree for feminine or mixed groups?
**Status**: ⚠️ Need paradigm: sejjer (MS), sejra (FS), sejrin (PL).
**Affected module**: `translator_v2/maltese/morphology/verbs.py`

---

## MALT-011 — Weather/existential constructions (hawn ħafna X) 🟡

**Evidence from user**: `Illum hawn ħafna kesħa` — hawn (there is) + kesħa (coldness, noun)
**Key insight**: Maltese expresses weather states as existential noun phrases, not adjective predicates.
  "It is cold" ≠ "huwa kiesaħ" → "hawn kesħa" (there is coldness).
**Open question**: What other weather/state words follow this pattern?
  `sħana` (heat)? `riħ` (wind)? `xita` (rain)?
**Status**: ⚠️ Need list of weather nouns. Do not default to adjective predicate.
**Affected module**: `translator_v2/maltese/validation/semantic_validation.py`

---

## MALT-012 — Clitic fusion on verbs (qal + lili → qalli) 🔴

**Evidence from user**: `Qalli storja` — qal + indirect object lili fused
**Key insight**: Maltese indirect object clitics fuse with verb surface forms.
  This is morphophonological, not just concatenation.
**Open question**: What are all the fusion forms? E.g.:
  - qal + lili = qalli
  - qal + lilek = qallek?
  - qal + lilu = qallu?
**Status**: ⚠️ Full clitic fusion paradigm needed. Do not apply suffix rules mechanically.
**Affected module**: `translator_v2/maltese/morphology/clitics.py`

---

## MALT-013 — Ditransitive constructions (told me a story) 🔴

**Evidence from user**: `Qalli storja` — verb + IDO clitic, direct object separate
**Key insight**: When both IDO and DO are present, IDO becomes a clitic on the verb,
  DO remains as a separate NP.
**Open question**: What if DO is also a pronoun? e.g. "He told it to me" — does it double-clitic?
**Status**: ⚠️ Needs example. Do not guess.
**Affected module**: `translator_v2/maltese/morphology/clitics.py`

---

## MALT-014 — Article assimilation rules 🟡

**Evidence from user**:
  - `ix-xarabank` — ix- before x
  - `it-tfal` — it- before t
  - `il-bank` — standard il-
  - `l-iskola` — l- before vowel
  - `id-dawl` — id- before d
**Status**: ✅ Standard rules documented. Implemented in legacy `_definite_noun()`.
  Must be extracted to `translator_v2/maltese/morphology/articles.py`.

---

## MALT-015 — Fused prepositions (fi + il → fil) 🟡

**Evidence from user**:
  - `fil-baħar` — fi + il-baħar
  - `fil-kompjuter` — fi + il-kompjuter  
  - `fuq il-mejda` — fuq not fused (fuq does not fuse)
  - `tax-xmara` — ta' + ix-xmara
**Open question**: Which prepositions fuse with the article and which do not?
  Known fusing: `fi`, `ta'`, `bi`, `minn`, `lil`, `sa`?
**Status**: ⚠️ Full fusion table needed.
**Affected module**: `translator_v2/maltese/morphology/prepositions.py`

---

## MALT-016 — Pro-drop defaults (conversational register) 🟡

**User confirmation**: All sentences beginning with a pronoun *could* have the Maltese pronoun added.
  Conversational = pro-drop. Formal = explicit pronoun.
**Rule for code**: Conversational → omit subject pronoun by default.
  Formal → include subject pronoun.
**Status**: ✅ Documented. Implement as `register` config option (already in V2Config).
**Affected module**: `translator_v2/pipeline.py`, `translator_v2/maltese/morphology/verbs.py`

---

## MALT-017 — "bank" (river) Maltese word 🟡

**Evidence from user**: `Ix-xatt tax-xmara` — xatt = river bank/shore
**Status**: ✅ Confirmed: `xatt` = river bank. Update `bank.jsonl`.

---

## MALT-018 — "book" (reserve) Maltese verb 🟡

**Evidence from user**: `nibbukkja titjira` — bbukkja (loan verb from English "book")
**Status**: ✅ Confirmed. Non-semitic loan verb paradigm: nibbukkja/tibbukkja/jibbukkja etc.
  Update `book.jsonl`.

---

## MALT-019 — Past tense question formation 🔴

**Evidence from user**: `Kiltu l-kolazzjon?` — no auxiliary, verb-initial, rising intonation
**Key insight**: Maltese past questions do NOT use a "did" equivalent.
  The perfect tense verb is used directly, in verb-initial position.
**Alternative**: `Kilt il-kolazzjon?` (2S) also acceptable.
**Status**: ✅ Documented. The `_translate_can_pattern` / question patterns in legacy
  must account for this — no "did" auxiliary should appear in Maltese output.
**Affected module**: `translator_v2/maltese/validation/agreement.py`

---

## MALT-020 — Number + noun constructions (żewġ aħwa subien) 🟡

**Evidence from user**: `Għandi żewġ aħwa subien u waħda tifla`
**Key insight**: `żewġ` (2) + plural noun; then gender/type specifier `subien`/`bniet`.
  `waħda tifla` = one girl (cardinal + noun).
**Open question**: Full counting paradigm: wieħed/waħda, żewġ, tliet, erba'... for M/F nouns?
**Status**: ⚠️ Partial data exists in legacy. Full paradigm table needed.
**Affected module**: `translator_v2/maltese/morphology/nouns.py`

---

## MALT-021 — "light" (adjective, not heavy) Maltese word 🟡

**Evidence from user**: `Il-basket ħafif qiegħed fuq il-mejda` — ħafif (MS), ħafifa (FS), ħfief (PL)?
**Alternative**: `Il-borża ħafifa qiegħda fuq il-mejda` — borża (FS) → ħafifa agrees in gender
**Status**: ✅ Confirmed: ħafif/ħafifa/ħfief. Adjective follows noun. Agrees in gender.
**Affected module**: `translator_v2/maltese/morphology/adjectives.py`

---

## MALT-022 — "qiegħed/qiegħda" as locative copula 🟡

**Evidence from user**: `Il-basket ħafif qiegħed fuq il-mejda` and `Taf fejn qiegħda hi`
**Key insight**: `qiegħed` (MS) / `qiegħda` (FS) / `qegħdin` (PL) = located/placed.
  Used as a locative copula, distinct from existential `hawn` and verbal `hija`.
**Status**: ✅ Documented. Need to distinguish hija (identity/attribute) vs qiegħed (location).
**Affected module**: `translator_v2/maltese/validation/semantic_validation.py`

---

## Unresolved Sense Mappings (Machine-Suggested, Unverified)

The following Maltese lemmas appear in sense data files as `null` (unverified).
These MUST be filled in by human review before being used as translation constraints:

| Sense ID | English | Maltese lemma needed |
|---|---|---|
| `run_manage` | run a company | ✅ **mexa** (confirmed above) |
| `run_move_on_foot` | run physically | ✅ **ġera** (confirmed above) |
| `run_operate_program` | program running | ✅ **ħadem** (confirmed above) |
| `run_function` | machine running | ⚠️ ħadem or dar? Needs example |
| `run_out` | run out of | ✅ **spiċċa + clitic** (confirmed above) |
| `run_for_election` | run for office | ✅ **ħareġ + għal** (confirmed above) |
| `run_extend_direction` | road runs along | ⚠️ jimxi? jgħaddi? Needs example |
| `bank_financial` | financial bank | ✅ **bank** (confirmed above) |
| `bank_river` | river bank | ✅ **xatt** (confirmed above) |
| `bank_store` | blood bank | ⚠️ Needs example |
| `book_noun_text` | reading book | ✅ **ktieb** (existing in dic) |
| `book_verb_reserve` | reserve/book | ✅ **ibbukkja** (confirmed above) |
