import os
import logging
import json
from dataclasses import dataclass, field, asdict
from typing import Literal
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

#TODO use ConceptDescription class from aas python package instead?
#TODO define data types
@dataclass
class PropertyDefinition():
    """
    A dataclass to represent a property definition within a dictionary.

    Attributes:
        id (str): The unique identifier for the property, typically an IRDI
        name (dict[str, str]): A dictionary containing language-specific names or labels for the property.
        type (str): The data type of the property. Defaults to 'string'. Well known types are: bool, numeric, string, range
        definition (dict[str, str]): A dictionary containing language-specific definitions for the property.
        unit (str): The measurement unit associated with the property. Defaults to an empty string.
        values (list[str|dict]): A list of strings or dictionarys that store possible values for the property. Defaults to an empty list. Well known keys in dictionary form are: value, defintition, id
        values_list (list[str]): Get possible values as flat list of strings
    """
    id: str
    name: dict[str, str] = field(default_factory= lambda: {})
    type: Literal['bool', 'numeric', 'string', 'range'] = 'string'
    definition: dict[str, str] = field(default_factory= lambda: {})
    unit: str = ''
    values: list[str | dict [Literal['value', 'id', 'definition'], str]] = field(default_factory= lambda: [])

    @property
    def values_list(self) -> list[str]:
        """Get possible values as flat list of strings"""
        values = []
        for value in self.values:
            if isinstance(value, str):
                values.append(value)
                continue
            if "value" in value:
                values.append(value["value"])
        return values

    def get_value_id(self, value:str) -> str | int | None:
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

class Dictionary(ABC):
    """
    Abstract base class for managing a collection of property and class definitions.

    Attributes:
        temp_dir (str): The directory path used for loading/saving a cached dictionary.
        properties (dict[str, PropertyDefinition]): Maps property IDs to PropertyDefinition instances.
        releases (dict[str, dict[str, object]]): Maps release versions to class objects.
        supported_releases (list[str]): A list of supported release versions.
        license: A link or note to the license or copyright of the dictionary.
    """

    temp_dir = 'temp/dict'
    properties: dict[str, PropertyDefinition] = {}
    releases: dict[dict[str, ClassDefinition]] = {}
    supported_releases: list[str] = []
    license: str | None = None

    def __init__(self, release: str, temp_dir: str = None, language: str = "en") -> None:
        if temp_dir:
            self.temp_dir=temp_dir
        self.language = language
        if release not in self.supported_releases:
            logger.warning(f"Release {release} unknown. Supported releases are {self.supported_releases}")
        self.release = release
        if release not in self.releases:
            self.releases[release] = {}
            self.load_from_file()

    @property
    def name(self):
        return self.__class__.__name__
    
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """
        Retrieves a list of property definitions associated with a given class.

        Args:
            class_id (str): The unique identifier for the class whose properties are to be retrieved.

        Returns:
            list[PropertyDefinition]: A list of PropertyDefinition instances associated with the class.
        """
        class_ = self.classes.get(class_id)
        if class_ is None:
            return []
        return class_.properties

    def get_property(self, property_id: str) -> PropertyDefinition:
        """
        Retrieve a single property definition for the given property ID from the dictionary.

        Args:
            property_id (str): The unique identifier of the property.

        Returns:
            PropertyDefinition: The definition of the property associated with the given ID.
        """
        return self.properties.get(property_id)

    @property
    def classes(self) -> dict[str, ClassDefinition]:
        """
        Retrieves the class definitions for the currently set release version.

        Returns:
            dict[str, ClassDefinition]: A dictionary of class definitions for the current release, with their class id as key.
        """
        return self.releases.get(self.release)

    def get_class_url(self, class_id: str) -> str | None:
        return None
    def get_property_url(self, property_id: str) -> str | None:
        return None

    def save_to_file(self, filepath: str | None = None):
        if filepath is None:
            filepath = os.path.join(self.temp_dir, f'{self.name}-{self.release}.json')
        logger.info(f"Save dictionary to file: {filepath}")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as file:
            json.dump(
                {
                    "type": self.name,
                    "release": self.release,
                    "properties": self.properties,
                    "classes": self.classes,
                    "license": self.license,
                },
                file,
                default=dictionary_serializer,
            )

    def load_from_file(self, filepath: str | None = None) -> bool:
        if filepath is None:
            filepath = os.path.join(self.temp_dir, f'{self.name}-{self.release}.json')
        if not os.path.exists(filepath):
            logger.debug(
                f"Couldn't load dictionary from file. File does not exist: {filepath}"
            )
            return False
        logger.info(f"Load dictionary from file: {filepath}")
        with open(filepath, "r") as file:
            dict = json.load(file)
            if dict["release"] != self.release:
                logger.warning(
                    f"Loading release {dict['release']} for dictionary with release {self.release}."
                )
            for id, property in dict["properties"].items():
                if id not in self.properties.keys():
                    logger.debug(f"Load property {property['id']}: {property['name']}")
                    self.properties[id] = PropertyDefinition(**property)
            if dict["release"] not in self.releases:
                self.releases[dict["release"]] = {}
            for id, class_ in dict["classes"].items():
                classes = self.releases[dict["release"]]
                if id not in classes.keys():
                    logger.debug(
                        f"Load class {class_['id']}: {class_['name']}"
                    )
                    new_class = ClassDefinition(**class_)
                    new_class.properties = [
                        self.properties[property_id]
                        for property_id in new_class.properties
                    ]
                    classes[id] = new_class
        return True
    
    def save_all_releases(self):
        original_release = self.release
        for release, classes in self.releases.items():
            if len(classes) == 0:
                continue
            self.release = release
            self.save_to_file()
        self.release = original_release