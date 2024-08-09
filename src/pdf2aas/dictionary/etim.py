import logging

from .core import Dictionary, ClassDefinition, PropertyDefinition

logger = logging.getLogger(__name__)

class ETIM(Dictionary):
    releases: dict[dict[str, ClassDefinition]] = {}
    properties: dict[str, PropertyDefinition] = {}
    supported_releases = [
        "9.0",
        "8.0",
        "7.0",
        "6.0",
        "5.0",
        "4.0",
        "DYNAMIC",
    ]
    
    def __init__(
        self,
        release: str = "9.0",
        temp_dir=None,
        client_id: str | None = None,
        client_secret: str | None = None,
        auth_url: str = "https://etimauth.etim-international.com",
        base_url: str = "https://etimapi.etim-international.com",
        scope: str = "EtimApi",
    ) -> None:
        super().__init__(release, temp_dir)
        self.client_id = client_id,
        self.client_secret = client_secret,
        self.auth_url = auth_url,
        self.base_url = base_url,
        self.scope = scope
    
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        raise NotImplementedError()
    
    def get_property(self, property_id: str) -> PropertyDefinition:
        raise NotImplementedError()
    
    def get_class_url(self, class_id: str) -> str :
        # Alternative: f"https://viewer.etim-international.com/class/{class_id}"
        return f"https://prod.etim-international.com/Class/Details/?classid={class_id}"

    def get_property_url(self, property_id: str) -> str:
        return f"https://prod.etim-international.com/Feature/Details/{property_id}"