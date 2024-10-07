"""Module containing different dictionaries for the PDF2AAS workflow."""
from .propertyDefinition import PropertyDefinition
from .classDefinition import ClassDefinition
from .core import  Dictionary, dictionary_serializer
from .cdd import CDD
from .eclass import ECLASS
from .etim import ETIM

__all__ = [
    "PropertyDefinition",
    "ClassDefinition",
    "Dictionary",
    "dictionary_serializer",
    "CDD",
    "ECLASS",
    "ETIM",
]
