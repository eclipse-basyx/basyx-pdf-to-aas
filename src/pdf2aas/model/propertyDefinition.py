"""Class to represent property definitions."""
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class PropertyDefinition():
    """A dataclass to represent a property definition within a dictionary.

    Attributes:
        id (str): The unique identifier for the property, typically an IRDI
        name (dict[str, str]): A dictionary containing language-specific names
            or labels for the property.
        type (str): The data type of the property. Defaults to 'string'. Well 
            known types are: bool, numeric, string, range
        definition (dict[str, str]): A dictionary containing language-specific 
            definitions for the property.
        unit (str): The measurement unit associated with the property. Defaults 
            to an empty string.
        values (list[str|dict]): A list of strings or dictionarys that store 
            possible values for the property. Defaults to an empty list. Well known keys in dictionary form are: value, defintition, id
        values_list (list[str]): Get possible values as flat list of strings.

    """

    id: str
    name: dict[str, str] = field(default_factory= lambda: {})
    type: Literal['bool', 'numeric', 'string', 'range'] = 'string'
    definition: dict[str, str] = field(default_factory= lambda: {})
    unit: str = ''
    values: list[str | dict [Literal['value', 'id', 'definition'], str]] = field(default_factory= lambda: [])

    @property
    def values_list(self) -> list[str]:
        """Get possible values as flat list of strings."""
        values = []
        for value in self.values:
            if isinstance(value, str):
                values.append(value)
                continue
            if "value" in value:
                values.append(value["value"])
        return values

    def get_value_id(self, value:str) -> str | int | None:
        """Try to find the value in the value list and return its id.
        
        Returns None if not found. Returns the index of the value list, if
        no `id` is given in the value dictionary.
        """
        for idx, value_definition in enumerate(self.values):
            if isinstance(value_definition, str):
                if value == value_definition:
                    return idx
                continue
            if "value" in value_definition:
                if value == value_definition['value']:
                    return value_definition.get('id', idx)
            continue
        return None