import json
import logging
import os
import re

import tiktoken
from openai import OpenAI, AzureOpenAI

from ..dictionary import PropertyDefinition
from . import PropertyLLM

logger = logging.getLogger(__name__)


class PropertyLLMOpenAI(PropertyLLM):
    system_prompt_template = """You act as an text API to extract technical properties from a given datasheet.
Answer only in valid JSON format.
Answer with a list of objects, containing the keys 'property', 'value', 'unit', 'reference'.
The property field must contain the property id as provided in the datasheet.
The value field must only contain the value you extracted.
The unit field contains the physical unit of measurement, if applicable.
The reference field contains a small excerpt of maximum 100 characters from the datasheet surrounding the extracted value.
Answer with null values if you don't find the information or if not applicable.
Example result, when asked for "rated load torque" and "supply voltage" of the device:
[{"property": "permissible torque", "value": 1000, "unit": "Nm", "reference": "the permissible torque is 1kNm"},
{"property": "supply voltage", "value": null, "unit": null, "reference": null}]
"""

    def __init__(
            self,
            model_identifier: str,
            api_endpoint: str = None,
            property_keys_in_prompt: list[str] = ['definition', 'unit', 'values'],
            client: OpenAI | AzureOpenAI | None = None,
    ) -> None:
        super().__init__()
        self.model_identifier = model_identifier
        self.use_property_definition = 'definition' in property_keys_in_prompt
        self.use_property_unit = 'unit' in property_keys_in_prompt
        self.use_property_values = 'values' in property_keys_in_prompt
        self.temperature = 0
        self.max_tokens = None
        self.response_format = None #{"type": "json_object"}
        if client is None and api_endpoint != "input":
            client = OpenAI(base_url=api_endpoint)
        self.client = client

    def extract(self, datasheet: str, property_definition: PropertyDefinition | list[PropertyDefinition]) -> dict | list[dict] | None:
        logger.info(f"Extracting {f'{len(property_definition)} properties' if isinstance(property_definition, list) else property_definition.id}")
        if isinstance(datasheet, list):
            logger.debug(f"Processing datasheet with {len(datasheet)} pages and {sum(len(p) for p in datasheet)} chars.")
        else:
            logger.debug(f"Processing datasheet with {len(datasheet)} chars.")

        messages = [
            {"role": "system", "content": self.system_prompt_template},
            {
                "role": "user",
                "content": self.create_prompt(datasheet, property_definition),
            },
        ]
        result = self._prompt_llm(messages)
        properties = self._parse_result(result)
        self._add_name_id_from_definition(properties, property_definition)
        return properties

    def _prompt_llm(self, messages):
        if self.client is None:
            logger.info("Systemprompt:\n"+ messages[0]["content"])
            logger.info("Prompt:\n"+ messages[1]["content"])
            return input("Enter result for LLM prompt via input:\n")

        try:
            logger.debug("System prompt token count: %i", self.calculate_token_count(messages[0]['content']))
            logger.debug("Prompt token count: %i", self.calculate_token_count(messages[1]['content']))
        except ValueError:
            logger.debug("System prompt char count: %i" % len(messages[0]["content"]))
            logger.debug("Prompt char count: %i" % len(messages[1]["content"]))
        
        if self.response_format is None:
            property_response = self.client.chat.completions.create(
                model=self.model_identifier,
                temperature=self.temperature,
                messages=messages,
                max_tokens=self.max_tokens,
            )
        else: # response format = None is not equal to NotGiven, e.g. AzureOpenAI won't work with it
            property_response = self.client.chat.completions.create(
                model=self.model_identifier,
                temperature=self.temperature,
                messages=messages,
                max_tokens=self.max_tokens,
                response_format=self.response_format,
            )
        result = property_response.choices[0].message.content
        logger.debug("Response from LLM:" + result)
        return result

    def _parse_result(self, result):
        try:
            properties = json.loads(result)
        except json.decoder.JSONDecodeError:
            md_block = re.search(r'```(?:json)?\s*(.*?)\s*```', result, re.DOTALL)
            if md_block is None:
                logger.error("Couldn't decode LLM result: " + result)
                return None
            try:
                properties = json.loads(md_block.group(1))
                logger.debug("Extracted json markdown block via regex from LLM result.")
            except json.decoder.JSONDecodeError:
                logger.error("Couldn't decode LLM markdown block: " + md_block.group(1))
                return None
        if isinstance(properties, dict):
            found_key = False
            for key in ['result', 'results', 'items', 'data', 'properties']:
                if key in properties:
                    properties = properties.get(key)
                    logger.debug(f"Heuristicly took '{key}' from LLM result.")
                    found_key = True
                    break
            if not found_key and len(properties) == 1:
                properties = properties.values()[0]
                logger.debug(f"Took '{properties.keys()[0]}' from LLM result.")
        return properties

    def _add_name_id_from_definition(self, properties, property_definition):
        if properties is None:
            return
        if isinstance(property_definition, list):
            if len(properties) != len(property_definition):
                logger.warning(f"Extracted property count {len(properties)} doesn't match expected count of {len(property_definition)}. Can't add 'id' and'name'")
                return
            if not isinstance(properties, list):
                logger.warning(f"Extracted properties are is {type(properties)} instead of list. Can't add 'id' and'name'")
                return
            dict_error = False
            for idx, property_def in enumerate(property_definition):
                if not isinstance(properties[idx], dict):
                    dict_error = True
                    continue
                properties[idx]["id"] = property_def.id
                properties[idx]["name"] = property_def.name["en"]
            if dict_error:
                logger.warning("Some or all extracted properties are not of type dict. Can't add 'id' and'name'")
        else:
            for property in properties:
                property["id"] = property_definition.id
                property["name"] = property_definition.name["en"]

    def create_property_prompt(self, property: PropertyDefinition, language: str = "en") -> str:
        if property.name is None:
            raise ValueError(f"Property {property.id} has no name.")
        property_name = property.name.get(language)
        if property_name is None:
            property_name = property.name
            logger.warning(
                f"Property {property.id} name not defined for language {language}. Using {property_name}."
            )
        
        prompt = ""
        property_definition = property.definition.get(language)
        if self.use_property_definition and property_definition:
            prompt += f'The "{property_name}" is defined as "{property_definition}".\n' 
        if self.use_property_unit and property.unit:
            prompt += f'The "{property_name}" has the unit of measure "{property.unit}".\n'
        if self.use_property_values and property.values:
            prompt += f'The "{property_name}" can be one of these values: "{[v["value"] for v in property.values]}".\n'

        prompt +=f'What is the "{property_name}" of the device?\n'
        return prompt

    def create_property_list_prompt(self, property_list: list[PropertyDefinition], language: str = "en") -> str:
        prompt = "Extract the following properties from the provided datasheet:\n"
        for property in property_list:
            if property.name is None:
                logger.warning(f"Property {property.id} has no name.")
                continue
            property_name = property.name.get(language)
            if property_name is None:
                property_name = property.name
                logger.warning(
                    f"Property {property.id} name not defined for language {language}. Using {property_name}."
                )
                continue
            prompt +=f'* Property: "{property_name}"\n'
            property_definition = property.definition.get(language)
            if self.use_property_definition and property_definition:
                prompt += f'  * Definition: "{property_definition}"\n' 
            if self.use_property_unit and property.unit:
                prompt += f'  * Unit: "{property.unit}"\n'
            if self.use_property_values and property.values:
                if isinstance(next(iter(property.values)), dict):
                    prompt += f'  * Possible values: "{[v["value"] for v in property.values]}"\n'
                else:
                    prompt += f'  * Possible values: "{property.values}"\n'
        return prompt


    def create_prompt(
        self, datasheet: str, property: PropertyDefinition | list[PropertyDefinition], language: str = "en"
    ) -> str:

        if isinstance(property, list):
            prompt = self.create_property_list_prompt(property, language)
        else: 
            prompt = self.create_property_prompt(property, language)
        
        prompt+= f"\nThe following text in triple # is the datasheet of the technical device. It was converted from pdf.\n###\n{datasheet}\n###"
        return prompt

    def calculate_token_count(self, text: str) -> int:
        """
        Calculate the number of tokens in a given text based on a specified model's encoding.

        Parameters:
        - text (str): The input text to encode.
        - model_identifier (str): The identifier of the model to use for encoding.

        Returns:
        - int: The number of tokens in the encoded text.

        Raises:
        - ValueError: If the model_identifier does not correspond to any known model encoding.
        """
        try:
            encoding = tiktoken.encoding_for_model(self.model_identifier)
        except KeyError:
            raise ValueError(f"Unknown model identifier: {self.model_identifier}")
        return len(encoding.encode(text))
