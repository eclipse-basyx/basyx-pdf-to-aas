from dataclasses import dataclass

#TODO use property class from aas python package instead?
@dataclass
class PropertyDefinition():
    id: str
    name: str = ''
    type: str = 'string'
    definition: str = ''
    language: str = 'en'
    unit: str = ''
    values = []

class Dictionary:
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        raise NotImplementedError()
    
class ETIM(Dictionary):
    pass

# CDD, UNSPSC, ...

class DummyDictionary(Dictionary):
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        # e.g.: https://prod.etim-international.com/Feature/Details/EF003647?local=False
        return [PropertyDefinition('EF003647', 'Switching distance', 'numeric')]
    