import logging
from .core import Dictionary, ClassDefinition, PropertyDefinition
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
        return []

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
