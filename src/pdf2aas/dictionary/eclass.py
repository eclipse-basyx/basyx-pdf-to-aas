"""Class and functions to use ECLASS as dictionary in PDF2AAS workflow."""

import csv
import json
import logging
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag

from pdf2aas.model import SimplePropertyDataType, ValueDefinitionKeyType

from .core import ClassDefinition, Dictionary, PropertyDefinition

logger = logging.getLogger(__name__)

eclass_datatype_to_type: dict[str | None, SimplePropertyDataType] = {
    "BOOLEAN": "bool",
    "INTEGER_COUNT": "numeric",
    "INTEGER_MEASURE": "numeric",
    "REAL_COUNT": "numeric",
    "REAL_CURRENCY": "numeric",
    "REAL_MEASURE": "numeric",
    "STRING": "string",
    "STRING_TRANSLATEABLE": "string",
    "URL": "string",
    # TODO: Map: DATE, RATIONAL, RATIONAL_MEASURE, REFERENCE, TIME, TIMESTAMP, AXIS1, AXIS2, AXIS3
}


def _extract_attribute_from_eclass_property_soup(
    soup: BeautifulSoup,
    search_text: str,
) -> str | None:
    th = soup.find(lambda tag: tag.name == "th" and tag.text.strip() == search_text)
    if th:
        td = th.find_next_sibling("td")
        if td:
            return td.text
    return None


def _extract_values_from_eclass_property_soup(soup: BeautifulSoup) -> list[str]:
    return [
        span.text for span in soup.find_all("span", attrs={"class": "proper", "data-props": True})
    ]


def _split_keywords(li_keywords: dict) -> list[str]:
    if li_keywords is None:
        return []
    keyword_tuple = li_keywords.get("title", "").strip().split(":")
    if len(keyword_tuple) == 0:
        return []
    keywords = keyword_tuple[1].split()
    keyphrases: list[str] = []
    for keyword in keywords:
        if len(keyphrases) == 0 or keyword[0].isupper():
            keyphrases.append(keyword)
        else:
            keyphrases[len(keyphrases) - 1] = keyphrases[len(keyphrases) - 1] + " " + keyword
    return keyphrases


