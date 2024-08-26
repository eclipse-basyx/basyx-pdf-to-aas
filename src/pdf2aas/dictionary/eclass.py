import json
import logging
from urllib.parse import quote
import re

import requests
from bs4 import BeautifulSoup

from .core import Dictionary, ClassDefinition, PropertyDefinition

logger = logging.getLogger(__name__)

eclass_datatype_to_type = {
    "BOOLEAN": "bool",
    "INTEGER_COUNT": "numeric",
    "INTEGER_MEASURE": "numeric",
    "REAL_COUNT": "numeric",
    "REAL_CURRENCY": "numeric",
    "REAL_MEASURE": "numeric",
    "STRING": "string",
    "STRING_TRANSLATEABLE": "string",
    "URL": "string",
    # TODO Map: DATE, RATIONAL, RATIONAL_MEASURE, REFERENCE, TIME, TIMESTAMP, AXIS1, AXIS2, AXIS3
}

def extract_attribute_from_eclass_property_soup(soup, search_text):
    th = soup.find(lambda tag: tag.name == "th" and tag.text.strip() == search_text)
    if th:
        td = th.find_next_sibling('td')
        if td:
            return td.text
    return None

def extract_values_from_eclass_property_soup(soup):
    values = []
    for span in soup.find_all('span', attrs={"class": "proper", "data-props": True}):
        values.append(span.text)
    return values

def parse_html_eclass_valuelist(property, span):
    valuelist_url = (
        "https://eclass.eu/?discharge=basic"
        + "&cc="
        + span["data-cc"].replace("#", "%")
        + "&data="
        + quote(span["data-json"])
    )
    # https://eclass.eu/?discharge=basic&cc=0173-1%2301-AGZ376%23020&data=%7B%22identifier%22%3A%22BAD853%22%2C%22preferred_name%22%3A%22cascadable%22%2C%22short_name%22%3A%22%22%2C%22definition%22%3A%22whether%20a%20base%20device%20(host)%20can%20have%20a%20subsidiary%20device%20(guest)%20connected%20to%20it%20by%20means%20of%20a%20cable%22%2C%22note%22%3A%22%22%2C%22remark%22%3A%22%22%2C%22formular_symbol%22%3A%22%22%2C%22irdiun%22%3A%22%22%2C%22attribute_type%22%3A%22INDIRECT%22%2C%22definition_class%22%3A%220173-1%2301-RAA001%23001%22%2C%22data_type%22%3A%22BOOLEAN%22%2C%22IRDI_PR%22%3A%220173-1%2302-BAD853%23008%22%2C%22language%22%3A%22en%22%2C%22version%22%3A%2213_0%22%2C%22values%22%3A%5B%7B%22IRDI_VA%22%3A%220173-1%2307-CAA017%23003%22%7D%2C%7B%22IRDI_VA%22%3A%220173-1%2307-CAA016%23001%22%7D%5D%7D
    valuelist = download_html(valuelist_url)
    valuelist_soup = BeautifulSoup(valuelist, "html.parser")
    for valuelist_span in valuelist_soup.find_all("span", attrs={"data-props": True}):
        try:
            valuelist_data = json.loads(valuelist_span["data-props"].replace("'", " "))
            value = {"value": valuelist_data["preferred_name"]}
            if len(valuelist_data["definition"].strip()) > 0:
                value['definition'] = valuelist_data["definition"]
            # valuelist_data["short_name"]
            # valuelist_data["data_type"]
            property.values.append(value)
        except json.decoder.JSONDecodeError:
            logger.warning("Couldn't parse eclass property value:" + valuelist_span["data-props"])

def parse_html_eclass_property(span, data, id):
    property = PropertyDefinition(
        id,
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
        property.unit = data["unit_ref"]["short_name"]

    # Check for value list
    value_list_span = span.find_next_sibling("span")
    if value_list_span:
        logger.debug("Download value list for " + property.name[data["language"]])
        parse_html_eclass_valuelist(property, value_list_span)
    return property

def split_keywords(li_keywords):
    if li_keywords is None:
        return []
    keywords = li_keywords.get("title").strip().split(":")[1].split()
    keyphrases = []
    for keyword in keywords:
        if len(keyphrases) == 0 or keyword[0].isupper():
            keyphrases.append(keyword)
        else:
            keyphrases[len(keyphrases) - 1] = (
                keyphrases[len(keyphrases) - 1] + " " + keyword
            )
    return keyphrases

def download_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"HTML download failed: {e}")
        return None

