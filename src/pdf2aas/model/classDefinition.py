"""Class to represent product, device or article classes."""
from dataclasses import dataclass, field

from .propertyDefinition import PropertyDefinition

@dataclass
class ClassDefinition():
    """Class to represent product, device or article classes in a dictionary.
    
    Arguments:
      id (str): Identifier of the class, e.g. an IRDI.
      name (str): Name or label of the class.
      description (str): Description of the class in the sense of a defition.
      keywords (str): similiar names of the class.
      properties (list[PropertyDefinition]): List of properties that describe
        the class object.

    """

    id: str
    name: str = ''
    description: str = ''
    keywords: list[str] = field(default_factory= lambda: [])
    properties: list[PropertyDefinition] = field(default_factory= lambda: [])
