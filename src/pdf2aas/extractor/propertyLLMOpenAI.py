import json
import logging
import re
import unicodedata
from typing import Literal

from openai import OpenAI, AzureOpenAI, OpenAIError

from ..dictionary import PropertyDefinition
from . import PropertyLLM
from . import CustomLLMClient
from . import Property

logger = logging.getLogger(__name__)


class PropertyLLMOpenAI(PropertyLLM):
    system_prompt_template = """You act as an text API to extract technical properties from a given datasheet.
Answer only in valid JSON format.
Answer with a list of objects, containing the keys 'property', 'value', 'unit', 'reference'.
Keep the order of the requested properties.
The property field must contain the property id as provided in the request.
The value field must only contain the value you extracted and converted to the requested unit.
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
            property_keys_in_prompt: list[Literal["definition", "unit", "values", "datatype"]] = [],
            client: OpenAI | AzureOpenAI | CustomLLMClient | None = None,
    ) -> None:
        super().__init__()
        self.model_identifier = model_identifier
        self.use_property_definition = 'definition' in property_keys_in_prompt
        self.use_property_unit = 'unit' in property_keys_in_prompt
        self.use_property_values = 'values' in property_keys_in_prompt
        self.use_property_datatype = 'datatype' in property_keys_in_prompt
        self.max_definition_chars = 0
        self.max_values_length = 0
        self.temperature = 0
        self.max_tokens = None
        self.response_format = {"type": "json_object"}
        if client is None and api_endpoint != "input":
            try:
                client = OpenAI(base_url=api_endpoint)
            except OpenAIError as error:
                logger.warning(f"Couldn't init OpenAI client, falling back to 'input'. {error}")
                client = None
        self.client = client

    def extract(
            self,
            datasheet: str,
            property_definition: PropertyDefinition | list[PropertyDefinition],
            raw_prompts: list[str] | None = None,
            raw_results: list[str] | None = None,
            prompt_hint: str | None = None,
    ) -> list[Property]:
        logger.info(f"Extracting {f'{len(property_definition)} properties' if isinstance(property_definition, list) else property_definition.id}")
        if isinstance(datasheet, list):
            logger.debug(f"Processing datasheet with {len(datasheet)} pages and {sum(len(p) for p in datasheet)} chars.")
        else:
            logger.debug(f"Processing datasheet with {len(datasheet)} chars.")

        messages = [
            {"role": "system", "content": self.system_prompt_template},
            {
                "role": "user",
                "content": self.create_prompt(datasheet, property_definition, hint=prompt_hint),
            },
        ]
        if isinstance(raw_prompts, list):
            raw_prompts.append(messages)
        result = self._prompt_llm(messages, raw_results)
        properties = self._parse_result(result)
        properties = self._add_definitions(properties, property_definition)
        return properties

    def _prompt_llm(self, messages, raw_results):
        if self.client is None:
            print("Systemprompt:\n"+ messages[0]["content"])
            print("Prompt:\n"+ messages[1]["content"])
            result = input("Enter result for LLM prompt via input:\n")
            raw_result = result
        elif isinstance(self.client, CustomLLMClient):
            result, raw_result = self.client.create_completions(messages, self.model_identifier, self.temperature, self.max_tokens, self.response_format)
        else:
            result, raw_result = self._prompt_llm_openai(messages)
        
        logger.debug(f"Response from LLM: {result}")
        if isinstance(raw_results, list):
            raw_results.append(raw_result)
        return result

    def _prompt_llm_openai(self, messages):
        if self.response_format is None:
            chat_completion = self.client.chat.completions.create(
                model=self.model_identifier,
                temperature=self.temperature,
                messages=messages,
                max_tokens=self.max_tokens,
            )
        else: # response format = None is not equal to NotGiven, e.g. AzureOpenAI won't work with it
            chat_completion = self.client.chat.completions.create(
                model=self.model_identifier,
                temperature=self.temperature,
                messages=messages,
                max_tokens=self.max_tokens,
                response_format=self.response_format,
            )
        result = chat_completion.choices[0].message.content
        if chat_completion.choices[0].finish_reason != 'stop':
            logger.warning(f"Chat completion finished with reason '{chat_completion.choices[0].finish_reason}'. (max_tokens={self.max_tokens})")
        return result, chat_completion.to_dict(mode="json")

    def _parse_result(self, result):
        if result is None:
            return None
        try:
            properties = json.loads("".join(ch for ch in result if unicodedata.category(ch)[0]!="C"))
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
                logger.debug(f"Took '{next(iter(properties.keys()))}' from LLM result.")
                properties = next(iter(properties.values()))
        return properties

    def _add_definitions(
            self,
            properties: dict | list | None,
            property_definition: list[PropertyDefinition] | PropertyDefinition
    ) -> list[Property]:
        if properties is None:
            return []
        if not isinstance(properties, (list, dict)):
            logger.warning(f"Extraction result type is {type(properties)} instead of list or dict.")
            return []
        
        if isinstance(property_definition, PropertyDefinition):
            property_definition = [property_definition]

        if isinstance(properties, dict): 
            if len(property_definition) == 1:
                properties = [properties]
            else:
                properties = list(properties.values())
                logger.debug(f"Extracted properties are a dict, try to encapsulate them in a list.")
        
        if len(property_definition) == 1:
            if len(properties) > 1:
                logger.warning(f"Extracted multiple properties {len(properties)} for one definition.")
            return [Property.from_dict(p, property_definition[0])
                    for p in properties if isinstance(p, dict)]

        if len(properties) == len(property_definition):
            return [Property.from_dict(p, property_definition[i])
                    for i, p in enumerate(properties) if isinstance(p, dict)]

        logger.warning(f"Extracted property count {len(properties)} doesn't match expected count of {len(property_definition)}.")
        property_definition_dict = {next(iter(p.name.values()), p.id).lower(): p for p in property_definition}
        result = []
        for property_ in properties:
            name = property_.get('property', property_.get('label', property_.get('id')))
            if name is not None and name.lower() in property_definition_dict:
                result.append(Property.from_dict(property_, property_definition_dict.get(name)))
        return result

    def create_property_prompt(self, property: PropertyDefinition, language: str = "en") -> str:
        if len(property.name) == 0:
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
            if self.max_definition_chars > 0 and len(property_definition) > self.max_definition_chars:
                property_definition = property_definition[:self.max_definition_chars] + " ..."
            prompt += f'The "{property_name}" is defined as "{property_definition[:self.max_definition_chars]}".\n'
        if self.use_property_datatype and property.type:
            prompt += f'The "{property_name}" has the datatype "{property.type}".\n'
        if self.use_property_unit and property.unit:
            prompt += f'The "{property_name}" has the unit of measure "{property.unit}".\n'
        if self.use_property_values and len(property.values) > 0:
            property_values = property.values_list
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

        for property in property_list:
            if len(property.name) == 0:
                logger.warning(f"Property {property.id} has no name.")
                continue
            property_name = property.name.get(language)
            if property_name is None:
                property_name = next(iter(property.name.values()))
                logger.warning(
                    f"Property {property.id} name not defined for language {language}. Using {property_name}."
                )
            
            property_row = f"| {property_name} |"
            if self.use_property_datatype:
                property_row += f" {property.type} |"
            if self.use_property_unit:
                property_row += f" {property.unit} |"
            if self.use_property_definition:
                property_definition = property.definition.get(language, '')
                if property_definition and self.max_definition_chars > 0 and len(property_definition) > self.max_definition_chars:
                    property_definition = property_definition[:self.max_definition_chars] + " ..."
                property_row += f" {property_definition} |"
            if self.use_property_values:
                property_values = property.values_list
                if self.max_values_length > 0 and len(property_values) > self.max_values_length:
                    property_values = property.values_list[:self.max_values_length] + ["..."]
                property_row += f" {', '.join(property_values)} |"
            prompt += property_row.replace('\n', ' ') + "\n"
            #TODO escape | sign in name, type, unit, definition, values, etc.

        return prompt

    def create_prompt(
        self, datasheet: str, property: PropertyDefinition | list[PropertyDefinition], language: str = "en", hint: str | None = None
    ) -> str:

        if isinstance(property, list):
            prompt = self.create_property_list_prompt(property, language)
        else: 
            prompt = self.create_property_prompt(property, language)

        if hint:
            prompt+= "\n" + hint
        
        prompt+= f"\nThe following text in triple # is the datasheet of the technical device. It was converted from pdf.\n###\n{datasheet}\n###"
        return prompt
