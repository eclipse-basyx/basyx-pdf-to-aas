"""Extractor for technical properties using an LLM or similar backend."""

import json
import logging
import re
import unicodedata
from typing import Any

from openai import AzureOpenAI, OpenAI, OpenAIError

from pdf2aas.model import Property, PropertyDefinition

from . import CustomLLMClient, Extractor

logger = logging.getLogger(__name__)


class PropertyLLM(Extractor):
    """Extractor that prompts an LLM client to extract properties from a datasheet.

    Will ignore the property definitions given and extract all technical data
    without definitions.

    Attributes:
        system_prompt_template (str): A string that is sent as system message to
            the LLM, typically to clarify the user message instruction.
            Currently, it contains no placeholders.
        user_prompt_template (str): A string with a {datasheet} placeholder,
            that contains instruction, e.g. which properties to extract.
        client (OpenAI | AzureOpenAI | CustomLLMClient): client which is used,
            to execute the prompts.
        model_identifier (str): String identifying the model to use, e.g. gpt-3.5.
        temperature (float): Temperature value for the LLM. Typically between 0
            and 2, where 0 indicates taking the most probable value to be more
            deterministic.
        max_tokens (int): Maximum number of tokes the LLM should generate in
            one run. 0 corresponds to no limit.
        response_format (dict | None): Leverage structured output from the LLM,
            by specifing a response format, if the LLM supports it.

    """

    system_prompt_template = """You act as an text API to extract technical properties from a given datasheet.
The datasheet will be surrounded by triple backticks (```).

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
]"""  # noqa: E501
    user_prompt_template = """Extract all technical properties from the following datasheet text.

```
{datasheet}
```"""

    def __init__(
        self,
        model_identifier: str,
        api_endpoint: str | None = None,
        client: OpenAI | AzureOpenAI | CustomLLMClient | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> None:
        """Initialize the Property LLM extractor with default values.

        If no `client` is given or the `api_endpoint` is not equal to "input",
        a OpenAI client is created using the specified `api_endpoint`.
        """
        super().__init__()
        self.model_identifier = model_identifier
        self.temperature = temperature
        self.max_tokens = max_tokens
        if response_format is None:
            response_format = {"type": "json_object"}
        self.response_format = response_format
        if client is None and api_endpoint != "input":
            try:
                client = OpenAI(base_url=api_endpoint)
            except OpenAIError as error:
                logger.warning("Couldn't init OpenAI client, falling back to 'input'. %s", error)
                client = None
        self.client = client

    def extract(
        self,
        datasheet: list[str] | str,
        property_definition: PropertyDefinition | list[PropertyDefinition],
        raw_prompts: list | None = None,
        raw_results: list | None = None,
        prompt_hint: str | None = None,
    ) -> list[Property]:
        """Try to extract all properties found in the given datasheet text.

        Ignores the `property_definition` list. Use a more specific PropertyLLM,
        e.g. PropertyLLMSearch extractor, if specific property definitions
        should be searched.

        If a `raw_prompt` or `raw_result` list is given, the created prompts and
        returned results are added to these lists.

        The `prompt_hint` can be used to add context or additional instructions
        to the prompt before it is sent to the LLM.
        """
        if isinstance(property_definition, list):
            logger.info("Extracting %s properties.", len(property_definition))
        else:
            logger.info("Extracting %s", property_definition.id)
        if isinstance(datasheet, list):
            logger.debug(
                "Processing datasheet with %s pages and %s chars.",
                len(datasheet),
                sum(len(p) for p in datasheet),
            )
            datasheet = "\n".join(datasheet)
        else:
            logger.debug("Processing datasheet with %s chars.", len(datasheet))

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
        return self._add_definitions(properties, property_definition)

    def create_prompt(
        self,
        datasheet: str,
        properties: PropertyDefinition | list[PropertyDefinition],  # noqa: ARG002
        language: str = "en",  # noqa: ARG002
        hint: str | None = None,
    ) -> str:
        """Create the prompt from the given datasheet.

        Can be used to check the prompt upfront, overwrite it or display it
        afterwards.

        The `properties` and `language` arguments are not used, but kept to be
        compatible with more specific implementations.

        A `hint` (c.f. "prompt_hint" in :meth: extract) is added to the top of
        the prompt.
        """
        prompt = "" if hint is None else hint
        prompt += self.user_prompt_template.format(datasheet=datasheet)
        return prompt

    def _prompt_llm(
        self,
        messages: list[dict[str, str]],
        raw_results: list | None,
    ) -> str | Any | None:
        if self.client is None:
            logger.info("Systemprompt:\n%s", messages[0]["content"])
            logger.info("Prompt:\n%s", messages[1]["content"])
            result: str | Any | None = input("Enter result for LLM prompt via input:\n")
            raw_result = result
        elif isinstance(self.client, CustomLLMClient):
            result, raw_result = self.client.create_completions(
                messages,
                self.model_identifier,
                self.temperature,
                self.max_tokens if self.max_tokens else 0,
                self.response_format,
            )
        else:
            try:
                result, raw_result = self._prompt_llm_openai(messages)
            except OpenAIError as error:
                logger.exception("Error calling openai endpoint.")
                raw_result = str(error)
                result = None
        logger.debug("Response from LLM: %s", result)
        if isinstance(raw_results, list):
            raw_results.append(raw_result)
        return result

    def _prompt_llm_openai(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[str | Any | None, dict]:
        if self.response_format is None or isinstance(self.client, AzureOpenAI):
            chat_completion = self.client.chat.completions.create(
                model=self.model_identifier,
                temperature=self.temperature,
                messages=messages, # type: ignore[arg-type]
                max_tokens=self.max_tokens,
            )
        else:  # response format = None is not equal to NotGiven, e.g. AzureOpenAI won't work
            chat_completion = self.client.chat.completions.create( # type: ignore[call-overload, union-attr]
                model=self.model_identifier,
                temperature=self.temperature,
                messages=messages,
                max_tokens=self.max_tokens,
                response_format=self.response_format,
            )
        result = chat_completion.choices[0].message.content
        if chat_completion.choices[0].finish_reason not in ["stop", "None"]:
            logger.warning(
                "Chat completion finished with reason '%s'. (max_tokens=%s)",
                chat_completion.choices[0].finish_reason,
                self.max_tokens,
            )
        return result, chat_completion.to_dict(mode="json")

    def _parse_result(self, result: str | None) -> Any | dict | None:
        if result is None:
            return None
        try:
            properties = json.loads(
                "".join(ch for ch in result if unicodedata.category(ch)[0] != "C"),
            )
        except json.decoder.JSONDecodeError:
            md_block = re.search(r"```(?:json)?\s*(.*?)\s*```", result, re.DOTALL)
            if md_block is None:
                logger.exception("Couldn't decode LLM result.")
                return None
            try:
                properties = json.loads(md_block.group(1))
                logger.debug("Extracted json markdown block via regex from LLM result.")
            except json.decoder.JSONDecodeError:
                logger.exception("Couldn't decode LLM markdown block: %s", md_block.group(1))
                return None
        if isinstance(properties, dict):
            found_key = False
            for key in ["result", "results", "items", "data", "properties"]:
                if key in properties:
                    properties = properties.get(key)
                    logger.debug("Heuristicly took '%s' from LLM result.", key)
                    found_key = True
                    break
            if not found_key and len(properties) == 1:
                logger.debug("Took '%s' from LLM result.", next(iter(properties.keys())))
                properties = next(iter(properties.values()))
        return properties

    def _parse_properties(
        self,
        properties: dict | list | None,
    ) -> list[Property]:
        if properties is None:
            return []
        if not isinstance(properties, list | dict):
            logger.warning(
                "Extraction result type is %s instead of list or dict.",
                type(properties),
            )
            return []

        if isinstance(properties, dict):
            if all(key in properties for key in ["property", "value", "unit", "reference"]):
                # only one property returned
                properties = [properties]
            else:
                properties = list(properties.values())
                logger.debug("Extracted properties are a dict, try to encapsulate them in a list.")

        return [Property.from_dict(p) for p in properties if isinstance(p, dict)]

    def _add_definitions(
        self,
        properties: list[Property],
        property_definition: list[PropertyDefinition] | PropertyDefinition,  # noqa: ARG002
    ) -> list[Property]:
        return properties
