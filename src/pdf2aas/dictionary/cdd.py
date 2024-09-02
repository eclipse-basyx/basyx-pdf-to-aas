import logging
import re
import requests

import xlrd
from bs4 import BeautifulSoup

from .core import Dictionary, ClassDefinition, PropertyDefinition
from .eclass import download_html

logger = logging.getLogger(__name__)

def cdd_datatype_to_type(data_type:str):
    if data_type.startswith("CLASS_REFERENCE_TYPE"):
        return "class"
    if data_type.startswith("ENUM_BOOLEAN_TYPE"):
        return "bool"
    if data_type.startswith("LEVEL(MIN,MAX)"):
        return "range"
    if "INT" in data_type or "REAL" in data_type:
        return "numeric"
    return "string"

class CDD(Dictionary):
    """ Common Data Dictionary

        C.f.: https://cdd.iec.ch/
        Class ids are full IRDIs, e.g.: 0112/2///62683#ACC501#002
        Property ids are currently IRDIs without version, e.g.: 0112/2///62683#ACE102

    """
    releases: dict[dict[str, ClassDefinition]] = {}
    properties: dict[str, PropertyDefinition] = {}
    supported_releases = [
        "V2.0018.0002",
    ]
    
    def __init__(
        self,
        release: str = "V2.0018.0002",
        temp_dir=None,
    ) -> None:
        super().__init__(release, temp_dir)
        #TODO implement release based lookup?
    
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        class_ = self.classes.get(class_id)
        if class_ is None:
            logger.info(f"Download class and property definitions for {class_id} in release {self.release}")
            html_content = download_html(self.get_class_url(class_id))
            if html_content is None:
                return []
            class_ = self._parse_cdd_class(html_content)
        return class_.properties
    
    def get_class_url(self, class_id: str) -> str :
        # example class_id: 0112/2///62683#ACC501 --> https://cdd.iec.ch/cdd/iec62683/cdddev.nsf/classes/0112-2---62683%23ACC501
        standard_id_version = class_id.split('/')[-1].split('#')
        #TODO find specified version
        return f"https://cdd.iec.ch/cdd/iec{standard_id_version[0][:5]}/cdddev.nsf/classes/0112-2---{standard_id_version[0]}%23{standard_id_version[1]}"

    def get_property_url(self, property_id: str) -> str:
        # example property_id: 0112/2///62683#ACC501#002 --> https://cdd.iec.ch/CDD/IEC62683/cdddev.nsf/PropertiesAllVersions/0112-2---62683%23ACE251
        standard_id_version = property_id.split('/')[-1].split('#')
        #TODO find specified version
        return f"https://cdd.iec.ch/CDD/IEC{standard_id_version[0][:5]}/cdddev.nsf/PropertiesAllVersions/0112-2---{standard_id_version[0]}%23{standard_id_version[1]}"

    @staticmethod
    def _get_table_data(labels, label) -> str:
        for td in labels:
            if td.text == f"\n{label}: ":
                return td.find_next_sibling('td').text.lstrip('\n')
        return None

    def _parse_cdd_class(self, html_content: dict) -> ClassDefinition:
        soup = BeautifulSoup(html_content, "html.parser")
        #TODO resolve language to table (English --> L1, France = L2, ...) from div id="onglet"
        #TODO translate the labels, e.g. Preferred name --> Nom préféré
        table = soup.find("table", attrs={"id": "contentL1"})
        tds = table.find_all('td', class_='label')

        class_id = self._get_table_data(tds, 'IRDI')
        class_ = ClassDefinition(
            id=class_id,
            name=self._get_table_data(tds, 'Preferred name'),
            description=self._get_table_data(tds, 'Definition')
        )

        keywords = self._get_table_data(tds, 'Synonymous name')
        if keywords and len(keywords.strip()) > 0:
            class_.keywords = keywords.split(', ')

        class_.properties = self._download_property_definitions(class_id, soup)
        self.classes[class_id] = class_
        return class_
    
    def _download_export_xls(self, export_html_content, selection):
        export_url = re.search(f'href="(.*{selection}.*)"', export_html_content)
        if export_url is None:
            return []
        export_url = f"https://cdd.iec.ch{export_url.group(1)}"

        try:
            response = requests.get(export_url)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"XLS download failed: {e}")
            return []
        workbook = xlrd.open_workbook(file_contents=response.content)
        return workbook.sheet_by_index(0)

    def _download_property_definitions(self, class_id, class_html_soup):
        export_id = class_html_soup.find('input', {'id': 'export6'}).get('onclick').split("'")[1]
        export_url = f"{self.get_class_url(class_id)}?OpenDocument&Click={export_id}"
        export_html_content = download_html(export_url)
        if export_html_content is None:
            return []

        property_sheet = self._download_export_xls(export_html_content, 'PROPERTY')
        value_list_sheet = self._download_export_xls(export_html_content, 'VALUELIST')
        value_terms_sheet = self._download_export_xls(export_html_content, 'VALUETERMS')

        properties = []
        for row in range(property_sheet.nrows):
            property_ = self._parse_property_xls_row(property_sheet.row_values(row), value_list_sheet, value_terms_sheet)
            if property_ is not None:
                properties.append(property_)
        return properties

    def _parse_property_xls_row(self, row, value_list, value_terms):
        if row[0].startswith('#'):
            return None
        type_ = row[14]
        data_type = cdd_datatype_to_type(type_)
        if data_type == "class":
            return None
        
        property_id = f"{row[1]}#{int(row[2]):03d}"
        if property_id in self.properties:
            return self.properties[property_id]
        
        property_ = PropertyDefinition(
                id=property_id,
                name={'en': row[4]},
                type=data_type,
                definition={'en': row[7]},
                unit=row[12] if len(row[12]) > 0 else None
            )
        if type_.startswith('ENUM'):
            value_list_id = type_.split('(')[1][:-1]
            value_ids = []
            for row in value_list:
                if row[1].value == value_list_id:
                    value_ids = row[2].value[1:-1].split(',')
                    break
            for value_id in value_ids:
                for row in value_terms:
                    if row[1].value == value_id:
                        value = {
                            'value': row[4].value,
                            'id': f"{row[1].value}#{int(row[2].value):03d}",
                        }
                        if len(row[5].value) > 0:
                            value['synonyms'] = row[5].value.split(',')
                        if len(row[6].value) > 0:
                            value['short_name'] = row[6].value
                        if len(row[7].value) > 0:
                            value['definition'] = row[7].value
                        if len(row[9].value) > 0:
                            value['definition_source'] = row[9].value
                        if len(row[10].value) > 0:
                            value['note'] = row[10].value
                        if len(row[11].value) > 0:
                            value['remark'] = row[11].value
                        if len(row[12].value) > 0:
                            value['symbol'] = row[12].value
                        property_.values.append(value)
                        break
        self.properties[property_id] = property_
        return property_
    
    @staticmethod
    def parse_class_id(class_id:str) -> str | None:
        if class_id is None:
            return None
        class_id = re.sub(r'[-]|\s', '', class_id)
        class_id = re.search(r"0112/2///[A-Z0-9_]+#[A-Z]{3}[0-9]{3}#[0-9]{3}", class_id, re.IGNORECASE)
        if class_id is None:
            return None
        return class_id.group(0)
