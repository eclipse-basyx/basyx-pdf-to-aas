from ..dictionary import PropertyDefinition


class PropertyLLM:
    def extract(self, datasheet: str, property_definition: PropertyDefinition) -> dict | None:
        raise NotImplementedError()


class DummyPropertyLLM(PropertyLLM):
    def empty_property_result(property_definition: PropertyDefinition):
        return {
                "property": None,
                "value": None,
                "unit": None,
                "reference": "Empty Property",
                "id": property_definition.id,
                "name": property_definition.name.get('en')
            }
    def extract(self, datasheet: str, property_definition: PropertyDefinition) -> dict | None:
        return DummyPropertyLLM.empty_property_result(property_definition)
