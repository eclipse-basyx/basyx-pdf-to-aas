from dataclasses import dataclass

from ..dictionary import PropertyDefinition

@dataclass
class Property():
    """
    A dataclass to represent a property with a value that was extracted.

    Attributes:
        label (str): The label of the property, e.g. "Rated Torque".
        value (any): The extracted value of the property.
        unit (str): The measurement unit as found in the data source.
        reference (str): A reference (~100 chars) where the value was found, e.g. an excerpt, or page reference. 
        defintion (PropertyDefinition): Definition of the property
    """
    label: str = ""
    value: any = None
    unit: str = ""
    reference: str = ""
    definition: PropertyDefinition | None = None

    @classmethod
    def from_dict(cls, property_dict:dict, defintion:PropertyDefinition):      
        label = property_dict.get('property')
        if label is None:
            label = property_dict.get('label')
        if label is None:
            label = defintion.name.get('en')
        if label is None:
            label = next(iter(defintion.name.values()), "")
        
        return cls(
            label,
            property_dict.get('value'),
            property_dict.get('unit'),
            property_dict.get('reference'),
            defintion
        )

class PropertyLLM:
    def extract(self, datasheet: str, property_definition: PropertyDefinition | list[PropertyDefinition]) -> list[Property]:
        raise NotImplementedError()

class DummyPropertyLLM(PropertyLLM):
    def empty_property_result(property_definition: PropertyDefinition):
        return [Property("empty", definition=property_definition)]
    def extract(self, datasheet: str, property_definition: PropertyDefinition | list[PropertyDefinition]) -> list[Property]:
        return DummyPropertyLLM.empty_property_result(property_definition)
