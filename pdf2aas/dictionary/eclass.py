from dictionary.core import Dictionary, PropertyDefinition, ClassDefinition
from bs4 import BeautifulSoup
import requests
import json
from urllib.parse import quote
import logging

logger = logging.getLogger(__name__)

eclass_datatype_to_type = {
    'BOOLEAN': 'bool',
    'INTEGER_COUNT': 'numeric',
    'INTEGER_MEASURE': 'numeric',
    'REAL_COUNT' : 'numeric',
    'REAL_CURRENCY': 'numeric',
    'REAL_MEASURE': 'numeric',
    'STRING': 'string',
    'STRING_TRANSLATEABLE': 'string',
    'URL': 'string'
    #TODO Map: DATE, RATIONAL, RATIONAL_MEASURE, REFERENCE, TIME, TIMESTAMP, AXIS1, AXIS2, AXIS3
}

def parse_html_eclass_valuelist(property, span):
        valuelist_url = "https://eclass.eu/?discharge=basic" + "&cc=" + span['data-cc'].replace('#','%') + "&data=" + quote(span['data-json'])
        # https://eclass.eu/?discharge=basic&cc=0173-1%2301-AGZ376%23020&data=%7B%22identifier%22%3A%22BAD853%22%2C%22preferred_name%22%3A%22cascadable%22%2C%22short_name%22%3A%22%22%2C%22definition%22%3A%22whether%20a%20base%20device%20(host)%20can%20have%20a%20subsidiary%20device%20(guest)%20connected%20to%20it%20by%20means%20of%20a%20cable%22%2C%22note%22%3A%22%22%2C%22remark%22%3A%22%22%2C%22formular_symbol%22%3A%22%22%2C%22irdiun%22%3A%22%22%2C%22attribute_type%22%3A%22INDIRECT%22%2C%22definition_class%22%3A%220173-1%2301-RAA001%23001%22%2C%22data_type%22%3A%22BOOLEAN%22%2C%22IRDI_PR%22%3A%220173-1%2302-BAD853%23008%22%2C%22language%22%3A%22en%22%2C%22version%22%3A%2213_0%22%2C%22values%22%3A%5B%7B%22IRDI_VA%22%3A%220173-1%2307-CAA017%23003%22%7D%2C%7B%22IRDI_VA%22%3A%220173-1%2307-CAA016%23001%22%7D%5D%7D
        valuelist = download_html(valuelist_url)
        valuelist_soup = BeautifulSoup(valuelist, 'html.parser')
        for valuelist_span in valuelist_soup.find_all('span', attrs={"data-props": True}):
            try:
                valuelist_data = json.loads(valuelist_span['data-props'].replace("'",' '))
                value = {
                    "value": valuelist_data['preferred_name'],
                    "definition": valuelist_data['definition'],
                }
                property.values.append(value)
            except json.decoder.JSONDecodeError:
                logger.warning("Error, while decoding:" + valuelist_span['data-props'])

def parse_html_eclass_property(span, data, id):
    property = PropertyDefinition(
        id,
        {data['language']: data['preferred_name']},
        eclass_datatype_to_type.get(data['data_type'], 'string'),
        {data['language']: data['definition']})

    # Check for physical unit
    if ('unit_ref' in data) and ('short_name' in data['unit_ref']) and data['unit_ref']['short_name'] != '':
        property.unit = data['unit_ref']['short_name']

    # Check for value list
    value_list_span = span.find_next_sibling('span')
    if value_list_span:
        logger.debug("Download value list for " + property.name[data['language']])
        parse_html_eclass_valuelist(property, value_list_span)
    return property

def parse_html_eclass_properties(soup : BeautifulSoup):
    properties = []
    li_elements = soup.find_all('li')
    for li in li_elements:
        span = li.find('span', attrs={"data-props": True})
        if span:
            data_props = span['data-props'].replace('&quot;', '"')
            data = json.loads(data_props)
            id = data['IRDI_PR']
            property = ECLASS.properties.get(id)
            if property is None:
                logger.debug(f"Add new property {id}: {data['preferred_name']}")
                property = parse_html_eclass_property(span, data, id)
                ECLASS.properties[id] = property
            else:
                logger.debug(f"Add existing property {id}: {property.name}")
            properties.append(property)
    return properties
                
def split_keywords(li_keywords):
    if li_keywords is None:
        return []
    keywords = li_keywords.get('title').strip().split(':')[1].split()
    keyphrases = []
    for keyword in keywords:
        if keyword[0].isupper():
            keyphrases.append(keyword)
        else:
            keyphrases[len(keyphrases)-1] = keyphrases[len(keyphrases)-1] + ' ' + keyword
    return keyphrases

def download_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error downloading the HTML from the URL: {e}")
        return None

