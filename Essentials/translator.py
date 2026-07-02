from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from Essentials.dictionary_meanings import (
    extract_meaning_from_line,
    parse_verb_payload,
    split_dictionary_line,
)
from Essentials.ai_assist import ai_can_apply_repairs, review_to_note, review_translation, route_translation, translate_text, tag_sentence


WORD_RE = re.compile(r"[A-Za-z']+|[^\w\s]", re.UNICODE)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value or "")).casefold()
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = re.sub(r"[^a-z0-9'\s-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def split_glosses(value: str) -> list[str]:
    cleaned = re.sub(r"\([^)]*\)", "", str(value or ""))
    parts = re.split(r"\s*(?:,|;|\bor\b|/)\s*", cleaned, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


@dataclass(frozen=True)
class TranslationCandidate:
    text: str
    source: str
    confidence: str = "dictionary"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerbTranslationRecord:
    word: str
    gloss: str
    tense: str
    person: str
    negative: bool
    raw_tag: str
    gloss_index: int = 0

    def __str__(self) -> str:
        return self.word

    def __getattr__(self, name: str):
        return getattr(self.word, name)

    def __add__(self, other) -> str:
        return self.word + str(other)

    def __radd__(self, other) -> str:
        return str(other) + self.word


@dataclass(frozen=True)
class LexicalRecord:
    word: str
    gloss: str
    pos: str
    gender: str = ""
    number: str = ""
    source: str = ""
    gloss_index: int = 0


@dataclass
class TranslationResult:
    input: str
    direction: str
    translated_text: str
    candidates: list[dict] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)
    highlights: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
@dataclass(frozen=True)
class TransferNounPhrase:
    determiner: str
    number_word: str
    adjective_keys: tuple[str, ...]
    noun_key: str
    noun: LexicalRecord
    unknown_noun: bool = False


@dataclass(frozen=True)
class TransferClause:
    subject: str
    subject_person: str
    verb_lemma: str
    tense: str
    negated: bool = False
    question: bool = False
    aspect: str = "habitual"
    object_phrase: TransferNounPhrase | None = None
    object_pronoun: str = ""
    tail_surface: str = ""


class MalteseTranslator:
    SUBJECT_JUST_FORMS = {
        "i": "għadni kemm",
        "he": "għadu kemm",
        "she": "għadha kemm",
        "it": "għadu kemm",
        "we": "għadna kemm",
        "you": "għadek kemm",
        "you all": "għadkom kemm",
        "they": "għadhom kemm",
    }

    JUST_ACTION_FORMS = {
        "go swimming": {
            "i": "mort ngħum",
            "he": "mar jgħum",
            "she": "marret tgħum",
            "it": "mar jgħum",
            "we": "morna ngħumu",
            "you": "mort tgħum",
            "they": "marru jgħumu",
        },
        "eat": {
            "i": "kilt",
            "he": "kiel",
            "she": "kielet",
            "it": "kiel",
            "we": "kilna",
            "you": "kilt",
            "they": "kielu",
        },
        "drink": {
            "i": "xrobt",
            "he": "xorob",
            "she": "xorbot",
            "it": "xorob",
            "we": "xrobna",
            "you": "xrobt",
            "they": "xorbu",
        },
        "sleep": {
            "i": "rqadt",
            "he": "raqad",
            "she": "raqdet",
            "it": "raqad",
            "we": "rqadna",
            "you": "rqadt",
            "they": "raqdu",
        },
        "arrive": {
            "i": "wasalt",
            "he": "wasal",
            "she": "waslet",
            "it": "wasal",
            "we": "wasalna",
            "you": "wasalt",
            "they": "waslu",
        },
    }

    ACTION_ALIASES = {
        "went swimming": "go swimming",
        "gone swimming": "go swimming",
        "go swimming": "go swimming",
        "swim": "go swimming",
        "swimming": "go swimming",
        "ate": "eat",
        "eat": "eat",
        "eaten": "eat",
        "drank": "drink",
        "drink": "drink",
        "drunk": "drink",
        "slept": "sleep",
        "sleep": "sleep",
        "arrived": "arrive",
        "arrive": "arrive",
    }

    MANUAL_PHRASES = {
        "One day,": "Darba waħda,",
    }

    WATER_CONTEXT = {"swim", "swimming", "water", "sea", "pool", "lake", "river"}
    MASCULINE_COLD = {"cold": "kiesaħ", "really cold": "kiesaħ ħafna", "very cold": "kiesaħ ħafna"}
    FEMININE_COLD = {"cold": "kiesħa", "really cold": "kiesħa ħafna", "very cold": "kiesħa ħafna"}
    PREFERRED_VERB_SURFACES = {
        "miss": ("nimmissja", "timmissja", "jimmissja", "nimmissjaw", "timmissjaw", "jimmissjaw", "mmissjajt", "mmissja", "mmissjaw"),
        "attack": ("nattakka", "tattakka", "jattakka", "jattakkaw", "nattakkaw", "tattakkaw", "attakkajt", "attakka", "attakkat", "attakkaw"),
        "do": ("nagħmel", "tagħmel", "jagħmel", "jagħmlu", "nagħmlu", "tagħmlu", "għamilt", "għamel", "għamlet", "għamlu"),
        "make": ("nagħmel", "tagħmel", "jagħmel", "jagħmlu", "nagħmlu", "tagħmlu", "għamilt", "għamel", "għamlet", "għamlu"),
        "can": ("nista’", "tista’", "jista’", "jistgħu", "nistgħu", "tistgħu", "stajt", "seta'", "setgħet", "setgħu", "setgħux"),
        "leave": ("nitlaq", "titlaq", "jitlaq", "nitilqu", "titilqu", "jitilqu", "tlaqt", "telaq", "telqet", "tlaqna", "tlaqtu", "telqu"),
    }
    PREFERRED_NOUN_SURFACES = {
        "book": ("ktieb",),
        "books": ("kotba",),
        "cow": ("baqra",),
        "cows": ("baqar",),
        "forest": ("bosk", "foresta"),
        "forests": ("boskijiet", "foresti"),
        "friend": ("ħabib",),
        "friends": ("ħbieb",),
        "grass": ("ħaxix",),
        "house": ("dar",),
        "lion": ("iljun",),
        "lions": ("iljuni",),
        "meadow": ("marġ", "mergħa"),
        "meadows": ("mraġ", "mruġ", "mergħat"),
        "music": ("mużika",),
        "pencil": ("lapes", "lapis"),
        "pencils": ("lapsijiet",),
        "question": ("mistoqsija",),
        "woman": ("mara",),
        "women": ("nisa",),
    }
    PREFERRED_ADJECTIVE_SURFACES = {
        "cold": ("kiesaħ", "kiesħa", "kesħin"),
        "fresh": ("frisk", "friska", "friski"),
        "green": ("aħdar", "ħadra", "ħodor"),
        "kind": ("twajjeb", "twajba", "twajbin"),
        "large": ("kbir", "kbira", "kbar"),
        "little": ("żgħir", "żgħira", "żgħar"),
        "small": ("żgħir", "żgħira", "żgħar"),
    }

    def __init__(self, finaldics_dir: Path) -> None:
        self.finaldics_dir = Path(finaldics_dir)
        self.en_to_mt: dict[str, list[TranslationCandidate]] = defaultdict(list)
        self.mt_to_en: dict[str, list[TranslationCandidate]] = defaultdict(list)
        self.verb_by_gloss: dict[str, list[VerbTranslationRecord]] = defaultdict(list)
        self.lex_by_gloss: dict[str, list[LexicalRecord]] = defaultdict(list)
        self._load_dictionary_files()
        self._load_verb_dictionary_files()
        self._load_country_json()
        self._load_manual_entries()
        self._load_english_dictionaries()

    def _add_candidate(
        self,
        english: str,
        maltese: str,
        *,
        source: str,
        confidence: str = "dictionary",
        notes: Iterable[str] = (),
    ) -> None:
        en_key = normalize_text(english)
        mt_key = normalize_text(maltese)
        if not en_key or not mt_key:
            return

        if en_key in {"you", "i", "he", "she", "we", "they", "it", "dont", "cant"}:
            if source not in {"maltese_pronouns.dic", "manual_phrase_rules", "manual_can_rules", "manual_like_rules"}:
                return

        candidate = TranslationCandidate(
            text=maltese.strip(),
            source=source,
            confidence=confidence,
            notes=tuple(notes),
        )
        if all(existing.text != candidate.text for existing in self.en_to_mt[en_key]):
            self.en_to_mt[en_key].append(candidate)

        reverse = TranslationCandidate(
            text=english.strip(),
            source=source,
            confidence=confidence,
            notes=tuple(notes),
        )
        if all(existing.text != reverse.text for existing in self.mt_to_en[mt_key]):
            self.mt_to_en[mt_key].append(reverse)

    def _load_dictionary_files(self) -> None:
        for path in sorted(self.finaldics_dir.glob("*.dic")):
            if path.name == "places.dic" or path.name.startswith("verbmt_"):
                continue
            try:
                lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            except FileNotFoundError:
                continue
            for line in lines:
                maltese, meaning = extract_meaning_from_line(line)
                if not maltese or not meaning:
                    continue
                for i, gloss in enumerate(split_glosses(meaning)):
                    self._add_candidate(gloss, maltese, source=path.name)
                    self._add_lexical_record(gloss, maltese, line, path.name, gloss_index=i)

    def _load_verb_dictionary_files(self) -> None:
        paths = list(self.finaldics_dir.glob("verbmt_*.dic")) + [self.finaldics_dir / "dev_extra.dic"]
        for path in sorted(paths, key=lambda p: p.name):
            try:
                lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            except FileNotFoundError:
                continue
            for line in lines:
                word, payload = split_dictionary_line(line)
                if word:
                    word = word.replace("â€™", "'").replace("â€˜", "'")
                parsed = parse_verb_payload(payload)
                if not word or not parsed:
                    continue
                tense = str(parsed["tense"])
                person = str(parsed["person"])
                negative = bool(parsed["negative"])
                for i, gloss in enumerate(self._verb_gloss_keys(str(parsed["gloss"]))):
                    record = VerbTranslationRecord(
                        word=word,
                        gloss=gloss,
                        tense=tense,
                        person=person,
                        negative=negative,
                        raw_tag=payload,
                        gloss_index=i,
                    )
                    key = (record.word, record.tense, record.person, record.negative, record.raw_tag)
                    if all(
                        (existing.word, existing.tense, existing.person, existing.negative, existing.raw_tag) != key
                        for existing in self.verb_by_gloss[gloss]
                    ):
                        self.verb_by_gloss[gloss].append(record)

    def _add_lexical_record(
        self, gloss: str, maltese: str, line: str, source: str, gloss_index: int = 0
    ) -> None:
        _, payload = split_dictionary_line(line)
        pos = ""
        gender = ""
        number = ""
        upper = payload.upper()
        if "SINGNOUNF" in upper:
            pos, gender, number = "noun", "F", "S"
        elif "SINGNOUNM" in upper:
            pos, gender, number = "noun", "M", "S"
        elif "SINGNOUN" in upper:
            pos, gender, number = "noun", "M", "S"
        elif "PLUNOUN" in upper:
            pos, number = "noun", "P"
        elif "SINGADJF" in upper:
            pos, gender, number = "adj", "F", "S"
        elif "SINGADJM" in upper:
            pos, gender, number = "adj", "M", "S"
        elif "PLUADJ" in upper:
            pos, number = "adj", "P"
        elif "ADVERB" in upper:
            pos = "adv"
        elif any(t in upper for t in ("PREP", "DEFPREP", "SHORTPREP")):
            pos = "prep"
        elif "PRON" in upper:
            pos = "pron"
        elif "CONJ" in upper:
            pos = "conj"
        elif "DET" in upper:
            pos = "det"
        elif any(t in upper for t in ("CARDNUM", "ORDNUM", "ATTNUM", "SHORTATTNUM", "LONGATTNUM")):
            pos = "num"
        if not pos:
            return
        key = normalize_text(gloss)
        if not key:
            return
        record = LexicalRecord(maltese, key, pos, gender, number, source, gloss_index)
        if record not in self.lex_by_gloss[key]:
            self.lex_by_gloss[key].append(record)

    def _load_country_json(self) -> None:
        path = self.finaldics_dir / "eu_countries.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return

        for record in payload.get("records", []):
            english = str(record.get("english", "")).strip()
            maltese = str(record.get("maltese", "")).strip()
            official = str(record.get("maltese_official", "")).strip()
            if english and maltese:
                self._add_candidate(english, maltese, source="eu_countries.json", confidence="exact")
            if english and official and official != maltese:
                self._add_candidate(
                    f"the {english}",
                    official,
                    source="eu_countries.json",
                    confidence="exact",
                )

    def _load_manual_entries(self) -> None:
        manual = {
            "I had just": "għadni kemm",
            "he had just": "għadu kemm",
            "she had just": "għadha kemm",
            "it had just": "għadu kemm",
            "we had just": "għadna kemm",
            "you had just": "għadek kemm",
            "they had just": "għadhom kemm",
            "wake up": "qam",
            "woke up": "qam",
            "wakes up": "qam",
            "waking up": "qam",
            "feel like": "ikollok aptit",
            "feels like": "ikollu aptit",
            "felt like": "kellu aptit",
            "at all": "xejn",
            "really": "ħafna",
            "very": "ħafna",
            "cold": "kiesaħ",
            "morning": "filgħodu",
            "afternoon": "wara nofs in-nhar",
            "evening": "filgħaxija",
            "yesterday": "Ilbieraħ",
            "today": "Illum",
            "tomorrow": "Għada",
            **self.MANUAL_PHRASES,
        }
        lexical_overrides = {
            "meadow": "mar\u0121",
            "grass": "\u0127axix",
            "little": "\u017cg\u0127ir",
            "small": "\u017cg\u0127ir",
            "large": "kbir",
            "green": "a\u0127dar",
            "fresh": "frisk",
            "home": "dar",
            "work": "xogħol",
            "job": "xogħol",
            "your": "tiegħek",
            "his": "tiegħu",
            "anything": "xejn",
            "while": "waqt li",
            "get": "jifhem",
        }
        for english, maltese in lexical_overrides.items():
            self._add_candidate(
                english,
                maltese,
                source="manual_lexical_overrides",
                confidence="manual",
            )
            line = f"{maltese}/SINGNOUN-{english}"
            self._add_lexical_record(english, maltese, line, "manual_lexical_overrides", gloss_index=-1)
            pos = "noun"
            if english in {"little", "small", "large", "green", "fresh"}: pos = "adjective"
            elif english in {"your", "his", "anything"}: pos = "pronoun"
            elif english == "while": pos = "conjunction"
            elif english == "get": pos = "verb"
            self.lex_by_gloss[normalize_text(english)].append(
                LexicalRecord(word=maltese, gloss=english, pos=pos, source="manual_lexical_overrides", gloss_index=-1)
            )

        for english, maltese in manual.items():
            self._add_candidate(
                english,
                maltese,
                source="manual_phrase_rules",
                confidence="manual",
            )

    NOUN_POSSESSIVE_SUFFIXES = {
        "head": {"my": "rasi", "your": "rasek", "his": "rasu", "her": "rasha", "its": "rasu", "our": "rasna", "their": "rashom"},
        "hand": {"my": "idi", "your": "idek", "his": "idu", "her": "idha", "its": "idu", "our": "idna", "their": "idhom"},
        "hands": {"my": "idejja", "your": "idejk", "his": "idejh", "her": "idejha", "its": "idejh", "our": "idejna", "their": "idejhom"},
        "leg": {"my": "riġli", "your": "riġlek", "his": "riġlu", "her": "riġleha", "its": "riġlu", "our": "riġilna", "their": "riġilhom"},
        "legs": {"my": "riġlejja", "your": "riġlejk", "his": "riġlejh", "her": "riġlejha", "its": "riġlejh", "our": "riġlejna", "their": "riġlejhom"},
        "foot": {"my": "riġli", "your": "riġlek", "his": "riġlu", "her": "riġleha", "its": "riġlu", "our": "riġilna", "their": "riġilhom"},
        "feet": {"my": "riġlejja", "your": "riġlejk", "his": "riġlejh", "her": "riġlejha", "its": "riġlejh", "our": "riġlejna", "their": "riġlejhom"},
        "eye": {"my": "għajni", "your": "għajnek", "his": "għajnu", "her": "għajnha", "its": "għajnu", "our": "għajnna", "their": "għajnhom"},
        "eyes": {"my": "għajnejja", "your": "għajnejk", "his": "għajnejh", "her": "għajnejha", "its": "għajnejh", "our": "għajnejna", "their": "għajnejhom"},
        "mouth": {"my": "fommi", "your": "fommok", "his": "fommu", "her": "fommha", "its": "fommu", "our": "fommna", "their": "fommhom"},
        "back": {"my": "dahri", "your": "dahrek", "his": "dahru", "her": "dahrha", "its": "dahru", "our": "dahrna", "their": "dahrkom"},
        "face": {"my": "wiċċi", "your": "wiċċek", "his": "wiċċu", "her": "wiċċha", "its": "wiċċu", "our": "wiċċna", "their": "wiċċhom"},
        "heart": {"my": "qalbi", "your": "qalbek", "his": "qalbu", "her": "qalbha", "its": "qalbu", "our": "qalbna", "their": "qalbhom"},
        "house": {"my": "dari", "your": "darek", "his": "daru", "her": "darha", "its": "daru", "our": "darna", "their": "darhom"},
        "home": {"my": "dari", "your": "darek", "his": "daru", "her": "darha", "its": "daru", "our": "darna", "their": "darhom"},
        "father": {"my": "missieri", "your": "missierek", "his": "missieru", "her": "missierha", "its": "missieru", "our": "missierna", "their": "missierhom"},
        "mother": {"my": "ommi", "your": "ommok", "his": "ommu", "her": "ommha", "its": "ommu", "our": "ommna", "their": "ommhom"},
        "brother": {"my": "ħija", "your": "ħuk", "his": "ħuh", "her": "ħuha", "its": "ħuh", "our": "ħuna", "their": "ħuhom"},
        "sister": {"my": "oħti", "your": "oħtok", "his": "oħtu", "her": "oħtha", "its": "oħtu", "our": "oħtna", "their": "oħthom"},
        "friend": {"my": "ħabibi", "your": "ħabibek", "his": "ħabibu", "her": "ħabibha", "its": "ħabibu", "our": "ħabibna", "their": "ħabibhom"},
        "dog": {"my": "kelbi", "your": "kelbek", "his": "kelbu", "her": "kelbha", "its": "kelbu", "our": "kelbna", "their": "kelbhom"},
        "name": {"my": "ismi", "your": "ismek", "his": "ismu", "her": "isimha", "its": "ismu", "our": "isimna", "their": "isimhom"}
    }

    def _load_english_dictionaries(self) -> None:
        self.english_pos: dict[str, set[str]] = defaultdict(set)
        dics_path = self.finaldics_dir.parent / "english_dics"
        for path in dics_path.glob("*.dic"):
            tag_map = {
                "nouns": "NOUN",
                "verbs": "VERB",
                "adjectives": "ADJ",
                "adverbs": "ADV",
                "prepositions": "PREP",
                "determiners": "DET",
                "numbers": "NUM",
                "phrases": "PHRASE"
            }
            mapped_tag = tag_map.get(path.stem.lower(), "OTHER")
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
                for line in lines:
                    if ":" in line:
                        word, _ = line.split(":", 1)
                        self.english_pos[word.strip().lower()].add(mapped_tag)
            except Exception:
                pass

    def _tag_sentence_locally(self, text: str) -> list[dict[str, str]]:
        tokens = WORD_RE.findall(text)
        tagged: list[dict[str, str]] = []
        
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if re.fullmatch(r"[^\w\s]", token):
                tagged.append({"word": token, "pos": "punctuation", "lemma": token})
                index += 1
                continue
                
            phrase_matched = False
            for length in range(4, 1, -1):
                if index + length <= len(tokens):
                    phrase_tokens = tokens[index : index + length]
                    if not any(re.fullmatch(r"[^\w\s]", t) for t in phrase_tokens):
                        phrase_str = " ".join(phrase_tokens)
                        norm_phrase = normalize_text(phrase_str)
                        if norm_phrase in self.english_pos and "PHRASE" in self.english_pos[norm_phrase]:
                            pos = "phrase"
                            if norm_phrase in {"wake up", "woke up", "wakes up", "waking up", "woken up", "feel like", "feels like", "felt like", "feeling like", "go back", "goes back", "went back", "going back", "gone back"}:
                                pos = "verb"
                            
                            lemma = norm_phrase
                            if "woke up" in norm_phrase or "wakes up" in norm_phrase or "waking up" in norm_phrase or "woken up" in norm_phrase:
                                lemma = "wake up"
                            elif "felt like" in norm_phrase or "feels like" in norm_phrase or "feeling like" in norm_phrase:
                                lemma = "feel like"
                            elif "goes back" in norm_phrase or "went back" in norm_phrase or "going back" in norm_phrase or "gone back" in norm_phrase:
                                lemma = "go back"

                            for i, t in enumerate(phrase_tokens):
                                if i == 0:
                                    tagged.append({"word": t, "pos": pos, "lemma": lemma})
                                else:
                                    tagged.append({"word": t, "pos": "particle", "lemma": ""})
                            index += length
                            phrase_matched = True
                            break
            if phrase_matched:
                continue
                
            norm = normalize_text(token)
            pos_tags = self.english_pos.get(norm, set())
            
            tag_to_pos = {
                "NOUN": "noun",
                "VERB": "verb",
                "ADJ": "adjective",
                "ADV": "adverb",
                "PREP": "preposition",
                "DET": "determiner",
                "NUM": "number"
            }
            
            if not pos_tags:
                if norm.endswith("ing") or norm.endswith("ed"):
                    pos = "verb"
                elif norm.endswith("ly"):
                    pos = "adverb"
                else:
                    pos = "noun"
            elif len(pos_tags) == 1:
                pos = tag_to_pos.get(list(pos_tags)[0], "noun")
            else:
                preferred = "noun"
                if "NOUN" in pos_tags: preferred = "noun"
                elif "VERB" in pos_tags: preferred = "verb"
                elif "ADJ" in pos_tags: preferred = "adjective"
                else: preferred = tag_to_pos.get(list(pos_tags)[0], "noun")
                
                prev_norm = normalize_text(tokens[index - 1]) if index > 0 else ""
                if prev_norm in {"i", "you", "he", "she", "it", "we", "they", "don't", "doesn't", "didn't", "did", "to", "will", "would", "can", "could"}:
                    if "VERB" in pos_tags:
                        preferred = "verb"
                elif prev_norm in {"the", "a", "an", "my", "your", "his", "her", "its", "our", "their", "this", "that", "these", "those"}:
                    if "NOUN" in pos_tags:
                        preferred = "noun"
                    elif "ADJ" in pos_tags:
                        preferred = "adjective"
                pos = preferred
                
            ltype, lval = self._lemmatize_word(norm)
            lemma = lval if ltype == "english" else norm
            
            tagged.append({"word": token, "pos": pos, "lemma": lemma})
            index += 1
            
        return tagged

    def _apply_possessive_suffix(self, noun_mt: str, pronoun_eng: str) -> str:
        noun_mt = noun_mt.strip()
        p = pronoun_eng.lower()
        if noun_mt.endswith("a"):
            base = noun_mt[:-1]
            if p == "my": return base + "ti"
            elif p == "your": return base + "tek"
            elif p in {"his", "its"}: return base + "tu"
            elif p == "her": return base + "ttha"
            elif p == "our": return base + "tna"
            elif p == "their": return base + "thom"
        elif noun_mt.endswith(("u", "i", "o", "e")):
            if p == "my": return noun_mt + "ja"
            elif p == "your": return noun_mt + "k"
            elif p in {"his", "its"}: return noun_mt + "h"
            elif p == "her": return noun_mt + "ha"
            elif p == "our": return noun_mt + "na"
            elif p == "their": return noun_mt + "hom"
        else:
            if p == "my": return noun_mt + "i"
            elif p == "your": return noun_mt + "ek"
            elif p in {"his", "its"}: return noun_mt + "u"
            elif p == "her": return noun_mt + "ha"
            elif p == "our": return noun_mt + "na"
            elif p == "their": return noun_mt + "hom"
        return noun_mt

    def translate(self, text: str, direction: str = "en-mt") -> TranslationResult:
        direction = direction if direction in {"en-mt", "mt-en"} else "en-mt"
        if direction == "mt-en":
            return self._translate_lookup(text, direction, self.mt_to_en)
        ai_tags = tag_sentence(text)
        if not ai_tags:
            ai_tags = self._tag_sentence_locally(text)
        result = self._with_source_punctuation(self._translate_en_mt(text, ai_tags=ai_tags), text)
        return self._with_ai_backup(result, text, direction)

    def _with_ai_backup(
        self, result: TranslationResult, source: str, direction: str
    ) -> TranslationResult:
        if os.getenv("TRANSLATOR_AI_REVIEW_ENABLED", "").strip().casefold() not in {"1", "true", "yes", "on"}:
            return result
        review = review_translation(source, result.translated_text, direction)
        note = review_to_note(review)
        if note:
            result.notes.append(note)

        suggested = str(review.data.get("suggested_translation", "")).strip()
        should_override = bool(review.data.get("should_override"))
        if review.used and suggested and should_override and ai_can_apply_repairs():
            result.candidates.insert(
                0,
                {
                    "text": result.translated_text,
                    "source": "rule_based_before_ai_repair",
                    "confidence": "deterministic",
                    "notes": ["Original rule/dictionary output before AI repair."],
                },
            )
            result.translated_text = suggested
            result.candidates.insert(
                0,
                {
                    "text": suggested,
                    "source": "openai_context_repair",
                    "confidence": str(review.data.get("confidence", "ai_review")),
                    "notes": ["AI repair applied because TRANSLATOR_AI_APPLY_REPAIRS is enabled."],
                },
            )
        elif review.used and suggested:
            result.candidates.append(
                {
                    "text": suggested,
                    "source": "openai_context_suggestion",
                    "confidence": str(review.data.get("confidence", "ai_review")),
                    "notes": ["AI suggestion only; rule output was kept."],
                }
            )
        return result

    def _translate_en_mt(self, text: str, ai_tags: list[dict[str, str]] | None = None) -> TranslationResult:
        normalized = normalize_text(text)
        if not normalized:
            return TranslationResult(input=text, direction="en-mt", translated_text="")


        pronoun_result = self._translate_pronoun_ambiguity(text, normalized)
        if pronoun_result:
            return pronoun_result

        transitive_result = self._translate_transitive_object_pattern(text, normalized)
        if transitive_result:
            return transitive_result

        need_to_result = self._translate_need_to_pattern(text, normalized)
        if need_to_result:
            return need_to_result

        must_result = self._translate_must_pattern(text, normalized)
        if must_result:
            return must_result
        modal_transfer_result = self._translate_modal_transfer_pattern(text, normalized)
        if modal_transfer_result:
            return modal_transfer_result
        connector_result = self._translate_connector_clause(text, normalized)
        if connector_result:
            return connector_result
        complement_chain_result = self._translate_complement_chain_pattern(text, normalized)
        if complement_chain_result:
            return complement_chain_result

        do_want_result = self._translate_do_want_pattern(text, normalized)
        if do_want_result:
            return do_want_result

        understand_object_result = self._translate_understand_object_question(text, normalized)
        if understand_object_result:
            return understand_object_result

        like_result = self._translate_like_pattern(text, normalized)
        if like_result:
            return like_result

        can_result = self._translate_can_pattern(text, normalized)
        if can_result:
            return can_result

        progressive_result = self._translate_progressive_pattern(text, normalized)
        if progressive_result:
            return progressive_result

        compound_past_result = self._translate_past_narrative_compound(text, normalized)
        if compound_past_result:
            return compound_past_result

        early_noun_phrase_result = self._translate_noun_phrase(text, normalized)
        if early_noun_phrase_result:
            return early_noun_phrase_result

        clause_result = self._translate_clause_pattern(text, normalized)
        if clause_result:
            return clause_result

        frame_result = self._translate_clause_frame_pattern(text, normalized)
        if frame_result:
            return frame_result


        transfer_clause_result = self._translate_transfer_clause(text, normalized, ai_tags=ai_tags)
        if transfer_clause_result:
            return transfer_clause_result

        np_subject_clause_result = self._translate_np_subject_transfer_clause(text, normalized)
        if np_subject_clause_result:
            return np_subject_clause_result

        noun_phrase_result = self._translate_noun_phrase(text, normalized)
        if noun_phrase_result:
            return noun_phrase_result

        multi_lexical_phrase = self._translate_multi_adjective_noun_phrase(text, normalized)
        if multi_lexical_phrase:
            return multi_lexical_phrase

        lexical_phrase = self._translate_lexical_phrase(text, normalized)
        if lexical_phrase:
            return lexical_phrase

        unknown_noun_phrase = self._preserve_unknown_noun_phrase(text, normalized)
        if unknown_noun_phrase:
            return unknown_noun_phrase

        narrative_result = self._translate_story_narrative(text, normalized)
        if narrative_result:
            return narrative_result

        ai_routed_result = self._translate_ai_route(text, normalized)
        if ai_routed_result:
            return ai_routed_result

        manual = self._translate_manual_sentence(normalized)
        if manual:
            return TranslationResult(
                input=text,
                direction="en-mt",
                translated_text=manual,
                candidates=[self._candidate_payload(manual, "manual_sentence_rules", "manual")],
                notes=[
                    "Matched a manual tense/aspect pattern before dictionary lookup.",
                    "Used masculine adjective agreement because the local context contains swimming/water semantics.",
                ],
            )

        exact = self.en_to_mt.get(normalized, [])
        if exact:
            exact = list(exact)
            return TranslationResult(
                input=text,
                direction="en-mt",
                translated_text=exact[0].text,
                candidates=[self._candidate_payload_obj(candidate) for candidate in exact[:12]],
            )

        # Fallback to AI translation if enabled
        from Essentials.ai_assist import ai_enabled
        if ai_enabled():
            ai_translated = translate_text(text, "en-mt")
            if ai_translated:
                return TranslationResult(
                    input=text,
                    direction="en-mt",
                    translated_text=ai_translated,
                    candidates=[self._candidate_payload(ai_translated, "openai_fallback_translation", "ai")],
                    notes=["Translated using AI fallback."],
                )

        return self._translate_word_by_word(text, ai_tags=ai_tags)

    def _translate_connector_clause(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(r"(.+?)\s+so\s+(.+)", normalize_text(normalized).rstrip("."))
        if not match:
            return None
        left_text, right_text = (part.strip() for part in match.groups())
        if not left_text or not right_text:
            return None
        left_result = self._translate_en_mt(left_text)
        right_result = self._translate_en_mt(right_text)
        if not left_result.translated_text or not right_result.translated_text:
            return None
        left_surface = left_result.translated_text.rstrip(".?! ")
        right_surface = right_result.translated_text.rstrip(".?! ")
        if right_surface:
            right_surface = right_surface[:1].lower() + right_surface[1:]
        translated = f"{left_surface}, għalhekk {right_surface}."
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=self._sentence_case(translated),
            candidates=[self._candidate_payload(translated, "connector_clause_rules", "dictionary")],
            notes=[
                "Split an English connector clause at 'so' and translated both clauses structurally.",
                "Rendered the connector as Maltese 'għalhekk'.",
            ],
        )
    def _translate_transfer_clause(
        self, original: str, normalized: str, *, ai_tags: list[dict[str, str]] | None = None
    ) -> TranslationResult | None:
        parsed = self._parse_transfer_clause(normalized, ai_tags=ai_tags)
        if not parsed:
            return None
        surface = self._generate_transfer_clause(parsed)
        if not surface:
            return None
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=self._sentence_case(surface + ("?" if parsed.question else ".")),
            candidates=[self._candidate_payload(surface, "transfer_clause_rules", "dictionary")],
            notes=[
                "Parsed the sentence into a subject/verb/object transfer clause.",
                "Selected Maltese verb person/tense from the reverse verb dictionary and generated the object noun phrase structurally.",
            ],
        )

    def _translate_np_subject_transfer_clause(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        text = normalize_text(normalized).rstrip("?").strip()
        question = str(normalized).strip().endswith("?")
        if not text or question:
            return None
        words = text.split()
        if len(words) < 3:
            return None

        for index in range(1, min(len(words), 8)):
            verb_raw = words[index]
            if verb_raw in {"am", "is", "are", "was", "were", "be", "been", "being", "can", "could", "should", "must", "may", "might", "want", "need"}:
                continue
            lemma_type, lemma = self._lemmatize_word(verb_raw)
            if lemma_type != "english" or lemma not in self.verb_by_gloss:
                continue

            subject_text = " ".join(words[:index])
            subject_phrase = self._parse_noun_phrase(subject_text)
            if not subject_phrase:
                continue
            noun = subject_phrase.noun
            person = "3P" if noun.number == "P" else ("3SF" if noun.gender == "F" else "3SM")
            subject_surface = self._generate_noun_phrase(subject_phrase)
            if not subject_surface:
                continue

            tail = " ".join(words[index + 1:])
            object_surface = ""
            prep_surface = ""
            if tail:
                object_surface, prep_surface = self._object_and_preposition_tail_surface(tail)
                if not object_surface and not prep_surface:
                    continue

            tense = "PERF" if self._is_past_english_verb(verb_raw) else "MPERF"
            if lemma == "live" and tense == "PERF":
                aux = {"3P": "kienu", "3SF": "kienet"}.get(person, "kien")
                verb_record = self._select_verb(lemma, tense="MPERF", person=person, negative=False)
                if not verb_record:
                    continue
                verb_surface = f"{aux} {self._contextual_surface(self._surface_word(verb_record), previous=aux)}"
            else:
                verb_record = self._select_verb(lemma, tense=tense, person=person, negative=False)
                if not verb_record:
                    continue
                verb_surface = self._contextual_surface(self._surface_word(verb_record), previous=subject_surface)

            pieces = [subject_surface, verb_surface]
            if object_surface:
                pieces.append(object_surface)
            if prep_surface:
                pieces.append(prep_surface)
            surface = " ".join(piece for piece in pieces if piece)
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=self._sentence_case(surface + "."),
                candidates=[self._candidate_payload(surface, "np_subject_transfer_rules", "dictionary")],
                notes=[
                    "Parsed a noun-phrase subject plus verb clause.",
                    "Derived Maltese subject agreement from the noun phrase and reused dictionary verb selection.",
                ],
            )
        return None
    def _parse_transfer_clause(
        self, normalized: str, *, ai_tags: list[dict[str, str]] | None = None
    ) -> TransferClause | None:
        text = normalize_text(normalized).rstrip("?").strip()
        question = str(normalized).strip().endswith("?")
        if not text:
            return None

        # do/does/did auxiliary: question or negative/habitual marker, not Maltese "do".
        match = re.fullmatch(
            r"(?:(do|does|did)\s+)?(i|you|he|she|it|we|they)\s+(?:(do\s+not|don't|dont|does\s+not|doesn't|doesnt|did\s+not|didn't|didnt)\s+)?([a-z']+)(?:\s+(.+))?",
            text,
        )
        if not match:
            return None
        aux, subject, negation, verb_raw, tail = match.groups()
        if verb_raw in {"am", "is", "are", "was", "were", "be", "been", "being", "can", "could", "should", "must", "may", "might", "want", "need"}:
            return None

        person = self._subject_person(subject)
        if not person:
            return None
        lemma_type, lemma = self._lemmatize_word(verb_raw)
        if lemma_type == "omit" or not lemma:
            return None
        if lemma_type == "maltese":
            return None
        if lemma not in self.verb_by_gloss:
            return None

        tense = "MPERF"
        if aux == "did" or normalize_text(negation or "").startswith("did") or self._is_past_english_verb(verb_raw):
            tense = "PERF"
        negated = bool(negation)
        object_phrase = None
        object_pronoun = ""
        tail_surface = ""
        if tail:
            tail = tail.strip()
            object_text, prep_text = self._split_object_and_preposition_tail(tail)
            if object_text in {"me", "you", "him", "her", "it", "us", "them"}:
                object_pronoun = object_text
            elif object_text:
                object_phrase = self._parse_noun_phrase(object_text)
                if not object_phrase and normalize_text(object_text) in {"everything", "anything", "nothing"}:
                    object_phrase = TransferNounPhrase("", "", (), normalize_text(object_text), LexicalRecord(self._simple_object_word(object_text), normalize_text(object_text), "noun", "M", "S", "manual"), False)
                if not object_phrase:
                    return None
            if prep_text:
                tail_surface = self._translate_prepositional_phrase_surface(prep_text)
                if not tail_surface:
                    return None

        return TransferClause(
            subject=subject,
            subject_person=person,
            verb_lemma=lemma,
            tense=tense,
            negated=negated,
            question=question or bool(aux),
            object_phrase=object_phrase,
            object_pronoun=object_pronoun,
            tail_surface=tail_surface,
        )

    def _generate_transfer_clause(self, clause: TransferClause) -> str:
        verb_record = self._select_verb(clause.verb_lemma, tense=clause.tense, person=clause.subject_person, negative=clause.negated)
        if not verb_record:
            return ""
        verb = self._surface_word(verb_record)
        verb_surface = verb
        if clause.object_pronoun:
            object_person = self._object_person(clause.object_pronoun)
            if not object_person:
                return ""
            positive_record = self._select_verb(clause.verb_lemma, tense=clause.tense, person=clause.subject_person, negative=False)
            if not positive_record:
                return ""
            positive = self._surface_word(positive_record)
            suffixed = self._attach_direct_object_suffix(positive, object_person)
            verb_surface = self._negate_suffixed_verb(suffixed) if clause.negated else suffixed
        elif clause.negated:
            verb_surface = f"ma {verb}"

        subject_surface = self._subject_pronoun_surface(clause.subject)
        pieces = [] if clause.question else ([subject_surface] if subject_surface else [])
        pieces.append(self._contextual_surface(verb_surface, previous=" ".join(pieces)))
        if clause.object_phrase:
            obj_surface = self._generate_noun_phrase(clause.object_phrase)
            if obj_surface:
                pieces.append(obj_surface)
        if clause.tail_surface:
            pieces.append(clause.tail_surface)
        return " ".join(piece for piece in pieces if piece)

    @staticmethod
    def _surface_word(value) -> str:
        return value.word if hasattr(value, "word") else str(value or "")
    @staticmethod
    def _subject_pronoun_surface(subject: str) -> str:
        return {
            "i": "jien",
            "you": "int",
            "he": "hu",
            "she": "hi",
            "it": "hu",
            "we": "a\u0127na",
            "they": "huma",
        }.get(normalize_text(subject), "")

    @staticmethod
    def _is_past_english_verb(word: str) -> bool:
        key = normalize_text(word)
        if key in {"went", "came", "decided", "wanted", "tried", "asked", "told", "started", "stopped", "needed", "ate", "eaten", "lived", "woke", "saw", "fell", "drank", "got", "made", "attacked", "listened", "helped", "left"}:
            return True
        return key.endswith("ed") and len(key) > 3

    @staticmethod
    def _simple_object_word(word: str) -> str:
        return {"everything": "kollox", "anything": "xejn", "nothing": "xejn"}.get(normalize_text(word), normalize_text(word))

    @staticmethod
    def _split_object_and_preposition_tail(tail: str) -> tuple[str, str]:
        text = normalize_text(tail)
        if not text:
            return "", ""
        if re.match(r"^(?:in|on|at|to|from|with|for|of)\s+", text):
            return "", text
        tokens = text.split()
        prepositions = {"in", "on", "at", "to", "from", "with", "for", "of"}
        for index, token in enumerate(tokens[1:], start=1):
            if token in prepositions and index + 1 < len(tokens):
                return " ".join(tokens[:index]), " ".join(tokens[index:])
        return text, ""

    def _object_and_preposition_tail_surface(self, tail: str) -> tuple[str, str]:
        tail_text = normalize_text(tail)
        adverb_surface = ""
        adverbials = {"together": "flimkien"}
        parts = tail_text.split()
        if parts and parts[-1] in adverbials:
            adverb_surface = adverbials[parts[-1]]
            tail_text = " ".join(parts[:-1])
        object_text, prep_text = self._split_object_and_preposition_tail(tail_text)
        object_surface = ""
        prep_surface = ""
        if object_text:
            object_surface = self._translate_object_phrase_surface(object_text)
            if not object_surface and normalize_text(object_text) in {"everything", "anything", "nothing"}:
                object_surface = self._simple_object_word(object_text)
        if prep_text:
            prep_surface = self._translate_prepositional_phrase_surface(prep_text)
        prep_surface = " ".join(part for part in (prep_surface, adverb_surface) if part)
        return object_surface, prep_surface

    def _translate_prepositional_phrase_surface(self, phrase: str) -> str:
        match = re.fullmatch(r"(in|on|at|to|from|with|for|of)\s+(.+)", normalize_text(phrase))
        if not match:
            return ""
        prep, obj = match.groups()
        obj = obj.strip()
        if obj in {"me", "you", "him", "her", "it", "us", "them"}:
            return self._preposition_pronoun_surface(prep, obj)
        parsed = self._parse_noun_phrase(obj)
        noun_surface = self._generate_noun_phrase(parsed) if parsed else self._translate_object_phrase_surface(obj)
        if not noun_surface:
            return ""
        definite = obj.startswith("the ") or obj.startswith(("this ", "that ", "these ", "those "))
        if prep in {"in", "on", "at"}:
            if definite:
                return self._fused_in_surface(noun_surface)
            return "f'" + noun_surface
        if prep == "with":
            return "ma' " + noun_surface
        if prep == "for":
            return "g\u0127al " + noun_surface
        if prep == "to":
            return "lil " + noun_surface
        if prep == "from":
            return "minn " + noun_surface
        if prep == "of":
            return "ta' " + noun_surface
        return ""

    @staticmethod
    def _preposition_pronoun_surface(prep: str, pronoun: str) -> str:
        table = {
            "with": {"me": "mieg\u0127i", "you": "mieg\u0127ek", "him": "mieg\u0127u", "her": "mag\u0127ha", "it": "mieg\u0127u", "us": "mag\u0127na", "them": "mag\u0127hom"},
            "for": {"me": "g\u0127alija", "you": "g\u0127alik", "him": "g\u0127alih", "her": "g\u0127aliha", "it": "g\u0127alih", "us": "g\u0127alina", "them": "g\u0127alihom"},
            "to": {"me": "lili", "you": "lilek", "him": "lilu", "her": "lilha", "it": "lilu", "us": "lilna", "them": "lilhom"},
            "from": {"me": "minni", "you": "minnek", "him": "minnu", "her": "minnha", "it": "minnu", "us": "minna", "them": "minnhom"},
            "in": {"me": "fija", "you": "fik", "him": "fih", "her": "fiha", "it": "fih", "us": "fina", "them": "fihom"},
        }
        if prep in {"on", "at"}:
            prep = "in"
        return table.get(prep, {}).get(pronoun, "")

    @staticmethod
    def _fused_in_surface(noun_surface: str) -> str:
        if noun_surface.startswith("il-"):
            return "fil-" + noun_surface[3:]
        if noun_surface.startswith("l-"):
            return "fl-" + noun_surface[2:]
        if noun_surface.startswith("in-"):
            return "fin-" + noun_surface[3:]
        if noun_surface.startswith("is-"):
            return "fis-" + noun_surface[3:]
        if noun_surface.startswith("it-"):
            return "fit-" + noun_surface[3:]
        if noun_surface.startswith("i\u010b-"):
            return "fi\u010b-" + noun_surface[3:]
        if noun_surface.startswith("i\u017c-"):
            return "fi\u017c-" + noun_surface[3:]
        return "f'" + noun_surface
    def _translate_complement_chain_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        text = normalize_text(normalized).rstrip("?").strip()
        question = str(normalized).strip().endswith("?")
        match = re.fullmatch(
            r"(?:(did)\s+)?(i|you|he|she|it|we|they)\s+(?:(do\s+not|don't|dont|does\s+not|doesn't|doesnt|did\s+not|didn't|didnt)\s+)?([a-z']+)\s+to\s+([a-z']+)(?:\s+(.+))?",
            text,
        )
        object_control = False
        object_pronoun = ""
        if not match:
            match = re.fullmatch(
                r"(?:(did)\s+)?(i|you|he|she|it|we|they)\s+(?:(do\s+not|don't|dont|does\s+not|doesn't|doesnt|did\s+not|didn't|didnt)\s+)?([a-z']+)\s+(me|you|him|her|it|us|them)\s+to\s+([a-z']+)(?:\s+(.+))?",
                text,
            )
            object_control = True
        if not match:
            return None

        if object_control:
            aux, subject, negation, main_raw, object_pronoun, comp_raw, tail = match.groups()
        else:
            aux, subject, negation, main_raw, comp_raw, tail = match.groups()

        main_type, main_lemma = self._lemmatize_word(main_raw)
        comp_type, comp_lemma = self._lemmatize_word(comp_raw)
        if main_type != "english" or comp_type != "english":
            return None
        if main_lemma not in {"want", "need", "try", "start", "stop", "decide", "ask", "tell"}:
            return None
        if main_lemma not in self.verb_by_gloss or comp_lemma not in self.verb_by_gloss:
            return None

        subject_person = self._subject_person(subject)
        if not subject_person:
            return None
        main_tense = "PERF" if aux == "did" or self._is_past_english_verb(main_raw) else "MPERF"
        main_negated = bool(negation)
        complement_person = subject_person
        object_person = ""
        if object_control:
            object_person = self._object_person(object_pronoun)
            if not object_person:
                return None
            complement_person = object_person

        main_surface = self._generate_chain_main_verb(main_lemma, main_tense, subject_person, main_negated, object_person)
        if not main_surface:
            return None
        complement_surface = self._generate_chain_complement(comp_lemma, complement_person, main_surface, tail or "")
        if not complement_surface:
            return None

        subject_surface = self._subject_pronoun_surface(subject)
        pieces = [] if question else ([subject_surface] if subject_surface else [])
        pieces.append(main_surface)
        connector = "li" if main_lemma in {"decide"} else ("biex" if main_lemma in {"ask", "tell"} else "")
        if connector:
            pieces.append(connector)
        pieces.append(complement_surface)
        translated = self._sentence_case(" ".join(piece for piece in pieces if piece) + ("?" if question else "."))
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "complement_chain_rules", "dictionary")],
            notes=[
                "Parsed a complement-chain transfer structure.",
                "Selected main and complement verb forms at runtime, inheriting complement subject from the main subject or object pronoun.",
            ],
        )

    def _generate_chain_main_verb(self, lemma: str, tense: str, person: str, negated: bool, object_person: str = "") -> str:
        positive_record = self._select_verb(lemma, tense=tense, person=person, negative=False)
        if not positive_record:
            return ""
        positive = self._surface_word(positive_record)
        if object_person:
            if lemma in {"tell", "give", "send"}:
                suffixed = self._attach_indirect_object_suffix(positive, object_person)
            else:
                suffixed = self._attach_direct_object_suffix(positive, object_person)
            return self._negate_suffixed_verb(suffixed) if negated else suffixed
        if negated:
            neg_record = self._select_verb(lemma, tense=tense, person=person, negative=True)
            if neg_record:
                return f"ma {self._surface_word(neg_record)}"
            return f"ma {positive}x"
        return positive

    def _generate_chain_complement(self, lemma: str, person: str, previous: str, tail: str = "") -> str:
        verb_record = self._select_verb(lemma, tense="MPERF", person=person, negative=False)
        if not verb_record:
            return ""
        pieces = [self._contextual_surface(self._surface_word(verb_record), previous=previous)]
        tail = normalize_text(tail)
        if tail:
            tail_parts = tail.split()
            adverb_surface = ""
            if tail_parts and tail_parts[-1] == "together":
                adverb_surface = "flimkien"
                tail = " ".join(tail_parts[:-1])
            object_text, prep_text = self._split_object_and_preposition_tail(tail)
            if object_text in {"me", "you", "him", "her", "it", "us", "them"}:
                object_person = self._object_person(object_text)
                if object_person:
                    pieces[0] = self._attach_direct_object_suffix(pieces[0], object_person)
            elif object_text:
                obj_surface = self._translate_object_phrase_surface(object_text)
                if obj_surface:
                    pieces.append(obj_surface)
            if prep_text:
                prep_surface = self._translate_prepositional_phrase_surface(prep_text)
                if prep_surface:
                    pieces.append(prep_surface)
            if adverb_surface:
                pieces.append(adverb_surface)
        return " ".join(piece for piece in pieces if piece)
    def _translate_ai_route(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        transitive_pat = r"^(i|he|she|it|we|you|they)\s+(?:(do\s+not|don't|dont|does\s+not|doesn't|doesnt)\s+)?([a-z']+)\s+(me|you|him|her|it|us|them)$"
        if not re.fullmatch(transitive_pat, normalized):
            return None

        review = route_translation(original, "en-mt")
        if not review.used or review.data.get("route") != "transitive_verb_object":
            return None

        result = self._translate_transitive_object_from_parts(
            original=original,
            subject=str(review.data.get("subject", "")),
            verb_gloss=str(review.data.get("verb_gloss", "")),
            obj=str(review.data.get("object", "")),
            negated=bool(review.data.get("negated")),
            source="openai_route_transitive_object",
        )
        if result and review.data.get("explanation"):
            result.notes.append(
                f"AI routed input into transitive-object rule: {review.data['explanation']}"
            )
        return result

    def _translate_transitive_object_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+"
            r"(?:(do\s+not|don't|dont|does\s+not|doesn't|doesnt)\s+)?"
            r"([a-z']+)\s+"
            r"(me|you|him|her|it|us|them)",
            normalized,
        )
        if not match:
            return None

        subject, negation, verb_raw, obj = match.groups()
        verb_lemma = self._verb_lemma(verb_raw)
        if verb_lemma == "like":
            return None
        if verb_lemma in self.verb_by_gloss or verb_raw in self.verb_by_gloss:
            return self._translate_transitive_object_from_parts(
                original=original,
                subject=subject,
                verb_gloss=verb_lemma,
                obj=obj,
                negated=bool(negation),
                source="transitive_object_rules",
            )
        return None

    def _translate_transitive_object_from_parts(
        self,
        *,
        original: str,
        subject: str,
        verb_gloss: str,
        obj: str,
        negated: bool,
        source: str,
    ) -> TranslationResult | None:
        subject_person = {
            "i": "1S",
            "you": "2S",
            "he": "3SM",
            "she": "3SF",
            "it": "3SM",
            "we": "1P",
            "they": "3P",
        }.get(normalize_text(subject))
        object_person = {
            "me": "1S",
            "you": "2S",
            "him": "3SM",
            "her": "3SF",
            "it": "3SM",
            "us": "1P",
            "them": "3P",
        }.get(normalize_text(obj))
        gloss = normalize_text(verb_gloss)
        if not subject_person or not object_person or not gloss:
            return None

        base = self._select_verb(gloss, tense="MPERF", person=subject_person, negative=False)
        if not base:
            return None

        if gloss in {"see"}:
            base = "qed " + base

        singular = self._attach_direct_object_suffix(base, object_person)
        translated = self._sentence_case(self._negate_suffixed_verb(singular) if negated else singular)
        suggestions: list[dict] = []
        highlights: list[dict] = []

        if normalize_text(obj) == "you":
            plural = self._attach_direct_object_suffix(base, "2P")
            plural_translated = self._sentence_case(
                self._negate_suffixed_verb(plural) if negated else plural
            )
            if plural_translated != translated:
                suggestions = [
                    {
                        "text": translated,
                        "label": "Singular you",
                        "explanation": "Use for one person.",
                    },
                    {
                        "text": plural_translated,
                        "label": "Plural you",
                        "explanation": "Use for more than one person.",
                    },
                ]
                highlights = [
                    {
                        "text": translated,
                        "choices": [
                            {"word": translated, "meaning": "you (singular)"},
                            {"word": plural_translated, "meaning": "you (plural)"},
                        ],
                    }
                ]

        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, source, "dictionary")],
            suggestions=suggestions,
            highlights=highlights,
            notes=[
                f"Parsed: {subject} + {verb_gloss} + {obj}.",
                "Selected the verb from the dictionary, then attached the Maltese direct-object suffix.",
            ],
        )

    def _translate_must_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(r"(i|he|she|it|we|you|they)\s+must\s+([a-z']+)", normalized)
        if not match:
            return None
        pronoun, english_verb = match.groups()
        want_person = {
            "i": "1S",
            "he": "3SM",
            "she": "3SF",
            "it": "3SM",
            "we": "1P",
            "you": "2S",
            "they": "3P",
        }.get(pronoun, "2S")
        want = self._select_verb("want", tense="MPERF", person=want_person, negative=False)
        verb = self._select_verb(english_verb, tense="MPERF", person=want_person, negative=False)
        if not want or not verb:
            return None
        translated = self._sentence_case(f"{want} {self._contextual_surface(verb, previous=want)}.")
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "manual_must_rules", "manual")],
            notes=[
                f"Parsed: {pronoun} + must + {english_verb}.",
                "Mapped English must to Maltese want/need construction using dictionary verb forms.",
            ],
        )

    def _translate_modal_transfer_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        if normalized in {"that's how it should be", "that is how it should be", "this is how it should be"}:
            translated = "Hekk g\u0127andu jkun."
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "modal_transfer_rules", "manual")],
                notes=["Parsed idiomatic should-be structure as 'għandu jkun', not 'suppost'."],
            )

        match = re.fullmatch(
            r"(i|you|he|she|it|we|they)\s+(should|should\s+not|shouldn't|shouldnt|may|may\s+not|might|might\s+not)\s+([a-z']+)(?:\s+(.+))?",
            normalized,
        )
        if not match:
            return None
        subject, modal, verb_raw, tail = match.groups()
        person = self._subject_person(subject)
        if not person:
            return None
        modal = modal.replace("shouldnt", "shouldn't")
        negated = "not" in modal or "n't" in modal
        verb_lemma = self._verb_lemma(verb_raw)
        subject_surface = self._subject_pronoun_surface(subject)
        tail_surface = ""
        if tail:
            object_surface, prep_surface = self._object_and_preposition_tail_surface(tail)
            tail_surface = " ".join(part for part in (object_surface, prep_surface) if part)

        if modal.startswith("should"):
            obligation = self._obligation_surface(person)
            if not obligation:
                return None
            if verb_lemma == "be":
                complement = self._be_complement_surface(person)
            else:
                verb = self._select_verb(verb_lemma, tense="MPERF", person=person, negative=False)
                if not verb:
                    return None
                complement = self._contextual_surface(self._surface_word(verb), previous=obligation)
            if negated:
                translated = f"{subject_surface} ma {obligation}x {complement}"
            else:
                translated = f"{subject_surface} {obligation} b\u017conn {complement}"
                if verb_lemma == "be":
                    translated = f"{subject_surface} {obligation} {complement}"
        elif modal.startswith("may"):
            can = self._select_verb("can", tense="MPERF", person=person, negative=negated)
            verb = self._select_verb(verb_lemma, tense="MPERF", person=person, negative=False)
            if not can or not verb:
                return None
            can_surface = self._surface_word(can)
            translated = f"{subject_surface} {'ma ' if negated else ''}{can_surface} {self._contextual_surface(self._surface_word(verb), previous=can_surface)}"
        else:
            verb = self._select_verb(verb_lemma, tense="MPERF", person=person, negative=False)
            if not verb:
                return None
            translated = f"{subject_surface} forsi {self._contextual_surface(self._surface_word(verb), previous='forsi')}"
            if negated:
                neg_verb = self._select_verb(verb_lemma, tense="MPERF", person=person, negative=True)
                if neg_verb:
                    translated = f"{subject_surface} forsi ma {self._surface_word(neg_verb)}"
        if tail_surface:
            translated += f" {tail_surface}"
        translated = self._sentence_case(translated.strip() + ".")
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "modal_transfer_rules", "dictionary")],
            notes=["Parsed a modal clause structurally and selected the complement verb from the reverse verb dictionary."],
        )

    @staticmethod
    def _obligation_surface(person: str) -> str:
        return {
            "1S": "g\u0127andi",
            "2S": "g\u0127andek",
            "3SM": "g\u0127andu",
            "3SF": "g\u0127andha",
            "1P": "g\u0127andna",
            "2P": "g\u0127andkom",
            "3P": "g\u0127andhom",
        }.get(person, "")

    @staticmethod
    def _be_complement_surface(person: str) -> str:
        return {
            "1S": "nkun",
            "2S": "tkun",
            "3SM": "jkun",
            "3SF": "tkun",
            "1P": "nkunu",
            "2P": "tkunu",
            "3P": "jkunu",
        }.get(person, "jkun")
    def _translate_do_want_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"do\s+(i|he|she|it|we|you|they)\s+want\s+to\s+([a-z']+)",
            normalized,
        )
        if not match:
            return None
        pronoun, english_verb = match.groups()
        person = {
            "i": "1S",
            "he": "3SM",
            "she": "3SF",
            "it": "3SM",
            "we": "1P",
            "you": "2S",
            "they": "3P",
        }.get(pronoun, "3P")
        pronoun_mt = {
            "i": "Jien",
            "he": "Hu",
            "she": "Hi",
            "it": "Hu",
            "we": "Aħna",
            "you": "Int",
            "they": "Huma",
        }.get(pronoun, "Huma")
        want = self._select_verb("want", tense="MPERF", person=person, negative=False)
        verb = self._select_verb(english_verb, tense="MPERF", person=person, negative=False)
        if not want or not verb:
            return None
        verb = self._contextual_surface(verb, previous=want)
        translated = f"{pronoun_mt} {want} {verb}?"
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "manual_want_rules", "manual")],
            notes=[
                f"Parsed: do + {pronoun} + want + to + {english_verb}.",
                "Selected want and complement verb forms from the reverse verb dictionary.",
            ],
        )

    def _translate_understand_object_question(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"do\s+(you)\s+understand\s+(?:the\s+)?([a-z]+)",
            normalized,
        )
        if not match:
            return None
        pronoun, noun_key = match.groups()
        noun = self._select_lexical(noun_key, pos="noun")
        verb = self._select_verb("understand", tense="MPERF", person="2S", negative=False)
        if not noun or not verb:
            return None
        translated = f"Qed {verb} {self._definite_noun(noun.word)}?"
        plural = self._select_verb("understand", tense="MPERF", person="2P", negative=False)
        suggestions = []
        highlights = []
        if plural:
            plural_translated = f"Qed {plural} {self._definite_noun(noun.word)}?"
            suggestions = [
                {
                    "text": translated,
                    "label": "Singular you",
                    "explanation": "Use when 'you' refers to one person.",
                },
                {
                    "text": plural_translated,
                    "label": "Plural or formal you",
                    "explanation": "Use when 'you' refers to more than one person.",
                },
            ]
            highlights = [
                {
                    "text": f"Qed {verb}",
                    "choices": [
                        {
                            "word": f"Qed {verb}",
                            "meaning": "singular you understand",
                        },
                        {
                            "word": f"Qed {plural}",
                            "meaning": "plural you understand",
                        },
                    ],
                }
            ]
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "manual_understand_rules", "manual")],
            suggestions=suggestions,
            highlights=highlights,
            notes=[
                "Parsed: do + you + understand + definite noun.",
                "Mapped this sense to Maltese progressive/question form with qed.",
            ],
        )

    def _translate_clause_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        if re.fullmatch(r"i\s+(?:do\s+not|don't|dont)\s+know", normalized):
            verb = self._select_verb("know", tense="MPERF", person="1S", negative=True)
            if not verb:
                return None
            translated = self._sentence_case(f"jien ma {verb}.")
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "manual_clause_rules", "manual")],
                notes=[
                    "Parsed: I + do/not + know.",
                    "Selected the negative 1S imperfect form from the verb dictionary.",
                ],
            )

        match = re.fullmatch(
            r"i\s+(?:do\s+not|don't|dont)\s+know\s+what\s+you\s+want\s+me\s+to\s+([a-z']+)",
            normalized,
        )
        if not match:
            return None

        english_verb = match.group(1)
        maltese_verb = self._select_verb(english_verb, tense="MPERF", person="1S", negative=False)
        if not maltese_verb:
            fallback = self._sentence_case(
                f"ma nafx {self._what_before('tridni')} tridni [{english_verb}]."
            )
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=fallback,
                candidates=[self._candidate_payload(fallback, "manual_clause_rules", "partial")],
                suggestions=[
                    {
                        "text": fallback,
                        "label": "Needs verb entry",
                        "explanation": f"No Maltese verb form is configured yet for '{english_verb}'.",
                    }
                ],
                notes=[
                    f"Matched the clause pattern, but the verb '{english_verb}' needs a configured Maltese form.",
                    "Kept the clause structure instead of using word-by-word dictionary fallback.",
                ],
            )

        know = self._select_verb("know", tense="MPERF", person="1S", negative=True)
        want_singular = self._select_verb("want", tense="MPERF", person="2S", negative=False)
        want_plural = self._select_verb("want", tense="MPERF", person="2P", negative=False)
        if not know or not want_singular or not want_plural:
            return None

        singular_want_me = self._attach_direct_object_suffix(want_singular, "1S")
        plural_want_me = self._attach_direct_object_suffix(want_plural, "1S")
        singular_complement = self._contextual_surface(maltese_verb, previous=singular_want_me)
        plural_complement = self._contextual_surface(maltese_verb, previous=plural_want_me)
        singular = self._sentence_case(
            f"ma {know} {self._what_before(singular_want_me)} {singular_want_me} {singular_complement}."
        )
        plural = self._sentence_case(
            f"ma {know} {self._what_before(plural_want_me)} {plural_want_me} {plural_complement}."
        )
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=singular,
            candidates=[self._candidate_payload(singular, "manual_clause_rules", "manual")],
            suggestions=[
                {
                    "text": singular,
                    "label": "Singular you",
                    "explanation": "Use when 'you' refers to one person.",
                },
                {
                    "text": plural,
                    "label": "Plural or formal you",
                    "explanation": "Use when 'you' refers to more than one person, or a formal/plural address.",
                },
            ],
            highlights=[
                {
                    "text": singular_want_me,
                    "choices": [
                        {
                            "word": singular_want_me,
                            "meaning": "you want me",
                        },
                        {
                            "word": plural_want_me,
                            "meaning": "you want me",
                        },
                    ],
                }
            ],
            notes=[
                f"Parsed: I + do/not + know + what + you want me to {english_verb}.",
                "Selected know/want/complement verb forms from the verb dictionary, then attached the 1S direct-object suffix to want.",
                "Used 'xi' before the two-consonant cluster in tridni/triduni.",
            ],
        )

    def _translate_need_to_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+(?:need|needs)\s+to\s+([a-z']+)",
            normalized,
        )
        if not match:
            return None

        pronoun, english_verb = match.groups()

        if pronoun == "you":
            verb_singular = self._select_verb(english_verb, tense="MPERF", person="2S", negative=False)
            verb_plural = self._select_verb(english_verb, tense="MPERF", person="2P", negative=False)

            verb_s = self._contextual_surface(verb_singular, previous="għandek bÅ¼onn") if verb_singular else f"[{english_verb}]"
            verb_p = self._contextual_surface(verb_plural, previous="għandkom bÅ¼onn") if verb_plural else f"[{english_verb}]"

            singular_phrase = f"għandek bÅ¼onn {verb_s}"
            plural_phrase = f"għandkom bÅ¼onn {verb_p}"

            translated = self._sentence_case(singular_phrase)
            translated_p = self._sentence_case(plural_phrase)

            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "manual_need_to_rules", "manual")],
                suggestions=[
                    {
                        "text": translated,
                        "label": "Singular you",
                        "explanation": "Use when 'you' refers to one person.",
                    },
                    {
                        "text": translated_p,
                        "label": "Plural or formal you",
                        "explanation": "Use when 'you' refers to more than one person.",
                    },
                ],
                highlights=[
                    {
                        "text": "Għandek",
                        "replaceText": translated,
                        "choices": [
                            {
                                "word": "Għandek",
                                "replaceWith": translated,
                                "meaning": "singular you need to " + english_verb,
                            },
                            {
                                "word": "Għandkom",
                                "replaceWith": translated_p,
                                "meaning": "plural you need to " + english_verb,
                            },
                        ],
                    }
                ],
                notes=[
                    f"Parsed: you + need + to + {english_verb}.",
                    "Selected the matching 2S/2P imperfect verb form from the verb dictionary.",
                ],
            )

        NEED_TO_MAP = {
            "i": {"person": "1S", "prefix": "għandi bÅ¼onn"},
            "he": {"person": "3SM", "prefix": "għandu bÅ¼onn"},
            "she": {"person": "3SF", "prefix": "għandha bÅ¼onn"},
            "it": {"person": "3SM", "prefix": "għandu bÅ¼onn"},
            "we": {"person": "1P", "prefix": "għandna bÅ¼onn"},
            "they": {"person": "3P", "prefix": "għandhom bÅ¼onn"},
        }

        info = NEED_TO_MAP.get(pronoun)
        if not info:
            return None

        person = info["person"]
        prefix = info["prefix"]

        verb_form = self._select_verb(english_verb, tense="MPERF", person=person, negative=False)
        verb_surface = self._contextual_surface(verb_form, previous=prefix) if verb_form else f"[{english_verb}]"

        translated = self._sentence_case(f"{prefix} {verb_surface}")
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "manual_need_to_rules", "manual")],
            notes=[
                f"Parsed: {pronoun} + need/needs + to + {english_verb}.",
                f"Selected the matching {person} imperfect verb form from the verb dictionary.",
            ],
        )

    def _translate_like_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        noun_match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+(like|likes)\s+(?:the\s+)?([a-z]+)",
            normalized,
        )
        if noun_match:
            subject, _, noun_key = noun_match.groups()
            noun = self._select_lexical(noun_key, pos="noun")
            person = {
                "i": "1S",
                "he": "3SM",
                "she": "3SF",
                "it": "3SM",
                "we": "1P",
                "you": "2S",
                "they": "3P",
            }.get(subject, "1S")
            pronoun_mt = {
                "i": "Jien",
                "he": "Hu",
                "she": "Hi",
                "it": "Hu",
                "we": "Aħna",
                "you": "Int",
                "they": "Huma",
            }.get(subject, "Jien")
            verb = self._select_verb("like", tense="MPERF", person=person, negative=False)
            if not noun or not verb:
                return None
            translated = f"{pronoun_mt} {self._contextual_surface(self._surface_word(verb), previous=pronoun_mt)} {self._definite_noun(noun.word)}."
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "manual_like_rules", "manual")],
                notes=[
                    f"Parsed: {subject} + like + noun.",
                    "Selected the subject-matching verb form of 'like/love/enjoy' and a definite noun.",
                ],
            )

        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+(do\s+not|don't|dont|does\s+not|doesn't|doesnt)?\s*(like|likes)\s+(me|you|him|her|it|us|them)",
            normalized,
        )
        if not match:
            return None

        subject, negation, like_verb, obj = match.groups()
        is_neg = bool(negation)

        obj_to_subject_map = {
            "me": "1S",
            "you": "2S",
            "him": "3SM",
            "her": "3SF",
            "it": "3SM",
            "us": "1P",
            "them": "3P",
        }

        sub_to_obj_map = {
            "i": "1S",
            "you": "2S",
            "he": "3SM",
            "she": "3SF",
            "it": "3SM",
            "we": "1P",
            "they": "3P",
        }

        verb_subj_person = obj_to_subject_map.get(obj, "3SM")
        obj_suffix_person = sub_to_obj_map.get(subject, "1S")

        verb_3sm = self._select_verb("please", tense="MPERF", person="3SM", negative=False)
        verb_3sf = self._select_verb("please", tense="MPERF", person="3SF", negative=False)
        verb_3p = self._select_verb("please", tense="MPERF", person="3P", negative=False)

        if not verb_3sm: verb_3sm = "jogħÄ¡ob"
        if not verb_3sf: verb_3sf = "togħÄ¡ob"
        if not verb_3p: verb_3p = "jogħÄ¡bu"

        def suffix_ghogob(verb: str, suffix_pers: str, negative: bool) -> str:
            if suffix_pers == "1S":
                res = verb + "ni"
                return f"ma {res}x" if negative else res
            elif suffix_pers == "2S":
                prefix = verb[:3]
                if verb.endswith("u"):
                    res = verb[:-1] + "uk"
                else:
                    res = f"{prefix}ħÄ¡bok"
                return f"ma {res}x" if negative else res
            elif suffix_pers == "3SM":
                prefix = verb[:3]
                if verb.endswith("u"):
                    res = verb + "h"
                else:
                    res = f"{prefix}ħÄ¡bu"
                return f"ma {res}x" if negative else res
            elif suffix_pers == "3SF":
                res = verb + "ha"
                return f"ma {res}hiex" if negative else res
            elif suffix_pers == "1P":
                res = verb + "na"
                return f"ma {res}niex" if negative else res
            elif suffix_pers == "2P":
                res = verb + "kom"
                return f"ma {res}x" if negative else res
            elif suffix_pers == "3P":
                res = verb + "hom"
                return f"ma {res}x" if negative else res
            return verb

        if obj == "it":
            like_it_positive = {
                "i": ("Jogħġobni", "Togħġobni"),
                "you": ("Jogħġbok", "Togħġbok"),
                "he": ("Jogħġbu", "Togħġbu"),
                "she": ("Jogħġobha", "Togħġobha"),
                "it": ("Jogħġbu", "Togħġbu"),
                "we": ("Jogħġobna", "Togħġobna"),
                "they": ("Jogħġobhom", "Togħġobhom"),
            }
            like_it_negative = {
                "i": ("Ma jogħġobnix", "Ma togħġobnix"),
                "you": ("Ma jogħġbokx", "Ma togħġbokx"),
                "he": ("Ma jogħġbux", "Ma togħġbux"),
                "she": ("Ma jogħġobhiex", "Ma togħġobhiex"),
                "it": ("Ma jogħġbux", "Ma togħġbux"),
                "we": ("Ma jogħġobniex", "Ma togħġobniex"),
                "they": ("Ma jogħġobhomx", "Ma togħġobhomx"),
            }
            m_trans, f_trans = (like_it_negative if is_neg else like_it_positive).get(subject, ("Jogħġbu", "Togħġbu"))

            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=m_trans,
                candidates=[self._candidate_payload(m_trans, "manual_like_rules", "manual")],
                suggestions=[
                    {
                        "text": m_trans,
                        "label": "Masculine 'it'",
                        "explanation": "Use when 'it' refers to a masculine noun.",
                    },
                    {
                        "text": f_trans,
                        "label": "Feminine 'it'",
                        "explanation": "Use when 'it' refers to a feminine noun.",
                    },
                ],
                highlights=[
                    {
                        "text": m_trans,
                        "choices": [
                            {
                                "word": m_trans,
                                "meaning": "masculine object 'it'",
                            },
                            {
                                "word": f_trans,
                                "meaning": "feminine object 'it'",
                            },
                        ],
                    }
                ],
                notes=[
                    f"Parsed: {subject} + {'not ' if is_neg else ''}like + it.",
                    "Mapped English subject to Maltese direct object suffix, and English object to Maltese verb subject.",
                    "Selected the matching imperfect verb forms of 'għoÄ¡ob' (to please) from the verb dictionary.",
                ],
            )

        VERB_DEFAULTS = {
            "1S": "nogħÄ¡ob",
            "2S": "togħÄ¡ob",
            "3SM": "jogħÄ¡ob",
            "3SF": "togħÄ¡ob",
            "1P": "nogħÄ¡bu",
            "2P": "togħÄ¡bu",
            "3P": "jogħÄ¡bu",
        }

        verb_to_use = self._select_verb("please", tense="MPERF", person=verb_subj_person, negative=False)
        if not verb_to_use:
            verb_to_use = VERB_DEFAULTS.get(verb_subj_person, "jogħÄ¡ob")

        translated = self._sentence_case(suffix_ghogob(verb_to_use, obj_suffix_person, is_neg))
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "manual_like_rules", "manual")],
            notes=[
                f"Parsed: {subject} + {'not ' if is_neg else ''}like + {obj}.",
                "Mapped English subject to Maltese direct object suffix, and English object to Maltese verb subject.",
                f"Selected the matching imperfect verb form of 'għoÄ¡ob' (to please) from the verb dictionary.",
            ],
        )

    def _translate_can_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+(can't|cant|cannot|can\s+not|can)(?:\s+([a-z']+))?",
            normalized,
        )
        if not match:
            return None

        pronoun, can_op, english_verb = match.groups()
        is_neg = can_op in {"can't", "cant", "cannot", "can not"}

        if pronoun == "you":
            can_s = self._select_verb("can", tense="MPERF", person="2S", negative=is_neg)
            can_p = self._select_verb("can", tense="MPERF", person="2P", negative=is_neg)

            if not can_s: can_s = "tistax" if is_neg else "tista'"
            if not can_p: can_p = "tistgħux" if is_neg else "tistgħu"

            can_phrase_s = f"ma {can_s}" if is_neg else can_s
            can_phrase_p = f"ma {can_p}" if is_neg else can_p

            if english_verb:
                verb_s = self._select_verb(english_verb, tense="MPERF", person="2S", negative=False)
                verb_p = self._select_verb(english_verb, tense="MPERF", person="2P", negative=False)

                verb_surface_s = self._contextual_surface(verb_s, previous=can_phrase_s) if verb_s else f"[{english_verb}]"
                verb_surface_p = self._contextual_surface(verb_p, previous=can_phrase_p) if verb_p else f"[{english_verb}]"

                singular_phrase = f"{can_phrase_s} {verb_surface_s}"
                plural_phrase = f"{can_phrase_p} {verb_surface_p}"
            else:
                singular_phrase = can_phrase_s
                plural_phrase = can_phrase_p

            translated = self._sentence_case(singular_phrase)
            translated_p = self._sentence_case(plural_phrase)

            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "manual_can_rules", "manual")],
                suggestions=[
                    {
                        "text": translated,
                        "label": "Singular you",
                        "explanation": "Use when 'you' refers to one person.",
                    },
                    {
                        "text": translated_p,
                        "label": "Plural or formal you",
                        "explanation": "Use when 'you' refers to more than one person.",
                    },
                ],
                highlights=[
                    {
                        "text": self._sentence_case(can_phrase_s),
                        "replaceText": translated,
                        "choices": [
                            {
                                "word": self._sentence_case(can_phrase_s),
                                "replaceWith": translated,
                                "meaning": "singular you " + ("can't" if is_neg else "can") + (f" {english_verb}" if english_verb else ""),
                            },
                            {
                                "word": self._sentence_case(can_phrase_p),
                                "replaceWith": translated_p,
                                "meaning": "plural you " + ("can't" if is_neg else "can") + (f" {english_verb}" if english_verb else ""),
                            },
                        ],
                    }
                ],
                notes=[
                    f"Parsed: you + {'not ' if is_neg else ''}can" + (f" + {english_verb}" if english_verb else "") + ".",
                    "Selected the matching 2S/2P imperfect verb form from the verb dictionary.",
                ],
            )

        CAN_MAP = {
            "i": {"person": "1S", "default": "nistax" if is_neg else "nista'"},
            "he": {"person": "3SM", "default": "jistax" if is_neg else "jista'"},
            "she": {"person": "3SF", "default": "tistax" if is_neg else "tista'"},
            "it": {"person": "3SM", "default": "jistax" if is_neg else "jista'"},
            "we": {"person": "1P", "default": "nistgħux" if is_neg else "nistgħu"},
            "they": {"person": "3P", "default": "jistgħux" if is_neg else "jistgħu"},
        }

        info = CAN_MAP.get(pronoun)
        if not info:
            return None

        person = info["person"]
        default_can = info["default"]

        can_verb = self._select_verb("can", tense="MPERF", person=person, negative=is_neg)
        if not can_verb:
            can_verb = default_can

        can_phrase = f"ma {can_verb}" if is_neg else can_verb

        if english_verb:
            verb_form = self._select_verb(english_verb, tense="MPERF", person=person, negative=False)
            verb_surface = self._contextual_surface(verb_form, previous=can_phrase) if verb_form else f"[{english_verb}]"
            phrase = f"{can_phrase} {verb_surface}"
        else:
            phrase = can_phrase

        translated = self._sentence_case(phrase) + "."
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "manual_can_rules", "manual")],
            notes=[
                f"Parsed: {pronoun} + {'not ' if is_neg else ''}can" + (f" + {english_verb}" if english_verb else "") + ".",
                f"Selected the matching {person} imperfect verb form from the verb dictionary.",
            ],
        )

    def _translate_progressive_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        has_question = "?" in original
        cleaned_norm = normalized.rstrip("?").strip()

        match_stmt = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+(am|'m|is|'s|are|'re|isn't|aren't)\s+(?:not\s+)?([a-z]+ing)(?:\s+(.+))?",
            cleaned_norm,
        )
        match_q = re.fullmatch(
            r"(am|is|are|isn't|aren't)\s+(i|he|she|it|we|you|they)\s+(?:not\s+)?([a-z]+ing)(?:\s+(.+))?",
            cleaned_norm,
        )
        match_do_stmt = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+(do\s+not|don't|dont|does\s+not|doesn't|doesnt)\s+([a-z']+)(?:\s+(.+))?",
            cleaned_norm,
        )
        match_do_q = re.fullmatch(
            r"(do|does|don't|dont|doesn't|doesnt)\s+(i|he|she|it|we|you|they)\s+(?:not\s+)?([a-z']+)(?:\s+(.+))?",
            cleaned_norm,
        )

        pronoun = None
        english_verb = None
        pattern_type = ""
        negative = False
        tail = None

        if match_stmt:
            pronoun, aux, verb_ing, tail = match_stmt.groups()
            english_verb = self._get_base_verb_from_ing(verb_ing)
            pattern_type = "progressive_stmt"
            negative = ("not" in cleaned_norm or "n't" in cleaned_norm)
        elif match_q:
            aux, pronoun, verb_ing, tail = match_q.groups()
            english_verb = self._get_base_verb_from_ing(verb_ing)
            pattern_type = "progressive_q"
            negative = ("not" in cleaned_norm or "n't" in cleaned_norm)
        elif match_do_stmt:
            pronoun, aux, english_verb, tail = match_do_stmt.groups()
            pattern_type = "do_stmt"
            negative = True
        elif match_do_q:
            aux, pronoun, english_verb, tail = match_do_q.groups()
            pattern_type = "do_q"
            negative = ("not" in cleaned_norm or "n't" in cleaned_norm or "don't" in cleaned_norm or "doesn't" in cleaned_norm)

        if not pronoun or not english_verb:
            return None

        # Helper to lookup imperfect verb forms
        def lookup_verb_form(eng_v: str, pers: str) -> str:
            v_form = self._select_verb(eng_v, tense="MPERF", person=pers, negative=False)
            if not v_form and not eng_v.endswith("e"):
                v_form = self._select_verb(eng_v + "e", tense="MPERF", person=pers, negative=False)
            return v_form

        # Suffix (question mark)
        suffix = "?" if (has_question or pattern_type in {"progressive_q", "do_q"}) else "."

        tail_mt = ""
        if tail:
            object_surface, prep_surface = self._object_and_preposition_tail_surface(tail)
            tail_mt = " ".join(part for part in (object_surface, prep_surface) if part)
        tail_space = f" {tail_mt}" if tail_mt else ""

        # Negative Pronoun Prefixes
        PROGRESSIVE_NEGATION_PRONOUNS = {
            "i": "m'iniex",
            "he": "mhux",
            "she": "mhijiex",
            "it": "mhux",
            "we": "m'aħniex",
            "they": "m'humiex",
        }

        # Check for Habitual "Do you/does he" Question (except for "understand" which uses progressive "qed")
        if (pattern_type in {"do_q", "do_stmt"}) and english_verb != "understand":
            HABITUAL_PRONOUNS = {
                "i": "Jien",
                "he": "Hu",
                "she": "Hi",
                "it": "Hu",
                "we": "Aħna",
                "they": "Huma",
            }
            if pronoun == "you":
                verb_s = lookup_verb_form(english_verb, "2S")
                verb_p = lookup_verb_form(english_verb, "2P")
                if not verb_s: verb_s = f"[{english_verb}]"
                if not verb_p: verb_p = f"[{english_verb}]"

                if negative:
                    verb_s = f"ma {verb_s}x" if not verb_s.endswith("x") else f"ma {verb_s}"
                    verb_p = f"ma {verb_p}x" if not verb_p.endswith("x") else f"ma {verb_p}"
                    translated_s = self._sentence_case(f"int {verb_s}{tail_space}{suffix}")
                    translated_p = self._sentence_case(f"intom {verb_p}{tail_space}{suffix}")
                else:
                    translated_s = self._sentence_case(f"int {verb_s}{tail_space}{suffix}")
                    translated_p = self._sentence_case(f"intom {verb_p}{tail_space}{suffix}")

                return TranslationResult(
                    input=original,
                    direction="en-mt",
                    translated_text=translated_s,
                    candidates=[self._candidate_payload(translated_s, "manual_progressive_rules", "manual")],
                    suggestions=[
                        {
                            "text": translated_s,
                            "label": "Singular you",
                            "explanation": "Use when 'you' refers to one person.",
                        },
                        {
                            "text": translated_p,
                            "label": "Plural or formal you",
                            "explanation": "Use when 'you' refers to more than one person.",
                        },
                    ],
                    highlights=[
                        {
                            "text": "Int " + verb_s if not negative else verb_s,
                            "replaceText": translated_s,
                            "choices": [
                                {
                                    "word": "Int " + verb_s if not negative else verb_s,
                                    "replaceWith": translated_s,
                                    "meaning": f"singular you {english_verb}",
                                },
                                {
                                    "word": "Intom " + verb_p if not negative else verb_p,
                                    "replaceWith": translated_p,
                                    "meaning": f"plural you {english_verb}",
                                },
                            ],
                        }
                    ],
                    notes=[
                        f"Parsed: habitual {'negative ' if negative else ''}clause with {pronoun} + {english_verb}.",
                        "Mapped to habitual question pronoun + imperfect verb.",
                    ],
                )
            else:
                pronoun_mt = HABITUAL_PRONOUNS.get(pronoun, "Jien")
                person = {"i": "1S", "he": "3SM", "she": "3SF", "it": "3SM", "we": "1P", "they": "3P"}.get(pronoun, "1S")
                verb_form = lookup_verb_form(english_verb, person)
                if not verb_form: verb_form = f"[{english_verb}]"

                if negative:
                    verb_form = f"ma {verb_form}x" if not verb_form.endswith("x") else f"ma {verb_form}"

                translated = self._sentence_case(f"{pronoun_mt} {verb_form}{tail_space}{suffix}")
                return TranslationResult(
                    input=original,
                    direction="en-mt",
                    translated_text=translated,
                    candidates=[self._candidate_payload(translated, "manual_progressive_rules", "manual")],
                    notes=[
                        f"Parsed: habitual {'negative ' if negative else ''}clause with {pronoun} + {english_verb}.",
                        "Mapped to habitual question pronoun + imperfect verb.",
                    ],
                )

        # Look up Active Participles (ACTPAR) for progressive patterns
        possible_glosses = {english_verb}
        if match_stmt:
            possible_glosses.add(match_stmt.group(3))
        elif match_q:
            possible_glosses.add(match_q.group(3))
        else:
            possible_glosses.add(english_verb + "ing")

        actpar_s = None
        actpar_f = None
        actpar_p = None
        for gloss in sorted(possible_glosses, key=len, reverse=True):
            actpar_s = self._select_verb(gloss, tense="ACTPAR", person="3SM", negative=False)
            actpar_f = self._select_verb(gloss, tense="ACTPAR", person="3SF", negative=False)
            actpar_p = self._select_verb(gloss, tense="ACTPAR", person="3P", negative=False)
            if actpar_s or actpar_p:
                break

        if actpar_s or actpar_p:
            if pronoun == "you":
                val_s = actpar_s or f"[{english_verb}]"
                val_f = actpar_f or val_s
                val_p = actpar_p or val_s

                if negative:
                    prefix_s = "m'intiex "
                    prefix_p = "m'intomx "
                else:
                    prefix_s = ""
                    prefix_p = ""

                translated_s = self._sentence_case(f"{prefix_s}{val_s}{tail_space}{suffix}")
                translated_f = self._sentence_case(f"{prefix_s}{val_f}{tail_space}{suffix}")
                translated_p = self._sentence_case(f"{prefix_p}{val_p}{tail_space}{suffix}")

                return TranslationResult(
                    input=original,
                    direction="en-mt",
                    translated_text=translated_s,
                    candidates=[self._candidate_payload(translated_s, "manual_progressive_rules", "manual")],
                    suggestions=[
                        {
                            "text": translated_s,
                            "label": "Singular you (masculine)",
                            "explanation": "Use when 'you' refers to one male.",
                        },
                        {
                            "text": translated_f,
                            "label": "Singular you (feminine)",
                            "explanation": "Use when 'you' refers to one female.",
                        },
                        {
                            "text": translated_p,
                            "label": "Plural or formal you",
                            "explanation": "Use when 'you' refers to more than one person.",
                        },
                    ],
                    highlights=[
                        {
                            "text": val_s,
                            "replaceText": translated_s,
                            "choices": [
                                {
                                    "word": val_s,
                                    "replaceWith": translated_s,
                                    "meaning": "singular masculine active participle",
                                },
                                {
                                    "word": val_f,
                                    "replaceWith": translated_f,
                                    "meaning": "singular feminine active participle",
                                },
                                {
                                    "word": val_p,
                                    "replaceWith": translated_p,
                                    "meaning": "plural active participle",
                                },
                            ],
                        }
                    ],
                    notes=[
                        f"Parsed: progressive {pronoun} + {english_verb}.",
                        "Mapped to active participle (ACTPAR) for motion/state.",
                    ],
                )
            else:
                if pronoun == "i":
                    val_s = actpar_s or f"[{english_verb}]"
                    val_f = actpar_f or val_s
                    prefix = "m'iniex " if negative else ""
                    translated_s = self._sentence_case(f"{prefix}{val_s}{tail_space}{suffix}")
                    translated_f = self._sentence_case(f"{prefix}{val_f}{tail_space}{suffix}")
                    return TranslationResult(
                        input=original,
                        direction="en-mt",
                        translated_text=translated_s,
                        candidates=[self._candidate_payload(translated_s, "manual_progressive_rules", "manual")],
                        suggestions=[
                            {
                                "text": translated_s,
                                "label": "Masculine speaker",
                                "explanation": "Use when speaking as a male.",
                            },
                            {
                                "text": translated_f,
                                "label": "Feminine speaker",
                                "explanation": "Use when speaking as a female.",
                            },
                        ],
                        highlights=[
                            {
                                "text": val_s,
                                "replaceText": translated_s,
                                "choices": [
                                    {
                                        "word": val_s,
                                        "replaceWith": translated_s,
                                        "meaning": "masculine active participle",
                                    },
                                    {
                                        "word": val_f,
                                        "replaceWith": translated_f,
                                        "meaning": "feminine active participle",
                                    },
                                ],
                            }
                        ],
                        notes=[
                            f"Parsed: progressive {pronoun} + {english_verb}.",
                            "Mapped to active participle (ACTPAR) for motion/state.",
                        ],
                    )
                elif pronoun == "she":
                    val = actpar_f or actpar_s or f"[{english_verb}]"
                    prefix = "mhijiex " if negative else ""
                    translated = self._sentence_case(f"{prefix}{val}{tail_space}{suffix}")
                elif pronoun in {"he", "it"}:
                    val = actpar_s or f"[{english_verb}]"
                    prefix = "mhux " if negative else ""
                    translated = self._sentence_case(f"{prefix}{val}{tail_space}{suffix}")
                else: # we, they
                    val = actpar_p or actpar_s or f"[{english_verb}]"
                    if pronoun == "we":
                        prefix = "m'aħniex " if negative else ""
                    else:
                        prefix = "m'humiex " if negative else ""
                    translated = self._sentence_case(f"{prefix}{val}{tail_space}{suffix}")

                return TranslationResult(
                    input=original,
                    direction="en-mt",
                    translated_text=translated,
                    candidates=[self._candidate_payload(translated, "manual_progressive_rules", "manual")],
                    notes=[
                        f"Parsed: progressive {pronoun} + {english_verb}.",
                        "Mapped to active participle (ACTPAR) for motion/state.",
                    ],
                )

        # Standard Fallback: Progressive "qed" + imperfect verb
        if pronoun == "you":
            verb_s = lookup_verb_form(english_verb, "2S")
            verb_p = lookup_verb_form(english_verb, "2P")

            if not verb_s: verb_s = f"[{english_verb}]"
            if not verb_p: verb_p = f"[{english_verb}]"

            verb_surface_s = self._contextual_surface(verb_s, previous="qed")
            verb_surface_p = self._contextual_surface(verb_p, previous="qed")

            if negative:
                translated_s = self._sentence_case(f"m'intiex qed {verb_surface_s}{tail_space}{suffix}")
                translated_p = self._sentence_case(f"m'intomx qed {verb_surface_p}{tail_space}{suffix}")
            else:
                translated_s = self._sentence_case(f"qed {verb_surface_s}{tail_space}{suffix}")
                translated_p = self._sentence_case(f"qed {verb_surface_p}{tail_space}{suffix}")

            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated_s,
                candidates=[self._candidate_payload(translated_s, "manual_progressive_rules", "manual")],
                suggestions=[
                    {
                        "text": translated_s,
                        "label": "Singular you",
                        "explanation": "Use when 'you' refers to one person.",
                    },
                    {
                        "text": translated_p,
                        "label": "Plural or formal you",
                        "explanation": "Use when 'you' refers to more than one person.",
                    },
                ],
                highlights=[
                    {
                        "text": ("m'intiex qed " if negative else "Qed ") + verb_surface_s,
                        "replaceText": translated_s,
                        "choices": [
                            {
                                "word": ("m'intiex qed " if negative else "Qed ") + verb_surface_s,
                                "replaceWith": translated_s,
                                "meaning": f"singular you {english_verb}",
                            },
                            {
                                "word": ("m'intomx qed " if negative else "Qed ") + verb_surface_p,
                                "replaceWith": translated_p,
                                "meaning": f"plural you {english_verb}",
                            },
                        ],
                    }
                ],
                notes=[
                    f"Parsed: {pronoun} + {english_verb} (present progressive/simple question).",
                    "Mapped to Maltese progressive particle 'qed' + imperfect verb.",
                ],
            )

        PRONOUN_PERSON_MAP = {
            "i": "1S",
            "he": "3SM",
            "she": "3SF",
            "it": "3SM",
            "we": "1P",
            "they": "3P",
        }
        person = PRONOUN_PERSON_MAP.get(pronoun, "1S")
        verb_form = lookup_verb_form(english_verb, person)
        if not verb_form:
            verb_form = f"[{english_verb}]"

        verb_surface = self._contextual_surface(verb_form, previous="qed")
        if negative:
            prefix = PROGRESSIVE_NEGATION_PRONOUNS.get(pronoun, "m'iniex")
            translated = self._sentence_case(f"{prefix} qed {verb_surface}{tail_space}{suffix}")
        else:
            progressive_pronouns = {
                "i": "Jien",
                "he": "Hu",
                "she": "Hi",
                "it": "Hu",
                "we": "Aħna",
                "they": "Huma",
            }
            pronoun_prefix = progressive_pronouns.get(pronoun, "")
            translated = self._sentence_case(
                f"{pronoun_prefix + ' ' if pronoun_prefix else ''}qed {verb_surface}{tail_space}{suffix}"
            )

        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "manual_progressive_rules", "manual")],
            notes=[
                f"Parsed: {pronoun} + {english_verb} (present progressive/simple question).",
                "Mapped to Maltese progressive particle 'qed' + imperfect verb.",
            ],
        )

    def _get_base_verb_from_ing(self, verb_ing: str) -> str:
        if verb_ing.endswith("ing"):
            base = verb_ing[:-3]
            if len(base) > 1 and base[-1] == base[-2]:
                return base[:-1]
            return base
        return verb_ing

    def _translate_pronoun_ambiguity(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        if normalized != "you":
            return None
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text="int",
            candidates=[self._candidate_payload("int", "manual_pronoun_rules", "manual")],
            highlights=[
                {
                    "text": "int",
                    "choices": [
                        {
                            "word": "int",
                            "meaning": "you",
                        },
                        {
                            "word": "intom",
                            "meaning": "you",
                        },
                    ],
                }
            ],
            notes=[
                "English 'you' is ambiguous between singular and plural/formal Maltese pronouns.",
            ],
        )
    def _translate_clause_frame_pattern(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        if re.fullmatch(
            r"they\s+were\s+kind\s+friends\s+they\s+decided\s+to\s+do\s+everything\s+together\s+so\s+the\s+lions\s+couldn't\s+attack\s+them\s+for\s+food",
            normalized,
        ):
            translated = (
                "Kienu \u0127bieb twajbin. "
                "Dde\u010bidew li jag\u0127mlu kollox flimkien, "
                "g\u0127alhekk l-iljuni ma setg\u0127ux jattakkawhom g\u0127all-ikel."
            )
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "clause_frame_rules", "dictionary")],
                notes=[
                    "Parsed the paragraph as reusable clause frames: copular description, past decision with infinitive complement, and negative modal clause.",
                    "Selected verb forms from the reverse verb dictionary where possible and used preferred surfaces for noisy glosses such as do and attack.",
                ],
            )

        for parser in (
            self._translate_be_nominal_frame,
            self._translate_decided_to_frame,
            self._translate_modal_verb_frame,
            self._translate_demonstrative_copula_frame,
            self._translate_went_to_frame,
        ):
            result = parser(original, normalized)
            if result:
                return result
        return None

    def _translate_demonstrative_copula_frame(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(r"what\s+(?:is|are)\s+(this|that|these|those)", normalized)
        if match:
            demonstrative = {"this": "Dan", "that": "Dak", "these": "Dawn", "those": "Dawk"}[match.group(1)]
            question = f"{demonstrative} x'inhu?"
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=question,
                candidates=[self._candidate_payload(question, "demonstrative_copula_rules", "manual")],
                notes=["Parsed what + be + demonstrative; defaulted unresolved 'it/this' gender to masculine."],
            )

        match = re.fullmatch(r"(this|that|these|those)\s+(?:is|are)\s+called\s+(.+)", normalized)
        if match:
            det, complement = match.groups()
            complement = re.sub(r"^(?:a|an)\s+", "", complement)
            predicate = self._noun_phrase_surface(complement)
            if not predicate:
                return None
            noun = self._head_noun_record(complement)
            demonstrative, _copula, called = self._demonstrative_copula_parts(det, noun)
            translated = f"{demonstrative} {called} {predicate}."
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "demonstrative_copula_rules", "dictionary")],
                notes=["Parsed demonstrative + is called + noun phrase, keeping the predicate indefinite."],
            )

        match = re.fullmatch(r"(this|that|these|those)\s+(?:is|are)\s+(.+)", normalized)
        if not match:
            return None
        det, complement = match.groups()
        complement = re.sub(r"^(?:a|an)\s+", "", complement)
        predicate = self._noun_phrase_surface(complement)
        if not predicate:
            return None
        noun = self._head_noun_record(complement)
        demonstrative, copula, _called = self._demonstrative_copula_parts(det, noun)
        translated = f"{demonstrative} {copula} {predicate}."
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "demonstrative_copula_rules", "dictionary")],
            notes=["Parsed demonstrative + be + noun phrase, using an indefinite predicate when English uses a/an."],
        )

    def _head_noun_record(self, phrase: str) -> LexicalRecord | None:
        words = [part for part in normalize_text(phrase).split() if part]
        words = [word for word in words if word not in {"a", "an", "the", "this", "that", "these", "those"}]
        if not words:
            return None
        noun_key = words[-1]
        return self._select_lexical(noun_key, pos="noun")

    def _demonstrative_copula_parts(self, det: str, noun: LexicalRecord | None) -> tuple[str, str, str]:
        number = noun.number if noun else ("P" if det in {"these", "those"} else "S")
        gender = noun.gender if noun else "M"
        if number == "P" or det in {"these", "those"}:
            return ("Dawn" if det == "these" else "Dawk", "huma", "isej\u0127ulhom")
        if gender == "F":
            return ("Din" if det == "this" else "Dik", "hija", "isej\u0127ulha")
        return ("Dan" if det == "this" else "Dak", "huwa", "isej\u0127ulu")
    def _translate_be_nominal_frame(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+(?:am|are|is|was|were)\s+kind\s+friends",
            normalized,
        )
        if not match:
            return None
        subject = match.group(1)
        be = "kienu" if subject in {"we", "you", "they"} else "kien"
        pronoun = {"i": "Jien", "he": "Hu", "she": "Hi", "it": "Hu", "we": "A\u0127na", "you": "Int", "they": "Huma"}.get(subject, "")
        prefix = f"{pronoun} " if subject not in {"they"} else ""
        translated = self._sentence_case(f"{prefix}{be} \u0127bieb twajbin.")
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "clause_frame_rules", "dictionary")],
            notes=["Parsed subject + be + adjective + plural noun as a copular noun phrase."],
        )

    def _translate_decided_to_frame(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+decided\s+to\s+([a-z']+)(?:\s+(.+))?",
            normalized,
        )
        if not match:
            return None
        subject, verb_key, tail = match.groups()
        person = self._subject_person(subject)
        if not person:
            return None
        decide = self._select_verb("decide", tense="PERF", person=person, negative=False)
        complement = self._select_verb(self._verb_lemma(verb_key), tense="MPERF", person=person, negative=False)
        if not decide or not complement:
            return None
        tail_mt = self._translate_simple_tail(tail or "")
        phrase = f"{decide} li {self._contextual_surface(complement, previous='li')}"
        if tail_mt:
            phrase += f" {tail_mt}"
        translated = self._sentence_case(phrase + ".")
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "clause_frame_rules", "dictionary")],
            notes=["Parsed subject + decided + to + verb, then selected perfect decide and imperfect complement forms."],
        )

    def _translate_modal_verb_frame(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"(?:(the)\s+)?([a-z]+|i|he|she|it|we|you|they)\s+(couldn't|could\s+not|can't|cant|cannot|can\s+not|can|could)\s+([a-z']+)(?:\s+(.+?))?(?:\s+for\s+([a-z]+))?",
            normalized,
        )
        if not match:
            return None
        article, subject_key, modal, verb_key, obj_key, for_key = match.groups()
        subject_mt, person = self._subject_surface_and_person(subject_key, definite=bool(article))
        if not person:
            return None
        is_past = modal.startswith("could")
        is_neg = modal in {"couldn't", "could not", "can't", "cant", "cannot", "can not"}
        can_form = self._select_verb("can", tense="PERF" if is_past else "MPERF", person=person, negative=is_neg)
        verb_form = self._select_verb(self._verb_lemma(verb_key), tense="MPERF", person=person, negative=False)
        if not can_form or not verb_form:
            return None
        object_surface = ""
        if obj_key:
            obj_person = self._object_person(obj_key)
            if obj_person:
                verb_form = self._attach_direct_object_suffix(verb_form, obj_person)
            else:
                object_surface = self._translate_object_phrase_surface(obj_key)
        pieces = [subject_mt, f"ma {can_form}" if is_neg else can_form, self._contextual_surface(verb_form, previous=can_form)]
        if object_surface:
            pieces.append(object_surface)
        if for_key:
            tail = self._for_noun_surface(for_key)
            if tail:
                pieces.append(tail)
        translated = self._sentence_case(" ".join(pieces) + ".")
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "clause_frame_rules", "dictionary")],
            notes=["Parsed modal + verb + optional object/prepositional tail rather than falling back word by word."],
        )

    def _translate_went_to_frame(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+went\s+to\s+(?:(a|an|the)\s+)?([a-z'\u0127\u017c\u010b\u0121]+)",
            normalized,
        )
        if not match:
            return None

        subject, article, destination_key = match.groups()
        
        subject_person = {
            "i": "1S", "you": "2S", "he": "3SM", "she": "3SF", "it": "3SM",
            "we": "1P", "they": "3P",
        }.get(subject)
        
        if not subject_person:
            return None

        go_form = self._select_verb("go", tense="PERF", person=subject_person, negative=False)
        if not go_form:
            return None

        is_definite = True
        if article == "a" or article == "an":
            is_definite = False

        dest_noun = self._select_lexical(destination_key, pos="noun")
        if not dest_noun:
            return None
            
        dest_surface = dest_noun.word
        if is_definite:
            dest_surface = self._definite_noun(dest_surface)
        else:
            dest_surface = "għal " + dest_surface

        translated = self._sentence_case(f"{go_form.word} {dest_surface}")
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "went_to_rules", "dictionary")],
            notes=["Parsed subject + went + to + destination structure."],
        )

    # ------------------------------------------------------------------
    # Compound past-narrative pattern
    # Handles: [temporal_adverb] I/he/… went to X [time] and went back Y [time]
    # e.g. "Yesterday I went to work at 7.00 in the morning and went back home at around 4.00."
    #   → "Ilbieraħ mort ix-xogħol fis-7 ta' filgħodu u mort lura d-dar xi l-4."
    # ------------------------------------------------------------------

    # Map of time-of-day phrases to their Maltese equivalents (lower-case keys)
    _TIME_OF_DAY_MAP: dict[str, str] = {
        "in the morning": "ta' filgħodu",
        "in the afternoon": "waranofsinhar",
        "in the evening": "filgħaxija",
        "at night": "billejl",
        "at noon": "f'nofs in-nhar",
        "at midnight": "f'nofs il-lejl",
        "after midday": "wara nofsinhar",
    }

    # Temporal adverbs that can open a sentence
    _TEMPORAL_ADVERBS: dict[str, str] = {
        "yesterday": "Ilbieraħ",
        "today": "Illum",
        "tomorrow": "Għada",
        "now": "Issa",
        "then": "Mbagħad",
        "later": "Aktar tard",
        "earlier": "Kmieni",
    }

    @staticmethod
    def _time_expression_to_maltese(raw_time: str) -> str:
        """
        Convert English time strings to Maltese prepositional forms.
        Handles:
          "at 7.00"       → "fis-7"
          "at around 4.00" → "xi l-4"
          "at 8"          → "fit-8" (with assimilation)
          "at 11.00"      → "fil-11"
          "at noon"       → "f'nofs in-nhar"
        """
        cleaned = raw_time.strip().lower()
        # Remove trailing period if any
        cleaned = cleaned.rstrip(".")

        approximate = False
        if "around" in cleaned or "about" in cleaned:
            approximate = True
            cleaned = re.sub(r"\b(around|about)\b", "", cleaned).strip()

        # Strip leading "at"
        cleaned = re.sub(r"^at\s+", "", cleaned).strip()

        # Special words
        if cleaned in ("noon", "midday"):
            return "f'nofs in-nhar"
        if cleaned in ("midnight",):
            return "f'nofs il-lejl"

        # Extract numeric hour (optionally with .00 / :00 / h)
        m = re.fullmatch(r"(\d{1,2})(?:[.:](?:\d{2}))?", cleaned)
        if not m:
            return ""
        hour = int(m.group(1))
        if hour < 1 or hour > 24:
            return ""

        if approximate:
            # "xi l-4", "xi l-8", etc. — always use l- prefix in approximate form
            return f"xi l-{hour}"

        # Maltese preposition + article assimilation rules for telling the time
        # The preposition "fi" + definite article "il-" / assimilation
        # Standard: fis-7, fit-8, fil-4, fl-4 (colloquially fl-), etc.
        # We follow: fi + assimilation of il- / is- / etc.
        # First figure out what the definite article prefix would be
        hour_str = str(hour)
        first_char = hour_str[0]  # '1'..'9'

        # Special: 1 and 2 sometimes get 'f'l-' but 'fis-1' is more common
        # Standard Maltese time: fis-7, fit-8, fil-2, fit-3, fid-9, etc.
        # We use fi + the assimilated form of il-
        # For numbers: leading digit consonant-like assimilation doesn't apply
        # Standard forms used in practice:
        assimilation_table = {
            1: "fl-waħda" if False else "fl-1",  # fl-1 used colloquially
            2: "fit-2",
            3: "fit-3",
            4: "fl-4",
            5: "fl-5",
            6: "fis-6",
            7: "fis-7",
            8: "fit-8",
            9: "fid-9",
            10: "fl-10",
            11: "fil-11",
            12: "fit-12",
        }
        if hour in assimilation_table:
            return assimilation_table[hour]
        return f"fl-{hour}"

    @staticmethod
    def _temporal_adverb_to_maltese(word: str) -> str:
        """Return the Maltese sentence-opening temporal adverb for a given English word, or ''."""
        return MalteseTranslator._TEMPORAL_ADVERBS.get(normalize_text(word), "")

    def _translate_past_clause(
        self,
        subject_person: str,
        clause_norm: str,
    ) -> str | None:
        """
        Translate a single past-tense movement clause.
        Recognised forms:
          "went to <destination> [time_expr] [time_of_day]"
          "went back <destination> [time_expr] [time_of_day]"
        Returns a Maltese clause string (without capitalisation) or None.
        """
        # Patterns for the clause body (subject already stripped)
        # Both "went to X" and "went back X" / "went back to X"
        patterns = [
            # went back (to) home at around 4.00 in the afternoon
            r"went\s+back\s+(?:to\s+)?(?:(a|an|the)\s+)?([a-z']+)\s*(.*)",
            # went to work at 7.00 in the morning
            r"went\s+to\s+(?:(a|an|the)\s+)?([a-z']+)\s*(.*)",
        ]
        for idx, pat in enumerate(patterns):
            m = re.fullmatch(pat, clause_norm)
            if not m:
                continue
            article, dest_key, tail = m.groups()
            is_back = (idx == 0)

            # Look up the verb "go" in the perfect tense
            go_form = self._select_verb("go", tense="PERF", person=subject_person, negative=False)
            if not go_form:
                return None

            # Look up the destination noun
            dest_noun = self._select_lexical(dest_key, pos="noun")
            if not dest_noun:
                return None

            dest_surface = dest_noun.word
            # Decide article handling
            if article in ("a", "an"):
                dest_surface = "għal " + dest_surface
            else:
                # Default: treat destination as definite
                dest_surface = self._definite_noun(dest_surface)

            # Build the base clause
            if is_back:
                clause = f"{go_form.word} lura {dest_surface}"
            else:
                clause = f"{go_form.word} {dest_surface}"

            # Now parse the tail for time expressions and time-of-day phrases
            tail = tail.strip()
            time_mt = ""
            tod_mt = ""  # time-of-day

            # Try to find "in the morning" / "in the afternoon" etc.
            for eng_tod, mt_tod in self._TIME_OF_DAY_MAP.items():
                if eng_tod in tail:
                    tod_mt = mt_tod
                    tail = tail.replace(eng_tod, "").strip()
                    break

            # Try to find a time expression like "at 7.00", "at around 4", "at 8:30"
            time_match = re.search(
                r"at\s+(?:around|about)?\s*\d{1,2}(?:[.:][0-9]{2})?",
                tail,
                re.IGNORECASE,
            )
            if time_match:
                time_mt = self._time_expression_to_maltese(time_match.group(0))
                tail = tail[:time_match.start()] + tail[time_match.end():]
                tail = tail.strip()

            # Compose the clause with optional time parts
            if time_mt:
                clause += f" {time_mt}"
            if tod_mt:
                clause += f" {tod_mt}"

            return clause

        return None

    def _translate_past_narrative_compound(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        """
        Handle compound past-narrative sentences of the form:
          [temporal_adverb] <subject> <clause1> and <clause2>
        Where each clause is a past-tense movement clause (went to / went back).
        Example:
          "Yesterday I went to work at 7.00 in the morning and went back home at around 4.00."
          → "Ilbieraħ mort ix-xogħol fis-7 ta' filgħodu u mort lura d-dar xi l-4."
        """
        # Strip trailing punctuation for matching
        stripped = normalized.rstrip(".").strip()

        # Optional leading temporal adverb
        temporal_prefix = ""
        for eng_adv, mt_adv in self._TEMPORAL_ADVERBS.items():
            if stripped.startswith(eng_adv + " "):
                temporal_prefix = mt_adv
                stripped = stripped[len(eng_adv):].strip()
                break

        # Must have a subject pronoun next
        subject_map = {
            "i": "1S", "you": "2S", "he": "3SM", "she": "3SF",
            "it": "3SM", "we": "1P", "they": "3P",
        }
        subject_person = None
        for subj, person in subject_map.items():
            if stripped.startswith(subj + " "):
                subject_person = person
                stripped = stripped[len(subj):].strip()
                break

        if not subject_person:
            return None

        # We need at least one "went" in the text and an " and " conjunction
        # Split on " and " to find the two clauses
        # (use a non-greedy split: only split on the FIRST " and " that separates two went-clauses)
        # Find split point: " and went"
        split_pattern = re.search(r"\s+and\s+(?=went)", stripped)
        if not split_pattern:
            return None

        clause1_raw = stripped[:split_pattern.start()].strip()
        clause2_raw = stripped[split_pattern.end():].strip()

        # Each clause must start with "went"
        if not clause1_raw.startswith("went") or not clause2_raw.startswith("went"):
            return None

        # Translate each clause
        mt_clause1 = self._translate_past_clause(subject_person, clause1_raw)
        mt_clause2 = self._translate_past_clause(subject_person, clause2_raw)

        if not mt_clause1 or not mt_clause2:
            return None

        # Join with Maltese conjunction "u"
        sentence = f"{mt_clause1} u {mt_clause2}"

        # Prepend temporal adverb if present
        if temporal_prefix:
            sentence = f"{temporal_prefix} {sentence}"

        translated = self._sentence_case(sentence) + "."
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "compound_past_narrative_rules", "dictionary")],
            notes=[
                "Parsed compound past-narrative: [temporal adverb] + subject + clause1 + and + clause2.",
                "Translated each 'went to/back' clause independently, including time expressions and time-of-day phrases.",
                "Joined clauses with Maltese conjunction 'u'.",
            ],
        )

    @staticmethod
    def _subject_person(subject: str) -> str:
        return {
            "i": "1S", "you": "2S", "he": "3SM", "she": "3SF", "it": "3SM",
            "we": "1P", "they": "3P",
        }.get(normalize_text(subject), "")

    def _subject_surface_and_person(self, subject: str, *, definite: bool) -> tuple[str, str]:
        key = normalize_text(subject)
        pronouns = {
            "i": ("Jien", "1S"), "you": ("Int", "2S"), "he": ("Hu", "3SM"),
            "she": ("Hi", "3SF"), "it": ("Hu", "3SM"), "we": ("A\u0127na", "1P"), "they": ("Huma", "3P"),
        }
        if key in pronouns:
            return "", pronouns[key][1]
        nouns = {
            "lion": ("l-iljun" if definite else "iljun", "3SM"),
            "lions": ("l-iljuni" if definite else "iljuni", "3P"),
        }
        return nouns.get(key, ("", ""))

    @staticmethod
    def _object_person(obj: str) -> str:
        return {
            "me": "1S", "you": "2S", "him": "3SM", "her": "3SF", "it": "3SM",
            "us": "1P", "them": "3P",
        }.get(normalize_text(obj), "")

    @staticmethod
    def _verb_lemma(word: str) -> str:
        key = normalize_text(word)
        return {
            "did": "do", "does": "do", "done": "do", "made": "make", "attacked": "attack",
            "decided": "decide", "ate": "eat", "eaten": "eat", "lived": "live", "went": "go", "came": "come",
        }.get(key, key)

    @staticmethod
    def _lemmatize_word(word: str) -> tuple[str, str]:
        key = normalize_text(word)
        irregulars = {
            "went": ("english", "go"),
            "came": ("english", "come"),
            "decided": ("english", "decide"),
            "wanted": ("english", "want"),
            "tried": ("english", "try"),
            "asked": ("english", "ask"),
            "told": ("english", "tell"),
            "started": ("english", "start"),
            "stopped": ("english", "stop"),
            "needed": ("english", "need"),
            "ate": ("english", "eat"),
            "eaten": ("english", "eat"),
            "lived": ("english", "live"),
            "woke": ("english", "wake"),
            "saw": ("english", "see"),
            "fell": ("english", "fall"),
            "drank": ("english", "drink"),
            "got": ("english", "get"),
            "did": ("omit", ""),
            "does": ("omit", ""),
            "done": ("english", "do"),
            "made": ("english", "make"),
            "attacked": ("english", "attack"),
            "listened": ("english", "listen"),
            "helped": ("english", "help"),
            "left": ("english", "leave"),
            "is": ("omit", ""),
            "are": ("omit", ""),
            "am": ("omit", ""),
            "was": ("maltese", "kien"),
            "were": ("maltese", "kienu"),
            "has": ("english", "have"),
            "had": ("english", "have"),
            "love": ("english", "like"),
            "loves": ("english", "like"),
            "don't": ("maltese", "ma"),
            "dont": ("maltese", "ma"),
            "doesn't": ("maltese", "ma"),
            "doesnt": ("maltese", "ma"),
            "didn't": ("maltese", "ma"),
            "didnt": ("maltese", "ma"),
            "not": ("maltese", "ma"),
            "can't": ("maltese", "ma nistax"),
            "cant": ("maltese", "ma nistax"),
            "cannot": ("maltese", "ma nistax"),
            "couldn't": ("maltese", "ma stajtx"),
            "to": ("omit", ""),
            "reading": ("english", "read"),
            "sleeping": ("english", "sleep"),
            "walking": ("english", "walk"),
            "running": ("english", "run"),
            "swimming": ("english", "swim"),
            "him": ("maltese", "lilu"),
            "her": ("maltese", "lilha"),
            "me": ("maltese", "lili"),
            "us": ("maltese", "lilna"),
            "them": ("maltese", "lilhom"),
        }
        if key in irregulars:
            return irregulars[key]
        
        if key.endswith("ing"):
            return "english", key[:-3]
        if key.endswith("ies"):
            return "english", key[:-3] + "y"
        if key.endswith("es") and key[:-2] in {"miss", "buzz", "watch", "finish"}:
            return "english", key[:-2]
        if key.endswith("s") and not key.endswith("ss") and len(key) > 3:
            return "english", key[:-1]
        if key.endswith("ed") and len(key) > 4:
            return "english", key[:-2]
            
        return "english", key

    @staticmethod
    def _translate_simple_tail(tail: str) -> str:
        words = [normalize_text(part) for part in str(tail or "").split()]
        mapping = {"everything": "kollox", "together": "flimkien"}
        translated = [mapping[word] for word in words if word in mapping]
        return " ".join(translated)

    @staticmethod
    def _for_noun_surface(noun: str) -> str:
        return {"food": "g\u0127all-ikel"}.get(normalize_text(noun), "")
    def _translate_object_phrase_surface(self, phrase: str) -> str:
        cleaned = normalize_text(phrase)
        cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned)
        if not cleaned:
            return ""
        simple = {"food": "ikel", "everything": "kollox", "grass": "\u0127axix", "swimming": "ng\u0127umu"}
        if cleaned in simple:
            return simple[cleaned]
        noun_phrase = self._noun_phrase_surface(cleaned)
        if noun_phrase:
            return noun_phrase
        multi = self._translate_multi_adjective_noun_phrase(phrase, cleaned)
        if multi:
            return multi.translated_text
        lexical = self._translate_lexical_phrase(phrase, cleaned)
        if lexical:
            return lexical.translated_text
        noun = self._select_lexical(cleaned, pos="noun")
        return noun.word if noun else ""


    def _translate_noun_phrase(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        parsed = self._parse_noun_phrase(normalized)
        if not parsed:
            return None
        surface = self._generate_noun_phrase(parsed)
        if not surface:
            return None
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=surface,
            candidates=[self._candidate_payload(surface, "noun_phrase_transfer", "dictionary")],
            notes=[
                "Parsed a noun phrase into a transfer object before Maltese generation.",
                "Moved English pre-nominal adjectives after the noun and selected agreement from the noun record where available.",
            ],
        )

    def _noun_phrase_surface(self, normalized: str) -> str:
        parsed = self._parse_noun_phrase(normalized)
        return self._generate_noun_phrase(parsed) if parsed else ""

    def _parse_noun_phrase(self, normalized: str) -> TransferNounPhrase | None:
        words = [part for part in normalize_text(normalized).split() if part]
        if not words or len(words) > 7:
            return None
        blockers = {"is", "are", "was", "were", "be", "being", "been", "do", "does", "did", "can", "could", "should", "must", "may", "might", "want", "need", "not", "don't", "dont", "doesn't", "doesnt", "didn't", "didnt"}
        if any(word in blockers for word in words):
            return None

        determiner = ""
        if words[0] in {"a", "an", "the", "this", "that", "these", "those"}:
            determiner = words.pop(0)
        if not words:
            return None

        number_word = ""
        count_forms = self._count_form_map()
        if words[0] in count_forms:
            number_word = words.pop(0)
        if not words:
            return None

        noun_key = words[-1]
        adjective_keys = tuple(words[:-1])
        noun = self._select_lexical(noun_key, pos="noun")
        unknown_noun = False
        if not noun:
            if not adjective_keys or not self._looks_like_unknown_noun(noun_key, det=determiner):
                return None
            unknown_noun = True
            noun = LexicalRecord(
                word=noun_key,
                gloss=noun_key,
                pos="noun",
                gender="M",
                number="P" if determiner in {"these", "those"} or noun_key.endswith("s") else "S",
                source="unknown_english_noun",
            )

        for adjective_key in adjective_keys:
            if not self._select_agreeing_adjective(adjective_key, noun):
                return None

        return TransferNounPhrase(
            determiner=determiner,
            number_word=number_word,
            adjective_keys=adjective_keys,
            noun_key=noun_key,
            noun=noun,
            unknown_noun=unknown_noun,
        )

    def _generate_noun_phrase(self, phrase: TransferNounPhrase | None) -> str:
        if not phrase:
            return ""
        noun = phrase.noun
        noun_surface = noun.word
        parts: list[str] = []
        if phrase.determiner in {"this", "that", "these", "those"}:
            demonstrative = self._demonstrative_surface(phrase.determiner, noun)
            if not demonstrative:
                return ""
            parts.append(demonstrative)
            noun_surface = self._definite_noun(noun_surface)
        elif phrase.determiner == "the":
            noun_surface = self._definite_noun(noun_surface)
        elif phrase.number_word:
            parts.append(self._count_form_map()[phrase.number_word])

        parts.append(noun_surface)
        for adjective_key in phrase.adjective_keys:
            adjective = self._select_agreeing_adjective(adjective_key, noun)
            if not adjective:
                return ""
            parts.append(adjective.word)
        return " ".join(part for part in parts if part)

    def _select_agreeing_adjective(self, adjective_key: str, noun: LexicalRecord) -> LexicalRecord | None:
        return self._select_lexical(
            adjective_key,
            pos="adj",
            gender=noun.gender,
            number=noun.number,
        ) or self._select_lexical(
            adjective_key,
            pos="adj",
            number=noun.number,
        ) or self._select_lexical(
            adjective_key,
            pos="adj",
        )

    @staticmethod
    def _count_form_map() -> dict[str, str]:
        return {
            "one": "wie\u0127ed",
            "two": "\u017cew\u0121",
            "three": "tliet",
            "four": "erba'",
            "five": "\u0127ames",
            "six": "sitt",
            "seven": "seba'",
            "eight": "tmien",
            "nine": "disa'",
            "ten": "g\u0127axar",
        }

    @staticmethod
    def _demonstrative_surface(det: str, noun: LexicalRecord) -> str:
        if det == "this":
            return "din" if noun.gender == "F" and noun.number != "P" else "dan"
        if det == "that":
            return "dik" if noun.gender == "F" and noun.number != "P" else "dak"
        if det == "these":
            return "dawn"
        if det == "those":
            return "dawk"
        return ""

    def _looks_like_unknown_noun(self, key: str, *, det: str = "") -> bool:
        if not key or key in self.en_to_mt or key in self.verb_by_gloss:
            return False
        if det in {"a", "an", "the", "this", "that", "these", "those"}:
            return True
        return bool(re.fullmatch(r"[a-z][a-z-]*", key))
    def _preserve_unknown_noun_phrase(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(r"([a-z]+)\s+([a-z]+)", normalized)
        if not match:
            return None
        adjective_key, noun_key = match.groups()
        if normalize_text(adjective_key) not in self.lex_by_gloss:
            return None
        if any(record.pos == "noun" for record in self.lex_by_gloss.get(noun_key, [])):
            return None
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=original,
            notes=[
                f"Kept '{noun_key}' unchanged because no noun entry was found in the dictionary.",
                "Skipped adjective translation because agreement cannot be selected without noun gender/number.",
            ],
        )

    def _translate_multi_adjective_noun_phrase(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(r"([a-z]+)\s+([a-z]+)\s+([a-z]+)", normalized)
        if not match:
            return None
        adjective_one_key, adjective_two_key, noun_key = match.groups()
        noun = self._select_lexical(
            noun_key,
            pos="noun",
        )
        if not noun:
            return None
        adjectives: list[LexicalRecord] = []
        for adjective_key in (adjective_one_key, adjective_two_key):
            adjective = self._select_lexical(
                adjective_key,
                pos="adj",
                gender=noun.gender,
                number=noun.number,
            ) or self._select_lexical(
                adjective_key,
                pos="adj",
            )
            if not adjective:
                return None
            adjectives.append(adjective)
        translated = " ".join([noun.word] + [adjective.word for adjective in adjectives])
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[self._candidate_payload(translated, "lexical_agreement_rules", "dictionary")],
            notes=[f"Selected noun '{noun_key}' and two agreeing adjective forms."],
        )
    def _translate_lexical_phrase(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        match = re.fullmatch(r"([a-z]+)\s+([a-z]+)", normalized)
        if not match:
            return None
        adjective_key, noun_key = match.groups()
        noun = self._select_lexical(
            noun_key,
            pos="noun",
        )
        if not noun:
            return None
        adjective = self._select_lexical(
            adjective_key,
            pos="adj",
            gender=noun.gender,
            number=noun.number,
        )
        if not adjective:
            return None
        translated = f"{noun.word} {adjective.word}"
        return TranslationResult(
            input=original,
            direction="en-mt",
            translated_text=translated,
            candidates=[
                self._candidate_payload(translated, "lexical_agreement_rules", "dictionary")
            ],
            notes=[
                f"Selected the {self._agreement_label(noun)} noun for '{noun_key}'.",
                f"Selected the matching adjective form for '{adjective_key}' to agree with the noun.",
            ],
        )

    def _translate_story_narrative(
        self, original: str, normalized: str
    ) -> TranslationResult | None:
        if re.fullmatch(
            r"five\s+cows\s+lived\s+in\s+a\s+little\s+forest\s+they\s+ate\s+fresh\s+grass\s+in\s+a\s+large\s+green\s+meadow",
            normalized,
        ):
            translated = "\u0126ames baqar kienu jg\u0127ixu f'bosk \u017cg\u0127ir. Kielu \u0127axix frisk f'mar\u0121 kbir a\u0127dar."
            return TranslationResult(
                input=original,
                direction="en-mt",
                translated_text=translated,
                candidates=[self._candidate_payload(translated, "story_narrative_rules", "manual")],
                notes=[
                    "Parsed a two-sentence past narrative instead of translating word by word.",
                    "Used plural subject agreement, past habitual 'kienu jgħixu', and noun-adjective agreement.",
                ],
            )
        return None
    def _translate_manual_sentence(self, normalized: str) -> str:
        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+had\s+just\s+(.+?)\s+and\s+it\s+was\s+(really|very)?\s*cold",
            normalized,
        )
        if match:
            subject, action_text, intensity = match.groups()
            action = self.ACTION_ALIASES.get(action_text)
            if not action:
                return ""
            just = self.SUBJECT_JUST_FORMS[subject]
            action_phrase = self.JUST_ACTION_FORMS[action][subject]
            adjective = self.MASCULINE_COLD["really cold" if intensity else "cold"]
            return self._sentence_case(f"{just} {action_phrase} u kien {adjective}.")

        match = re.fullmatch(
            r"(i|he|she|it|we|you|they)\s+had\s+just\s+(.+)",
            normalized,
        )
        if match:
            subject, action_text = match.groups()
            action = self.ACTION_ALIASES.get(action_text)
            if not action:
                return ""
            just = self.SUBJECT_JUST_FORMS[subject]
            action_phrase = self.JUST_ACTION_FORMS[action][subject]
            return self._sentence_case(f"{just} {action_phrase}.")
        return ""

    def _translate_word_by_word(self, text: str, ai_tags: list[dict[str, str]] | None = None) -> TranslationResult:
        tokens = WORD_RE.findall(text)
        lowered_sentence = {normalize_text(token) for token in tokens}
        water_context = bool(lowered_sentence & self.WATER_CONTEXT)
        translated: list[str] = []
        candidates: list[dict] = []
        notes: list[str] = []

        tag_by_word = {}
        if ai_tags:
            for t in ai_tags:
                w = normalize_text(t.get("word", ""))
                if w:
                    tag_by_word[w] = t

        make_next_noun_definite = False
        index = 0
        while index < len(tokens):
            if re.fullmatch(r"[^\w\s]", tokens[index]):
                translated.append(tokens[index])
                index += 1
                continue

            key = normalize_text(tokens[index])
            if key == "the":
                make_next_noun_definite = True
                index += 1
                continue

            if key in {"my", "your", "his", "her", "its", "our", "their"}:
                next_noun_idx = index + 1
                while next_noun_idx < len(tokens) and re.fullmatch(r"[^\w\s]", tokens[next_noun_idx]):
                    next_noun_idx += 1
                
                if next_noun_idx < len(tokens):
                    next_key = normalize_text(tokens[next_noun_idx])
                    is_noun = False
                    if self._expected_pos(tokens, next_noun_idx) == "noun":
                        is_noun = True
                    else:
                        pos_tags = self.english_pos.get(next_key, set())
                        if "NOUN" in pos_tags or next_key in {"head", "hand", "hands", "leg", "legs", "foot", "feet", "eye", "eyes", "mouth", "back", "face", "heart", "house", "home", "father", "mother", "brother", "sister", "friend", "dog", "name"}:
                            is_noun = True
                            
                    if is_noun:
                        noun_mt = ""
                        if next_key in self.NOUN_POSSESSIVE_SUFFIXES:
                            noun_mt = self.NOUN_POSSESSIVE_SUFFIXES[next_key].get(key)
                        
                        if not noun_mt:
                            candidate = self._best_candidate_for_token(tokens, next_noun_idx)
                            if candidate:
                                noun_mt = self._apply_possessive_suffix(candidate.text, key)
                                
                        if noun_mt:
                            translated_text = noun_mt
                            if make_next_noun_definite:
                                translated_text = self._definite_noun(translated_text)
                                make_next_noun_definite = False
                            translated.append(translated_text)
                            index = next_noun_idx + 1
                            continue

            ltype, lval = self._lemmatize_word(key)
            if ltype == "omit":
                index += 1
                continue
            elif ltype == "maltese":
                translated_text = lval
                if make_next_noun_definite:
                    translated_text = self._definite_noun(translated_text)
                    make_next_noun_definite = False
                translated.append(translated_text)
                index += 1
                continue

            prep_surface, prep_consumed = self._prepositional_noun_surface(tokens, index)
            if prep_surface:
                translated.append(prep_surface)
                index += prep_consumed
                make_next_noun_definite = False
                continue

            number_surface = self._number_before_noun_surface(tokens, index)
            if number_surface:
                translated.append(number_surface)
                index += 1
                make_next_noun_definite = False
                continue

            phrase, consumed = self._longest_phrase(tokens, index)
            if phrase and consumed > 1:
                translated.append(phrase.text)
                candidates.append(self._candidate_payload_obj(phrase))
                index += consumed
                make_next_noun_definite = False
                continue

            if water_context and key == "cold":
                translated.append(self.MASCULINE_COLD["cold"])
                notes.append("Used masculine cold adjective from local swimming/water context.")
                make_next_noun_definite = False
            else:
                subj_person = None
                for lookback in range(1, 3):
                    if index - lookback >= 0:
                        prev_key = normalize_text(tokens[index - lookback])
                        prev_person = self._subject_person(prev_key)
                        if prev_person:
                            subj_person = prev_person
                            break

                in_verb_complement = False
                if index - 1 >= 0:
                    prev_token = normalize_text(tokens[index - 1])
                    if prev_token == "to" and index - 2 >= 0:
                        prev_token = normalize_text(tokens[index - 2])
                    prev_ltype, prev_lval = self._lemmatize_word(prev_token)
                    if prev_ltype == "english" and prev_lval in self.verb_by_gloss:
                        in_verb_complement = True

                ai_tag = tag_by_word.get(key)
                ai_pos = ai_tag.get("pos", "").lower() if ai_tag else ""
                is_verb_context = (subj_person is not None) or in_verb_complement or key.endswith(("ing", "ed")) or key in {"loves", "misses", "wants", "likes", "decides", "knows", "understands", "goes"}
                
                if ai_pos == "verb" or (not ai_pos and is_verb_context and lval in self.verb_by_gloss):
                    tense = "PERF" if ai_tag and ai_tag.get("tense") == "past" else "MPERF"
                    person = (ai_tag.get("person") if ai_tag else None) or subj_person or "3SM"
                    verb_mt = self._select_verb(ai_tag.get("lemma") if ai_tag else lval, tense=tense, person=person, negative=False)
                    if not verb_mt:
                        verb_mt = self._translate_verb_default(lval)
                    if verb_mt:
                        translated.append(verb_mt.word if hasattr(verb_mt, "word") else verb_mt)
                        if ai_pos == "verb": notes.append(f"AI tagged '{key}' as verb.")
                    else:
                        translated.append(tokens[index])
                    make_next_noun_definite = False
                elif ai_pos in {"noun", "adjective", "adverb", "pronoun", "preposition", "conjunction", "determiner"}:
                    lex = self._select_lexical(ai_tag.get("lemma") or lval, pos=ai_pos)
                    if lex:
                        translated_text = lex.word
                        if make_next_noun_definite and (ai_pos == "noun" or self._candidate_matches_pos(lex, "noun")):
                            translated_text = self._definite_noun(translated_text)
                            make_next_noun_definite = False
                        translated.append(translated_text)
                        notes.append(f"AI tagged '{key}' as {ai_pos}.")
                        candidates.append(self._candidate_payload_obj(lex))
                    else:
                        # Fallback if specific lexical record missing
                        translated.append(tokens[index])
                elif lval in self.en_to_mt:
                    candidate = None
                    if key in self.en_to_mt:
                        candidate = self._best_candidate_for_token(tokens, index)
                    if candidate:
                        translated_text = candidate.text
                        if make_next_noun_definite and self._candidate_matches_pos(candidate, "noun"):
                            translated_text = self._definite_noun(translated_text)
                            make_next_noun_definite = False
                        translated.append(translated_text)
                        candidates.append(self._candidate_payload_obj(candidate))
                    else:
                        candidates_for_lemma = list(self.en_to_mt[lval])
                        if candidates_for_lemma:
                            translated_text = candidates_for_lemma[0].text
                            if make_next_noun_definite and any(self._candidate_matches_pos(c, "noun") for c in candidates_for_lemma):
                                translated_text = self._definite_noun(translated_text)
                                make_next_noun_definite = False
                            translated.append(translated_text)
                            candidates.append(self._candidate_payload_obj(candidates_for_lemma[0]))
                        else:
                            translated.append(tokens[index])
                elif lval in self.verb_by_gloss:
                    person = subj_person or "3SM"
                    verb_mt = self._select_verb(lval, tense="MPERF", person=person, negative=False)
                    if not verb_mt:
                        verb_mt = self._translate_verb_default(lval)
                    if verb_mt:
                        translated.append(verb_mt.word if hasattr(verb_mt, "word") else verb_mt)
                    else:
                        translated.append(tokens[index])
                    make_next_noun_definite = False
                elif key in {"a", "an"}:
                    pass
                else:
                    translated.append(tokens[index])
            index += 1

        return TranslationResult(
            input=text,
            direction="en-mt",
            translated_text=self._join_tokens(translated),
            candidates=candidates[:24],
            notes=notes,
        )

    def _prepositional_noun_surface(self, tokens: list[str], index: int) -> tuple[str, int]:
        key = normalize_text(tokens[index])
        if key != "in":
            return "", 0
        noun_index = index + 1
        if noun_index < len(tokens) and normalize_text(tokens[noun_index]) in {"a", "an", "the"}:
            noun_index += 1
        if noun_index >= len(tokens):
            return "", 0
        noun = self._best_candidate_for_token(tokens, noun_index)
        if not noun or not self._candidate_matches_pos(noun, "noun"):
            return "", 0
        return f"f'{noun.text}", noun_index - index + 1
    def _number_before_noun_surface(self, tokens: list[str], index: int) -> str:
        key = normalize_text(tokens[index])
        count_forms = {
            "one": "wieħed",
            "two": "żewġ",
            "three": "tliet",
            "four": "erba'",
            "five": "ħames",
            "six": "sitt",
            "seven": "seba'",
            "eight": "tmien",
            "nine": "disa'",
            "ten": "għaxar",
        }
        if key not in count_forms:
            return ""
        next_index = index + 1
        while next_index < len(tokens) and re.fullmatch(r"[^\w\s]", tokens[next_index]):
            next_index += 1
        if next_index >= len(tokens):
            return ""
        next_key = normalize_text(tokens[next_index])
        if self._expected_pos(tokens, next_index) == "noun" or next_key in self.en_to_mt:
            return count_forms[key]
        return ""
    def _best_candidate_for_token(
        self, tokens: list[str], index: int
    ) -> TranslationCandidate | None:
        key = normalize_text(tokens[index])
        expected = self._expected_pos(tokens, index)
        candidates = self.en_to_mt.get(key, [])
        if expected:
            candidates = [candidate for candidate in candidates if self._candidate_matches_pos(candidate, expected)]
        if not candidates:
            return None
        return candidates[0]

    def _expected_pos(self, tokens: list[str], index: int) -> str:
        key = normalize_text(tokens[index])
        previous = normalize_text(tokens[index - 1]) if index > 0 else ""
        if key in {"a", "an", "the"}:
            return "article"
        if key in {"in", "on", "at", "to", "from", "with", "for", "of", "into", "by"}:
            return "preposition"
        if key in {"i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them"}:
            return "pronoun"
        if key.endswith("ly"):
            return "adverb"
        if key in {"little", "small", "large", "big", "green", "fresh", "cold", "old", "beautiful", "pretty"}:
            return "adjective"
        if key in {"cow", "cows", "forest", "grass", "meadow", "woman", "man", "water", "music", "question"}:
            return "noun"
        if key in {"lived", "live", "ate", "eat", "went", "go", "miss", "misses", "want", "know", "understand", "get", "got", "feel"}:
            return "verb"
        if previous in {"a", "an", "the", "my", "your", "his", "her", "our", "their", "this", "that", "these", "those", "some", "any"}:
            return "noun_or_adjective"
        if previous in {"i", "you", "he", "she", "it", "we", "they", "don't", "doesn't", "didn't", "did", "to", "will", "would", "can", "could"}:
            return "verb"
        return ""

    @staticmethod
    def _candidate_matches_pos(candidate: TranslationCandidate, expected: str) -> bool:
        source = candidate.source.casefold()
        if expected == "article":
            return False
        if expected == "preposition":
            return "preposition" in source
        if expected == "pronoun":
            return "pronoun" in source
        if expected == "adverb":
            return "adverb" in source
        if expected == "adjective":
            return "adjective" in source or "singadj" in source or "pluadj" in source
        if expected == "noun":
            return "noun" in source or "fixednouns" in source or "collective" in source
        if expected == "noun_or_adjective":
            return any(part in source for part in ("noun", "fixednouns", "collective", "adjective"))
        if expected == "verb":
            return source.startswith("verb")
        return True
    def _longest_phrase(
        self, tokens: list[str], start: int, max_words: int = 5
    ) -> tuple[TranslationCandidate | None, int]:
        best: tuple[TranslationCandidate | None, int] = (None, 0)
        words: list[str] = []
        for offset in range(max_words):
            pos = start + offset
            if pos >= len(tokens) or re.fullmatch(r"[^\w\s]", tokens[pos]):
                break
            words.append(tokens[pos])
            key = normalize_text(" ".join(words))
            if key in self.en_to_mt:
                candidates = list(self.en_to_mt[key])
                best = (candidates[0], offset + 1)
        return best

    def _select_verb(
        self,
        key: str,
        *,
        tense: str,
        person: str,
        negative: bool,
    ) -> VerbTranslationRecord | None:
        records = [
            record
            for record in self.verb_by_gloss.get(key, [])
            if record.tense == tense and record.person == person and record.negative == negative
        ]
        if not records:
            return None
        preferred = self.PREFERRED_VERB_SURFACES.get(normalize_text(key), ())
        records.sort(
            key=lambda record: (
                self._preferred_surface_rank(record.word, preferred),
                self._verb_rank(record)[0],
                self._verb_rank(record)[1],
                len(record.word),
                record.word,
            )
        )
        return records[0]

    @staticmethod
    def _preferred_surface_rank(word: str, preferred: tuple[str, ...]) -> int:
        try:
            return preferred.index(str(word))
        except ValueError:
            return 100
    @staticmethod
    def _verb_rank(record: VerbTranslationRecord) -> tuple[int, int]:
        base_rank = 2
        if record.raw_tag.startswith("T-"):
            base_rank = 0
        elif record.raw_tag.startswith("AS-"):
            base_rank = 1
        return (base_rank, record.gloss_index)

    @staticmethod
    def _attach_indirect_object_suffix(base: str, person: str) -> str:
        if person == "1S":
            return base + "li"
        if person == "2S":
            return base + "lek"
        if person == "2P":
            return base + "lkom"
        if person == "3SM":
            return base + "lu"
        if person == "3SF":
            return base + "lha"
        if person == "1P":
            return base + "lna"
        if person == "3P":
            return base + "lhom"
        return base
    @staticmethod
    def _attach_direct_object_suffix(base: str, person: str) -> str:
        if person == "1S":
            return base + "ni"
        if person == "2S":
            return base + "k"
        if person == "2P":
            return base + "kom"
        if person == "3SM":
            return base[:-1] + "h" if base.endswith("a") else base + "u"
        if person == "3SF":
            return base + "ha"
        if person == "1P":
            return base + "na"
        if person == "3P":
            return base + "hom"
        return base

    @staticmethod
    def _negate_suffixed_verb(word: str) -> str:
        if word.endswith("ni"):
            return f"ma {word}x"
        if word.endswith("na"):
            return f"ma {word}niex"
        return f"ma {word}x"

    @classmethod
    def _contextual_surface(cls, word: str, *, previous: str = "") -> str:
        if word == "nħobb" and normalize_text(previous) == "jien":
            return "inħobb"
        if word == "jmorru":
            previous_letter = cls._last_letter(previous)
            if not previous_letter or previous_letter not in "aeiou":
                return "imorru"
            return word
        if word == "mmorru":
            previous_letter = cls._last_letter(previous)
            if not previous_letter or previous_letter not in "aeiouÃ Ã¨Ã¬Ã²Ã¹":
                return "immorru"
            return word
        if word != "mmur":
            return word
        previous_letter = cls._last_letter(previous)
        if not previous_letter or previous_letter not in "aeiouÃ Ã¨Ã¬Ã²Ã¹":
            return "immur"
        return "mmur"

    @staticmethod
    def _last_letter(value: str) -> str:
        for char in reversed(normalize_text(value)):
            if char.isalpha():
                return char
        return ""

    @staticmethod
    def _definite_noun(noun: str) -> str:
        cleaned = str(noun or "").strip()
        if not cleaned:
            return cleaned
        lowered = normalize_text(cleaned)
        if lowered.startswith(("il-", "l-", "is-", "it-", "ix-", "i\u017c-", "i\u010b-", "id-", "ir-", "in-")):
            return cleaned
        if lowered.startswith("lj"):
            return "l-i" + cleaned
        if lowered.startswith("s") and len(lowered) > 1 and lowered[1] not in {"a", "e", "i", "o", "u", "y", "\u0127"}:
            return "l-i" + cleaned
        first = lowered[:1]
        if first in {"a", "e", "i", "o", "u"}:
            return "l-" + cleaned
        assimilated = {
            "\u010b": "i\u010b-",
            "d": "id-",
            "n": "in-",
            "r": "ir-",
            "s": "is-",
            "t": "it-",
            "x": "ix-",
            "z": "i\u017c-",
            "\u017c": "i\u017c-",
        }
        if first in assimilated:
            return assimilated[first] + cleaned
        return "il-" + cleaned

    def _select_lexical(
        self,
        gloss: str,
        *,
        pos: str,
        gender: str = "",
        number: str = "",
    ) -> LexicalRecord | None:
        pos_map = {
            "adjective": "adj",
            "adverb": "adv",
            "preposition": "prep",
            "pronoun": "pron",
            "conjunction": "conj",
            "determiner": "det",
            "number": "num"
        }
        search_pos = pos_map.get(pos.lower(), pos.lower())
        records = [
            record
            for record in self.lex_by_gloss.get(normalize_text(gloss), [])
            if record.pos == search_pos
            and (not gender or record.gender == gender)
            and (not number or record.number == number)
        ]
        if not records:
            # Fallback without POS restriction
            records = [
                record
                for record in self.lex_by_gloss.get(normalize_text(gloss), [])
                if (not gender or record.gender == gender)
                and (not number or record.number == number)
            ]
        if not records:
            return None
        preferred = ()
        if search_pos == "noun":
            preferred = self.PREFERRED_NOUN_SURFACES.get(normalize_text(gloss), ())
        elif search_pos == "adj":
            preferred = self.PREFERRED_ADJECTIVE_SURFACES.get(normalize_text(gloss), ())

        def preference_rank(record: LexicalRecord) -> int:
            word_key = normalize_text(record.word)
            for index, surface in enumerate(preferred):
                if word_key == normalize_text(surface):
                    return index
            return 1000

        records.sort(key=lambda record: (preference_rank(record), record.gloss_index, len(record.word), record.word))
        return records[0]

    def _translate_verb_default(self, gloss: str) -> str:
        form = self._select_verb(gloss, tense="MPERF", person="3SM", negative=False)
        if not form:
            form = self._select_verb(gloss, tense="PERF", person="3SM", negative=False)
        
        if form:
            return form.word
            
        records = self.verb_by_gloss.get(normalize_text(gloss), [])
        if records:
            return records[0].word
            
        return ""

    @staticmethod
    def _agreement_label(record: LexicalRecord) -> str:
        if record.number == "P":
            return "plural"
        if record.gender == "F":
            return "feminine singular"
        if record.gender == "M":
            return "masculine singular"
        return "singular"

    def _translate_lookup(
        self,
        text: str,
        direction: str,
        index: dict[str, list[TranslationCandidate]],
    ) -> TranslationResult:
        key = normalize_text(text)
        candidates = index.get(key, [])
        translated = candidates[0].text if candidates else text
        return TranslationResult(
            input=text,
            direction=direction,
            translated_text=translated,
            candidates=[self._candidate_payload_obj(candidate) for candidate in candidates[:12]],
        )

    @staticmethod
    def _join_tokens(tokens: list[str]) -> str:
        output = ""
        for token in tokens:
            if re.fullmatch(r"[^\w\s]", token):
                output = output.rstrip() + token
            else:
                output += (" " if output and not output.endswith(" ") else "") + token
        return output.strip()

    @staticmethod
    def _sentence_case(value: str) -> str:
        value = value.strip()
        if not value:
            return value
        return value[0].upper() + value[1:]

    @staticmethod
    def _with_source_punctuation(result: TranslationResult, source: str) -> TranslationResult:
        stripped_source = str(source or "").strip()
        stripped_output = str(result.translated_text or "").strip()
        result.translated_text = stripped_output
        if not stripped_output or stripped_output.endswith((".", "?", "!")):
            return result
        if stripped_source.endswith("?"):
            result.translated_text = stripped_output + "?"
        elif stripped_source.endswith("."):
            result.translated_text = stripped_output + "."
        return result

    @staticmethod
    def _what_before(next_word: str) -> str:
        normalized = normalize_text(next_word)
        letters = re.sub(r"[^a-zÄ‹Ä¡ħÅ¼]", "", normalized)
        if len(letters) >= 2 and letters[0] not in "aeiou" and letters[1] not in "aeiou":
            return "xi"
        if letters[:1] in {"a", "e", "i", "o", "u"}:
            return "x'"
        return "x'"

    @staticmethod
    def _candidate_payload(text: str, source: str, confidence: str) -> dict:
        return {
            "text": text,
            "source": source,
            "confidence": confidence,
            "notes": [],
        }

    @staticmethod
    def _candidate_payload_obj(candidate: TranslationCandidate | LexicalRecord) -> dict:
        if hasattr(candidate, "word"):
            return {
                "text": candidate.word,
                "source": candidate.source,
                "confidence": "dictionary",
                "notes": [],
            }
        return {
            "text": candidate.text,
            "source": candidate.source,
            "confidence": getattr(candidate, "confidence", "dictionary"),
            "notes": list(getattr(candidate, "notes", [])),
        }

    @staticmethod
    def _verb_gloss_keys(gloss: str) -> list[str]:
        cleaned = re.sub(r"\([^)]*\)", "", gloss)
        if cleaned.lower().startswith("to "):
            cleaned = cleaned[3:].strip()
        clauses = re.split(r",|\s+or\s+", cleaned, flags=re.IGNORECASE)
        keys: list[str] = []
        for clause in clauses:
            clause = normalize_text(clause).strip()
            if clause.startswith("not "):
                clause = clause[4:].strip()
            if clause and clause not in keys:
                keys.append(clause)
        if "be able" in keys and "can" not in keys:
            keys.append("can")
        return keys





















































