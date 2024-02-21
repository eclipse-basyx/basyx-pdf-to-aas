from extractor import PropertyLLM
from dictionary import PropertyDefinition
from openai import OpenAI
import tiktoken
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