class ECLASS(Dictionary):
    """
    ECLASS is a class designed to interact with the eCl@ss standard for classification
    and product description. It provides functionalities to search for eCl@ss classes
    and retrieve their properties based on different releases of the standard.

    Attributes:
        eclass_class_search_pattern (str): The URL pattern to search for eCl@ss classes.
            The URL contains placeholders for class_id, language, and release which
            are filled in dynamically when performing a search.
        properties (dict[str, PropertyDefinition]): A dictionary that maps property
            IDs to their PropertyDefinition instances.
        releases (dict[str, dict[str, object]]): A dictionary that maps release versions
            to another dictionary. This nested dictionary maps class IDs to their
            corresponding class objects for that release version.

    Args:
        release (str): The release version of the eCl@ss standard to be used when
            interacting with the eCl@ss database. Defaults to '14.0'.

    Methods:
        get_class_properties(class_id: str) -> list[PropertyDefinition]:
            Retrieves a list of property definitions for a given eCl@ss class ID.
            If the properties are already cached in the `properties` attribute, those
            are returned. Otherwise, a web request is made to the eCl@ss website to
            fetch and parse the properties.

            Args:
                class_id (str): The ID of the eCl@ss class for which to retrieve properties.

            Returns:
                list[PropertyDefinition]: A list of PropertyDefinition instances
                associated with the specified class ID.
        classes (property) -> dict[str, ClassDefinition]:
            A property that retrieves the class definitions for the currently set release
            version from the `releases` attribute.

            Returns:
                dict[str, ClassDefinition]: A dictionary of class definitions for the current release.
    """
    eclass_class_search_pattern: str = 'https://eclass.eu/en/eclass-standard/search-content/show?tx_eclasssearch_ecsearch%5Bdischarge%5D=0&tx_eclasssearch_ecsearch%5Bid%5D={class_id}&tx_eclasssearch_ecsearch%5Blanguage%5D={language}&tx_eclasssearch_ecsearch%5Bversion%5D={release}'
    properties: dict[str, PropertyDefinition] = {}
    releases: dict[dict[str, ClassDefinition]] = {'14.0': {}, '13.0': {}, '12.0': {}, '11.1': {}, '11.0': {}, '10.1': {}, '10.0.1': {}, '9.1': {}, '9.0': {}, '8.1': {}, '8.0': {}, '7.1': {}, '7.0': {}, '6.2': {}, '6.1': {}, '5.14': {}}

    def __init__(self, release = '14.0') -> None:
        """
        Initializes the ECLASS instance with a specified eCl@ss release version.

        Args:
            release (str): The release version of the eCl@ss standard to be used.
                           Defaults to '14.0'.
        """
        super().__init__()
        self.release = release
    
    @property
    def classes(self) -> dict[str, ClassDefinition]:
        """
        Retrieves the class definitions for the currently set eCl@ss release version.

        Returns:
            dict[str, ClassDefinition]: A dictionary of class definitions for the current release, with their class id as key.
        """
        return self.releases.get(self.release)

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
        if len(class_id) != 8 or not class_id.isdigit():
            logger.warning(f"Class id has unknown format. Should be 8 digits, but got: {class_id}")
            return []
        if class_id.endswith('00'):
            logger.warning(f"No properties for {class_id}. Currently only concrete (level 4) classes are supported.")
            # Because the eclass content-search only lists properties in level 4 for classes
            return []
        eclass_class = self.classes.get(class_id)
        if eclass_class is None:
            logger.info(f"Download class and property definitions for {class_id} in release {self.release}")
            html_content = download_html(ECLASS.eclass_class_search_pattern.format(
                class_id=class_id,
                language='1', # 0=de, 1=en, 2=fr, 3=cn
                release=self.release))
            if html_content is None:
                return []
            eclass_class = self.__parse_html_eclass_class(html_content)
        else:
            logger.info(f"Found class and property definitions for {class_id} in release {self.release}.")
        return eclass_class.properties
    
    def __parse_html_eclass_class(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        #TODO get IRDI instead of id, e.g.: 0173-1#01-AGZ376#020, which is = data-cc in span of value lists
        class_hierarchy = soup.find('ul', attrs={"class": "tree-simple-list"})
        li_elements = class_hierarchy.find_all('li', attrs={"id": True})
        for li in li_elements:
            identifier = li['id'].replace('node_', '')
            eclass_class = self.classes.get(identifier)
            if eclass_class is None:
                a_description = li.find('a', attrs={"title": True})
                eclass_class = ClassDefinition(
                    id = identifier,
                    name = ' '.join(li.getText().strip().split()[1:]),
                    description = a_description['title'] if a_description != None else '',
                    keywords = split_keywords(li.find('i', attrs={"data-toggle": "tooltip"})),
                )
                logger.debug(f"Add class {identifier}: {eclass_class.name}")
                self.classes[identifier] = eclass_class
            else:
                logger.debug(f"Found class {identifier}: {eclass_class.name}")
        eclass_class.properties = parse_html_eclass_properties(soup)
        return eclass_class