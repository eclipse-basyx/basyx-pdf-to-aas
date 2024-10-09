"""Abstract dictionary class to provide class and property definitions."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Any, ClassVar

import requests

from pdf2aas.model import ClassDefinition, PropertyDefinition

logger = logging.getLogger(__name__)


def dictionary_serializer(obj: Any) -> dict:
    """Serialize Class and PropertyDefinitions to save Dictionaries as JSON."""
    if isinstance(obj, PropertyDefinition):
        return asdict(obj)
    if isinstance(obj, ClassDefinition):
        class_dict = asdict(obj)
        class_dict["properties"] = [prop.id for prop in obj.properties]
        return class_dict
    error = f"Object of type {obj.__class__.__name__} is not JSON serializable"
    raise TypeError(error)


class Dictionary(ABC):
    """Abstract dictionary to manage a collection of property and class definitions.

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
        timeout (float): Time limit in seconds for property or class information
            downloads. Defaults to 120s.

    """

    temp_dir = "temp/dict"
    properties: ClassVar[dict[str, PropertyDefinition]] = {}
    releases: ClassVar[dict[dict[str, ClassDefinition]]] = {}
    supported_releases: ClassVar[list[str]] = []
    license: str | None = None
    timeout: float = 120

    def __init__(
        self,
        release: str,
        temp_dir: str | None = None,
        language: str = "en",
    ) -> None:
        """Initialize Dictionary with default release and cache directory."""
        if temp_dir:
            self.temp_dir = temp_dir
        self.language = language
        if release not in self.supported_releases:
            logger.warning(
                "Release %s unknown. Supported releases are %s",
                release,
                self.supported_releases,
            )
        self.release = release
        if release not in self.releases:
            self.releases[release] = {}
            self.load_from_file()

    @property
    def name(self) -> str:
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
            dict[str, ClassDefinition]: A dictionary of class definitions for
                the current release, with their class id as key.

        """
        return self.releases.get(self.release)

    @abstractmethod
    def get_class_url(self, class_id: str) -> str | None:
        """Get the web URL for the class of the class_id for details."""
        return None

    @abstractmethod
    def get_property_url(self, property_id: str) -> str | None:
        """Get the web URL for the property id for details."""
        return None

    def save_to_file(self, filepath: str | None = None) -> None:
        """Save the dictionary to a file.

        Saves as json on default. Uses the `temp_dir` with dictionary name and
        release, if none is provided.
        """
        if filepath is None:
            path = Path(self.temp_dir) / f"{self.name}-{self.release}.json"
        else:
            path = Path(filepath)
        logger.info("Save dictionary to file: %s", path)
        path.mkdir(parents=True)
        with open(path, "w") as file:
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
            path = Path(self.temp_dir) / f"{self.name}-{self.release}.json"
        else:
            path = Path(filepath)
        if not path.exists():
            logger.debug("Couldn't load dictionary from file. File does not exist: %s", path)
            return False
        logger.info("Load dictionary from file: %s", path)
        with open(path) as file:
            dict_ = json.load(file)
            if dict_["release"] != self.release:
                logger.warning(
                    "Loading release %s for dictionary with release %s.",
                    dict_["release"],
                    self.release,
                )
            for id_, property_ in dict_["properties"].items():
                if id_ not in self.properties:
                    logger.debug("Load property %s: %s", property_["id"], property_["name"])
                    self.properties[id_] = PropertyDefinition(**property_)
            if dict_["release"] not in self.releases:
                self.releases[dict_["release"]] = {}
            for id_, class_ in dict_["classes"].items():
                classes = self.releases[dict_["release"]]
                if id_ not in classes:
                    logger.debug("Load class %s: %s", class_["id"], class_["name"])
                    new_class = ClassDefinition(**class_)
                    new_class.properties = [
                        self.properties[property_id] for property_id in new_class.properties
                    ]
                    classes[id_] = new_class
        return True

    def save_all_releases(self) -> None:
        """Save all releases currently available in the Dictionary class."""
        original_release = self.release
        for release, classes in self.releases.items():
            if len(classes) == 0:
                continue
            self.release = release
            self.save_to_file()
        self.release = original_release

    def _download_html(self, url: str) -> str | None:
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("HTML download failed.")
            return None
        return response.text
