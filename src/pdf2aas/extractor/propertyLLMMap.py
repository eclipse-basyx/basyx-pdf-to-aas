"""Extractors that uses two steps to extract and map the properties."""
import logging

from ..dictionary import PropertyDefinition
from . import PropertyLLM
from . import Property

logger = logging.getLogger(__name__)

class PropertyLLMMap(PropertyLLM):
    """PropertyLLM that extracts all properties and maps them to given definitions.
    
    The mapping is done verry naively based on the extracted property label and 
    the definition name.
    """

    def _add_definitions(
            self,
            properties: list[Property],
            property_definition: list[PropertyDefinition] | PropertyDefinition
    ) -> list[Property]:
        if len(properties) == 0:
            return []
        if isinstance(property_definition, PropertyDefinition):
            property_definition = [property_definition]

        # Naive approach to map by name
        property_definition_dict = {next(iter(p.name.values()), p.id).lower(): p for p in property_definition}
        for property_ in properties:
            property_.definition = property_definition_dict.get(
                property_.label.strip().lower())
        return properties