import logging
import json
import re

from basyx.aas import model
from basyx.aas.util.traversal import walk_submodel
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer, AASXWriter, AASXReader
from basyx.aas.adapter.json import json_serialization

from .core import Generator
from .aas import cast_property, cast_range, anti_alphanumeric_regex
from ..extractor import Property

logger = logging.getLogger(__name__)

class AASTemplate(Generator):
    def __init__(
        self,
        aasx_path: str,
    ) -> None:
        self.aasx_path = aasx_path
        self.reset()

    def reset(self):
        self.object_store = model.DictObjectStore()
        self.file_store = DictSupplementaryFileContainer()
        try:
            with AASXReader(self.aasx_path) as reader:
                reader.read_into(self.object_store, self.file_store)
        except (ValueError, OSError) as e:
            logger.error(f"Couldn't load aasx template from '{self.aasx_path}':{e}")
        self.submodels = [submodel for submodel in self.object_store if isinstance(submodel, model.Submodel)]

    def _walk_properties(self):
        for submodel in self.submodels:
            for element in walk_submodel(submodel):
                if isinstance(element, (model.Property, model.Range, model.MultiLanguageProperty)):
                    yield element

    def _search_property_by_semantic_id(self, id_):
        if id_ is None:
            return None
        for property_ in self._walk_properties():
            if property_.semantic_id is None:
                continue
            for key in property_.semantic_id.key:
                if key.value == id_:
                    return property_
        return None
    
    def _search_property_by_id_short(self, name):
        if name is None or len(name.strip()) == 0:
            return None
        # TODO add option for exact matches only?
        name = re.sub(anti_alphanumeric_regex,'', name.lower())
        for property_ in self._walk_properties():
            if re.sub(anti_alphanumeric_regex,'', property_.id_short.lower()) == name:
                return property_
        return None

    def _search_property(self, property_: Property) -> model.Property | model.Range | model.MultiLanguageProperty | None:
        search_result = self._search_property_by_semantic_id(property_.definition_id)
        if search_result is None:
            search_result = self._search_property_by_id_short(property_.definition_name)
        if search_result is None:
            search_result = self._search_property_by_id_short(property_.label)
        return search_result

    def add_properties(self, properties: list[Property]):
        """
        Search the property by semantic id or id_short to update its value.
        
        Instead of adding the property, only its value is updated, as the AAS 
        Template defines the properties and their place in the AAS hierarchy.
        """
        for property_ in properties:
            aas_property = self._search_property(property_)
            if aas_property is None:
                continue
            if isinstance(aas_property, model.Property):
                value = cast_property(property_.value, property_.definition)
                aas_property.value_type = type(value)
                aas_property.value = value
            elif isinstance(aas_property, model.MultiLanguageProperty):
                aas_property.value = model.MultiLanguageTextType({property_.language: str(property_.value)})
            elif isinstance(aas_property, model.Range):
                min_, max_, type_ = cast_range(property_)
                aas_property.value_type = type_
                aas_property.min = min_
                aas_property.max = max_

    def get_properties(self) -> list[Property]:
        return []

    def dumps(self):
        return json.dumps([o for o in self.object_store], cls=json_serialization.AASToJsonEncoder, indent=2)

    def save_as_aasx(self, filepath: str):
        with AASXWriter(filepath) as writer:
            writer.write_aas(
                aas_ids=[aas.id for aas in self.object_store if isinstance(aas, model.AssetAdministrationShell)],
                object_store=self.object_store,
                file_store=self.file_store,
                write_json=True)
