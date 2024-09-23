import logging
import json
import copy

from basyx.aas import model
from basyx.aas.util.traversal import walk_submodel
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer, AASXWriter, AASXReader
from basyx.aas.adapter.json import json_serialization

from .core import Generator
from .aas import cast_property, cast_range, get_dict_data_type_from_xsd, get_dict_data_type_from_IEC6360, anti_alphanumeric_regex
from ..dictionary import PropertyDefinition
from ..extractor import Property

logger = logging.getLogger(__name__)

class AASTemplate(Generator):
    """
    Generator, that loads an AAS as template to read and update its properties.

    Attributes:
        aasx_path (str): The file path to the AASX package which is used as template.
    """
    def __init__(
        self,
        aasx_path: str,
    ) -> None:
        self._properties: dict[str, tuple[Property, model.Property | model.Range | model.MultiLanguageProperty]] = {}
        self._aasx_path = aasx_path
        self.reset()

    @property
    def aasx_path(self):
        return self._aasx_path
    
    @aasx_path.setter
    def aasx_path(self, value):
        self._aasx_path = value
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
        self._properties = self._search_properties()

    def add_properties(self, properties: list[Property]):
        """
        Search the property by its `id` to update the aas property value.
        
        Instead of adding the property, only its value is updated, as the AAS 
        Template defines the properties and their place in the AAS hierarchy.
        The property id resembles the submodel id plus the id_short hierarchy.
        """
        for property_ in properties:
            if property_.id is None:
                continue
            old_property, aas_property = self._properties.get(property_.id, (None, None))
            if aas_property is None:
                continue
            old_property.value = property_.value
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
        return [p for (p, _) in self._properties.values()]
    
    def get_property(self, id_) -> Property | None:
        property_, _ =  self._properties.get(id_, (None, None))
        return property_

    def get_property_definitions(self):
        definitions = []
        for property_, _ in self._properties.values():
            definition = copy.copy(property_.definition)
            if property_.definition_name is None:
                if property_.label is None or len(property_.label) == 0:
                    definition.name = {}
                else:
                    definition.name = {property_.language: property_.label}
            if definition.definition is None or len(definition.definition) == 0:
                if property_.reference is None or len(property_.reference) == 0:
                    definition.definition = {}
                else:
                    definition.definition = {property_.language: property_.reference}
            definitions.append(definition)
        return definitions

    def _walk_properties(self):
        for submodel in self.submodels:
            for element in walk_submodel(submodel):
                if isinstance(element, (model.Property, model.Range, model.MultiLanguageProperty)):
                    yield element

    @staticmethod
    def _get_multilang_string(string_dict: dict[str,str], language: str) -> tuple[str | None, str]:
        if string_dict is not None and len(string_dict) > 0:
            if language in string_dict:
                return string_dict[language], language
            else:
                next(iter(string_dict.items()))
        return None, language

    @staticmethod
    #TODO move to PropertyDefinition
    def _fill_definition_from_data_spec(definition:PropertyDefinition, embedded_data_specifications):
        data_spec:model.DataSpecificationIEC61360 = next(
                    (spec.data_specification_content for spec in embedded_data_specifications
                    if isinstance(spec.data_specification_content, model.DataSpecificationIEC61360)),
                    None)
        if data_spec is None:
            return
        
        if (definition.name is None or len(definition.name) == 0):
            if data_spec.preferred_name is not None and len(data_spec.preferred_name) > 0:
                definition.name = data_spec.preferred_name._dict
            elif data_spec.short_name is not None and len(data_spec.short_name) > 0:
                definition.name = data_spec.short_name._dict

        if definition.type is None and data_spec.data_type is not None:
            definition.type = get_dict_data_type_from_IEC6360(data_spec.data_type)
        
        if len(definition.definition) == 0 and data_spec.definition is not None:
            definition.definition = data_spec.definition._dict

        if len(definition.unit) == 0 and data_spec.unit is not None:
            definition.unit = data_spec.unit
        
        if definition.values is None or len(definition.values) == 0 and \
                data_spec.value_list is not None and len(data_spec.value_list) > 0:
            definition.values = [{"value": value.value, "id": value.value_id.key[0].value} #TODO get key more robust
                                  for value in data_spec.value_list]
        #use data_spec.value as default value?

    def _resolve_concept_description(self, semantic_id):
        try:
            cd = semantic_id.resolve(self.object_store)
            if not isinstance(cd, model.concept.ConceptDescription):
                raise model.UnexpectedTypeError(value=type(cd))
            return cd
        except (IndexError, TypeError, KeyError):
            logger.debug("ConceptDescription for semantidId %s not found in object store.", str(semantic_id))
        except model.UnexpectedTypeError as e:
            logger.debug("semantidId %s resolves to %s, which is not a ConceptDescription",
                        str(semantic_id), e.value)
        return None

    @staticmethod
    def _create_id_from_path(item: model.Referable):
        parent_path = []
        if item.id_short is not None:
            while item is not None:
                if isinstance(item, model.Identifiable):
                    parent_path.append(item.id)
                    break
                elif isinstance(item, model.Referable):
                    if isinstance(item.parent, model.SubmodelElementList):
                        parent_path.append(f"{item.parent.id_short}[{item.parent.value.index(item)}]")
                        item = item.parent
                    else:
                        parent_path.append(item.id_short)
                    item = item.parent
        return "/".join(reversed(parent_path))

    def _search_properties(self):
        properties = {}
        for aas_property in self._walk_properties():
            property_ = Property(
                id=self._create_id_from_path(aas_property),
            )
            
            property_.label, property_.language = self._get_multilang_string(
                aas_property.display_name, property_.language)
            if property_.label is None:
                property_.label = aas_property.id_short
            
            property_.reference, _ = self._get_multilang_string(
                aas_property.description, property_.language)
            
            if isinstance(aas_property, model.Range):
                property_.value = [aas_property.min, aas_property.max]
                type_ = "range"
            elif isinstance(aas_property, model.MultiLanguageProperty):
                property_.value, _ = self._get_multilang_string(
                    aas_property.value, property_.language)
                type_ = "string"
            else:
                property_.value = aas_property.value
                type_ = get_dict_data_type_from_xsd(aas_property.value_type)

            definition = PropertyDefinition(
                id=property_.id,
                type=type_
            )
            self._fill_definition_from_data_spec(definition, aas_property.embedded_data_specifications)
            
            semantic_id = aas_property.semantic_id
            if semantic_id:
                definition.id = semantic_id.key[0].value # TODO handle types and multiple keys etc.
                if isinstance(semantic_id, model.ModelReference):
                    cd = self._resolve_concept_description(semantic_id)
                else:
                    cd = self.object_store.get(semantic_id.key[0].value)
                if cd is not None:
                    self._fill_definition_from_data_spec(definition, cd.embedded_data_specifications)
                    if len(definition.name) == 0:
                        if cd.display_name:
                            definition.name = cd.display_name._dict
                        else:
                            definition.name = {'en': cd.id_short}
            property_.definition = definition
            properties[property_.id] = (property_, aas_property)
        return properties

    def dumps(self):
        return json.dumps([o for o in self.object_store], cls=json_serialization.AASToJsonEncoder, indent=2)

    def save_as_aasx(self, filepath: str):
        with AASXWriter(filepath) as writer:
            writer.write_aas(
                aas_ids=[aas.id for aas in self.object_store if isinstance(aas, model.AssetAdministrationShell)],
                object_store=self.object_store,
                file_store=self.file_store,
                write_json=True)
