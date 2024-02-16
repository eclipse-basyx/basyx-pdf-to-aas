class PropertyLLM:
    def extract(self, datasheet: str, property_definition: str) -> str:
        raise NotImplementedError()


class DummyPropertyLLM(PropertyLLM):
    def extract(self, datasheet: str, property_definition: str) -> str:
        return '{"property_x":"12"}'
