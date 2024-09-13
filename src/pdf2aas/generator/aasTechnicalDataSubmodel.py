import logging
import json
from datetime import date
import re
import uuid

from basyx.aas import model
from basyx.aas.model.base import AASConstraintViolation
from basyx.aas.adapter.aasx import AASXWriter, DictSupplementaryFileContainer
from basyx.aas.adapter.json import json_serialization

from .core import Generator
from .aas import cast_property, cast_range, anti_alphanumeric_regex
from ..dictionary import Dictionary, PropertyDefinition, ECLASS
from ..extractor import Property

logger = logging.getLogger(__name__)

class AASSubmodelTechnicalData(Generator):
    def __init__(
        self,
        identifier: str | None = None,
    ) -> None:
        self.identifier = f"https://eclipse.dev/basyx/pdf-to-aas/submodel/{uuid.uuid4()}" if identifier is None else identifier
        self.concept_descriptions: dict[str, model.concept.ConceptDescription] = {}
        self.reset()
        
    def reset(self):
        super().reset()
        self.concept_descriptions = {}
        self.submodel = self._create_submodel_template()

    def _create_submodel_template(self):
        submodel = model.Submodel(
            id_= self.identifier,
            id_short = "TechnicalData",
            semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2")
        )
        
        self.general_information = model.SubmodelElementCollection(
            id_short ="GeneralInformation",
            semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/GeneralInformation/1/1")
        )
        self.general_information.value.add(
            model.Property(
                    id_short='ManufacturerName',
                    value_type = model.datatypes.String,
                    category = "PARAMETER",
                    semantic_id = self._create_semantic_id("0173-1#02-AAO677#002")
            )
        )
        # ManufacturerLogo is optional
        self.general_information.value.add(
            model.MultiLanguageProperty(
                    id_short='ManufacturerProductDesignation',
                    category = "PARAMETER",
                    semantic_id = self._create_semantic_id("0173-1#02-AAW338#001")
            )
        )
        self.general_information.value.add(
            model.Property(
                    id_short='ManufacturerArticleNumber',
                    value_type = model.datatypes.String,
                    category = "PARAMETER",
                    semantic_id = self._create_semantic_id("0173-1#02-AAO676#003")
            )
        )
        self.general_information.value.add(
            model.Property(
                    id_short='ManufacturerOrderCode',
                    value_type = model.datatypes.String,
                    category = "PARAMETER",
                    semantic_id = self._create_semantic_id("0173-1#02-AAO227#002")
            )
        )
         # ProductImage is optional
        submodel.submodel_element.add(self.general_information)

        self.product_classifications = model.SubmodelElementCollection(
            id_short = "ProductClassifications",
            semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassifications/1/1")
        )
        submodel.submodel_element.add(self.product_classifications)

        self.technical_properties = model.SubmodelElementCollection(
            id_short = "TechnicalProperties",
            semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/TechnicalProperties/1/1")
        )
        submodel.submodel_element.add(self.technical_properties)

        self.further_information = model.SubmodelElementCollection(
            id_short = "FurtherInformation",
            semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/FurtherInformation/1/1")
        )
        self.further_information.value.add(
            model.MultiLanguageProperty(
                id_short = 'TextStatement01',
                value = model.MultiLanguageTextType({'en': 'Created with basyx pdf-to-aas. No liability of any kind is assumed for the contained information.'}),
                category = "PARAMETER",
                semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/TextStatement/1/1")
            )
        )
        self.further_information.value.add(
            model.Property(
                    id_short='ValidDate',
                    value_type = model.datatypes.Date,
                    value = date.today(),
                    category = "PARAMETER",
                    semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ValidDate/1/1")
            )
        )
        submodel.submodel_element.add(self.further_information)
        return submodel

    def add_classification(self, dictionary:Dictionary, class_id:str):
        classification = model.SubmodelElementCollection(
            id_short = f"ProductClassificationItem{len(self.product_classifications.value)+1:02d}",
            semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationItem/1/1")
        )
        classification.value.add(
            model.Property(
                id_short = 'ProductClassificationSystem',
                value_type = model.datatypes.String,
                value = dictionary.name,
                category = "PARAMETER",
                semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationSystem/1/1")
            )
        )
        classification.value.add(
            model.Property(
                id_short = 'ClassificationSystemVersion',
                value_type = model.datatypes.String,
                value = dictionary.release,
                category = "PARAMETER",
                semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ClassificationSystemVersion/1/1")
            )
        )
        classification.value.add(
            model.Property(
                id_short='ProductClassId',
                value_type = model.datatypes.String,
                value = class_id,
                category = "PARAMETER",
                semantic_id = self._create_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassId/1/1")
            )
        )
        self.product_classifications.value.add(classification)

    @staticmethod
    def _add_embedded_data_spec(cd: model.concept.ConceptDescription, defintion: PropertyDefinition):
        if len(defintion.name) == 0:
            return
        data_spec = model.DataSpecificationIEC61360(
            model.PreferredNameTypeIEC61360({l:v[:255] for l, v in defintion.name.items()}),
        )
        match defintion.type:
            case "bool": data_spec.data_type = model.DataTypeIEC61360.BOOLEAN
            case "numeric": data_spec.data_type = model.DataTypeIEC61360.REAL_COUNT
            case "range":
                data_spec.data_type = model.DataTypeIEC61360.REAL_COUNT
                # data_spec.level_types = model.IEC61360LevelType.MAX
            case "string": data_spec.data_type = model.DataTypeIEC61360.STRING
        if len(defintion.definition) > 0:
            data_spec.definition = model.DefinitionTypeIEC61360({l:v[:1024] for l, v in defintion.definition.items()})
        if defintion.unit is not None and len(defintion.unit) > 0:
            data_spec.unit = defintion.unit
        if defintion.values:
            data_spec.value_list = set()
            for idx, value in enumerate(defintion.values):
                if isinstance(value, str):
                    value_id = str(idx)
                elif isinstance(value, dict):
                    value_id = value.get("id")
                    value = value.get("value")
                else:
                    continue
                data_spec.value_list.add(
                    model.ValueReferencePair(value, 
                        model.ExternalReference(
                            (model.Key(
                                type_= model.KeyTypes.GLOBAL_REFERENCE,
                                value=value_id
                            ),)
                        )
                    )
                )
        cd.embedded_data_specifications.append(
            model.EmbeddedDataSpecification(
                data_specification=next(iter(cd.is_case_of)),
                data_specification_content=data_spec
            ))

    def _add_concept_description(self, reference, property_defintion: PropertyDefinition | None = None, value: str = None):
        if reference in self.concept_descriptions:
            return
        cd = model.concept.ConceptDescription(
            id_ = reference,
            is_case_of = {model.ExternalReference((
                model.Key(
                    type_= model.KeyTypes.GLOBAL_REFERENCE,
                    value=reference
                ), ),
            )},
            category = "PROPERTY" if value is None else "VALUE"
        )
        if property_defintion:
            name = property_defintion.name.get('en')
            if name is None:
                name = next(iter(property_defintion.name.values()), None)
            if name is not None:
                cd.id_short = re.sub(anti_alphanumeric_regex, '_', name)
                cd.display_name = model.MultiLanguageNameType({l:n[:64] for l,n in property_defintion.name.items()})
            if property_defintion.definition is not None and len(property_defintion.definition) > 0:
                cd.description = model.MultiLanguageTextType({l:n[:1024] for l,n in property_defintion.definition.items()})
            self._add_embedded_data_spec(cd, property_defintion)
        elif value:
            cd.id_short = re.sub(anti_alphanumeric_regex, '_', value)
            cd.display_name = model.MultiLanguageNameType({'en': value[:64]})

        self.concept_descriptions[reference] = cd

    def _create_semantic_id(self, reference, property_defintion: PropertyDefinition | None = None, value: str = None):
        if reference is None:
            return None
        self._add_concept_description(reference, property_defintion, value)
        return model.ModelReference((
                    model.Key(
                        type_= model.KeyTypes.CONCEPT_DESCRIPTION,
                        value=reference
                    ), ), type_=model.concept.ConceptDescription
                )

    @staticmethod
    def _create_id_short(proposal:str | None = None):
        id_short = re.sub(anti_alphanumeric_regex, '_', proposal) if proposal is not None else ''
        if len(id_short) == 0:
            id_short = "ID_" + str(uuid.uuid4())
        elif id_short[0].isdigit():
            id_short = "ID_" + id_short
        return id_short[:128]

    def _create_aas_property_recursive(self, property_: Property, value, id_short, display_name, description):
        if isinstance(value, (list, set, tuple, dict)):
            if len(value) == 0:
                value = None
            elif len(value) == 1:
                value = value[0]
            else:
                #TODO check wether to use SubmodelElementList for ordered stuff
                smc = model.SubmodelElementCollection(
                    id_short = self._create_id_short(id_short),
                    display_name = display_name,
                    semantic_id = self._create_semantic_id(property_.definition_id),
                    description = description,
                )
                if isinstance(value, dict):
                    iterator = value.items()
                elif isinstance(value, (list, tuple)):
                    iterator = enumerate(value)
                elif isinstance(value, set):
                    iterator = enumerate(list(value))
                for key, val in iterator:
                    try:
                        smc.value.add(
                            self._create_aas_property_recursive(
                                property_,
                                val,
                                id_short+'_'+str(key),
                                None,
                                None,
                            )
                        )
                    except AASConstraintViolation as error:
                        logger.warning(f"Couldn't add {type(value)} item to property {display_name}: {error}")
                return smc
    
        value_id = None
        if property_.definition is not None and len(property_.definition.values) > 0 and value is not None:
            value_id = property_.definition.get_value_id(str(value))
            if value_id is None:
                logger.warning(f"Value '{value}' of '{property_.label}' not found in defined values.")
            else:
                if isinstance(value_id, int):
                    value_id = property_.definition_id + "/" + str(value_id)
                value_id = self._create_semantic_id(value_id, property_.definition, str(value))

        value = cast_property(value, property_.definition)
        return model.Property(
            id_short = self._create_id_short(id_short),
            display_name = display_name,
            description = description,
            value_type = type(value) if value is not None else model.datatypes.String,
            value = value,
            value_id = value_id,
            semantic_id = self._create_semantic_id(property_.definition_id, property_.definition)
        )

    def _create_aas_property(self, property_: Property) -> model.DataElement | None:
        if property_.label is not None and len(property_.label) > 0:
            id_short = property_.label
        elif property_.definition is not None:
            id_short = property_.definition_name
            if id_short is None or len(id_short) == 0:
                id_short = property_.definition_id
        else:
            logger.warning(f"No id_short for: {property_}")
            return None
        
        display_name = {}
        if property_.definition is not None:
            unit = property_.unit
            if property_.unit is not None and len(unit.strip()) > 0 and len(property_.definition.unit) > 0 and unit != property_.definition.unit:
                logger.warning(f"Unit '{unit}' of '{property_.label}' differs from definition '{property_.definition.unit}'")
            if len(property_.definition.name) > 0:
                display_name = model.MultiLanguageNameType({l:n[:64] for l,n in property_.definition.name.items()})
        
        if len(display_name) == 0:
            display_name = model.MultiLanguageNameType({property_.language: id_short[:64]})
        
        if property_.reference is None:
            description = None
        else:
            description = model.MultiLanguageTextType({property_.language: property_.reference[:1023]})

        if property_.definition is not None and property_.definition.type == "range":
            min, max, type_ = cast_range(property_)
            return model.Range(
                id_short = self._create_id_short(id_short),
                display_name = display_name,
                description = description,
                min=min,
                max=max,
                value_type = type_,
                semantic_id = self._create_semantic_id(property_.definition_id, property_.definition)
            )

        return self._create_aas_property_recursive(property_, property_.value, id_short, display_name, description)

    general_information_semantic_ids_short = {
        "AAO677" : "ManufacturerName",
        "AAW338" : "ManufacturerProductDesignation",
        "AAO676" : "ManufacturerArticleNumber",
        "AAO227" : "ManufacturerOrderCode",
    }

    def _update_general_information(self, property_: Property):
        id_short = None
        if property_.definition_id is not None and ECLASS.check_property_irdi(property_.definition_id):
            id_short = self.general_information_semantic_ids_short.get(property_.definition_id[10:16])
         
        if property_.label is not None:
            for label in self.general_information_semantic_ids_short.values():
                if re.sub(anti_alphanumeric_regex,'', property_.label.lower()) == label.lower():
                    id_short = label
                    break
        if id_short is None:
            return False
        
        general_info = self.general_information.value.get('id_short', id_short)
        if isinstance(general_info, model.MultiLanguageProperty):
            general_info.value = model.MultiLanguageTextType({property_.language: str(property_.value)})
        else:
            general_info.value = str(property_.value)
        return True

    def add_properties(self, properties: list[Property]):
        super().add_properties(properties)
        for property_ in properties:
            if self._update_general_information(property_):
                continue
            
            aas_property = self._create_aas_property(property_)
            if aas_property is None:
                continue

            if self.technical_properties.value.contains_id('id_short', aas_property.id_short):
                aas_property.id_short = self._create_id_short()
            try:
                self.technical_properties.value.add(aas_property)
            except AASConstraintViolation as error:
                logger.warning(f"Couldn't add property to submodel: {error}")
    
    @staticmethod
    def _remove_empty_submodel_element(element):
        if isinstance(element, (model.SubmodelElementCollection, model.SubmodelElementList)):
            element.value = [subelement for subelement in element.value if not AASSubmodelTechnicalData._remove_empty_submodel_element(subelement)]
            if len(element.value) == 0:
                return True
        elif isinstance(element, model.Property):
            if element.value is None:
                return True
            if hasattr(element.value, '__len__') and len(element.value) == 0:
                return True
        elif isinstance(element, model.MultiLanguageProperty):
            if element.value is None:
                return True
        elif isinstance(element, model.Range):
            if element.min is None and element.max is None:
                return True
        return False

    def remove_empty_submodel_elements(self, remove_mandatory=False):
        if remove_mandatory:
            self.submodel.submodel_element = [
                element
                for element in self.submodel.submodel_element
                if not self._remove_empty_submodel_element(element)
            ]
        else:
            self.general_information.value = [
                element
                for element in self.general_information.value
                if element.id_short not in self.general_information_semantic_ids_short.values()
                and not self._remove_empty_submodel_element(element)
            ]
            self.technical_properties.value = [
                element
                for element in self.technical_properties.value
                if not self._remove_empty_submodel_element(element)
            ]
            self.further_information.value = [
                element
                for element in self.further_information.value
                if not self._remove_empty_submodel_element(element)
            ]

    def dumps(self):
        return json.dumps(self.submodel, cls=json_serialization.AASToJsonEncoder, indent=2)
    
    def save_as_aasx(self, filepath: str, aas: model.AssetAdministrationShell | None = None):
        if aas is None:
            aas = model.AssetAdministrationShell(
                id_= f"https://eclipse.dev/basyx/pdf-to-aas/aas/{uuid.uuid4()}",
                asset_information=model.AssetInformation(
                    asset_kind=model.AssetKind.TYPE,
                    global_asset_id=f"https://eclipse.dev/basyx/pdf-to-aas/asset/{uuid.uuid4()}"
                    )
            )

        aas.submodel.add(model.ModelReference.from_referable(self.submodel))
        #TODO add pdf file (to handover documentation submodel) if given?

        with AASXWriter(filepath) as writer:
            writer.write_aas(
                aas_ids=aas.id,
                object_store=model.DictObjectStore([aas, self.submodel] + list(self.concept_descriptions.values())),
                file_store=DictSupplementaryFileContainer(),
                write_json=True)