from dataclasses import dataclass, field

#TODO use property class from aas python package instead?
#TODO define data types
@dataclass
class PropertyDefinition():
    """
    A dataclass to represent a property definition within a dictionary.

    Attributes:
        id (str): The unique identifier for the property, typically an IRDI
        name (dict[str, str]): A dictionary containing language-specific names or labels for the property.
        type (str): The data type of the property. Defaults to 'string'. Well known types are: bool, numeric, string
        definition (dict[str, str]): A dictionary containing language-specific definitions for the property.
        unit (str): The measurement unit associated with the property. Defaults to an empty string.
        values (dict): A dictionary that stores possible values for the property. Defaults to an empty list.
    """
    id: str
    name: dict[str, str] = field(default_factory= lambda: {})
    type: str = 'string'
    definition: dict[str, str] = field(default_factory= lambda: {})
    unit: str = ''
    values: dict = field(default_factory= lambda: [])

class Dictionary:

    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """
        Retrieves a list of property definitions associated with a given class.

        Args:
            class_id (str): The unique identifier for the class whose properties are to be retrieved.

        Returns:
            list[PropertyDefinition]: A list of PropertyDefinition instances associated with the class.
        """
        raise NotImplementedError()
    
class ETIM(Dictionary):
    pass

# CDD, UNSPSC, ...

class DummyDictionary(Dictionary):
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        # e.g.: https://prod.etim-international.com/Feature/Details/EF003647?local=False
        return [PropertyDefinition('EF003647', 'Switching distance', 'numeric')]
    