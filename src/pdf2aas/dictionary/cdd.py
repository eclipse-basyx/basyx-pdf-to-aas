"""Class and functions to use Common Data Dictionary (CDD) as dictionary in PDF2AAS workflow."""

import logging
import re
from typing import ClassVar, Literal

import requests
import xlrd
from bs4 import BeautifulSoup

from .core import ClassDefinition, Dictionary, PropertyDefinition

logger = logging.getLogger(__name__)


def cdd_datatype_to_type(data_type: str) -> str:
    """Convert a cdd datatype to "class", "bool", "range", "numeric" or "string"."""
    if data_type.startswith("CLASS_REFERENCE_TYPE"):
        return "class"
    if data_type.startswith("ENUM_BOOLEAN_TYPE"):
        return "bool"
    if data_type.startswith("LEVEL(MIN,MAX)"):
        return "range"
    if "INT" in data_type or "REAL" in data_type:
        return "numeric"
    return "string"


IDX_CODE = 1
IDX_VERSION = 2
IDX_PREFERRED_NAME = 4
IDX_DEFINTION = 7
# CLASS xls files
IDX_INSTANCE_SHAREABLE = 16
# PROPERTY xls files
IDX_PRIMARY_UNIT = 12
IDX_DATA_TYPE = 14
# VALUELIST xls files
IDX_TERMINOLOGIES = 2
# VALUETERMS xls file
IDX_SYNONYMS = 5
IDX_SHORT_NAME = 6
IDX_SYMBOL = 12


