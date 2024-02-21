from extractor import PropertyLLM
from dictionary import PropertyDefinition
from openai import OpenAI
import tiktoken
import json
import os
import logging

logger = logging.getLogger(__name__)

class PropertyLLMOpenAI(PropertyLLM):
    system_prompt_template = """You are a technical expert and worked as mechatronic engineer.
Answer only in valid JSON format with the keys 'property', 'value', 'unit', 'reference'.
The property field must contain the property name as provided in the data source.
The value field must only contain the value.
The unit field contains the physical unit of measurement, if applicable.
The reference field contains a small excerpt from the source surrounding the extracted value.
Answer with null values if you don't find the information or if not applicable.
Example result:
{'property': 'Rated Torque', 'value': 1000, 'unit': 'Nm', 'reference': 'nominal torque is 1kNm.'}"""
    
    def __init__(self, model_identifier: str, api_endpoint: str = None) -> None:
        super().__init__()
        self.model_identifier = model_identifier
        self.api_endpoint = api_endpoint
    
    def extract(self, datasheet: str, property_definition: PropertyDefinition) -> str:
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("No OpenAI API key found in environment")
        client = OpenAI()

        #TODO create Datasheet class and add information about char length
        if datasheet.isinstance(list):
            logger.info(f"Processing datasheet with {len(datasheet)} pages and {sum(len(p) for p in datasheet)} chars.")
        else:
            logger.info(f"Processing datasheet with {len(datasheet)} chars.")
        logger.info(f"Extracting property {property_definition.id}: {property_definition.name}")

        messages=[
                {"role": "system", "content": self.system_prompt_template },
                {"role": "user", "content": self.create_prompt(datasheet, property_definition)}
            ]
        logger.debug("System prompt token count: %i" % self.calculate_token_count(messages[0]['content']))
        logger.debug("Prompt token count: %i" % self.calculate_token_count(messages[1]['content']))
        
        property_response = client.chat.completions.create(
            model=self.model_identifier,
            response_format={ "type": "json_object" },
            messages=messages)
        
        result = property_response.choices[0].message.content
        logger.debug("Response from LLM:" + result)
        property = json.loads(result)
        
        property['id'] = property_definition.id
        property['name'] = property_definition.name
        
        return property

    def create_prompt(self, datasheet: str, property: PropertyDefinition, language: str = 'en') -> str :
        if property.name is None:
            raise ValueError(f"Property {property.id} has no name.")
        property_name = property.name.get(language)
        if property_name is None:
            property_name = property.name
            logger.warning(f"Property {property.id} name not defined for language {language}.")
        property_definition = property.definition.get(language)
        prompt =f"The following html text in triple # is a datasheet of a technical device that was converted from pdf.\n Datasheet:###{datasheet}###"
        if property_definition or property.unit or property.values:
            prompt += f'\nThe "{property_name}"'
            if property_definition: 
                prompt += f'\n- is defined as "{property_definition}".'
            if property.unit: 
                prompt += f'\n- has the unit of measure "{property.unit}".'
            if property.values: 
                prompt += f'\n- has possible values: "{[v["value"] for v in property.values]}".'
        
        prompt += f'\nWhat is the "{property_name}" of the device?'
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