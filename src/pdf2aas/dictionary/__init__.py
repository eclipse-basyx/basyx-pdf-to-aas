"""Module containing different dictionaries for the PDF2AAS workflow."""

from .cdd import CDD
from .core import Dictionary, dictionary_serializer
from .eclass import ECLASS
from .etim import ETIM

__all__ = [
    "Dictionary",
    "dictionary_serializer",
    "CDD",
    "ECLASS",
    "ETIM",
]
