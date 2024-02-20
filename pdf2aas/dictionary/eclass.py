from dictionary.core import Dictionary, PropertyDefinition
from bs4 import BeautifulSoup
import requests
import json
from urllib.parse import quote

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
                print("Error, while decoding:" + valuelist_span['data-props'])
                print("  Url: " + valuelist_url)

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
        print(" -- Download value list for " + property.name[data['language']])
        parse_html_eclass_valuelist(property, value_list_span)
        property.type = "enum"
    
    ECLASS.properties[id] = property
    return property

def parse_html_eclass_properties(soup : BeautifulSoup):
    identifiers = []
    properties = []
    li_elements = soup.find_all('li')
    for li in li_elements:
        span = li.find('span', attrs={"data-props": True})
        if span:
            data_props = span['data-props'].replace('&quot;', '"')
            data = json.loads(data_props)
            id = data['IRDI_PR']
            identifiers.append(id)
            if id in ECLASS.properties:
                property = ECLASS.properties[id]
                print(f" - Found property {id}: {property.name}")
                properties.append(property)
            else:
                print(f" - Create property {id}: {data['preferred_name']}")
                properties.append(parse_html_eclass_property(span, data, id))

    return (identifiers, properties)

def parse_html_eclass_class(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    eclass_class = {}
    superclass_identifier=''
    #TODO get IRDI instead of id, e.g.: 0173-1#01-AGZ376#020, which is = data-cc in span of value lists
    class_hierarchy = soup.find('ul', attrs={"class": "tree-simple-list"})
    li_elements = class_hierarchy.find_all('li', attrs={"id": True})
    for li in li_elements:
        identifier = li['id'].replace('node_', '')
        if identifier in ECLASS.classes:
            print(f" - Found class {identifier}: {ECLASS.classes[identifier]['name']}")
        else:
            a_description = li.find('a', attrs={"title": True})
            keywords = li.find('i', attrs={"data-toggle": "tooltip"})
            eclass_class = {
                'subClassOf': superclass_identifier,
                'description': a_description['title'] if a_description != None else '',
                'id': li.getText().strip().split()[0],
                'name': ' '.join(li.getText().strip().split()[1:]),
                "keywords": keywords.get('title').strip().replace('Schlagwörter: ', '').split() if keywords != None else []
            }
            print(f" - Create class {identifier}: {eclass_class['name']}")
            ECLASS.classes[identifier] = eclass_class
        superclass_identifier = identifier
    (eclass_class['properties'], properties) = parse_html_eclass_properties(soup)
    return (eclass_class, properties)

def download_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error downloading the HTML from the URL: {e}")
        return None

class ECLASS(Dictionary):
    eclass_class_search_pattern: str = 'https://eclass.eu/en/eclass-standard/search-content/show?tx_eclasssearch_ecsearch%5Bdischarge%5D=0&tx_eclasssearch_ecsearch%5Bid%5D={class_id}&tx_eclasssearch_ecsearch%5Blanguage%5D={language}&tx_eclasssearch_ecsearch%5Bversion%5D={version}'
    properties: dict[str, PropertyDefinition] = {}
    classes: dict[str, object] = {}
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        html_content = download_html(ECLASS.eclass_class_search_pattern.format(class_id=class_id, language='1', version='14.0'))
        (_, properties) = parse_html_eclass_class(html_content)

        return properties