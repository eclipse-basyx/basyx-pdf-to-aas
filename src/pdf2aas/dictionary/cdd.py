import logging
import re
import requests

from bs4 import BeautifulSoup

from .core import Dictionary, ClassDefinition, PropertyDefinition
from .eclass import download_html

logger = logging.getLogger(__name__)

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
        return f"https://cdd.iec.ch/cdd/iec{standard_id_version[0]}/cdddev.nsf/classes/0112-2---{standard_id_version[0]}%23{standard_id_version[1]}"

    def get_property_url(self, property_id: str) -> str:
        # example property_id: 0112/2///62683#ACC501#002 --> https://cdd.iec.ch/CDD/IEC62683/cdddev.nsf/PropertiesAllVersions/0112-2---62683%23ACE251
        standard_id_version = property_id.split('/')[-1].split('#')
        #TODO find specified version
        return f"https://cdd.iec.ch/CDD/IEC{standard_id_version[0]}/cdddev.nsf/PropertiesAllVersions/0112-2---{standard_id_version[0]}%23{standard_id_version[1]}"

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

        self.classes[class_id] = class_
        return class_
