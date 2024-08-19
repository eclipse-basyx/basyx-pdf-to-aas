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

def cast_range(property_: Property):
    min, max = property_.parse_numeric_range()
    if isinstance(min, float) or isinstance(max, float):
        return None if min is None else float(min), None if max is None else float(max), model.datatypes.Float
    if isinstance(min, int) or isinstance(max, int):
        return None if min is None else int(min), None if max is None else int(max), model.datatypes.Integer
    else:
        return None, None, model.datatypes.String # XSD has no equivalent to None

def cast_property(value, definition) -> model.ValueDataType:
    if value is None:
        return None
    if definition is not None:
        match definition.type:
            case 'bool': return model.datatypes.Boolean(value)
            case 'numeric' | 'range':
            # Range is catched earlier and should not be reached
                try:
                    casted = float(value)
                except (ValueError, TypeError):
                    return model.datatypes.String(value)
                if casted.is_integer():
                    casted = int(casted)
                    return model.datatypes.Integer(casted)
                return model.datatypes.Float(casted)
            case 'string': return model.datatypes.String(value)
    
    if isinstance(value, bool):
        return model.datatypes.Boolean(value)
    if isinstance(value, int):
        return model.datatypes.Integer(value)
    if isinstance(value, float):
        if value.is_integer():
            return model.datatypes.Integer(value)
        return model.datatypes.Float(value)
    return model.datatypes.String(value)

def create_aas_property_recursive(property_: Property, value, id_short, display_name):
    if isinstance(value, (list, set, tuple, dict)):
        if len(value) == 0:
            value = None
        else:
            #TODO check wether to use SubmodelElementList for ordered stuff
            smc = model.SubmodelElementCollection(
                id_short = id_short,
                display_name = display_name,
                semantic_id = semantic_id(property_.definition_id)
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
                        create_aas_property_recursive(
                            property_,
                            val,
                            id_short+'_'+str(key),
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

    value = cast_property(value, property_.definition)
    return model.Property(
        id_short = id_short,
        display_name = display_name,
        value_type = type(value) if value is not None else model.datatypes.String,
        value = value,
        value_id=semantic_id(value_id),
        semantic_id = semantic_id(property_.definition_id)
    )

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

    @staticmethod
    def create_aas_property(property_: Property) -> model.DataElement | None:
        if property_.definition is not None:
            unit = property_.unit
            if property_.unit is not None and len(unit.strip()) > 0 and len(property_.definition.unit) > 0 and unit != property_.definition.unit:
                logger.warning(f"Unit '{unit}' of '{property_.label}' differs from definition '{property_.definition.unit}'")
        
        if property_.label is not None and len(property_.label) > 0:
            id_short = property_.label
        elif property_.definition is not None:
            id_short = property_.definition_name
            if id_short is None or len(id_short) == 0:
                id_short = property_.definition_id
        else:
            logger.warning(f"No id_short for: {property_}")
            return None

        display_name = id_short[:64] # MultiLanguageNameType has a maximum length of 64!
        display_name = model.MultiLanguageNameType({property_.language: display_name})
        id_short = re.sub(r'[^a-zA-Z0-9]', '_', id_short)

        if property_.definition is not None and property_.definition.type == "range":
            min, max, type_ = cast_range(property_)
            return model.Range(
                id_short = id_short,
                display_name = display_name,
                min=min,
                max=max,
                value_type = type_,
                semantic_id = semantic_id(property_.definition_id)
            )

        return create_aas_property_recursive(property_, property_.value, id_short, display_name)

    def add_properties(self, properties : list[Property]):       
        #TODO fill general information if provided in properties

        technical_properties : model.SubmodelElementCollection = self.submodel.submodel_element.get('id_short', 'TechnicalProperties')
        for property_ in properties:
            aas_property = self.create_aas_property(property_)
            if aas_property is None:
                continue

            if technical_properties.value.contains_id('id_short', aas_property.id_short):
                aas_property.id_short = str(uuid.uuid4())
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