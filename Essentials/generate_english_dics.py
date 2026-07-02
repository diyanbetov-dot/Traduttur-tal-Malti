import os
import re
import unicodedata
from pathlib import Path

# Paths
ESSENTIALS_DIR = Path(__file__).parent
FINALDICS_DIR = ESSENTIALS_DIR / "finaldics"
ENGLISH_DICS_DIR = ESSENTIALS_DIR / "english_dics"
ENGLISH_DICS_DIR.mkdir(exist_ok=True)

def normalize_word(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value or "")).casefold()
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = re.sub(r"[^a-z0-9'\s-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def split_glosses(value: str) -> list[str]:
    cleaned = re.sub(r"\([^)]*\)", "", str(value or ""))
    parts = re.split(r"\s*(?:,|;|\bor\b|/)\s*", cleaned, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]

def clean_verb_gloss(gloss: str) -> str:
    gloss = gloss.strip()
    if gloss.lower().startswith("to "):
        gloss = gloss[3:].strip()
    return gloss

def main():
    nouns = set()
    verbs = set()
    adjectives = set()
    adverbs = set()
    prepositions = set()
    pronouns = set()
    numbers = set()
    phrases = set()

    # Add hardcoded common phrasal verbs
    phrasal_verbs = {
        "wake up", "woke up", "wakes up", "waking up", "woken up",
        "feel like", "feels like", "felt like", "feeling like",
        "go back", "goes back", "went back", "going back", "gone back",
        "look for", "looks for", "looked for", "looking for",
        "give up", "gives up", "gave up", "giving up", "given up",
        "run out", "runs out", "ran out", "running out",
        "get up", "gets up", "got up", "getting up",
        "fall down", "falls down", "fell down", "falling down", "fallen down",
        "at all", "at around", "in the morning", "in the afternoon", "in the evening",
        "yesterday morning", "tomorrow morning", "last night"
    }
    for p in phrasal_verbs:
        phrases.add(normalize_word(p))

    # Seed pronouns/determiners
    for p in ["i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their", "this", "that", "these", "those", "some", "any", "every", "each", "no"]:
        pronouns.add(normalize_word(p))

    # Seed prepositions
    for prep in ["in", "on", "at", "to", "from", "with", "by", "for", "of", "about", "into", "through", "over", "under", "while", "as"]:
        prepositions.add(normalize_word(prep))

    # Parse Maltese dictionaries to build English entries
    # Standard dic files
    for path in sorted(FINALDICS_DIR.glob("*.dic")):
        if path.name == "places.dic" or path.name.startswith("verbmt_"):
            continue
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except FileNotFoundError:
            continue
        
        for line in lines:
            if not line or "/" not in line:
                continue
            parts = line.split("/", 1)
            if len(parts) < 2:
                continue
            payload = parts[1]
            if "-" not in payload:
                continue
            tag_part, meaning = payload.split("-", 1)
            tag_part = tag_part.upper()

            glosses = split_glosses(meaning)
            for gloss in glosses:
                norm = normalize_word(gloss)
                if not norm:
                    continue

                if "SINGNOUN" in tag_part or "PLUNOUN" in tag_part or "COLLNOUN" in tag_part:
                    nouns.add(norm)
                elif "SINGADJ" in tag_part or "PLUADJ" in tag_part:
                    adjectives.add(norm)
                elif "ADVERB" in tag_part:
                    adverbs.add(norm)
                elif "PRON" in tag_part:
                    pronouns.add(norm)
                elif "PREP" in tag_part:
                    prepositions.add(norm)
                elif "CARDNUM" in tag_part or "ORDNUM" in tag_part:
                    numbers.add(norm)
                elif "ATTNUM" in tag_part:
                    numbers.add(norm)

    # Parse Verb Dictionaries
    verb_paths = list(FINALDICS_DIR.glob("verbmt_*.dic")) + [FINALDICS_DIR / "dev_extra.dic"]
    for path in verb_paths:
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except FileNotFoundError:
            continue
        for line in lines:
            if not line or "/" not in line:
                continue
            parts = line.split("/", 1)
            if len(parts) < 2:
                continue
            payload = parts[1]
            # Format: T-ksr-PERF-3SM-to break
            # Find the meaning after the last dash
            meaning_match = re.search(r'-([^-]+)$', payload)
            if not meaning_match:
                continue
            meaning = meaning_match.group(1)
            glosses = split_glosses(meaning)
            for gloss in glosses:
                cleaned = clean_verb_gloss(gloss)
                norm = normalize_word(cleaned)
                if norm:
                    verbs.add(norm)

    # Write dictionary files
    def write_dic(filename, items, tag):
        filepath = ENGLISH_DICS_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            for item in sorted(items):
                f.write(f"{item}: {tag}\n")
        print(f"Wrote {len(items)} items to {filepath}")

    write_dic("nouns.dic", nouns, "NOUN")
    write_dic("verbs.dic", verbs, "VERB")
    write_dic("adjectives.dic", adjectives, "ADJ")
    write_dic("adverbs.dic", adverbs, "ADV")
    write_dic("prepositions.dic", prepositions, "PREP")
    write_dic("determiners.dic", pronouns, "DET")
    write_dic("numbers.dic", numbers, "NUM")
    write_dic("phrases.dic", phrases, "PHRASE")

if __name__ == "__main__":
    main()
