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
from ..dictionary import Dictionary
from ..extractor import Property

logger = logging.getLogger(__name__)

def semantic_id(reference):
    if reference is None:
        return None
    return model.ExternalReference((
                model.Key(
                    type_= model.KeyTypes.GLOBAL_REFERENCE,
                    value=reference
                ),)
            )

def create_submodel_template(identifier:str=None):
    submodel = model.Submodel(
        id_= f"https://eclipse.dev/basyx/pdf-to-aas/submodel/{uuid.uuid4()}" if identifier is None else identifier,
        id_short = "TechnicalData",
        semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2")
    )
    submodel.submodel_element.add(
        model.SubmodelElementCollection(
            id_short ="GeneralInformation",
            semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/GeneralInformation/1/1")
        )
    )
    # TODO add mandatory properties?
    submodel.submodel_element.add(
        model.SubmodelElementCollection(
            id_short = "ProductClassifications",
            semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassifications/1/1")
        )
    )
    submodel.submodel_element.add(
        model.SubmodelElementCollection(
            id_short = "TechnicalProperties",
            semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/TechnicalProperties/1/1")
        )
    )
    further_information = model.SubmodelElementCollection(
            id_short = "FurtherInformation",
            semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/FurtherInformation/1/1")
    )
    further_information.value.add(
        model.Property(
            id_short = 'TextStatement',
            value_type = model.datatypes.String,
            value = 'Created with basyx pdf-to-aas. We assume no liability for the accuracy of the information.',
            category = "PARAMETER",
            semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/TextStatement/1/1")
        )
    )
    further_information.value.add(
        model.Property(
                id_short='ValidDate',
                value_type = model.datatypes.Date,
                value = date.today(),
                category = "PARAMETER",
                semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ValidDate/1/1")
        )
    )
    submodel.submodel_element.add(further_information)
    return submodel

def get_property_xsd_type(property_: Property):
    if isinstance(property_.value, bool):
        return model.datatypes.Boolean
    if isinstance(property_.value, int):
        return model.datatypes.Integer
    if isinstance(property_.value, float):
        if property_.value.is_integer():
            property_.value = int(property_.value)
            return model.datatypes.Integer
        return model.datatypes.Float

    if property_.definition is not None:
        match property_.definition.type:
            case 'bool': return model.datatypes.Boolean
            case 'numeric':
                try:
                    property_.value = float(property_.value)
                    if property_.value.is_integer():
                        property_.value = int(property_.value)
                        return model.datatypes.Integer
                except (ValueError, TypeError):
                    return model.datatypes.String
                return model.datatypes.Float
            case 'range': return (model.datatypes.Float, )
            case 'bool': return model.datatypes.Boolean
            case 'string': return model.datatypes.String

    return model.datatypes.String

class AASSubmodelTechnicalData(Generator):
    def __init__(
        self,
        identifier: str = None,
        dictionary: Dictionary = None,
        class_id: str = None
    ) -> None:
        self.identifier = identifier
        self.dictionary = dictionary
        self.class_id = class_id
        self.reset()
        
    def reset(self): 
        self.submodel = create_submodel_template(self.identifier)
        if self.dictionary is not None and self.class_id is not None:
            self._add_classification(self.dictionary, self.class_id)

    def _add_classification(self, dictionary:Dictionary, class_id:str):
        classification = model.SubmodelElementCollection(
            id_short = "ProductClassificationItem01",
            semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationItem/1/1")
        )
        classification.value.add(
            model.Property(
                id_short = 'ProductClassificationSystem',
                value_type = model.datatypes.String,
                value = dictionary.name,
                category = "PARAMETER",
                semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationSystem/1/1")
            )
        )
        classification.value.add(
            model.Property(
                id_short = 'ClassificationSystemVersion',
                value_type = model.datatypes.String,
                value = dictionary.release,
                category = "PARAMETER",
                semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ClassificationSystemVersion/1/1")
            )
        )
        classification.value.add(
            model.Property(
                id_short='ProductClassId',
                value_type = model.datatypes.String,
                value = class_id,
                category = "PARAMETER",
                semantic_id = semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassId/1/1")
            )
        )
        self.submodel.submodel_element.get('id_short', 'ProductClassifications').value.add(classification)

    def add_properties(self, properties : list[Property]):       
        #TODO fill general information if provided in properties

        technical_properties : model.SubmodelElementCollection = self.submodel.submodel_element.get('id_short', 'TechnicalProperties')
        for property_ in properties:
            value_id = None
            if property_.definition is not None:
                unit = property_.unit
                if property_.unit is not None and len(unit.strip()) > 0 and len(property_.definition.unit) > 0 and unit != property_.definition.unit:
                    logger.warning(f"Unit '{unit}' of '{property_.label}' differs from definition '{property_.definition.unit}'")
                if len(property_.definition.values) > 0 and property_.value is not None:
                    value_id = property_.definition.get_value_id(str(property_.value))
                    if value_id is None:
                        logger.warning(f"Value '{property_.value}' of '{property_.label}' not found in defined values.")
            
            if property_.label is not None and len(property_.label) > 0:
                id_short = property_.label
            elif property_.definition is not None:
                id_short = property_.definition_name
                if id_short is None:
                    id_short = property_.definition_id
            else:
                logger.warning(f"No id_short for: {property_}")
                continue

            display_name = id_short[:64] # MultiLanguageNameType has a maximum length of 64!
            display_name = model.MultiLanguageNameType({property_.language: display_name})

            id_short = re.sub(r'[^a-zA-Z0-9]', '_', id_short)
            if technical_properties.value.contains_id('id_short', id_short):
                id_short += str(uuid.uuid4())
            
            value_type = get_property_xsd_type(property_)
            try:
                if isinstance(value_type, tuple):
                    value = property_.parse_range()
                    aas_property = model.Range(
                        id_short = id_short,
                        display_name = display_name,
                        min=value[0],
                        max=value[1],
                        value_type = value_type[0],
                        semantic_id = semantic_id(property_.definition_id)
                    )
                else:
                    aas_property = model.Property(
                        id_short = id_short,
                        display_name = display_name,
                        value_type = value_type,
                        value = property_.value,
                        value_id=value_id,
                        semantic_id = semantic_id(property_.definition_id)
                    )
            except TypeError as error:
                logger.warning(f"Couldn't create property for submodel: {error}")
                continue

            try:
                technical_properties.value.add(aas_property)
            except AASConstraintViolation as error:
                logger.warning(f"Couldn't add property to submodel: {error}")
    
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
                object_store=model.DictObjectStore([aas, self.submodel]),
                file_store=DictSupplementaryFileContainer(),
                write_json=True)