import re
from dataclasses import dataclass, field

from ..dictionary import PropertyDefinition

_number_regex = r"([-+]?[0-9_]*\.?[0-9_]+)"
_numeric_range_regex = _number_regex + r".+?" + _number_regex

def try_cast_number(value:any) -> float | int | None:
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    if value.is_integer():
        value = int(value)
    return value

@dataclass
class Property():
    """
    A dataclass to represent a property with a value that was extracted.

    Attributes:
        label (str): The label of the property, e.g. "Rated Torque".
        value (any): The extracted value of the property.
        unit (str | None): The measurement unit for the given value.
        reference (str | None): A reference (~100 chars) where the value was found, e.g. an excerpt, or page reference. 
        defintion (PropertyDefinition | None): Definition of the property if available.
        language(str): Language code (default en) used for the fields (except maybe reference, when it was translated).
    """
    label: str = ""
    value: any = None
    unit: str | None = None
    reference: str | None = None
    definition: PropertyDefinition | None = field(default=None, repr=False)
    language: str =  field(default='en', repr=False)

    @property
    def definition_id(self) -> str | None:
        """Get the id of the definition if available, else None."""
        return self.definition.id if self.definition is not None else None
    
    @property
    def definition_name(self)  -> str | None:
        """Get the definition name for the property language.
           
           Returns the first definition name if selected language is not available.
           Returns None if no definition or name is available."""
        if self.definition is None:
            return None
        name = self.definition.name.get(self.language)
        if name is None:
            name = next(iter(self.definition.name.values()), '')
        return name

    def parse_numeric_range(self) -> tuple[float|int| None, float|int|None]:
        """Try to parse the value as a numerical range
        
           Returns (None,None) if not parseable.
           Returns first and last argument if value is a collection (list, tuple, set, dict)."""
        value = (self.value, self.value)
        if isinstance(self.value, (list, tuple, set, dict)):
            if len(self.value) == 0:
                return None, None
            value = list(self.value)
            value = (value[0], value[-1])
        elif isinstance(self.value, str):
            result = re.search(_numeric_range_regex, self.value)
            if result is not None:
                value = (result.group(1), result.group(2))
        return (try_cast_number(value[0]), try_cast_number(value[1]))

    def to_legacy_dict(self):
        return {
            'property': self.label,
            'value': self.value,
            'unit': self.unit,
            'reference': self.reference,
            'id': self.definition.id if self.definition else '',
            'name': self.definition_name
        }

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
            defintion,
            property_dict.get('language', 'en')
        )

class PropertyLLM:
    def extract(self, datasheet: str, property_definition: PropertyDefinition | list[PropertyDefinition]) -> list[Property]:
        raise NotImplementedError()

