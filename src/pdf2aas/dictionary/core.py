from dataclasses import dataclass, field, asdict

#TODO use ConceptDescription class from aas python package instead?
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

#TODO use ConceptDescription class from aas python package instead?
@dataclass
class ClassDefinition():
    id: str
    name: str = ''
    description: str = ''
    keywords: list[str] = field(default_factory= lambda: [])
    properties: list[PropertyDefinition] = field(default_factory= lambda: [])

def dictionary_serializer(obj):
    if isinstance(obj, PropertyDefinition):
        return asdict(obj)
    if isinstance(obj, ClassDefinition):
        class_dict = asdict(obj)
        class_dict['properties'] = [prop.id for prop in obj.properties]
        return class_dict
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

class Dictionary:
    temp_dir = 'temp/dict'

    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """
        Retrieves a list of property definitions associated with a given class.

        Args:
            class_id (str): The unique identifier for the class whose properties are to be retrieved.

        Returns:
            list[PropertyDefinition]: A list of PropertyDefinition instances associated with the class.
        """
        raise NotImplementedError()

    def save_to_file(self, filepath: str = None):
        raise NotImplementedError()

    def load_from_file(self, filepath: str = None):
        raise NotImplementedError()
    
class ETIM(Dictionary):
    pass

# CDD, UNSPSC, ...

class DummyDictionary(Dictionary):
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        # e.g.: https://prod.etim-international.com/Feature/Details/EF003647?local=False
        return [PropertyDefinition('EF003647', {'en': 'Switching distance'}, 'numeric')]
    