from dictionary.core import Dictionary, PropertyDefinition

class ECLASS(Dictionary):
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        return []