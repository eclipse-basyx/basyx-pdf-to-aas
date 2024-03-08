from ..dictionary import PropertyDefinition


class PropertyLLM:
    def extract(self, datasheet: str, property_definition: PropertyDefinition) -> str:
        raise NotImplementedError()


class DummyPropertyLLM(PropertyLLM):
    def extract(self, datasheet: str, property_definition: PropertyDefinition) -> str:
        return '{"property_x":"12"}'
