import json
import logging
import os
import re

import tiktoken
from openai import OpenAI

from ..dictionary import PropertyDefinition
from . import PropertyLLM

logger = logging.getLogger(__name__)


class PropertyLLMOpenAI(PropertyLLM):
    system_prompt_template = """You act as an text API to extract technical properties from a given datasheet.
Answer only in valid JSON format.
Answer with a ordered list of objects, containing the keys 'property', 'value', 'unit', 'reference'.
The property field must contain the property id as provided in the datasheet.
The value field must only contain the value you extracted.
The unit field contains the physical unit of measurement, if applicable.
The reference field contains a small excerpt of maximum 100 characters from the datasheet surrounding the extracted value.
Answer with null values if you don't find the information or if not applicable.
Example result, when asked for "rated load torque" and "supply voltage" of the device:
[{'property': 'rated load torque', 'value': 1000, 'unit': 'Nm', 'reference': 'the permissible torque is 1kNm'},
{'property': 'supply voltage', 'value': null, 'unit': null, 'reference': null}]
"""

    def __init__(self, model_identifier: str, api_endpoint: str = None, property_keys_in_prompt: list[str] = ['definition', 'unit', 'values']) -> None:
        super().__init__()
        self.model_identifier = model_identifier
        self.api_endpoint = api_endpoint
        self.use_property_definition = 'definition' in property_keys_in_prompt
        self.use_property_unit = 'unit' in property_keys_in_prompt
        self.use_property_values = 'values' in property_keys_in_prompt

    def extract(self, datasheet: str, property_definition: PropertyDefinition | list[PropertyDefinition]) -> dict | list[dict] | None:
        if self.api_endpoint != "input" and os.getenv("OPENAI_API_KEY") is None:
            raise ValueError("No OpenAI API key found in environment")

        logger.info(f"Extracting {f'{len(property_definition)} properties' if isinstance(property_definition, list) else property_definition.id}")

        # TODO create Datasheet class and add information about char length
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
        try:
            logger.debug(
                "System prompt token count: %i"
                % self.calculate_token_count(messages[0]["content"])
            )
            logger.debug(
                "Prompt token count: %i"
                % self.calculate_token_count(messages[1]["content"])
            )
        except ValueError:
            logger.debug("System prompt char count: %i" % len(messages[0]["content"]))
            logger.debug("Prompt char count: %i" % len(messages[1]["content"]))

        if self.api_endpoint == "input":
            logger.info("Systemprompt:\n"+ messages[0]["content"])
            logger.info("Prompt:\n"+ messages[1]["content"])
            result = input("Enter dryrun result for LLM prompt:\n")
        else:
            client = OpenAI(base_url=self.api_endpoint)
            property_response = client.chat.completions.create(
                model=self.model_identifier,
                # response_format={"type": "json_object"},
                messages=messages,
            )
            result = property_response.choices[0].message.content
            logger.debug("Response from LLM:" + result)

        try:
            properties = json.loads(result)
        except json.decoder.JSONDecodeError:
            md_block = re.search(r'```(?:json)?\s*(.*?)\s*```', result, re.DOTALL)
            if md_block is None:
                logger.warning("Couldn't decode LLM result: " + result)
                return None
            try:
                properties = json.loads(md_block.group(1))
                logger.debug("Extracted json markdown block via regex from LLM result.")
            except json.decoder.JSONDecodeError:
                logger.warning("Couldn't decode LLM markdown block: " + md_block.group(1))
                return None
        if isinstance(properties, dict) and properties.get('results') is not None:
            properties = properties.get('results')

        if isinstance(property_definition, list):
            if len(properties) != len(property_definition):
                logger.warning(f"Extracted property count {len(properties)} doesn't match expected: {len(property_definition)}")
                return properties
            for idx, property_def in enumerate(property_definition):
                properties[idx]["id"] = property_def.id
                properties[idx]["name"] = property_def.name["en"]
        else:
            for property in properties:
                property["id"] = property_definition.id
                property["name"] = property_definition.name["en"]

        return properties

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
                prompt += f'  * Possible values: "{[v["value"] for v in property.values]}"\n'
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
