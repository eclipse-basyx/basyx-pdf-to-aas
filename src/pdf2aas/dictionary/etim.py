import os
import logging
import requests
import time
import re

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
        self.client_id = client_id if client_id is not None else os.environ.get("ETIM_CLIENT_ID")
        self.client_secret = client_secret if client_secret is not None else os.environ.get("ETIM_CLIENT_SECRET")
        self.auth_url = auth_url
        self.base_url = base_url
        self.scope = scope
        self.__access_token = None
        self.__expire_time = None
    
    def get_class_properties(self, class_id: str) -> list[PropertyDefinition]:
        raise NotImplementedError()
    
    def get_property(self, property_id: str) -> PropertyDefinition:
        raise NotImplementedError()
    
    def get_class_url(self, class_id: str) -> str :
        # Alternative: f"https://viewer.etim-international.com/class/{class_id}"
        return f"https://prod.etim-international.com/Class/Details/?classid={class_id}"

    def get_property_url(self, property_id: str) -> str:
        return f"https://prod.etim-international.com/Feature/Details/{property_id}"
    
    def __get_access_token(self) -> str:
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
            "scope": self.scope
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Authorization at ETIM API failed: {e}")
            return None
        self.__expire_time = timestamp + response.json()['expires_in']
        self.__access_token = response.json()["access_token"]
        logger.debug(f"Got new access token '{self.__access_token}'. Expires in: {response.json()['expires_in']}[s]")
        return self.__access_token
    
    @staticmethod
    def parse_class_id(class_id:str) -> str | None:
        if class_id is None:
            return None
        class_id = re.sub(r'[-_]|\s', '', class_id)
        class_id = re.search("EC[0-9]{6}", class_id, re.IGNORECASE)
        if class_id is None:
            return None
        return class_id.group(0)