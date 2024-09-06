
from ..dictionary import PropertyDefinition
from . import Property
from . import Extractor

class PropertyLLM(Extractor):
    def extract(
        self,
        datasheet: str,
        property_definition: PropertyDefinition | list[PropertyDefinition],
        raw_prompts: list[str] | None = None,
        raw_results: list[str] | None = None,
        prompt_hint: str | None = None
    ) -> list[Property]:
        ...