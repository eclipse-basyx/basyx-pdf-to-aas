"""Abstract extractor class to search or extract property values from a document."""

from abc import ABC, abstractmethod

from ..model.property import Property, PropertyDefinition


class Extractor(ABC):
    """Abstract class that provides an `extract` method to be used in PDF2AAS toolchain."""

    @abstractmethod
    def extract(
        self,
        datasheet: str,
        property_definition: PropertyDefinition | list[PropertyDefinition],
    ) -> list[Property]:
        """Try to extract the defined properties from the given datasheet text."""
