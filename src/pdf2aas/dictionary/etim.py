import os
import logging
import requests
import time
import re
import csv
import shutil
from collections import defaultdict

from .core import Dictionary, ClassDefinition, PropertyDefinition

logger = logging.getLogger(__name__)

etim_datatype_to_type = {
    "L": "bool",
    "Logical": "bool",
    "N": "numeric",
    "Numeric": "numeric",
    "R": "range",
    "Range": "range",
    "A": "string",
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
    license = "https://opendatacommons.org/licenses/by/1-0/"
    
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
    
    def get_class_url(self, class_id: str) -> str :
        # Alternative: f"https://viewer.etim-international.com/class/{class_id}"
        return f"https://prod.etim-international.com/Class/Details/?classid={class_id}"

    def get_property_url(self, property_id: str) -> str:
        return f"https://prod.etim-international.com/Feature/Details/{property_id.split('/')[0]}"
    
    def _download_etim_class(self, etim_class_code) -> dict:
        logger.debug(f"Download etim class details for {etim_class_code} in {self.language} and release {self.release}")
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
            "languagecode": self.language.upper(),
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
            feature_id = f'{self.release}/{etim_class['code']}/{feature['code']}'
            property_ = PropertyDefinition(
                id=feature_id,
                name={self.language: feature['description']},
                type=etim_datatype_to_type.get(feature['type'], 'string'),
                # definition is currently not available via ETIM API
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
            self.properties[feature_id] = property_
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
    
    def _load_from_release_csv_zip(self, filepath: str):
        logger.info(f"Load ETIM dictionary from CSV release zip: {filepath}")
        
        zip_dir = os.path.join(os.path.dirname(filepath), os.path.splitext(os.path.basename(filepath))[0])
        if not os.path.exists(zip_dir):
            try:
                os.makedirs(zip_dir)
                shutil.unpack_archive(filepath, zip_dir)
            except (shutil.ReadError, FileNotFoundError, PermissionError) as e:
                logger.warning(f"Error while unpacking ETIM CSV Release: {e}")
                if os.path.exists(zip_dir):
                    shutil.rmtree(zip_dir)

        synonyms = defaultdict(list)
        with open(os.path.join(zip_dir, 'ETIMARTCLASSSYNONYMMAP.csv'), encoding='utf-16') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                synonyms[row['ARTCLASSID']].append(row['CLASSSYNONYM'])
        
        feature_descriptions = {}
        with open(os.path.join(zip_dir, 'ETIMFEATURE.csv'), encoding='utf-16') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                feature_descriptions[row['FEATUREID']]= row['FEATUREDESC']
        
        unit_abbreviations = {}
        with open(os.path.join(zip_dir, 'ETIMUNIT.csv'), encoding='utf-16') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                unit_abbreviations[row['UNITOFMEASID']]= row['UNITDESC']

        value_descriptions = {}
        with open(os.path.join(zip_dir, 'ETIMVALUE.csv'), encoding='utf-16') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                value_descriptions[row['VALUEID']]= row['VALUEDESC']

        feature_value_map = {}
        with open(os.path.join(zip_dir, 'ETIMARTCLASSFEATUREVALUEMAP.csv'), encoding='utf-16') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                value = {
                    # 'orderNumber' = index in this list
                    'code': row['VALUEID'],
                    'description': value_descriptions[row['VALUEID']]
                }
                if row['ARTCLASSFEATURENR'] not in feature_value_map:
                    feature_value_map[row['ARTCLASSFEATURENR']] = [value]
                else:
                    feature_value_map[row['ARTCLASSFEATURENR']].append(value)

        class_feature_map = defaultdict(list)
        with open(os.path.join(zip_dir, 'ETIMARTCLASSFEATUREMAP.csv'), encoding='utf-16') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                feature = {
                    # orderNumber = index in the list
                    'code': row['FEATUREID'],
                    'type': row['FEATURETYPE'],
                    'description': feature_descriptions[row['FEATUREID']],
                    # 'portcode' : None,
                    # 'unitImperial': None,
                }
                if len(row['UNITOFMEASID']) > 0:
                    feature['unit'] =  {
                        'code': row['UNITOFMEASID'],
                        #'description': None,
                        'abbreviation': unit_abbreviations[row['UNITOFMEASID']],
                    }
                values = feature_value_map.get(row['ARTCLASSFEATURENR'])
                if values:
                    feature['values'] = values
                class_feature_map[row['ARTCLASSID']].append(feature)

        with open(os.path.join(zip_dir, 'ETIMARTCLASS.csv'), encoding='utf-16') as file:
            reader = csv.DictReader(file, delimiter=';')
            for row in reader:
                class_dict = {
                    'code': row['ARTCLASSID'],
                    'description': row['ARTCLASSDESC'],
                    'synonyms': synonyms[row['ARTCLASSID']],
                    # "version": row['ARTCLASSVERSION'],
                    # "status": None,
                    # "mutationDate": None,
                    # "revision": None,
                    # "revisionDate": None,
                    # "modelling": false,
                    # "descriptionEn": None,
                    'features' : class_feature_map[row['ARTCLASSID']]
                }
                self._parse_etim_class(class_dict)

    def load_from_file(self, filepath: str | None = None) -> bool:
        """
        Loads a whole ETIM release from CSV zip file.

        Searches in `self.tempdir` for "ETIM-<release>-...CSV....zip" file, if
        no filepath is given.
        """
        if filepath is None and os.path.exists(self.temp_dir):
            for filename in os.listdir(self.temp_dir):
                if re.match(f'{self.name}-{self.release}.*CSV.*\\.zip', filename, re.IGNORECASE):
                    self._load_from_release_csv_zip(os.path.join(self.temp_dir, filename))
        return super().load_from_file(filepath)