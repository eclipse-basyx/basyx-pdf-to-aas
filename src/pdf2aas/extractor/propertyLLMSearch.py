import logging
from typing import Literal

from openai import OpenAI, AzureOpenAI

from ..dictionary import PropertyDefinition
from . import PropertyLLM
from . import CustomLLMClient
from . import Property

logger = logging.getLogger(__name__)


class PropertyLLMSearch(PropertyLLM):
    """
    PropertyLLM that searches for given property definitions only.
    """
    system_prompt_template = PropertyLLM.system_prompt_template + """

Search exactly for the reuqested properties.
Keep the order of the requested properties.
The property field is used to assign your extracted property to the requested property definitions.
Convert the value to the requested unit if provided.
"""

    def __init__(
            self,
            model_identifier: str,
            api_endpoint: str = None,
            client: OpenAI | AzureOpenAI | CustomLLMClient | None = None,
            temperature: str = 0,
            max_tokens: int | None = None,
            response_format: dict | None = {"type": "json_object"},
            property_keys_in_prompt: list[Literal["definition", "unit", "values", "datatype"]] = [],
    ) -> None:
        super().__init__(model_identifier, api_endpoint, client, temperature, max_tokens, response_format)
        self.use_property_definition = 'definition' in property_keys_in_prompt
        self.use_property_unit = 'unit' in property_keys_in_prompt
        self.use_property_values = 'values' in property_keys_in_prompt
        self.use_property_datatype = 'datatype' in property_keys_in_prompt
        self.max_definition_chars = 0
        self.max_values_length = 0

    def create_prompt(
        self,
        datasheet: str,
        properties: PropertyDefinition | list[PropertyDefinition],
        language: str = "en",
        hint: str | None = None
    ) -> str:

        if isinstance(properties, list):
            prompt = self.create_property_list_prompt(properties, language)
        else: 
            prompt = self.create_property_prompt(properties, language)

        if hint:
            prompt+= "\n" + hint
        
        prompt+= f"\nThe following text in triple # is the datasheet of the technical device. It was converted from pdf.\n###\n{datasheet}\n###"
        return prompt

    def create_property_prompt(self, property_: PropertyDefinition, language: str = "en") -> str:
        if len(property_.name) == 0:
            raise ValueError(f"Property {property_.id} has no name.")
        property_name = property_.name.get(language)
        if property_name is None:
            property_name = property_.name
            logger.warning(
                f"Property {property_.id} name not defined for language {language}. Using {property_name}."
            )
        
        prompt = ""
        property_definition = property_.definition.get(language)
        if self.use_property_definition and property_definition:
            if self.max_definition_chars > 0 and len(property_definition) > self.max_definition_chars:
                property_definition = property_definition[:self.max_definition_chars] + " ..."
            prompt += f'The "{property_name}" is defined as "{property_definition[:self.max_definition_chars]}".\n'
        if self.use_property_datatype and property_.type:
            prompt += f'The "{property_name}" has the datatype "{property_.type}".\n'
        if self.use_property_unit and property_.unit:
            prompt += f'The "{property_name}" has the unit of measure "{property_.unit}".\n'
        if self.use_property_values and len(property_.values) > 0:
            property_values = property_.values_list
            if self.max_values_length > 0 and len(property_values) > self.max_values_length:
                property_values = property_values[:self.max_values_length] + ["..."]
            prompt += f'The "{property_name}" can be one of these values: "{property_values}".\n'

        prompt +=f'What is the "{property_name}" of the device?\n'
        return prompt

    def create_property_list_prompt(self, property_list: list[PropertyDefinition], language: str = "en") -> str:
        prompt = "Extract the following properties from the provided datasheet:\n"
        prompt+= "| Property |"
        separator = "| - |"
        if self.use_property_datatype:
            prompt += " Datatype |"
            separator += " - |"
        if self.use_property_unit:
            prompt += " Unit |"
            separator += " - |"
        if self.use_property_definition:
            prompt += " Definition |"
            separator += " - |"
        if self.use_property_values:
            prompt += " Values |"
            separator += " - |"
        prompt+= "\n" + separator + "\n"

        for property_ in property_list:
            if len(property_.name) == 0:
                logger.warning(f"Property {property_.id} has no name.")
                continue
            property_name = property_.name.get(language)
            if property_name is None:
                property_name = next(iter(property_.name.values()))
                logger.warning(
                    f"Property {property_.id} name not defined for language {language}. Using {property_name}."
                )
            
            property_row = f"| {property_name} |"
            if self.use_property_datatype:
                property_row += f" {property_.type} |"
            if self.use_property_unit:
                property_row += f" {property_.unit} |"
            if self.use_property_definition:
                property_definition = property_.definition.get(language, '')
                if property_definition and self.max_definition_chars > 0 and len(property_definition) > self.max_definition_chars:
                    property_definition = property_definition[:self.max_definition_chars] + " ..."
                property_row += f" {property_definition} |"
            if self.use_property_values:
                property_values = property_.values_list
                if self.max_values_length > 0 and len(property_values) > self.max_values_length:
                    property_values = property_.values_list[:self.max_values_length] + ["..."]
                property_row += f" {', '.join(property_values)} |"
            prompt += property_row.replace('\n', ' ') + "\n"
            #TODO escape | sign in name, type, unit, definition, values, etc.
        return prompt

    def _add_definitions(
            self,
            properties: list[Property],
            property_definition: list[PropertyDefinition] | PropertyDefinition
    ) -> list[Property]:
        if len(properties) == 0:
            return []
        if isinstance(property_definition, PropertyDefinition):
            property_definition = [property_definition]

        if len(properties) == len(property_definition):
            for i, property_ in enumerate(properties):
                property_.definition = property_definition[i]
        elif len(property_definition) == 1 and len(properties) > 1:
            logger.warning(f"Extracted {len(properties)} properties for one definition.")
            for property_ in properties:
                property_.definition = property_definition[0]
        else:
            logger.warning(f"Extracted {len(properties)} properties for {len(property_definition)} definitions.")
            property_definition_dict = {next(iter(p.name.values()), p.id).lower(): p for p in property_definition}
            for property_ in properties:
                property_.definition = property_definition_dict.get(
                    property_.label.strip().lower())
        return properties