class CDD(Dictionary):
    """Common Data Dictionary of IEC.

    Dictionary for multiple ISO/IEC standards (referred to as `domains`).
    The implementation uses "Free Attributes" from https://cdd.iec.ch/.
    C.f. `licence` for details.
    Class and property ids are IRDIs, e.g.: 0112/2///62683#ACC501#002
    Only the currently available release from the website is available.

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
        domains (dict): Lists IEC standards called "domains" in context of CDD
            with their representation in the URL, the standard name and the
            root class.
        timeout (float): Time limit in seconds for downloads from CDD website.
            Defaults to 120s.

    """

    releases: ClassVar[dict[dict[str, ClassDefinition]]] = {}
    properties: ClassVar[dict[str, PropertyDefinition]] = {}
    supported_releases: ClassVar[list[str]] = [
        "V2.0018.0002",
    ]
    license = "https://cdd.iec.ch/cdd/iec62683/iec62683.nsf/License?openPage"
    timeout: ClassVar[str] = 120

    # keys are the part of the IRDIs
    domains: ClassVar[dict[str, dict[str, str]]] = {
        "61360_7": {
            "standard": "IEC 61360-7",
            "name": "General items",
            "url": "https://cdd.iec.ch/cdd/common/iec61360-7.nsf",
            "class": "0112/2///61360_7#CAA000#001",
        },
        "61360_4": {
            "standard": "IEC 61360-4",
            "name": "Electric/electronic components",
            "url": "https://cdd.iec.ch/cdd/iec61360/iec61360.nsf",
            "class": "0112/2///61360_4#AAA000#001",
        },
        "61987": {
            "standard": "IEC 61987 series",
            "name": "Process automation",
            "url": "https://cdd.iec.ch/cdd/iec61987/iec61987.nsf",
            "class": "0112/2///61987#ABA000#002",
        },
        "62720": {
            "standard": "IEC 62720",
            "name": "Units of measurement",
            "url": "https://cdd.iec.ch/cdd/iec62720/iec62720.nsf",
            "class": "0112/2///62720#UBA000#001",
        },
        "62683": {
            "standard": "IEC 62683 series",
            "name": "Low voltage switchgear",
            "url": "https://cdd.iec.ch/cdd/iec62683/iec62683.nsf",
            "class": "0112/2///62683#ACC001#001",
        },
        "63213": {
            "standard": " IEC 63213",
            "name": "Measuring equipment for electrical quantities",
            "url": "https://cdd.iec.ch/cdd/iectc85/iec63213.nsf",
            "class": "0112/2///63213#KEA001#001",
        },
    }

    def __init__(
        self,
        release: str = "V2.0018.0002",
        temp_dir: str | None = None,
    ) -> None:
        """Initialize CDD dictionary.

        Arguments:
            release (str): Only the currently available release is supported,
                so that the release is only used for storing and loading files.
            temp_dir (str): Overwrite temporary dictionary for caching the dict.

        """
        super().__init__(release, temp_dir)
        # TODO: implement release based lookup?

    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """Get properties from the class in the dictionary or try to download otherwise.

        We are only using "FREE ATTRIBUTES" according to the IEC license agreement, c.f. section 5:
        ```
        5. FREE ATTRIBUTES
        FREE ATTRIBUTES are intended for the reference and mapping to dictionary
        entries/elements in the IEC CDD database and to enable electronic data exchange.
        YOU are allowed to print, copy, reproduce, distribute or otherwise exploit,
        whether commercially or not, in any way freely, internally in your organization
        or to a third party, the following attributes of the data elements in the database
        with or without contained values, also referred to as FREE ATTRIBUTES:

        • Identity number (Code and IRDI);
        • Version/Revision;
        • Name (Preferred name, Synonymous name, Short name, Coded name);
        • Value formats (Data type and Data format);
        • Property data element type
        • Superclass
        • Applicable properties
        • DET class
        • Symbol
        • Enumerated list of terms
        • Unit of measurement (IRDI, Preferred name, Short name, Codes of units,
          Code for unit, Code for alternate units, Code for unit list);
        ```
        """
        class_ = self.classes.get(class_id)
        if class_ is None:
            logger.info(
                "Download class and property definitions for %s in release %s",
                class_id,
                self.release,
            )
            class_ = self._download_cdd_class(self.get_class_url(class_id))
            if class_ is None:
                return []
        return class_.properties

    def get_class_url(self, class_id: str) -> str:
        """Convert the class id into a URL from https://cdd.iec.ch.

        The class id needs to be a IRDI starting with 0112/2////.
        Currently the version of the IRDI is ignored and the link leads to
        the most current version. Check the "Version history" field at the
        bottom of the page to find the correct version.

        Example id: 0112/2///62683#ACC501
        Exmaple url: https://cdd.iec.ch/cdd/iec62683/iec62683.nsf/classes/0112-2---62683%23ACC501?OpenDocument
        """
        standard_id_version = class_id.split("/")[-1].split("#")
        # TODO: find specified version
        if standard_id_version[0] not in self.domains:
            return None
        return "{}/classes/0112-2---{}%23{}?OpenDocument".format(
            self.domains[standard_id_version[0]]["url"],
            standard_id_version[0],
            standard_id_version[1],
        )

    def get_property_url(self, property_id: str) -> str:
        """Convert the property id into a URL from https://cdd.iec.ch.

        The property id needs to be a IRDI starting with 0112/2////.
        Currently the version of the IRDI is ignored and the link leads to
        the most current version. Check the "Version history" field at the
        bottom of the page to find the correct version.

        Example id: 0112/2///62683#ACE251
        Exmaple url: https://cdd.iec.ch/cdd/iec62683/iec62683.nsf/PropertiesAllVersions/0112-2---62683%23ACE251?OpenDocument
        """
        standard_id_version = property_id.split("/")[-1].split("#")
        # TODO: find specified version
        if standard_id_version[0] not in self.domains:
            return None
        return "{}/PropertiesAllVersions/0112-2---{}%23{}?OpenDocument".format(
            self.domains[standard_id_version[0]]["url"],
            standard_id_version[0],
            standard_id_version[1],
        )

    @staticmethod
    def _get_table_data(labels: list, label: str) -> str:
        for td in labels:
            if td.text == f"\n{label}: ":
                return td.find_next_sibling("td").text.lstrip("\n")
        return None

    def _download_cdd_class(self, url: str) -> ClassDefinition | None:
        html_content = self._download_html(url)
        if html_content is None:
            return None
        soup = BeautifulSoup(html_content, "html.parser")
        # TODO: resolve language to table (English --> L1, France = L2, ...) from div id="onglet"
        # TODO: translate the labels, e.g. Preferred name --> Nom préféré
        table = soup.find("table", attrs={"id": "contentL1"})
        tds = table.find_all("td", class_="label")

        class_id = self._get_table_data(tds, "IRDI")
        class_ = ClassDefinition(
            id=class_id,
            name=self._get_table_data(tds, "Preferred name"),
            # Probably non "FREE ATTRIBUTES", c.f. CDD license section 5
            # description=self._get_table_data(tds, 'Definition')  # noqa: ERA001
        )

        keywords = self._get_table_data(tds, "Synonymous name")
        if keywords and len(keywords.strip()) > 0:
            class_.keywords = keywords.split(", ")

        class_.properties = self._download_property_definitions(url, soup)
        self.classes[class_id] = class_
        return class_

    def _download_export_xls(
        self,
        export_html_content: str,
        selection: str,
    ) -> xlrd.sheet.Sheet | None:
        export_url = re.search(f'href="(.*{selection}.*)"', export_html_content)
        if export_url is None:
            return None
        export_url = f"https://cdd.iec.ch{export_url.group(1)}"

        try:
            response = requests.get(export_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("XLS download failed.")
            return None
        workbook = xlrd.open_workbook(file_contents=response.content)
        return workbook.sheet_by_index(0)

    def _download_property_definitions(
        self,
        class_url: str,
        class_html_soup: str,
    ) -> list[PropertyDefinition]:
        # export6 corresponds menu Export > All > Class and superclasses
        export_id = class_html_soup.find("input", {"id": "export6"}).get("onclick").split("'")[1]
        export_url = f"{class_url}&Click={export_id}"
        export_html_content = self._download_html(export_url)
        if export_html_content is None:
            return []

        property_sheet = self._download_export_xls(export_html_content, "PROPERTY")
        value_list_sheet = self._download_export_xls(export_html_content, "VALUELIST")
        value_terms_sheet = self._download_export_xls(export_html_content, "VALUETERMS")

        if property_sheet is None:
            return []

        properties = []
        for row in range(property_sheet.nrows):
            property_ = self._parse_property_xls_row(
                property_sheet.row_values(row),
                value_list_sheet,
                value_terms_sheet,
            )
            if property_ is not None:
                properties.append(property_)
        return properties

    def _parse_property_xls_row(
        self,
        row: list[str],
        value_list: xlrd.sheet.Sheet,
        value_terms: xlrd.sheet.Sheet,
    ) -> PropertyDefinition | None:
        if row[0].startswith("#"):
            return None
        type_ = row[IDX_DATA_TYPE]
        data_type = cdd_datatype_to_type(type_)
        if data_type == "class":
            return None

        property_id = f"{row[IDX_CODE]}#{int(row[IDX_VERSION]):03d}"
        if property_id in self.properties:
            return self.properties[property_id]

        property_ = PropertyDefinition(
            id=property_id,
            name={"en": row[IDX_PREFERRED_NAME]},
            type=data_type,
            definition={"en": row[IDX_DEFINTION]},
            unit=row[IDX_PRIMARY_UNIT] if len(row[IDX_PRIMARY_UNIT]) > 0 else "",
        )

        if value_list is not None and type_.startswith("ENUM") and "(" in type_:
            property_.values = self._parse_property_value_list(
                type_.split("(")[1][:-1],
                value_list,
                value_terms,
            )

        self.properties[property_id] = property_
        return property_

    def _parse_property_value_list(
        self,
        value_list_id: str,
        value_list: xlrd.sheet.Sheet,
        value_terms: xlrd.sheet.Sheet | None,
    ) -> list[str | dict[Literal["value", "id", "synonyms", "short_name", "symbol"], str]]:
        value_ids = []
        for row in value_list:
            if row[IDX_CODE].value == value_list_id:
                value_ids = row[IDX_TERMINOLOGIES].value[1:-1].split(",")
                break

        if value_terms is None:
            return value_ids
        values = []
        for value_id in value_ids:
            for row in value_terms:
                if row[IDX_CODE].value == value_id:
                    value = {
                        "value": row[IDX_PREFERRED_NAME].value,
                        "id": f"{row[IDX_CODE].value}#{int(row[IDX_VERSION].value):03d}",
                    }
                    if len(row[IDX_SYNONYMS].value) > 0:
                        value["synonyms"] = row[IDX_SYNONYMS].value.split(",")
                    if len(row[IDX_SHORT_NAME].value) > 0:
                        value["short_name"] = row[IDX_SHORT_NAME].value
                    # Probably non "FREE ATTRIBUTES", c.f. CDD license section 5
                    # if len(row[7].value) > 0:
                    #     value['definition'] = row[7].value  # noqa: ERA001
                    # if len(row[9].value) > 0:
                    #     value['definition_source'] = row[9].value  # noqa: ERA001
                    # if len(row[10].value) > 0:
                    #     value['note'] = row[10].value  # noqa: ERA001
                    # if len(row[11].value) > 0:
                    #     value['remark'] = row[11].value  # noqa: ERA001
                    if len(row[IDX_SYMBOL].value) > 0:
                        value["symbol"] = row[IDX_SYMBOL].value
                    values.append(value)
                    break
        return values

    @staticmethod
    def parse_class_id(class_id: str) -> str | None:
        """Search for a valid CDD IRDI in `class_id` and returns it.

        The IRDI is searched by regex containing:
        Regex: 0112/2///[A-Z0-9_]+#[A-Z]{3}[0-9]{3}#[0-9]{3}
        IRDI must begin with 0112/2/// to belong to IEC CDD.
        IEC standard / domain: [A-Z0-9_]+
        IRDI must have 3 upper letters and 3 digits as property id: #ABC123
        IRDI must have 3 digits as version, e.g. #005
        """
        if class_id is None:
            return None
        class_id = re.sub(r"[-]|\s", "", class_id)
        class_id = re.search(
            r"0112/2///[A-Z0-9_]+#[A-Z]{3}[0-9]{3}#[0-9]{3}",
            class_id,
            re.IGNORECASE,
        )
        if class_id is None:
            return None
        return class_id.group(0)

    def download_sub_class_instances(self, class_id: str) -> None:
        """Download all instances below the class with the given class id.

        Instances are recognized by downloading the export xls file
        "Attributes > Class and subclasses" and checking the column
        "InstanceShareable".
        """
        class_url = self.get_class_url(class_id)
        html_content = self._download_html(class_url)
        if html_content is None:
            return
        class_soup = BeautifulSoup(html_content, "html.parser")

        # export2 corresponds menu Export > Attributes > Class and subclasses
        export_id = class_soup.find("input", {"id": "export2"}).get("onclick").split("'")[1]
        export_url = f"{class_url}&Click={export_id}"
        export_html_content = self._download_html(export_url)
        if export_html_content is None:
            return

        class_list = self._download_export_xls(export_html_content, "CLASS")
        for row in class_list:
            if row[0].value.startswith("#"):
                continue
            if row[IDX_INSTANCE_SHAREABLE].value != "true":
                logger.debug(
                    "Skipped %s because InstanceSharable value '%s' != true.",
                    row[1].value,
                    row[IDX_INSTANCE_SHAREABLE].value,
                )
                continue
            class_ = self._download_cdd_class(
                self.get_class_url(f"{row[IDX_CODE].value}#{int(row[IDX_VERSION].value):03d}"),
            )
            if class_ is not None:
                logger.info("Parsed %s with %s properties.", class_.id, len(class_.properties))

    def download_full_release(self) -> None:
        """Download all class instances from the defined`domains`.

        Make sure to comply with CDD license agreement, especially section 7
        and 8.
        """
        logger.warning(
            "Make sure to comply with CDD license agreement, especially section 7 and 8.",
        )
        for domain in self.domains.values():
            logger.info(
                "Downloading classes of domain: %s (%s)",
                domain["name"],
                domain["standard"],
            )
            self.download_sub_class_instances(domain["class"])
