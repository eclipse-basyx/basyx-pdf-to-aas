import os
import logging
import requests
import time
import re

from .core import Dictionary, ClassDefinition, PropertyDefinition

logger = logging.getLogger(__name__)

etim_datatype_to_type = {
    "Logical": "bool",
    "Numeric": "numeric",
    "Range": "string",
    "Alphanumeric": "string",
}

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
        class_id = self.parse_class_id(class_id)
        if class_id is None:
            return []
        class_ = self.classes.get(class_id)
        if class_ is None:
            etim_class = self._download_etim_class(class_id)
            if etim_class is None:
                return []
            class_ = self._parse_etim_class(etim_class)
        return class_.properties
    
    def get_property(self, property_id: str) -> PropertyDefinition:
        raise NotImplementedError()
    
    def get_class_url(self, class_id: str) -> str :
        # Alternative: f"https://viewer.etim-international.com/class/{class_id}"
        return f"https://prod.etim-international.com/Class/Details/?classid={class_id}"

    def get_property_url(self, property_id: str) -> str:
        return f"https://prod.etim-international.com/Feature/Details/{property_id}"
    
    def _download_etim_class(self, etim_class_code, language = "EN") -> dict:
        logger.debug(f"Download etim class details for {etim_class_code} in {language} and release {self.release}")
        access_token = self.__get_access_token()
        if access_token is None:
            return None
        url = f"{self.base_url}/api/v2/Class/DetailsForRelease"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        data = {
            "include": {
                "descriptions": True,
                "translations": False,
                "fields": [
                    "features"
                ]
            },
            "languagecode": language,
            "code": etim_class_code,
            "release": f"ETIM-{self.release}" if self.release[0].isdigit() else self.release 
        }
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            logger.debug(f"ETIM API Response: {response}")
            return response.json()
        except requests.HTTPError as http_err:
            logger.error(f"Can't find class {etim_class_code}. HTTP error occurred: {http_err}")
        except Exception as err:
            logger.error(f"Can't find class {etim_class_code}. An error occurred: {err}")
        return None

    def _parse_etim_class(self, etim_class: dict) -> ClassDefinition:
        class_ = ClassDefinition(
            id=etim_class['code'],
            name=etim_class['description'],
            keywords=etim_class['synonyms'],
        )
        for feature in etim_class['features']:
            property_ = PropertyDefinition(
                id=feature['code'],
                name=feature['description'],
                type=etim_datatype_to_type.get(feature['type'], 'string'),
            )
            if 'unit' in feature:
                property_.unit = feature['unit']['abbreviation']
            if 'values' in feature:
                property_.values = [
                    {
                        'value': value['description'],
                        'id': value['code']
                    }
                    for value in feature['values']]
            self.properties[f'{feature['code']}/{etim_class['code']}'] = property_
            class_.properties.append(property_)
        self.classes[etim_class['code']] = class_
        return class_

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