"""Generator for Technical Data Submodels of Asset Administration Shells."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import ClassVar

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXWriter, DictSupplementaryFileContainer
from basyx.aas.adapter.json import json_serialization
from basyx.aas.model.base import AASConstraintViolation

from pdf2aas.dictionary import ECLASS, Dictionary
from pdf2aas.model import Property, PropertyDefinition

from .aas import anti_alphanumeric_regex, cast_property, cast_range
from .core import Generator

logger = logging.getLogger(__name__)

AAS_NAME_LENGTH = 128
AAS_MULTILANG_TEXT_LENGTH = 1023
AAS_MULTILANG_NAME_LENGTH = 64
AAS_IEC61360_NAME_LENGTH = 255
AAS_IEC61360_DEFINITION_LENGTH = 1023
AAS_IEC61360_VALUE_LENGTH = 2000
AAS_IEC61360_DATA_SPEC_REFERENCE = model.ExternalReference(
    (
        model.Key(
            model.KeyTypes.GLOBAL_REFERENCE,
            "http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0",
        ),
    ),
)


class AASSubmodelTechnicalData(Generator):
    """Generator for technical data submodels according to IDTA Template 02003.

    Attributes:
        identifier (str): Submodel identifier.
        submodel (Submodel): The submodel with added properties.
        concept_descriptions: (dict[str, model.concept.ConceptDescription]):
            Id to concept description mapping for added properties.
        general_information (SubmodelElementCollection): Shortcut to the general
            information collection of the submodel. Contains only pre defined
            properties, like ManufacturerName. They are updated, if found in new
            properties added to the submodel.
        general_information_semantic_ids_short (dict[str,str]): Maps the
            relevant part of the general information IRDIs to their id short.
        product_classifications (SubmodelElementCollection): Shortcut to the
            product classifications collection of the submodel. Can be extended
            via `add_classification()`.
        technical_properties (SubmodelElementCollection): Shortcut to the
            technical properties collection of the submodel. This is were
            typically properties are added via `add_properties()`.
        further_information (SubmodelElementCollection): Shortcut to the
            further information collection of the submodel. Holding the date
            and a remark, which can be extended.

    """

    def __init__(
        self,
        identifier: str | None = None,
    ) -> None:
        """Initialize the AAS submodel with a specified or uuid identifer."""
        self.identifier = (
            f"https://eclipse.dev/basyx/pdf-to-aas/submodel/{uuid.uuid4()}"
            if identifier is None
            else identifier
        )
        self.concept_descriptions: dict[str, model.concept.ConceptDescription] = {}
        self.reset()

    def reset(self) -> None:
        """Reset the properties list and concept descriptions.

        Also resets the submodel by instanciating a new submodel template.
        """
        super().reset()
        self.concept_descriptions = {}
        self.submodel = self._create_submodel_template()

    def _create_submodel_template(self) -> model.Submodel:
        submodel = model.Submodel(
            id_=self.identifier,
            id_short="TechnicalData",
            semantic_id=self._create_semantic_id(
                "https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2",
            ),
        )

        self.general_information = model.SubmodelElementCollection(
            id_short="GeneralInformation",
            semantic_id=self._create_semantic_id(
                "https://admin-shell.io/ZVEI/TechnicalData/GeneralInformation/1/1",
            ),
        )
        self.general_information.value.add(
            model.Property(
                id_short="ManufacturerName",
                value_type=model.datatypes.String,
                category="PARAMETER",
                semantic_id=self._create_semantic_id("0173-1#02-AAO677#002"),
            ),
        )
        # ManufacturerLogo is optional
        self.general_information.value.add(
            model.MultiLanguageProperty(
                id_short="ManufacturerProductDesignation",
                category="PARAMETER",
                semantic_id=self._create_semantic_id("0173-1#02-AAW338#001"),
            ),
        )
        self.general_information.value.add(
            model.Property(
                id_short="ManufacturerArticleNumber",
                value_type=model.datatypes.String,
                category="PARAMETER",
                semantic_id=self._create_semantic_id("0173-1#02-AAO676#003"),
            ),
        )
        self.general_information.value.add(
            model.Property(
                id_short="ManufacturerOrderCode",
                value_type=model.datatypes.String,
                category="PARAMETER",
                semantic_id=self._create_semantic_id("0173-1#02-AAO227#002"),
            ),
        )
        # ProductImage is optional
        submodel.submodel_element.add(self.general_information)

        self.product_classifications = model.SubmodelElementCollection(
            id_short="ProductClassifications",
            semantic_id=self._create_semantic_id(
                "https://admin-shell.io/ZVEI/TechnicalData/ProductClassifications/1/1",
            ),
        )
        submodel.submodel_element.add(self.product_classifications)

        self.technical_properties = model.SubmodelElementCollection(
            id_short="TechnicalProperties",
            semantic_id=self._create_semantic_id(
                "https://admin-shell.io/ZVEI/TechnicalData/TechnicalProperties/1/1",
            ),
        )
        submodel.submodel_element.add(self.technical_properties)

        self.further_information = model.SubmodelElementCollection(
            id_short="FurtherInformation",
            semantic_id=self._create_semantic_id(
                "https://admin-shell.io/ZVEI/TechnicalData/FurtherInformation/1/1",
            ),
        )
        self.further_information.value.add(
            model.MultiLanguageProperty(
                id_short="TextStatement01",
                value=model.MultiLanguageTextType(
                    {
                        "en": "Created with basyx pdf-to-aas. No liability of any kind is assumed for the contained information.",  # noqa: E501
                    },
                ),
                category="PARAMETER",
                semantic_id=self._create_semantic_id(
                    "https://admin-shell.io/ZVEI/TechnicalData/TextStatement/1/1",
                ),
            ),
        )
        self.further_information.value.add(
            model.Property(
                id_short="ValidDate",
                value_type=model.datatypes.Date,
                value=datetime.now(tz=timezone.utc).date(),
                category="PARAMETER",
                semantic_id=self._create_semantic_id(
                    "https://admin-shell.io/ZVEI/TechnicalData/ValidDate/1/1",
                ),
            ),
        )
        submodel.submodel_element.add(self.further_information)
        return submodel

    def add_classification(self, dictionary: Dictionary, class_id: str) -> None:
        """Add a ProductClassificationItem based on the dictionary and class to the submodel."""
        classification = model.SubmodelElementCollection(
            id_short=f"ProductClassificationItem{len(self.product_classifications.value)+1:02d}",
            semantic_id=self._create_semantic_id(
                "https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationItem/1/1",
            ),
        )
        classification.value.add(
            model.Property(
                id_short="ProductClassificationSystem",
                value_type=model.datatypes.String,
                value=dictionary.name,
                category="PARAMETER",
                semantic_id=self._create_semantic_id(
                    "https://admin-shell.io/ZVEI/TechnicalData/ProductClassificationSystem/1/1",
                ),
            ),
        )
        classification.value.add(
            model.Property(
                id_short="ClassificationSystemVersion",
                value_type=model.datatypes.String,
                value=dictionary.release,
                category="PARAMETER",
                semantic_id=self._create_semantic_id(
                    "https://admin-shell.io/ZVEI/TechnicalData/ClassificationSystemVersion/1/1",
                ),
            ),
        )
        classification.value.add(
            model.Property(
                id_short="ProductClassId",
                value_type=model.datatypes.String,
                value=class_id,
                category="PARAMETER",
                semantic_id=self._create_semantic_id(
                    "https://admin-shell.io/ZVEI/TechnicalData/ProductClassId/1/1",
                ),
            ),
        )
        self.product_classifications.value.add(classification)

    @staticmethod
    def _add_embedded_data_spec(
        cd: model.concept.ConceptDescription,
        definition: PropertyDefinition,
    ) -> None:
        if len(definition.name) == 0:
            return
        data_spec = model.DataSpecificationIEC61360(
            model.PreferredNameTypeIEC61360(
                {ln: v[:AAS_IEC61360_NAME_LENGTH] for ln, v in definition.name.items()},
            ),
        )
        match definition.type:
            case "bool":
                data_spec.data_type = model.DataTypeIEC61360.BOOLEAN
            case "numeric":
                data_spec.data_type = model.DataTypeIEC61360.REAL_COUNT
            case "range":
                data_spec.data_type = model.DataTypeIEC61360.REAL_COUNT
                data_spec.level_types = {model.IEC61360LevelType.MIN, model.IEC61360LevelType.MAX}
            case "string":
                data_spec.data_type = model.DataTypeIEC61360.STRING
        if len(definition.definition) > 0:
            data_spec.definition = model.DefinitionTypeIEC61360(
                {ln: v[:AAS_IEC61360_DEFINITION_LENGTH] for ln, v in definition.definition.items()},
            )
        if definition.unit is not None and len(definition.unit) > 0:
            data_spec.unit = definition.unit
        if definition.values:
            data_spec.value_list = AASSubmodelTechnicalData._get_embedded_data_spec_value_list(
                definition,
            )
        cd.embedded_data_specifications.append(
            model.EmbeddedDataSpecification(
                data_specification=AAS_IEC61360_DATA_SPEC_REFERENCE,
                data_specification_content=data_spec,
            ),
        )

    @staticmethod
    def _get_embedded_data_spec_value_list(
        definition: PropertyDefinition,
    ) -> set[model.ValueReferencePair]:
        value_list = set()
        for value_dict in definition.values:
            if isinstance(value_dict, dict):
                value_id = value_dict.get("id")
                value = value_dict.get("value")
            else:
                value_id = None
                value = str(value_dict)
            if value is None or len(value) == 0:
                continue
            if value_id is None:
                value_id = f"{definition.id}/{value}"
            value_list.add(
                model.ValueReferencePair(
                    value[:AAS_IEC61360_VALUE_LENGTH],
                    model.ExternalReference(
                        (
                            model.Key(
                                type_=model.KeyTypes.GLOBAL_REFERENCE,
                                value=value_id[:AAS_IEC61360_VALUE_LENGTH],
                            ),
                        ),
                    ),
                ),
            )
        return value_list

    def _add_concept_description(
        self,
        reference: str,
        property_defintion: PropertyDefinition | None = None,
        value: str | None = None,
    ) -> None:
        if reference in self.concept_descriptions:
            return
        cd = model.concept.ConceptDescription(
            id_=reference,
            is_case_of={
                model.ExternalReference(
                    (
                        model.Key(
                            type_=model.KeyTypes.GLOBAL_REFERENCE,
                            value=reference,
                        ),
                    ),
                ),
            },
            category="PROPERTY" if value is None else "VALUE",  # deprecated since V3.0
        )
        if property_defintion:
            name = property_defintion.get_name("en")
            if name is not None:
                cd.id_short = re.sub(anti_alphanumeric_regex, "_", name)
                cd.display_name = model.MultiLanguageNameType(
                    {
                        ln: n[:AAS_MULTILANG_NAME_LENGTH]
                        for ln, n in property_defintion.name.items()
                    },
                )
            if property_defintion.definition is not None and len(property_defintion.definition) > 0:
                cd.description = model.MultiLanguageTextType(
                    {
                        ln: n[:AAS_MULTILANG_TEXT_LENGTH]
                        for ln, n in property_defintion.definition.items()
                    },
                )
            self._add_embedded_data_spec(cd, property_defintion)
        elif value:
            cd.id_short = re.sub(anti_alphanumeric_regex, "_", value)
            cd.display_name = model.MultiLanguageNameType({"en": value[:AAS_MULTILANG_NAME_LENGTH]})

        self.concept_descriptions[reference] = cd

    def _create_semantic_id(
        self,
        reference: str | None,
        property_defintion: PropertyDefinition | None = None,
        value: str | None = None,
    ) -> model.ModelReference | None:
        if reference is None:
            return None
        self._add_concept_description(reference, property_defintion, value)
        return model.ModelReference(
            (
                model.Key(
                    type_=model.KeyTypes.CONCEPT_DESCRIPTION,
                    value=reference,
                ),
            ),
            type_=model.concept.ConceptDescription,
        )

    @staticmethod
    def _create_id_short(proposal: str | None = None) -> str:
        id_short = re.sub(anti_alphanumeric_regex, "_", proposal) if proposal is not None else ""
        if len(id_short) == 0:
            id_short = "ID_" + str(uuid.uuid4()).replace("-", "_")
        elif not id_short[0].isalpha():
            id_short = "ID_" + id_short
        return id_short[:AAS_NAME_LENGTH]

    def _create_aas_property_smc(
        self,
        property_: Property,
        value: model.ValueDataType,
        id_short: str,
        display_name: model.MultiLanguageNameType | None,
        description: model.MultiLanguageTextType | None,
    ) -> model.SubmodelElementCollection:
        # TODO: check wether to use SubmodelElementList for ordered stuff
        smc = model.SubmodelElementCollection(
            id_short=self._create_id_short(id_short),
            display_name=display_name,
            semantic_id=self._create_semantic_id(property_.definition_id),
            description=description,
        )
        if isinstance(value, dict):
            iterator = iter(value.items())
        elif isinstance(value, list | tuple):
            iterator = enumerate(value)
        elif isinstance(value, set):
            iterator = enumerate(list(value))
        for key, val in iterator:
            try:
                smc.value.add(
                    self._create_aas_property_recursive(
                        property_,
                        val,
                        id_short + "_" + str(key),
                        None,
                        None,
                    ),
                )
            except AASConstraintViolation as error:  # noqa: PERF203
                logger.warning(
                    "Couldn't add %s item to property %s: %s",
                    type(value),
                    display_name,
                    error,
                )
        return smc

    def _create_aas_property_recursive(
        self,
        property_: Property,
        value: model.ValueDataType,
        id_short: str,
        display_name: model.MultiLanguageNameType | None,
        description: model.MultiLanguageTextType | None,
    ) -> model.SubmodelElement:
        if isinstance(value, list | set | tuple | dict):
            if len(value) == 0:
                value = None
            elif len(value) == 1:
                value = next(iter(value))
            else:
                return self._create_aas_property_smc(
                    property_,
                    value,
                    id_short,
                    display_name,
                    description,
                )

        value_id: model.ModelReference | None = None
        if (
            property_.definition is not None
            and len(property_.definition.values) > 0
            and value is not None
        ):
            value_id_raw = property_.definition.get_value_id(str(value))
            if value_id_raw is None:
                logger.warning(
                    "Value '%s' of '%s' not found in defined values.",
                    value,
                    property_.label,
                )
            else:
                if isinstance(value_id_raw, int):
                    value_id_raw = property_.definition.id + "/" + str(value_id_raw)
                value_id = self._create_semantic_id(value_id_raw, property_.definition, str(value))

        value = cast_property(value, property_.definition)
        return model.Property(
            id_short=self._create_id_short(id_short),
            display_name=display_name,
            description=description,
            value_type=type(value) if value is not None else model.datatypes.String,
            value=value,
            value_id=value_id,
            semantic_id=self._create_semantic_id(property_.definition_id, property_.definition),
        )

    def _create_aas_property(self, property_: Property) -> model.SubmodelElement | None:
        if property_.label is not None and len(property_.label) > 0:
            id_short = property_.label
        elif property_.definition is not None:
            id_short = property_.definition_name or property_.definition.id
        else:
            logger.warning("No id_short for: %s", property_)
            return None

        display_name = None
        if property_.definition is not None:
            unit = property_.unit
            if (
                unit is not None
                and len(unit.strip()) > 0  # type: ignore[unit-attr]
                and len(property_.definition.unit) > 0
                and unit != property_.definition.unit
            ):
                logger.warning(
                    "Unit '%s' of '%s' differs from definition '%s'",
                    unit,
                    property_.label,
                    property_.definition.unit,
                )
            if len(property_.definition.name) > 0:
                display_name = model.MultiLanguageNameType(
                    {
                        ln: n[:AAS_MULTILANG_NAME_LENGTH]
                        for ln, n in property_.definition.name.items()
                    },
                )

        if display_name is None or len(display_name) == 0:
            display_name = model.MultiLanguageNameType(
                {property_.language: id_short[:AAS_MULTILANG_NAME_LENGTH]},
            )

        if property_.reference is None:
            description = None
        else:
            description = model.MultiLanguageTextType(
                {property_.language: property_.reference[:AAS_MULTILANG_TEXT_LENGTH]},
            )

        if property_.definition is not None and property_.definition.type == "range":
            min_, max_, type_ = cast_range(property_)
            return model.Range(
                id_short=self._create_id_short(id_short),
                display_name=display_name,
                description=description,
                min=min_,
                max=max_,
                value_type=type_,
                semantic_id=self._create_semantic_id(property_.definition_id, property_.definition),
            )

        return self._create_aas_property_recursive(
            property_,
            property_.value,
            id_short,
            display_name,
            description,
        )

    general_information_semantic_ids_short: ClassVar[dict[str, str]] = {
        "AAO677": "ManufacturerName",
        "AAW338": "ManufacturerProductDesignation",
        "AAO676": "ManufacturerArticleNumber",
        "AAO227": "ManufacturerOrderCode",
    }

    def _update_general_information(self, property_: Property) -> bool:
        id_short = None
        if property_.definition_id is not None and ECLASS.check_property_irdi(
            property_.definition_id,
        ):
            id_short = self.general_information_semantic_ids_short.get(
                property_.definition_id[10:16],
            )

        if property_.label is not None:
            for label in self.general_information_semantic_ids_short.values():
                if re.sub(anti_alphanumeric_regex, "", property_.label.lower()) == label.lower():
                    id_short = label
                    break
        if id_short is None:
            return False

        general_info = self.general_information.value.get("id_short", id_short)
        if isinstance(general_info, model.MultiLanguageProperty):
            general_info.value = model.MultiLanguageTextType(
                {property_.language: str(property_.value)},
            )
        elif isinstance(general_info, model.Property):
            general_info.value = str(property_.value)
        else:
            return False
        return True

    @staticmethod
    def _generate_next_free_id_short(container: model.NamespaceSet, id_short: str) -> str:
        while container.contains_id("id_short", id_short):
            i = len(id_short) - 1
            while i >= 0 and id_short[i].isdigit():
                i -= 1

            if i == len(id_short) - 1:
                next_id_short = id_short + "_1"
            else:
                prefix = id_short[: i + 1]
                num = int(id_short[i + 1 :]) + 1
                next_id_short = prefix + str(num)

            if len(next_id_short) > AAS_NAME_LENGTH:
                if i == len(id_short) - 1:
                    next_id_short = id_short[: AAS_NAME_LENGTH - 2] + "_1"
                else:
                    prefix = id_short[: AAS_NAME_LENGTH - len(str(num))]
                    next_id_short = prefix + str(num)
            id_short = next_id_short
        return id_short

    def add_properties(self, properties: list[Property]) -> None:
        """Add extracted properties to the submodel.

        Converts the given extracted properties to AAS Property, Range or
        Collections of them if multiple values are given. If the property seems
        to be one of the general information fields, it is updated in the
        respective collection. Also generates concept descriptions and id short
        etc. when needed.
        """
        super().add_properties(properties)
        for property_ in properties:
            if self._update_general_information(property_):
                continue

            aas_property = self._create_aas_property(property_)
            if aas_property is None:
                continue

            aas_property.id_short = self._generate_next_free_id_short(
                self.technical_properties.value,
                aas_property.id_short,
            )

            try:
                self.technical_properties.value.add(aas_property)
            except AASConstraintViolation as error:
                logger.warning("Couldn't add property to submodel: %s", error)

    @staticmethod
    def _remove_empty_submodel_element(element: model.SubmodelElement) -> bool:
        if isinstance(element, model.SubmodelElementCollection | model.SubmodelElementList):
            element.value = [
                subelement
                for subelement in element.value
                if not AASSubmodelTechnicalData._remove_empty_submodel_element(subelement)
            ]  # type: ignore[assignment]
            if len(element.value) == 0:
                return True
        elif isinstance(element, model.Property):
            if element.value is None:
                return True
            if hasattr(element.value, "__len__") and len(element.value) == 0:
                return True
        elif isinstance(element, model.MultiLanguageProperty):
            if element.value is None:
                return True
        elif isinstance(element, model.Range):
            if element.min is None and element.max is None:
                return True
        return False

    def remove_empty_submodel_elements(self, *, remove_mandatory: bool = False) -> None:
        """Remove all submodel elements that have a value, which can be considered empty.

        Only removes mandatory values from general information collection, if
        `remove_mandatory` is true. This breaks conformance with the submodel
        template.

        This can not be reverted. To get an AAS with empty values again, one has
        to call reset() and add_properties() again.
        """
        if remove_mandatory:
            self.submodel.submodel_element = [
                element
                for element in self.submodel.submodel_element
                if not self._remove_empty_submodel_element(element)
            ]  # type: ignore[assignment]
        else:
            self.general_information.value = [
                element
                for element in self.general_information.value
                if element.id_short in self.general_information_semantic_ids_short.values()
                or not self._remove_empty_submodel_element(element)
            ]  # type: ignore[assignment]
            self.technical_properties.value = [
                element
                for element in self.technical_properties.value
                if not self._remove_empty_submodel_element(element)
            ]  # type: ignore[assignment]
            self.further_information.value = [
                element
                for element in self.further_information.value
                if not self._remove_empty_submodel_element(element)
            ]  # type: ignore[assignment]

    def dumps(self) -> str:
        """Serialize and return the submodel to a json string."""
        return json.dumps(self.submodel, cls=json_serialization.AASToJsonEncoder, indent=2)

    def save_as_aasx(
        self,
        filepath: str,
        aas: model.AssetAdministrationShell | None = None,
    ) -> None:
        """Save the submodel together with an AAS in an aasx package.

        A new AAS with a uuid in the identifier will be created, if `aas` is None.
        """
        if aas is None:
            aas = model.AssetAdministrationShell(
                id_=f"https://eclipse.dev/basyx/pdf-to-aas/aas/{uuid.uuid4()}",
                asset_information=model.AssetInformation(
                    asset_kind=model.AssetKind.TYPE,
                    global_asset_id=f"https://eclipse.dev/basyx/pdf-to-aas/asset/{uuid.uuid4()}",
                ),
            )

        aas.submodel.add(model.ModelReference.from_referable(self.submodel))
        # TODO: add pdf file (to handover documentation submodel) if given?

        with AASXWriter(filepath) as writer:
            writer.write_aas(
                aas_ids=aas.id,
                object_store=model.DictObjectStore(
                    [aas, self.submodel, *list(self.concept_descriptions.values())],
                ),
                file_store=DictSupplementaryFileContainer(),
                write_json=True,
            )
