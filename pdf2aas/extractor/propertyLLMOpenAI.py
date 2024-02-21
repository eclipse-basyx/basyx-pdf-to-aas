from extractor import PropertyLLM
from dictionary import PropertyDefinition
from openai import OpenAI
import os


class PropertyLLMOpenAI(PropertyLLM):
    
    def __init__(self, model_identifier: str, api_endpoint: str = None) -> None:
        super().__init__()
        self.model_identifier = model_identifier
        self.api_endpoint = api_endpoint
    
    def extract(self, datasheet: str, property_definition: PropertyDefinition) -> str:
        if os.getenv('OPENAI_API_KEY') is None:
            raise ValueError("No OpenAI API key found in environment")
        client = OpenAI()
        return ''