class ECLASS(Dictionary):
    """
    ECLASS is a class designed to interact with the eCl@ss standard for classification
    and product description. It provides functionalities to search for eCl@ss classes
    and retrieve their properties based on different releases of the standard.

    Attributes:
        eclass_class_search_pattern (str): URL pattern for class search.
        eclass_property_search_pattern (str): URL pattern for property search.
        properties_download_failed (dict[str, set[str]]): Maps release versions to a set of property ids, that could not be downloaded.
    """

    class_search_pattern:    str = "https://eclass.eu/en/eclass-standard/search-content/show?tx_eclasssearch_ecsearch%5Bdischarge%5D=0&tx_eclasssearch_ecsearch%5Bid%5D={class_id}&tx_eclasssearch_ecsearch%5Blanguage%5D={language}&tx_eclasssearch_ecsearch%5Bversion%5D={release}"
    property_search_pattern: str = "https://eclass.eu/en/eclass-standard/search-content/show?tx_eclasssearch_ecsearch%5Bcc2prdat%5D={property_id}&tx_eclasssearch_ecsearch%5Bdischarge%5D=0&tx_eclasssearch_ecsearch%5Bid%5D=-1&tx_eclasssearch_ecsearch%5Blanguage%5D={language}&tx_eclasssearch_ecsearch%5Bversion%5D={release}"
    releases: dict[dict[str, ClassDefinition]] = {}
    properties: dict[str, PropertyDefinition] = {}
    properties_download_failed: dict[str, set[str]] = {}
    supported_releases = [
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

    def __init__(self, release="14.0", temp_dir=None) -> None:
        """
        Initializes the ECLASS instance with a specified eCl@ss release version.

        Args:
            release (str): The release version of the eCl@ss standard to be used.
                           Defaults to '14.0'.
            temp_dir (str): Set the temporary directory. Will be used to load
                            releases from file, the first time the release is used.
        """
        super().__init__(release, temp_dir)
        if release not in self.properties_download_failed:
            self.properties_download_failed[release] = set()

    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        """
        Retrieves a list of property definitions for the given eCl@ss class ID, e.g. 27274001.

        If the class properties are already stored in the `classes` property, they
        are returned directly. Otherwise, an HTML page is downloaded based on the
        eclass_class_search_pattern and the parsed HTML is used to obtain the
        properties.
        Currently only concrete classes (level 4, not endingin with 00) are supported.

        Args:
            class_id (str): The ID of the eCl@ss class for which to retrieve properties, e.g. 27274001.

        Returns:
            list[PropertyDefinition]: A list of PropertyDefinition instances
                                      associated with the specified class ID.
        """
        class_id = self.parse_class_id(class_id)
        if class_id is None:
            return []
        eclass_class = self.classes.get(class_id)
        if eclass_class is None:
            logger.info(f"Download class and property definitions for {class_id} in release {self.release}")
            html_content = download_html(self.get_class_url(class_id))
            if html_content is None:
                return []
            eclass_class = self.__parse_html_eclass_class(html_content)
        return eclass_class.properties
    
    def get_property(self, property_id: str) -> PropertyDefinition:
        """
        Retrieves a single property definition from the dictionary.

        It is returned directly, if the property definition is already stored in
        the `properties` property. Otherwise, an HTML page is downloaded based on
        the eclass_property_search_pattern and the parsed HTML is used to obtain
        the definition. The definition is stored in the dictionary class.
        If the download fails, the property_id is saved in `properties_download_failed`.
        The download is skipped next time.
        
        The eclass_property_search_pattern based search doesn't retrieve units.

        Args:
            property_id (str): The IRDI of the eCl@ss property, e.g. 0173-1#02-AAQ326#002.

        Returns:
            PropertyDefinition: The requested PropertyDefinition instance.
        """
        if self.check_property_irdi(property_id) is False:
            logger.warning(f"Property id has wrong format, should be IRDI: 0173-1#02-([A-Z]{{3}}[0-9]{{3}})#([0-9]{{3}}), got instead: {property_id}")
            return None
        property = self.properties.get(property_id)
        if property is None:
            if property_id in self.properties_download_failed.get(self.release):
                logger.debug(f"Property {property_id} definition download failed already. Skipping download.")
                return None

            logger.info(f"Property {property_id} definition not found in dictionary, try download.")
            html_content = download_html(self.get_property_url(property_id))
            if html_content is None:
                self.properties_download_failed[self.release].add(property_id)
                return None
            property = self.__parse_html_eclass_property(html_content, property_id)
            if property is None:
                self.properties_download_failed[self.release].add(property_id)
                return None
            logger.debug(f"Add new property {property_id} without class to dictionary: {property.name}")
            self.properties[property_id] = property
        return property

    def __parse_html_eclass_class(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        # TODO get IRDI instead of id, e.g.: 0173-1#01-AGZ376#020, which is = data-cc in span of value lists
        class_hierarchy = soup.find("ul", attrs={"class": "tree-simple-list"})
        li_elements = class_hierarchy.find_all("li", attrs={"id": True})
        for li in li_elements:
            identifier = li["id"].replace("node_", "")
            eclass_class = self.classes.get(identifier)
            if eclass_class is None:
                a_description = li.find("a", attrs={"title": True})
                eclass_class = ClassDefinition(
                    id=identifier,
                    name=" ".join(li.getText().strip().split()[1:]),
                    description=a_description["title"]
                    if a_description is not None
                    else "",
                    keywords=split_keywords(
                        li.find("i", attrs={"data-toggle": "tooltip"})
                    ),
                )
                logger.debug(f"Add class {identifier}: {eclass_class.name}")
                self.classes[identifier] = eclass_class
            else:
                logger.debug(f"Found class {identifier}: {eclass_class.name}")
        eclass_class.properties = self.__parse_html_eclass_properties(soup)
        return eclass_class
    
    def __parse_html_eclass_properties(self, soup: BeautifulSoup):
        properties = []
        li_elements = soup.find_all("li")
        for li in li_elements:
            span = li.find("span", attrs={"data-props": True})
            if span:
                data_props = span["data-props"].replace("&quot;", '"')
                data = json.loads(data_props)
                id = data["IRDI_PR"]
                property = self.properties.get(id)
                if property is None:
                    logger.debug(f"Add new property {id}: {data['preferred_name']}")
                    property = parse_html_eclass_property(span, data, id)
                    self.properties[id] = property
                else:
                    logger.debug(f"Add existing property {id}: {property.name}")
                properties.append(property)
        return properties

    def __parse_html_eclass_property(html_content, property_id):
        soup = BeautifulSoup(html_content, 'html.parser')
        # with open("temp/property.html", 'w', encoding="utf-8") as file:
        #     file.write(html_content)

        if not soup.find(lambda tag: tag.name == "th" and tag.text.strip() == "Preferred name"):
            logger.warning(f"Couldn't parse 'preferred name' for {property_id}")
            return None
        property = PropertyDefinition(
            id=property_id,
            name={'en': extract_attribute_from_eclass_property_soup(soup, "Preferred name")},
            type=eclass_datatype_to_type.get(extract_attribute_from_eclass_property_soup(soup, "Data type"), "string"),
            definition={'en':extract_attribute_from_eclass_property_soup(soup, "Definition")},
            values=extract_values_from_eclass_property_soup(soup)
        )
        return property

    def get_class_url(self, class_id: str) -> str | None:
        return self.class_search_pattern.format(
                    class_id=class_id,
                    release=self.release,
                    language="1",  # 0=de, 1=en, 2=fr, 3=cn
                )
    def get_property_url(self,property_id: str) -> str | None:
        return self.property_search_pattern.format(
                    property_id=quote(property_id),
                    release=self.release,
                    language="1",  # 0=de, 1=en, 2=fr, 3=cn
                )

    @staticmethod
    def check_property_irdi(property_id:str) -> bool:
        """
        Checks the format of the property IRDI.
        
        Regex: 0173-1#02-([A-Z]{3}[0-9]{3})#([0-9]{3})
        IRDI must begin with 0173-1 to belong to ECLASS.
        IRDI must represent a property (not a class, value, ...): #02
        IRDI must have 3 upper letters and 3 digits as property id: ABC123
        IRDI must have 3 digits as version, e.g. #005 
        """
        re_match = re.fullmatch(r"0173-1#02-([A-Z]{3}[0-9]{3})#([0-9]{3})", property_id)
        if re_match is None:
            return False
        return True

    @staticmethod
    def parse_class_id(class_id):
        """
        Checks the format of the eclass class id and returns it in 8 digit format.
        
        Must be an 8 digit number (underscores, dash and whitespace alike chars are ignored).
        Only concrete (level 4) classes will be returned.
        """
        #TODO also support eclass IRDIs and prefix "ECLASS" or Postfix "(BASIC)" etc.
        #https://eclass.eu/support/content-creation/release-process/release-numbers-and-versioning
        if class_id is None:
            return None
        class_id = str(class_id) 
        class_id = re.sub(r'[-_]|\s', '', class_id)
        class_id = class_id[:8]
        if len(class_id) != 8 or not class_id.isdigit():
            logger.warning(
                f"Class id has unknown format. Should be 8 digits, but got: {class_id}"
            )
            return None
        if class_id.endswith("00"):
            logger.warning(
                f"No properties for {class_id}. Currently only concrete (level 4) classes are supported."
            )
            # Because the eclass content-search only lists properties in level 4 for classes
            return None
        return class_id