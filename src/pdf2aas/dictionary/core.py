"""Abstract dictionary class to provide class and property definitions."""
import json
import logging
import os
from abc import ABC
from dataclasses import asdict

from ..model import ClassDefinition, PropertyDefinition

logger = logging.getLogger(__name__)

def dictionary_serializer(obj):
    """Serialize Class and PropertyDefinitions to save Dictionaries as JSON."""
    if isinstance(obj, PropertyDefinition):
        return asdict(obj)
    if isinstance(obj, ClassDefinition):
        class_dict = asdict(obj)
        class_dict["properties"] = [prop.id for prop in obj.properties]
        return class_dict
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

class Dictionary(ABC):
    """Abstract class to manage a collection of property and class definitions.

    Attributes:
        temp_dir (str): The directory path used for loading/saving a cached
            dictionary.
        properties (dict[str, PropertyDefinition]): Maps property IDs to
            PropertyDefinition instances.
        releases (dict[str, dict[str, ClassDefinition]]): Maps release versions
            to class definition objects.
        supported_releases (list[str]): A list of supported release versions.
        license (str): A link or note to the license or copyright of the
            dictionary.

    """

    temp_dir = "temp/dict"
    properties: dict[str, PropertyDefinition] = {}
    releases: dict[dict[str, ClassDefinition]] = {}
    supported_releases: list[str] = []
    license: str | None = None

    def __init__(
            self,
            release: str,
            temp_dir: str = None,
            language: str = "en",
    ) -> None:
        """Initialize Dictionary with default release and cache directory."""
        if temp_dir:
            self.temp_dir=temp_dir
        self.language = language
        if release not in self.supported_releases:
            logger.warning("Release %s unknown. Supported releases are %s", release, self.supported_releases)
        self.release = release
        if release not in self.releases:
            self.releases[release] = {}
            self.load_from_file()

    @property
    def name(self):
        """Get the type name of the dictionary, e.g. ECLASS, ETIM, ..."""
        return self.__class__.__name__

    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """Retrieve a list of property definitions associated with a given class.

        Arguments:
            class_id (str): The unique identifier for the class whose properties
                are to be retrieved.

        Returns:
            properties (list[PropertyDefinition]): A list of PropertyDefinition
                instances associated with the class.

        """
        class_ = self.classes.get(class_id)
        if class_ is None:
            return []
        return class_.properties

    def get_property(self, property_id: str) -> PropertyDefinition:
        """Retrieve a single property definition for the given property ID from the dictionary.

        Arguments:
            property_id (str): The unique identifier of the property.

        Returns:
            PropertyDefinition: The definition of the property associated with the given ID.

        """
        return self.properties.get(property_id)

    @property
    def classes(self) -> dict[str, ClassDefinition]:
        """Retrieves the class definitions for the currently set release version.

        Arguments:
            dict[str, ClassDefinition]: A dictionary of class definitions for the current release, with their class id as key.

        """
        return self.releases.get(self.release)

    def get_class_url(self, class_id: str) -> str | None:
        """Get the web URL for the class of the class_id for details."""
        return None
    def get_property_url(self, property_id: str) -> str | None:
        """Get the web URL for the property id for details."""
        return None

    def save_to_file(self, filepath: str | None = None):
        """Save the dictionary to a file.
        
        Saves as json on default. Uses the `temp_dir` with dictionary name and
        release, if none is provided.
        """
        if filepath is None:
            filepath = os.path.join(self.temp_dir, f"{self.name}-{self.release}.json")
        logger.info("Save dictionary to file: %s", filepath)
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
        """Load the dictionary from a file.
        
        Checks the `temp_dir` for dictionary name and release, if none is given.
        """
        if filepath is None:
            filepath = os.path.join(self.temp_dir, f"{self.name}-{self.release}.json")
        if not os.path.exists(filepath):
            logger.debug("Couldn't load dictionary from file. File does not exist: %s",filepath)
            return False
        logger.info("Load dictionary from file: %s", filepath)
        with open(filepath) as file:
            dict = json.load(file)
            if dict["release"] != self.release:
                logger.warning("Loading release %s for dictionary with release %s.",dict["release"], self.release)
            for id, property in dict["properties"].items():
                if id not in self.properties.keys():
                    logger.debug("Load property %s: %s", property["id"], property["name"])
                    self.properties[id] = PropertyDefinition(**property)
            if dict["release"] not in self.releases:
                self.releases[dict["release"]] = {}
            for id, class_ in dict["classes"].items():
                classes = self.releases[dict["release"]]
                if id not in classes.keys():
                    logger.debug("Load class %s: %s", class_["id"], class_["name"])
                    new_class = ClassDefinition(**class_)
                    new_class.properties = [
                        self.properties[property_id]
                        for property_id in new_class.properties
                    ]
                    classes[id] = new_class
        return True

    def save_all_releases(self):
        """Save all releases currently available in the Dictionary class."""
        original_release = self.release
        for release, classes in self.releases.items():
            if len(classes) == 0:
                continue
            self.release = release
            self.save_to_file()
        self.release = original_release
