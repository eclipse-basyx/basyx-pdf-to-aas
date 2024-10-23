"""Class and functions to use ETIM as dictionary in PDF2AAS workflow."""

import csv
import logging
import os
import re
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import ClassVar

import requests

from .core import ClassDefinition, Dictionary, PropertyDefinition

logger = logging.getLogger(__name__)

etim_datatype_to_type = {
    "L": "bool",
    "Logical": "bool",
    "N": "numeric",
    "Numeric": "numeric",
    "R": "range",
    "Range": "range",
    "A": "string",
    "Alphanumeric": "string",
}


class ETIM(Dictionary):
    """Represent a release of the ETIM dictionary.

    Allows to interact with the ETIM standard for classification and product
    description. It provides functionalities to search for ETIM classes and
    retrieve their properties based on different releases of the standard.

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
        timeout (float): Time limit in seconds for downloads from ETIM website.
            Defaults to 120s.

    """

    releases: ClassVar[dict[dict[str, ClassDefinition]]] = {}
    properties: ClassVar[dict[str, PropertyDefinition]] = {}
    supported_releases: ClassVar[list[str]] = [
        "9.0",
        "8.0",
        "7.0",
        "6.0",
        "5.0",
        "4.0",
        "DYNAMIC",
    ]
    license = "https://opendatacommons.org/licenses/by/1-0/"

    def __init__(
        self,
        release: str = "9.0",
        temp_dir: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        auth_url: str = "https://etimauth.etim-international.com",
        base_url: str = "https://etimapi.etim-international.com",
        scope: str = "EtimApi",
    ) -> None:
        """Initialize the ETIM dictionary with default values.

        Arguments:
            release (str): Release this dictionary represents. Defaults to "9.0"
            temp_dir (str): Overwrite temporary dictionary for caching the dict.
            client_id (str): Client id for the ETIM API.
            client_secret (str): Client secret to use the ETIM API.
            auth_url (str): Authorization URL for the ETIM API. Defaults to
                "https://etimauth.etim-international.com".
            base_url (str): Base URL for the ETIM API. Defaults to
                "https://etimapi.etim-international.com",
            scope (str): ETIM API scrope. Defaults to "EtimApi".

        """
        super().__init__(release, temp_dir)
        self.client_id = client_id if client_id is not None else os.environ.get("ETIM_CLIENT_ID")
        self.client_secret = (
            client_secret if client_secret is not None else os.environ.get("ETIM_CLIENT_SECRET")
        )
        self.auth_url = auth_url
        self.base_url = base_url
        self.scope = scope
        self.__access_token = None
        self.__expire_time = None

    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """Get all properties (called features in ETIM) of a given class.

        The class ID should start with EC and a 6 digit number. Tries to
        download the class if it is not in memory.
        """
        class_id = self.parse_class_id(class_id)
        if class_id is None:
            return []
        class_ = self.classes.get(class_id)
        if class_ is None:
            etim_class = self._download_etim_class(class_id)
            if etim_class is None:
                return []
            class_ = self._parse_etim_class(etim_class)
        return class_.properties

    def get_class_url(self, class_id: str) -> str:
        """Get the URL to the class in the class management tool (CMT)."""
        # Alternative: f"https://viewer.etim-international.com/class/{class_id}"  # noqa: ERA001
        return f"https://prod.etim-international.com/Class/Details/?classid={class_id}"

    def get_property_url(self, property_id: str) -> str:
        """Get the URL to the feature in the class management tool (CMT)."""
        return f"https://prod.etim-international.com/Feature/Details/{property_id.split('/')[0]}"

    def _download_etim_class(self, etim_class_code:str) -> dict:
        logger.debug(
            "Download etim class details for %s in %s and release %s",
            etim_class_code,
            self.language,
            self.release,
        )
        access_token = self._get_access_token()
        if access_token is None:
            return None
        url = f"{self.base_url}/api/v2/Class/DetailsForRelease"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        data = {
            "include": {
                "descriptions": True,
                "translations": False,
                "fields": [
                    "features",
                ],
            },
            "languagecode": self.language.upper(),
            "code": etim_class_code,
            "release": f"ETIM-{self.release}" if self.release[0].isdigit() else self.release,
        }
        try:
            response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            logger.debug("ETIM API Response: %s", response)
            return response.json()
        except (requests.HTTPError, Exception):
            logger.exception("Can't download ETIM class %s.", etim_class_code)
        return None

    def _parse_etim_class(self, etim_class: dict) -> ClassDefinition:
        class_ = ClassDefinition(
            id=etim_class["code"],
            name=etim_class["description"],
            keywords=etim_class["synonyms"],
        )
        for feature in etim_class["features"]:
            feature_id = f"{self.release}/{etim_class['code']}/{feature['code']}"
            property_ = PropertyDefinition(
                id=feature_id,
                name={self.language: feature["description"]},
                type=etim_datatype_to_type.get(feature["type"], "string"),
                # definition is currently not available via ETIM API
            )
            if "unit" in feature:
                property_.unit = feature["unit"]["abbreviation"]
            if "values" in feature:
                property_.values = [
                    {
                        "value": value["description"],
                        "id": value["code"],
                    }
                    for value in feature["values"]
                ]
            self.properties[feature_id] = property_
            class_.properties.append(property_)
        self.classes[etim_class["code"]] = class_
        return class_

    def _get_access_token(self) -> str:
        if (self.__access_token is not None) and (time.time() < self.__expire_time):
            return self.__access_token

        if self.client_id is None or self.client_secret is None:
            logger.error("No client id or secret specified for ETIM.")
            return None
        timestamp = time.time()
        url = f"{self.auth_url}/connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }
        try:
            response = requests.post(url, data=data, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Authorization at ETIM API failed.")
            return None
        self.__expire_time = timestamp + response.json()["expires_in"]
        self.__access_token = response.json()["access_token"]
        logger.debug(
            "Got new access token '%s'. Expires in: %s [s]",
            self.__access_token,
            response.json()["expires_in"],
        )
        return self.__access_token

    @staticmethod
    def parse_class_id(class_id: str) -> str | None:
        """Try to find a ETIM conform class id in the given string and return it.

        Is case insensitive and ignores minus, underscores and spaces.
        Matches any string that starts with EC followed by 6 digits.
        """
        if class_id is None:
            return None
        class_id = re.sub(r"[-_ ]|\s", "", class_id)
        class_id = re.search("EC[0-9]{6}", class_id, re.IGNORECASE)
        if class_id is None:
            return None
        return class_id.group(0)

    def _load_from_release_csv_zip(self, filepath_str: str) -> None:  # noqa: C901, PLR0912
        logger.info("Load ETIM dictionary from CSV release zip: %s", filepath_str)

        filepath = Path(filepath_str)
        zip_dir = filepath.parent / filepath.stem
        if not zip_dir.exists():
            try:
                zip_dir.mkdir(parents=True)
                shutil.unpack_archive(filepath, zip_dir)
            except (shutil.ReadError, FileNotFoundError, PermissionError) as e:
                logger.warning("Error while unpacking ETIM CSV Release: %s", e)
                if zip_dir.exists():
                    shutil.rmtree(zip_dir)

        synonyms = defaultdict(list)
        with open(zip_dir / "ETIMARTCLASSSYNONYMMAP.csv", encoding="utf-16") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                synonyms[row["ARTCLASSID"]].append(row["CLASSSYNONYM"])

        feature_descriptions = {}
        with open(zip_dir / "ETIMFEATURE.csv", encoding="utf-16") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                feature_descriptions[row["FEATUREID"]] = row["FEATUREDESC"]

        unit_abbreviations = {}
        with open(zip_dir / "ETIMUNIT.csv", encoding="utf-16") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                unit_abbreviations[row["UNITOFMEASID"]] = row["UNITDESC"]

        value_descriptions = {}
        with open(zip_dir / "ETIMVALUE.csv", encoding="utf-16") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                value_descriptions[row["VALUEID"]] = row["VALUEDESC"]

        feature_value_map = {}
        with open(zip_dir / "ETIMARTCLASSFEATUREVALUEMAP.csv", encoding="utf-16") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                value = {
                    # 'orderNumber' = index in this list
                    "code": row["VALUEID"],
                    "description": value_descriptions[row["VALUEID"]],
                }
                if row["ARTCLASSFEATURENR"] not in feature_value_map:
                    feature_value_map[row["ARTCLASSFEATURENR"]] = [value]
                else:
                    feature_value_map[row["ARTCLASSFEATURENR"]].append(value)

        class_feature_map = defaultdict(list)
        with open(zip_dir / "ETIMARTCLASSFEATUREMAP.csv", encoding="utf-16") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                feature = {
                    # orderNumber = index in the list
                    "code": row["FEATUREID"],
                    "type": row["FEATURETYPE"],
                    "description": feature_descriptions[row["FEATUREID"]],
                    # 'portcode' is None,
                    # 'unitImperial' is None,
                }
                if len(row["UNITOFMEASID"]) > 0:
                    feature["unit"] = {
                        "code": row["UNITOFMEASID"],
                        #'description' is None,
                        "abbreviation": unit_abbreviations[row["UNITOFMEASID"]],
                    }
                values = feature_value_map.get(row["ARTCLASSFEATURENR"])
                if values:
                    feature["values"] = values
                class_feature_map[row["ARTCLASSID"]].append(feature)

        with open(zip_dir / "ETIMARTCLASS.csv", encoding="utf-16") as file:
            reader = csv.DictReader(file, delimiter=";")
            for row in reader:
                class_dict = {
                    "code": row["ARTCLASSID"],
                    "description": row["ARTCLASSDESC"],
                    "synonyms": synonyms[row["ARTCLASSID"]],
                    # "version" = row['ARTCLASSVERSION'],
                    # "status" = None,
                    # "mutationDate" = None,
                    # "revision" = None,
                    # "revisionDate" = None,
                    # "modelling" = false,
                    # "descriptionEn" = None,
                    "features": class_feature_map[row["ARTCLASSID"]],
                }
                self._parse_etim_class(class_dict)

    def load_from_file(self, filepath: str | None = None) -> bool:
        """Load a whole ETIM release from CSV zip file.

        Searches in `self.tempdir` for "ETIM-<release>-...CSV....zip" file, if
        no filepath is given.
        """
        if filepath is None and Path(self.temp_dir).exists():
            for filename in os.listdir(self.temp_dir):
                if re.match(f"{self.name}-{self.release}.*CSV.*\\.zip", filename, re.IGNORECASE):
                    try:
                        self._load_from_release_csv_zip(Path(self.temp_dir) / filename)
                    except OSError as e:
                        logger.warning("Error while loading csv zip '%s': %s", filename, e)
                    return True
        return super().load_from_file(filepath)

