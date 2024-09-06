import json
import logging
import re
import unicodedata

from openai import OpenAI, AzureOpenAI, OpenAIError

from ..dictionary import PropertyDefinition
from . import Property
from . import CustomLLMClient
from . import Extractor

logger = logging.getLogger(__name__)


class PropertyLLM(Extractor):
    """
    Extractor that prompts an LLM client to extract properties from a datasheet.
    
    Will ignore the property definitions given and extract all technical data
    without definitions.
    """
    system_prompt_template = \
"""You act as an text API to extract technical properties from a given datasheet.
The datasheet will be surrounded by triple hashtags (###).

Answer only in valid JSON format.
Answer with a list of objects, containing the keys 'property', 'value', 'unit', 'reference':
1. The property field must contain the property label as provided.
2. The value field must only contain the value you extracted.
3. The unit field contains the physical unit of measurement, if applicable.
4. The reference field contains a small excerpt of maximum 100 characters from the datasheet surrounding the extracted value.
Answer with null values if you don't find the information or if not applicable.

Example result:
[
    {"property": "rated load torque", "value": 1000, "unit": "Nm", "reference": "the permissible torque is 1kNm"},
    {"property": "supply voltage", "value": null, "unit": null, "reference": null}
]"""
    user_prompt_template = \
"""Extract all technical properties from the following datasheet text.

###
{datasheet}
###"""

    def __init__(
        self,
        model_identifier: str,
        api_endpoint: str = None,
        client: OpenAI | AzureOpenAI | CustomLLMClient | None = None,
        temperature: str = 0,
        max_tokens: int | None = None,
        response_format: dict | None = {"type": "json_object"}
    ) -> None:
        super().__init__()
        self.model_identifier = model_identifier
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format = response_format
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
        properties = self._parse_properties(properties)
        properties = self._add_definitions(properties, property_definition)
        return properties
    
    def create_prompt(
        self,
        datasheet: str,
        properties: PropertyDefinition | list[PropertyDefinition],
        language: str = "en",
        hint: str | None = None
    ) -> str:
        prompt = '' if hint is None else hint
        prompt += self.user_prompt_template.format(datasheet=datasheet)
        return prompt

    def _prompt_llm(self, messages, raw_results):
        if self.client is None:
            print("Systemprompt:\n"+ messages[0]["content"])
            print("Prompt:\n"+ messages[1]["content"])
            result = input("Enter result for LLM prompt via input:\n")
            raw_result = result
        elif isinstance(self.client, CustomLLMClient):
            result, raw_result = self.client.create_completions(messages, self.model_identifier, self.temperature, self.max_tokens, self.response_format)
        else:
            try:
                result, raw_result = self._prompt_llm_openai(messages)
            except OpenAIError as error:
                logger.error(f"Error calling openai endpoint: {error}")
                raw_result = error
                result = None
        logger.debug(f"Response from LLM: {result}")
        if isinstance(raw_results, list):
            raw_results.append(raw_result)
        return result

    def _prompt_llm_openai(self, messages):
        if self.response_format is None or isinstance(self.client, AzureOpenAI):
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
        if chat_completion.choices[0].finish_reason not in ['stop', 'None']:
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
    
    def _parse_properties(
            self,
            properties: dict | list | None,
    ) -> list[Property]:
        if properties is None:
            return []
        if not isinstance(properties, (list, dict)):
            logger.warning(f"Extraction result type is {type(properties)} instead of list or dict.")
            return []

        if isinstance(properties, dict):
            if all(key in properties for key in ['property', 'value', 'unit', 'reference']):
                # only one property returned
                properties = [properties]
            else:
                properties = list(properties.values())
                logger.debug(f"Extracted properties are a dict, try to encapsulate them in a list.")
        
        return [Property.from_dict(p) for p in properties if isinstance(p, dict)]

    def _add_definitions(
            self,
            properties: list[Property],
            property_definition: list[PropertyDefinition] | PropertyDefinition
    ) -> list[Property]:
        return properties