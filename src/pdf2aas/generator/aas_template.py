"""Generator for using Asset Administration Shell files as template."""

import collections.abc
import copy
import io
import logging
from collections.abc import Callable

from basyx.aas import model
from basyx.aas.adapter.aasx import (
    AASXReader,
    AASXWriter,
    DictSupplementaryFileContainer,
)
from basyx.aas.adapter.json import json_serialization
from basyx.aas.util.traversal import walk_submodel

from pdf2aas.model import Property, PropertyDefinition

from .aas import (
    cast_property,
    cast_range,
    get_dict_data_type_from_iec6360,
    get_dict_data_type_from_xsd,
)
from .core import Generator

logger = logging.getLogger(__name__)


class AASTemplate(Generator):
    """Generator, that loads an AAS as template to read and update its properties.

    Attributes:
        aasx_path (str): The file path to the AASX package which is used as template.
        object_store (DictObjectStore): Objects read from the AASX package.
        file_store (DictSupplementaryFileContainer): Files read from the AASX package.
        submodels (list[Submodel]): list of submodels read from the AASX package.
        submodel_filter (Callable[[model.Submodel], bool]): filter submodels used to
            select properties and their definitions.
        submodel_element_filter (Callable[[model.SubmodelElement], bool]): filter submodel elements
            to select properties and their definitions.

    """

    def __init__(
        self,
        aasx_path: str | None = None,
        submodel_filter: Callable[[model.Submodel], bool] | None = None,
        submodel_element_filter: Callable[[model.SubmodelElement], bool] | None = None,
    ) -> None:
        """Initialize the AASTemplate with a specified AASX package path and filters."""
        self._properties: dict[
            str,
            tuple[Property, model.Property | model.Range | model.MultiLanguageProperty],
        ] = {}
        self._aasx_path = aasx_path
        self.submodel_filter = submodel_filter
        self.submodel_element_filter = submodel_element_filter
        self.reset()

    @property
    def aasx_path(self) -> str:
        """Get the file path to the AASX package used as template."""
        return self._aasx_path

    @aasx_path.setter
    def aasx_path(self, value: str) -> None:
        """Set the file path to the AASX package.

        This resets the template, which might take some time.
        """
        self._aasx_path = value
        self.reset()

    def reset(self) -> None:
        """Reset the AAS template by loading the AASX package and searching the properties."""
        self.object_store = model.DictObjectStore()
        self.file_store = DictSupplementaryFileContainer()
        if self.aasx_path is None:
            self.submodels = []
            self._properties = {}
            return
        try:
            with AASXReader(self.aasx_path) as reader:
                reader.read_into(self.object_store, self.file_store)
        except (ValueError, OSError):
            logger.exception("Couldn't load aasx template from: %s.", self.aasx_path)
        self.submodels = [
            submodel for submodel in self.object_store if isinstance(submodel, model.Submodel)
        ]
        self._properties = self._search_properties()

    def add_properties(self, properties: list[Property]) -> None:
        """Search the property by its `id` to update the aas property value.

        Instead of adding the property, only its value is updated, as the AAS
        Template defines the properties and their place in the AAS hierarchy.
        The property id resembles the submodel id plus the id_short hierarchy.
        """
        for property_ in properties:
            old_property, aas_property = self._properties.get(property_.definition_id, (None, None))
            if aas_property is None or old_property is None:
                old_property, aas_property = self._properties.get(property_.id, (None, None))
            if aas_property is None or old_property is None:
                continue
            old_property.value = property_.value
            if isinstance(aas_property, model.Property):
                value = cast_property(property_.value, property_.definition)
                aas_property.value_type = (
                    type(value) if value is not None else model.datatypes.String
                )
                aas_property.value = value
            elif isinstance(aas_property, model.MultiLanguageProperty):
                aas_property.value = model.MultiLanguageTextType(
                    {property_.language: str(property_.value)},
                )
            elif isinstance(aas_property, model.Range):
                min_, max_, type_ = cast_range(property_)
                aas_property.value_type = type_
                aas_property.min = min_
                aas_property.max = max_

    def get_properties(self) -> list[Property]:
        """Get all properties found in the template with updated values."""
        return [p for (p, _) in self._properties.values()]

    def get_property(self, id_: str) -> Property | None:
        """Get a single property by its id."""
        property_, _ = self._properties.get(id_, (None, None))
        return property_

    def get_property_definitions(
        self,
        *,
        overwrite_dataspec: bool = False,
    ) -> list[PropertyDefinition]:
        """Derive the property definition from the properties found in the template."""
        definitions = []
        for property_, _ in self._properties.values():
            definition = copy.copy(property_.definition)
            definition.id = property_.id
            if property_.definition_name is None or overwrite_dataspec:
                if property_.label is None or len(property_.label) == 0:
                    definition.name = {}
                else:
                    definition.name = {property_.language: property_.label}
            if (
                definition.definition is None
                or len(definition.definition) == 0
                or overwrite_dataspec
            ):
                if property_.reference is None or len(property_.reference) == 0:
                    definition.definition = {}
                else:
                    definition.definition = {property_.language: property_.reference}
            definitions.append(definition)
        return definitions

    def _walk_properties(
        self,
    ) -> collections.abc.Generator[
        model.Property | model.Range | model.MultiLanguageProperty,
        None,
        None,
    ]:
        submodels = self.submodels
        if self.submodel_filter:
            submodels = filter(self.submodel_filter, submodels)
        for submodel in submodels:
            elements = walk_submodel(submodel)
            if self.submodel_element_filter:
                elements = filter(self.submodel_element_filter, elements)
            for element in elements:
                if isinstance(element, model.Property | model.Range | model.MultiLanguageProperty):
                    yield element

    @staticmethod
    def _get_multilang_string(string_dict: dict[str, str], language: str) -> tuple[str | None, str]:
        if string_dict is not None and len(string_dict) > 0:
            if language in string_dict:
                return string_dict[language], language
            lang_string = next(iter(string_dict.items()))
            return lang_string[1], lang_string[0]
        return None, language

    @staticmethod
    # TODO: move to PropertyDefinition
    def _fill_definition_from_data_spec(
        definition: PropertyDefinition,
        embedded_data_specifications: list[model.EmbeddedDataSpecification],
    ) -> None:
        data_spec: model.DataSpecificationIEC61360 = next(
            (
                spec.data_specification_content
                for spec in embedded_data_specifications
                if isinstance(spec.data_specification_content, model.DataSpecificationIEC61360)
            ),
            None,
        )
        if data_spec is None:
            return

        if definition.name is None or len(definition.name) == 0:
            if data_spec.preferred_name is not None and len(data_spec.preferred_name) > 0:
                definition.name = data_spec.preferred_name._dict  # noqa: SLF001
            elif data_spec.short_name is not None and len(data_spec.short_name) > 0:
                definition.name = data_spec.short_name._dict  # noqa: SLF001

        if definition.type is None and data_spec.data_type is not None:
            definition.type = get_dict_data_type_from_iec6360(data_spec.data_type)

        if len(definition.definition) == 0 and data_spec.definition is not None:
            definition.definition = data_spec.definition._dict  # noqa: SLF001

        if len(definition.unit) == 0 and data_spec.unit is not None:
            definition.unit = data_spec.unit

        if (
            definition.values is None
            or len(definition.values) == 0
            and data_spec.value_list is not None
            and len(data_spec.value_list) > 0
        ):
            definition.values = [
                {
                    "value": value.value,
                    "id": value.value_id.key[0].value,
                }  # TODO: get key more robust
                for value in data_spec.value_list
            ]
        # use data_spec.value as default value?

    def _resolve_concept_description(
        self,
        semantic_id: model.Reference,
    ) -> model.concept.ConceptDescription | None:
        try:
            cd = semantic_id.resolve(self.object_store)
        except (IndexError, TypeError, KeyError):
            logger.debug(
                "ConceptDescription for semantidId %s not found in object store.",
                str(semantic_id),
            )
            return None
        if not isinstance(cd, model.concept.ConceptDescription):
            logger.debug(
                "semantidId %s resolves to %s, which is not a ConceptDescription",
                str(semantic_id),
                type(cd),
            )
            return None
        return cd

    @staticmethod
    def _create_id_from_path(item: model.Referable) -> str:
        parent_path = []
        if item.id_short is not None:
            while item is not None:
                if isinstance(item, model.Identifiable):
                    parent_path.append(item.id)
                    break
                if isinstance(item, model.Referable):
                    if isinstance(item.parent, model.SubmodelElementList):
                        parent_path.append(
                            f"{item.parent.id_short}[{item.parent.value.index(item)}]",
                        )
                        item = item.parent
                    else:
                        parent_path.append(item.id_short)
                    item = item.parent
        return "/".join(reversed(parent_path))

    def _search_properties(self) -> dict[str, tuple[Property, model.SubmodelElement]]:
        properties = {}
        for aas_property in self._walk_properties():
            property_ = Property(
                id=self._create_id_from_path(aas_property),
            )

            property_.label, property_.language = self._get_multilang_string(
                aas_property.display_name,
                property_.language,
            )
            if property_.label is None:
                property_.label = aas_property.id_short

            property_.reference, _ = self._get_multilang_string(
                aas_property.description,
                property_.language,
            )

            if isinstance(aas_property, model.Range):
                property_.value = [aas_property.min, aas_property.max]
                type_ = "range"
            elif isinstance(aas_property, model.MultiLanguageProperty):
                property_.value, _ = self._get_multilang_string(
                    aas_property.value,
                    property_.language,
                )
                type_ = "string"
            else:
                property_.value = aas_property.value
                type_ = get_dict_data_type_from_xsd(aas_property.value_type)

            definition = PropertyDefinition(
                id=property_.id,
                type=type_,
            )
            self._fill_definition_from_data_spec(
                definition,
                aas_property.embedded_data_specifications,
            )
            self._fill_definition_from_semantic_id(
                definition,
                aas_property.semantic_id,
            )

            property_.definition = definition
            properties[property_.id] = (property_, aas_property)
        return properties

    def _fill_definition_from_semantic_id(
        self,
        definition: PropertyDefinition,
        semantic_id: model.Reference | None,
    ) -> None:
        if semantic_id is None or len(semantic_id.key) == 0:
            return
        definition.id = "/".join([key.value for key in semantic_id.key])
        if isinstance(semantic_id, model.ModelReference):
            cd = self._resolve_concept_description(semantic_id)
        else:
            cd = self.object_store.get(semantic_id.key[0].value, None)
        if cd is None:
            return
        self._fill_definition_from_data_spec(
            definition,
            cd.embedded_data_specifications,
        )
        if len(definition.name) == 0:
            if cd.display_name:
                definition.name = cd.display_name._dict  # noqa: SLF001
            elif cd.id_short:
                definition.name = {"en": cd.id_short}

    def dumps(self) -> str:
        """Serialize and return the whole object store to a json string."""
        with io.StringIO() as string_io:
            json_serialization.write_aas_json_file(string_io, self.object_store)
            return string_io.getvalue()

    def save_as_aasx(self, filepath: str) -> None:
        """Save the aas template with updated values to an AASX package."""
        with AASXWriter(filepath) as writer:
            writer.write_aas(
                aas_ids=[
                    aas.id
                    for aas in self.object_store
                    if isinstance(aas, model.AssetAdministrationShell)
                ],
                object_store=self.object_store,
                file_store=self.file_store,
                write_json=True,
            )

    def search_datasheet(
        self,
        submodel_id_short: str | None = "HandoverDocumentation",
        classification: str | None = None,
        language: str = "en",
    ) -> str | None:
        """Search submodels for a datsheet file.

        Args:
        submodel_id_short (str | None): Check only submodels with this id short.
            Defaults to "HandoverDocumentation". Searches all submodels if None.
        classification (str | None): The classification name of the datasheet,
            e.g. according to VDI 2770 part 1. Defaults to None, which allows
            all class names.
        language (str): The language code for the datasheet and classification
            name. Defaults to "en". Allows all languages if None.

        Returns:
            str | None: The path or identifier of the found datasheet file, or None if not found.

        """
        for submodel in self.submodels:
            if submodel_id_short is not None and submodel.id_short != submodel_id_short:
                continue
            for document in submodel.submodel_element:
                if not isinstance(document, model.SubmodelElementCollection):
                    continue
                class_names, languages, file = self._search_document_spec(document)
                if file is None:
                    continue
                if classification is not None and classification not in class_names:
                    continue
                if language is not None and language not in languages:
                    continue
                return file
        return None

    @staticmethod
    def _search_document_spec(
        document: model.SubmodelElementCollection,
    ) -> tuple[dict[str, str], list[str], str]:
        class_names = []
        languages = []
        file = None
        for element in document.value:
            if element.id_short.startswith("DocumentClassification"):
                for subelement in element:
                    if subelement.id_short.lower() == "classname":
                        if isinstance(subelement.value, model.MultiLanguageTextType):
                            class_names.extend(subelement.value.values())
                        else:
                            class_names.append(str(subelement.value))
            elif element.id_short.startswith("DocumentVersion"):
                for subelement in element:
                    if subelement.id_short.startswith("Language"):
                        languages.append(subelement.value.lower())
                    elif subelement.id_short.startswith("DigitalFile"):
                        file = subelement.value
        return class_names, languages, file
