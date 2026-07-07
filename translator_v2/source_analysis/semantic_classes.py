"""
translator_v2/source_analysis/semantic_classes.py

Semantic class taxonomy for lexical-sense disambiguation.
These classes describe the semantic type of nouns/noun phrases
and are used to match sense frames.

All classes are defined as string constants, not an enum,
so they can be serialised to JSON without custom encoders.
"""
from __future__ import annotations


# Top-level semantic classes
HUMAN = "HUMAN"
ANIMATE = "ANIMATE"
INANIMATE = "INANIMATE"
ORGANISATION = "ORGANISATION"
LOCATION = "LOCATION"
TIME = "TIME"
EVENT = "EVENT"
ABSTRACT = "ABSTRACT"
PHYSICAL_OBJECT = "PHYSICAL_OBJECT"
FLUID = "FLUID"
FOOD = "FOOD"
VEHICLE = "VEHICLE"
DIGITAL_ARTEFACT = "DIGITAL_ARTEFACT"
FINANCIAL = "FINANCIAL"
NATURAL_FEATURE = "NATURAL_FEATURE"
POLITICAL_ENTITY = "POLITICAL_ENTITY"
BODY_PART = "BODY_PART"
PLANT = "PLANT"
ANIMAL = "ANIMAL"
QUANTITY = "QUANTITY"
UNKNOWN = "UNKNOWN"

ALL_CLASSES = frozenset({
    HUMAN, ANIMATE, INANIMATE, ORGANISATION, LOCATION, TIME, EVENT,
    ABSTRACT, PHYSICAL_OBJECT, FLUID, FOOD, VEHICLE, DIGITAL_ARTEFACT,
    FINANCIAL, NATURAL_FEATURE, POLITICAL_ENTITY, BODY_PART, PLANT,
    ANIMAL, QUANTITY, UNKNOWN,
})

# Subsumption relationships (child → parents)
# Used to match frame constraints: "object must be ANIMATE" matches HUMAN too
SUBSUMES: dict[str, list[str]] = {
    HUMAN: [ANIMATE, INANIMATE],
    ANIMAL: [ANIMATE, INANIMATE],
    ANIMATE: [INANIMATE],
    ORGANISATION: [INANIMATE, ABSTRACT],
    LOCATION: [INANIMATE],
    FINANCIAL: [INANIMATE, ABSTRACT],
    NATURAL_FEATURE: [INANIMATE, LOCATION],
    VEHICLE: [PHYSICAL_OBJECT, INANIMATE],
    DIGITAL_ARTEFACT: [INANIMATE],
    FOOD: [PHYSICAL_OBJECT, INANIMATE],
    PLANT: [ANIMATE, INANIMATE],
    BODY_PART: [PHYSICAL_OBJECT, INANIMATE],
}


def is_subclass(candidate: str, required: str) -> bool:
    """Return True if candidate is the same as required, or is a subclass of it."""
    if candidate == required:
        return True
    return required in SUBSUMES.get(candidate, [])


# Heuristic NER-label → semantic class mapping
# Used when spaCy NER is available
NER_TO_SEMANTIC_CLASS: dict[str, str] = {
    "PERSON": HUMAN,
    "ORG": ORGANISATION,
    "GPE": LOCATION,       # Geo-political entity
    "LOC": LOCATION,
    "FAC": LOCATION,       # Facility
    "PRODUCT": PHYSICAL_OBJECT,
    "EVENT": EVENT,
    "WORK_OF_ART": ABSTRACT,
    "LAW": ABSTRACT,
    "LANGUAGE": ABSTRACT,
    "DATE": TIME,
    "TIME": TIME,
    "MONEY": FINANCIAL,
    "QUANTITY": QUANTITY,
    "CARDINAL": QUANTITY,
    "ORDINAL": QUANTITY,
    "NORP": HUMAN,         # Nationality/religious/political groups
}
