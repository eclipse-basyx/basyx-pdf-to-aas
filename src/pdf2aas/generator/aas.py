import logging
import json
from datetime import date
import re

from basyx.aas import model
from basyx.aas.adapter.json import json_deserialization, json_serialization

from .core import Generator
from ..dictionary import ECLASS

logger = logging.getLogger(__name__)

def ext_semantic_id(reference):
    return model.ExternalReference((
                model.Key(
                    type_= model.KeyTypes.GLOBAL_REFERENCE,
                    value=reference
                ),)
            )

def create_submodel_template():
    submodel = model.Submodel(
        id_= "https://eclipse.dev/basyx/pdf-to-aas/technical-data-submodel",
        id_short = "TechnicalData",
        semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2")
    )
    submodel.submodel_element.add(
        model.SubmodelElementCollection(
            id_short ="GeneralInformation",
            semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/GeneralInformation/1/1")
        )
    )
    # TODO add mandatory properties?
    submodel.submodel_element.add(
        model.SubmodelElementCollection(
            id_short = "ProductClassifications",
            semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassifications/1/1")
        )
    )
    submodel.submodel_element.add(
        model.SubmodelElementCollection(
            id_short = "TechnicalProperties",
            semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/TechnicalProperties/1/1")
        )
    )
    further_information = model.SubmodelElementCollection(
            id_short = "FurtherInformation",
            semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/FurtherInformation/1/1")
    )
    further_information.value.add(
        model.Property(
            id_short = 'TextStatement',
            value_type = model.datatypes.String,
            value = 'Created with basyx pdf-to-aas. We assume no liability for the accuracy of the information.',
            category = "PARAMETER",
            semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/TextStatement/1/1")
        )
    )
    further_information.value.add(
        model.Property(
                id_short='ValidDate',
                value_type = model.datatypes.Date,
                value = date.today(),
                category = "PARAMETER",
                semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ValidDate/1/1")
        )
    )
    submodel.submodel_element.add(further_information)
    return submodel

def json_data_type_to_xsd(value):
    if isinstance(value, str):
        return model.datatypes.String
    if isinstance(value, int):
        return model.datatypes.Integer
    if isinstance(value, float):
        return model.datatypes.Float
    if isinstance(value, bool):
        return model.datatypes.Boolean
    return model.datatypes.String

class AASSubmodelTechnicalData(Generator):      

    def generate(self, properties : list, identifier : str = None, dictionary : ECLASS = None , class_id : str = None) -> str:
        submodel = create_submodel_template()
        if identifier:
            submodel.identifier = identifier
        
        if dictionary is not None:
            classification = model.SubmodelElementCollection(
                id_short = "ProductClassificationItem01",
                semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationItem/1/1")
            )
            classification.value.add(
                model.Property(
                    id_short = 'ProductClassificationSystem',
                    value_type = model.datatypes.String,
                    value = 'ECLASS',
                    category = "PARAMETER",
                    semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationSystem/1/1")
                )
            )
            classification.value.add(
                model.Property(
                    id_short = 'ClassificationSystemVersion',
                    value_type = model.datatypes.String,
                    value = dictionary.release,
                    category = "PARAMETER",
                    semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ClassificationSystemVersion/1/1")
                )
            )
            classification.value.add(
                model.Property(
                    id_short='ProductClassId',
                    value_type = model.datatypes.String,
                    value = class_id,
                    category = "PARAMETER",
                    semantic_id = ext_semantic_id("https://admin-shell.io/ZVEI/TechnicalData/ProductClassId/1/1")
                )
            )
            submodel.submodel_element.get('id_short', 'ProductClassifications').value.add(classification)
        
        #TODO fill general information if provided in properties

        technical_properties = submodel.submodel_element.get('id_short', 'TechnicalProperties')
        for property in properties:
            property = model.Property(
                id_short = re.sub(r'[^a-zA-Z0-9]|_', '', property.get('property')),
                display_name = model.MultiLanguageNameType({'en': property.get('property')}),
                value_type = json_data_type_to_xsd(property.get('value')), #TODO get from definition?
                value = property.get('value'),
                semantic_id = ext_semantic_id(property.get('id'))
                #TODO unit?
            )
            technical_properties.value.add(property)

        return json.dumps(submodel, cls=json_serialization.AASToJsonEncoder, indent=2)