class ECLASS(Dictionary):
    """Represent a release of the ECLASS dictionary.

    Allows to interact with the eCl@ss standard for classification and product
    description. It provides functionalities to search for eCl@ss classes and
    retrieve their properties based on different releases of the standard.

    Attributes:
        temp_dir (str): Overwrite temporary dictionary for caching the dict.
        properties (dict[str, PropertyDefinition]): Maps property IDs to
            PropertyDefinition instances.
        releases (dict[str, dict[str, ClassDefinition]]): Maps release versions
            to class definition objects.
        supported_releases (list[str]): A list of supported release versions.
        license (str): A link or note to the license or copyright of the
            dictionary.
        timeout (float): Time limit in seconds for downloads from ECLASS website.
            Defaults to 120s.
        class_search_pattern (str): URL pattern for class search on ECLASS
            website content search.
        property_search_pattern (str): URL pattern for property search on ECLASS
            website content search.
        language_idx (dict[str, str]): Maps the supported language code to the
            number used in the content search.
        properties_download_failed (dict[str, set[str]]): Maps release versions
            to a set of property ids, that could not be downloaded

    """

    class_search_pattern: str = "https://eclass.eu/en/eclass-standard/search-content/show?tx_eclasssearch_ecsearch%5Bdischarge%5D=0&tx_eclasssearch_ecsearch%5Bid%5D={class_id}&tx_eclasssearch_ecsearch%5Blanguage%5D={language}&tx_eclasssearch_ecsearch%5Bversion%5D={release}"
    property_search_pattern: str = "https://eclass.eu/en/eclass-standard/search-content/show?tx_eclasssearch_ecsearch%5Bcc2prdat%5D={property_id}&tx_eclasssearch_ecsearch%5Bdischarge%5D=0&tx_eclasssearch_ecsearch%5Bid%5D=-1&tx_eclasssearch_ecsearch%5Blanguage%5D={language}&tx_eclasssearch_ecsearch%5Bversion%5D={release}"
    releases: ClassVar[dict[str, dict[str, ClassDefinition]]] = {}
    properties: ClassVar[dict[str, PropertyDefinition]] = {}
    properties_download_failed: ClassVar[dict[str, set[str]]] = {}
    supported_releases: ClassVar[list[str]] = [
        "14.0",
        "13.0",
        "12.0",
        "11.1",
        "11.0",
        "10.1",
        "10.0.1",
        "9.1",
        "9.0",
        "8.1",
        "8.0",
        "7.1",
        "7.0",
        "6.2",
        "6.1",
        "5.14",
    ]
    license = "https://eclass.eu/en/eclass-standard/licenses"
    language_idx: ClassVar[dict[str, str]] = {"de": "0", "en": "1", "fr": "2", "cn": "3"}

    def __init__(self, release: str = "14.0", temp_dir: str | None = None) -> None:
        """Initialize ECLASS dictionary with a specified eCl@ss release version.

        Arguments:
            release (str): The release version of the eCl@ss standard to be
                used. Defaults to '14.0'.
            temp_dir (str): Set the temporary directory. Will be used to load
                releases from file, the first time the release is used.

        """
        super().__init__(release, temp_dir)
        if release not in self.properties_download_failed:
            self.properties_download_failed[release] = set()

    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """Retrieve a list of property definitions for the given ECLASS class.

        If the class properties are already stored in the `classes` property,
        they are returned directly. Otherwise, an HTML page is downloaded based
        on the eclass_class_search_pattern and the parsed HTML is used to obtain
        the properties.

        Currently only concrete classes (level 4, not endingin with 00) are
        supported.

        Arguments:
            class_id (str): The ID of the eCl@ss class for which to retrieve
            properties, e.g. 27274001.

        Returns:
            list[PropertyDefinition]: A list of PropertyDefinition instances
                                      associated with the specified class ID.

        """
        parsed_class_id = self.parse_class_id(class_id)
        if parsed_class_id is None:
            return []
        eclass_class = self.classes.get(parsed_class_id)
        if eclass_class is None:
            logger.info(
                "Download class and property definitions for %s in release %s",
                parsed_class_id,
                self.release,
            )
            html_content = self._download_html(self.get_class_url(parsed_class_id))
            if html_content is None:
                return []
            eclass_class = self._parse_html_eclass_class(html_content)
            if eclass_class is None:
                return []
        return eclass_class.properties

    def get_property(self, property_id: str) -> PropertyDefinition | None:
        """Retrieve a single property definition from the dictionary.

        It is returned directly, if the property definition is already stored in
        the `properties` property. Otherwise, an HTML page is downloaded based
        on the eclass_property_search_pattern and the parsed HTML is used to
        obtain the definition. The definition is stored in the dictionary class.
        If the download fails, the property_id is saved in
        `properties_download_failed`. The download is skipped next time.

        The eclass_property_search_pattern based search doesn't retrieve units.

        Arguments:
            property_id (str): The IRDI of the eCl@ss property,
                e.g. 0173-1#02-AAQ326#002.

        Returns:
            PropertyDefinition: The requested PropertyDefinition instance.

        """
        if self.check_property_irdi(property_id) is False:
            logger.warning(
                "Property id should be IRDI: 0173-1#02-([A-Z]{3}[0-9]{3})#([0-9]{3}), got: %s",
                property_id,
            )
            return None
        property_ = self.properties.get(property_id)
        if property_ is None:
            if property_id in self.properties_download_failed.get(self.release, {}):
                logger.debug(
                    "Property %s definition download failed already. Skipping download.",
                    property_id,
                )
                return None

            logger.info(
                "Property %s definition not found in dictionary, try download.",
                property_id,
            )
            html_content = self._download_html(self.get_property_url(property_id))
            if html_content is None:
                self.properties_download_failed[self.release].add(property_id)
                return None
            property_ = self._parse_html_eclass_property(html_content, property_id)
            if property_ is None:
                self.properties_download_failed[self.release].add(property_id)
                return None
            logger.debug(
                "Add new property %s without class to dictionary: %s",
                property_id,
                property_.name,
            )
            self.properties[property_id] = property_
        return property_

    def _parse_html_eclass_class(self, html_content: str) -> ClassDefinition | None:
        soup = BeautifulSoup(html_content, "html.parser")
        # TODO: get IRDI instead of id, e.g.: 0173-1#01-AGZ376#020,
        # which is = data-cc in span of value lists
        class_hierarchy = soup.find("ul", attrs={"class": "tree-simple-list"})
        if not isinstance(class_hierarchy, Tag):
            return None
        li_elements = class_hierarchy.find_all("li", attrs={"id": True})
        eclass_class = None
        for li in li_elements:
            identifier = li["id"].replace("node_", "")
            eclass_class = self.classes.get(identifier)
            if eclass_class is None:
                a_description = li.find("a", attrs={"title": True})
                eclass_class = ClassDefinition(
                    id=identifier,
                    name=" ".join(li.getText().strip().split()[1:]),
                    description=a_description["title"] if a_description is not None else "",
                    keywords=_split_keywords(
                        li.find("i", attrs={"data-toggle": "tooltip"}),
                    ),
                )
                logger.debug("Add class %s: %s", identifier, eclass_class.name)
                self.classes[identifier] = eclass_class
            else:
                logger.debug("Found class %s: %s", identifier, eclass_class.name)
        if eclass_class is None:
            return None
        eclass_class.properties = self._parse_html_eclass_properties(soup)
        return eclass_class

    def _parse_html_eclass_properties(self, soup: BeautifulSoup) -> list[PropertyDefinition]:
        properties = []
        li_elements = soup.find_all("li")
        for li in li_elements:
            span = li.find("span", attrs={"data-props": True})
            if span:
                data_props = span["data-props"].replace("&quot;", '"')
                data = json.loads(data_props)
                id_ = data["IRDI_PR"]
                property_ = self.properties.get(id_)
                if property_ is None:
                    logger.debug("Add new property %s: %s", id_, data["preferred_name"])
                    property_ = self._parse_html_eclass_property_from_class(span, data, id_)
                    self.properties[id_] = property_
                else:
                    logger.debug("Add existing property %s: %s", id_, property_.name)
                properties.append(property_)
        return properties

    def _parse_html_eclass_property_from_class(
        self,
        span: Tag,
        data: dict,
        id_: str,
    ) -> PropertyDefinition:
        property_ = PropertyDefinition(
            id_,
            {data["language"]: data["preferred_name"]},
            eclass_datatype_to_type.get(data["data_type"], "string"),
            {data["language"]: data["definition"]},
        )

        # Check for physical unit
        if (
            ("unit_ref" in data)
            and ("short_name" in data["unit_ref"])
            and data["unit_ref"]["short_name"] != ""
        ):
            property_.unit = data["unit_ref"]["short_name"]

        # Check for value list
        value_list_span = span.find_next_sibling("span")
        if value_list_span and isinstance(value_list_span, Tag):
            logger.debug("Download value list for %s", property_.name[data["language"]])
            self._parse_html_eclass_valuelist(property_, value_list_span)
        return property_

    def _parse_html_eclass_property(
        self,
        html_content: str,
        property_id: str,
    ) -> PropertyDefinition | None:
        soup = BeautifulSoup(html_content, "html.parser")

        if not soup.find(lambda tag: tag.name == "th" and tag.text.strip() == "Preferred name"):
            logger.warning("Couldn't parse 'preferred name' for %s", property_id)
            return None
        preferred_name = _extract_attribute_from_eclass_property_soup(soup, "Preferred name")
        definition = _extract_attribute_from_eclass_property_soup(soup, "Definition")
        return PropertyDefinition(
            id=property_id,
            name={self.language: preferred_name} if preferred_name else {},
            type=eclass_datatype_to_type.get(
                _extract_attribute_from_eclass_property_soup(soup, "Data type"),
                "string",
            ),
            definition={self.language: definition} if definition else {},
            values=_extract_values_from_eclass_property_soup(soup),
        )

    def get_class_url(self, class_id: str) -> str:
        """Return the class URL for ECLASS content search using the class_search_pattern."""
        return self.class_search_pattern.format(
            class_id=class_id,
            release=self.release,
            language=self.language_idx.get(self.language, "1"),
        )

    def get_property_url(self, property_id: str) -> str:
        """Return the property URL for ECLASS content search using the property_search_pattern."""
        return self.property_search_pattern.format(
            property_id=quote(property_id),
            release=self.release,
            language=self.language_idx.get(self.language, "1"),
        )

    @staticmethod
    def check_property_irdi(property_id: str) -> bool:
        """Check the format of the property IRDI.

        Regex: 0173-1#02-([A-Z]{3}[0-9]{3})#([0-9]{3})
        IRDI must begin with 0173-1 to belong to ECLASS.
        IRDI must represent a property (not a class, value, ...): #02
        IRDI must have 3 upper letters and 3 digits as property id: ABC123
        IRDI must have 3 digits as version, e.g. #005
        """
        re_match = re.fullmatch(r"0173-1#02-([A-Z]{3}[0-9]{3})#([0-9]{3})", property_id)
        return re_match is not None

    @staticmethod
    def parse_class_id(class_id: str) -> str | None:
        """Search for a valid eclass 8 digit class id and returns it.

        Must be an 8 digit number (underscores, dash and whitespace alike chars
        are ignored). Only concrete (level 4) classes will be returned.
        """
        # TODO: also support eclass IRDIs and prefix "ECLASS" or Postfix "(BASIC)" etc.
        # https://eclass.eu/support/content-creation/release-process/release-numbers-and-versioning
        if class_id is None:
            return None
        class_id = str(class_id)
        class_id = re.sub(r"[-_]|\s", "", class_id)
        class_id = class_id[:8]
        if len(class_id) != 8 or not class_id.isdigit():  # noqa: PLR2004
            logger.warning("Class id has unknown format. Should be 8 digits, but got: %s", class_id)
            return None
        if class_id.endswith("00"):
            logger.warning(
                "No properties for %s. Currently only concrete (level 4) classes are supported.",
                class_id,
            )
            # Because the eclass content-search only lists properties in level 4 for classes
            return None
        return class_id

    def _load_from_release_csv_zip(self, filepath_str: str | Path) -> None:  # noqa: C901, PLR0912, PLR0915
        logger.info("Load ECLASS dictionary from CSV release zip: %s", filepath_str)

        filepath = Path(filepath_str)
        zip_dir = filepath.parent / filepath.stem
        if not zip_dir.exists():
            try:
                zip_dir.mkdir(parents=True)
                shutil.unpack_archive(filepath, zip_dir)
            except (shutil.ReadError, FileNotFoundError, PermissionError) as e:
                logger.warning("Error while unpacking ECLASS CSV Release: %s", e)
                if zip_dir.exists():
                    shutil.rmtree(zip_dir)

        csv_filename = f"ECLASS{self.release.replace('.','_')}_{{}}_{self.language}.csv"

        units = {}
        with open(zip_dir / csv_filename.format("UN"), encoding="utf-8") as file:
            # PreferredName;ShortName;Definition;Source;Comment;SINotation;SIName;
            # DINNotation;ECEName;ECECode;NISTName;IECClassification;IrdiUN;
            # NameOfDedicatedQuantity
            reader = csv.reader(file, delimiter=";")
            next(reader, None)
            for row in reader:
                units[row[12]] = row[1]  # IrdiUN -> ShortName

        with open(zip_dir / csv_filename.format("PR"), encoding="utf-8") as file:
            # Supplier;IdPR;Identifier;VersionNumber;VersionDate;RevisionNumber;
            # PreferredName;ShortName;Definition;SourceOfDefinition;Note;Remark;
            # PreferredSymbol;IrdiUN;ISOLanguageCode;ISOCountryCode;Category;
            # AttributeType;DefinitionClass;DataType;IrdiPR;CurrencyAlphaCode
            reader = csv.reader(file, delimiter=";")
            next(reader, None)
            for row in reader:
                irdi = row[20]  # IrdiPR
                property_: PropertyDefinition | None = PropertyDefinition(
                    id=irdi,
                    name={row[14]: row[6]},  # ISOLanguageCode: PreferredName
                    type=eclass_datatype_to_type.get(row[19], "string"),  # DataType
                    definition={row[14]: row[8]},  # ISOLanguageCode: Definition
                    unit=units.get(row[13], ""),  # IrdiUN
                )
                self.properties[irdi] = property_  # type: ignore[assignment]

        values = {}
        with open(zip_dir / csv_filename.format("VA"), encoding="utf-8") as file:
            # Supplier;IdVA;Identifier;VersionNumber;RevisionNumber;VersionDate;
            # PreferredName;ShortName;Definition;Reference;ISOLanguageCode;
            # ISOCountryCode;IrdiVA;DataType
            reader = csv.reader(file, delimiter=";")
            next(reader, None)
            for row in reader:
                values[row[12]] = {  # IrdiVA
                    "value": row[6],  # PreferredName
                    "id": row[12],  # IrdiVA
                    "definition": row[8],  # Definition
                }

        with open(
            zip_dir / csv_filename.format("CC_PR_VA_suggested_incl_constraints"),
            encoding="utf-8",
        ) as file:
            # IrdiCC;IrdiPR;IrdiVA;Constraint
            reader = csv.reader(file, delimiter=";")
            next(reader, None)
            current_property_id = None
            property_values: list = []

            for row in reader:
                property_id = row[1]
                value_id = row[2]

                if current_property_id is None:
                    current_property_id = property_id

                if property_id != current_property_id:
                    property_ = self.properties.get(current_property_id)
                    if property_:
                        property_.values = property_values
                    current_property_id = property_id
                    property_values = []

                value = values.get(value_id)
                if value:
                    property_values.append(value)

            # Update the last property
            if property_values and current_property_id is not None:
                property_ = self.properties.get(current_property_id)
                if property_:
                    property_.values = property_values

        class_property_map: dict[str, list] = defaultdict(list)
        with open(zip_dir / csv_filename.format("CC_PR"), encoding="utf-8") as file:
            # SupplierIdCC;IdCC;ClassCodedName;SupplierIdPR;IdPR;IrdiCC;IrdiPR;
            # PreferredNameBlockAspect
            reader = csv.reader(file, delimiter=";")
            next(reader, None)
            for row in reader:
                class_property_map[row[2]].append(
                    self.properties.get(row[6], []),
                )  # ClassCodedName -> IrdiPR -> PropertyDefinition

        class_keyword_map = defaultdict(list)
        with open(zip_dir / csv_filename.format("KWSY"), encoding="utf-8") as file:
            # SupplierKW/SupplierSY;Identifier;VersionNumber;IdCC/IdPR;
            # KeywordValue/SynonymValue;Explanation;ISOLanguageCode;
            # ISOCountryCode;TypeOfTargetSE;IrdiTarget;IrdiKW/IrdiSY;TypeOfSE
            reader = csv.reader(file, delimiter=";")
            next(reader, None)
            for row in reader:
                if row[8] != "CC":  # TypeOfTargetSE
                    continue
                class_keyword_map[row[1]].append(row[4])  # Identifier -> KeywordValue/SynonymValue

        with open(zip_dir / csv_filename.format("CC"), encoding="utf-8") as file:
            # Supplier;IdCC;Identifier;VersionNumber;VersionDate;RevisionNumber;
            # CodedName;PreferredName;Definition;ISOLanguageCode;ISOCountryCode;
            # Note;Remark;Level;MKSubclass;MKKeyword;IrdiCC
            reader = csv.reader(file, delimiter=";")
            next(reader, None)
            for row in reader:
                code = row[6]  # CodedName
                if row[13] != "4":  # Level
                    continue
                class_ = ClassDefinition(
                    id=code,
                    name=row[7],  # PreferredName
                    description=row[8],  # Definition
                    keywords=class_keyword_map[row[2]],
                    properties=class_property_map[code],
                )
                self.classes[code] = class_

    def load_from_file(self, filepath: str | None = None) -> bool:
        """Load a whole ECLASS release from CSV zip file.

        Searches in `self.tempdir` for "ECLASS-<release>-...CSV....zip" file,
        if no filepath is given. Otherwise, searches for cached dicts.
        """
        temp_path = Path(self.temp_dir)
        if filepath is None and temp_path.exists():
            for filename in temp_path.iterdir():
                if re.match(f"{self.name}-{self.release}.*CSV.*\\.zip",
                            str(filename), re.IGNORECASE):
                    try:
                        self._load_from_release_csv_zip(temp_path / filename)
                    except OSError as e:
                        logger.warning("Error while loading csv zip '%s': %s", str(filename), e)
                        continue
                    return True
        return super().load_from_file(filepath)

    def _parse_html_eclass_valuelist(
        self,
        property_: PropertyDefinition,
        span: Tag,
    ) -> None:
        if not isinstance(span["data-cc"], str) or not isinstance(span["data-json"], str):
            return
        valuelist_url = (
            "https://eclass.eu/?discharge=basic&cc="
            + span["data-cc"].replace("#", "%")
            + "&data="
            + quote(span["data-json"])
        )
        # https://eclass.eu/?discharge=basic&cc=0173-1%2301-AGZ376%23020&data=%7B%22identifier%22%3A%22BAD853%22%2C%22preferred_name%22%3A%22cascadable%22%2C%22short_name%22%3A%22%22%2C%22definition%22%3A%22whether%20a%20base%20device%20(host)%20can%20have%20a%20subsidiary%20device%20(guest)%20connected%20to%20it%20by%20means%20of%20a%20cable%22%2C%22note%22%3A%22%22%2C%22remark%22%3A%22%22%2C%22formular_symbol%22%3A%22%22%2C%22irdiun%22%3A%22%22%2C%22attribute_type%22%3A%22INDIRECT%22%2C%22definition_class%22%3A%220173-1%2301-RAA001%23001%22%2C%22data_type%22%3A%22BOOLEAN%22%2C%22IRDI_PR%22%3A%220173-1%2302-BAD853%23008%22%2C%22language%22%3A%22en%22%2C%22version%22%3A%2213_0%22%2C%22values%22%3A%5B%7B%22IRDI_VA%22%3A%220173-1%2307-CAA017%23003%22%7D%2C%7B%22IRDI_VA%22%3A%220173-1%2307-CAA016%23001%22%7D%5D%7D
        valuelist = self._download_html(valuelist_url)
        if valuelist is None:
            return
        valuelist_soup = BeautifulSoup(valuelist, "html.parser")
        for valuelist_span in valuelist_soup.find_all("span", attrs={"data-props": True}):
            try:
                valuelist_data = json.loads(valuelist_span["data-props"].replace("'", " "))
            except json.decoder.JSONDecodeError:
                logger.warning(
                    "Couldn't parse eclass property value: %s",
                    valuelist_span["data-props"],
                )
                continue
            value: dict[ValueDefinitionKeyType, str] = {"value": valuelist_data["preferred_name"]}
            if len(valuelist_data["definition"].strip()) > 0:
                value["definition"] = valuelist_data["definition"]
            # add valuelist_data["short_name"]
            # add valuelist_data["data_type"]
            property_.values.append(value)  # type: ignore[arg-type]
