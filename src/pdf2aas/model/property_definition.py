"""Class to represent property definitions."""

from dataclasses import dataclass, field
from typing import Literal

SimplePropertyDataType = Literal["bool", "numeric", "string", "range"]

@dataclass
class PropertyDefinition:
    """A dataclass to represent a property definition within a dictionary.

    Attributes:
        id (str): The unique identifier for the property, typically an IRDI
        name (dict[str, str]): A dictionary containing language-specific names
            or labels for the property.
        type (SimplePropertyDataType): The data type of the property. Defaults to 'string'. Well
            known types are: bool, numeric, string, range
        definition (dict[str, str]): A dictionary containing language-specific
            definitions for the property.
        unit (str): The measurement unit associated with the property. Defaults
            to an empty string.
        values (list[str|dict]): A list of strings or dictionarys that store
            possible values for the property. Defaults to an empty list.
            Well known keys in dictionary form are: value, defintition, id.
        values_list (list[str]): Get possible values as flat list of strings.

    """

    id: str
    name: dict[str, str] = field(default_factory=dict)
    type: SimplePropertyDataType = "string"
    definition: dict[str, str] = field(default_factory=dict)
    unit: str = ""
    values: list[str | dict[Literal["value", "id", "definition"], str]] = field(
        default_factory=list,
    )

    @property
    def values_list(self) -> list[str]:
        """Get possible values as flat list of strings."""
        values = []
        for value in self.values:
            if isinstance(value, dict) and "value" in value:
                values.append(value["value"])
            else:
                values.append(str(value))
        return values

    def get_value_id(self, value: str) -> str | int | None:
        """Try to find the value in the value list and return its id.

        Returns None if not found. Returns the index of the value list, if
        no `id` is given in the value dictionary.
        """
        for idx, value_definition in enumerate(self.values):
            if isinstance(value_definition, str):
                if value == value_definition:
                    return idx
                continue
            if "value" in value_definition and value == value_definition["value"]:
                return value_definition.get("id", idx)
            continue
        return None

    def get_name(self, preferred_language:str) -> str | None:
        """Try to get the property name in the preferred language.

        Returns the first name if selected language is not available.
        Returns None if no name is available.
        """
        name = self.name.get(preferred_language)
        if name is None and len(self.name) > 0:
            name = next(iter(self.name.values()))
        return name

    def get_definition(self, preferred_language:str) -> str | None:
        """Try to get the property definition in the preferred language.

        Returns the first definition if selected language is not available.
        Returns None if no definition is available.
        """
        definition = self.definition.get(preferred_language)
        if definition is None and len(self.definition) > 0:
            definition = next(iter(self.definition.values()))
        return definition
