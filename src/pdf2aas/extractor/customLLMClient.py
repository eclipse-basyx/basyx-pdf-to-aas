import string
import logging
import requests

logger = logging.getLogger(__name__)

# class CustomLLMClient():
#     def create_completions(
#             self,
#             messages: list[dict[str, str]],
#             model: str,
#             temperature: float,
#             max_tokens: int,
#             response_format: str
#     ) -> tuple[str, str]:
#         raise NotImplementedError()

# class CustomLLMClientHTTP(CustomLLMClient):
#     def __init__(self,
#                  endpoint: str ,
#                  api_key :str = None,
#                  request_template : str = None,
#                  response_template: str = None,
#     ) -> None:
#         super().__init__()
#         self.endpoint = endpoint
#         self.api_key = api_key
#         self.request_template=request_template
#         self.response_template=response_template
    
#     def create_completions(self, messages: list[dict[str, str]], model: str, temperature: float, max_tokens: int, response_format: str) -> tuple[str, str]:
        

class CustomLLMClient:
    """
    Abstract base class for a custom LLM client.
    
    This class defines the interface for creating completions using a language model.
    Subclasses must implement the `create_completions` method.
    """
    def create_completions(
            self,
            messages: list[dict[str, str]],
            model: str,
            temperature: float,
            max_tokens: int,
            response_format: dict
    ) -> tuple[str, str]:
        """
        Create completions using a language model.
        
        Parameters:
        - messages (list[dict[str, str]]): List of message dictionaries with role and content.
        - model (str): The model to use for generating completions.
        - temperature (float): Sampling temperature.
        - max_tokens (int): Maximum number of tokens to generate.
        - response_format (str): The desired format of the response, e.g. {"type": "json_object"}
        
        Returns:
        - tuple[str, str]: A tuple containing the extracted response and the raw result.
        
        Raises:
        - NotImplementedError: If the method is not implemented by a subclass.
        """
        raise NotImplementedError()

class CustomLLMClientHTTP(CustomLLMClient):
    """
    Custom LLM client that communicates with an HTTP endpoint.
    
    This client sends requests to a specified HTTP endpoint to generate chat completions.
    """
    def __init__(self,
                 endpoint: str,
                 api_key: str = None,
                 request_template: str = None,
                 response_template: str = None,
    ) -> None:
        """
        Initialize the CustomLLMClientHTTP instance.
        
        Parameters:
        - endpoint (str): The URL of the HTTP endpoint.
        - api_key (str, optional): The API key for authentication.
        - request_template (str, optional): The template for the request payload.
        - response_template (str, optional): The template for extracting the result from the response.
        """
        super().__init__()
        self.endpoint = endpoint
        self.api_key = api_key
        self.request_template = request_template
        self.response_template = response_template

    def create_completions(self, messages: list[dict[str, str]], model: str, temperature: float, max_tokens: int, response_format: dict) -> tuple[str, str]:
        """
        Create completions using the specified HTTP endpoint.
        
        Parameters:
        - messages (list[dict[str, str]]): List of message dictionaries with role and content.
        - model (str): The model to use for generating completions.
        - temperature (float): Sampling temperature.
        - max_tokens (int): Maximum number of tokens to generate.
        - response_format (str): The format of the response.
        
        Returns:
        - tuple[str, str]: A tuple containing the extracted response and the raw result.
        
        Raises:
        - requests.exceptions.RequestException: If an error occurs during the HTTP request.
        """
        # Prepare the request payload using the request_template
        request_payload = string.Template(self.request_template).substitute(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        
        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        try:
            response = requests.post(self.endpoint, headers=headers, json=request_payload)
            response.raise_for_status()
            result = response.json()
            
            if self.response_template:
                response_content = string.Template(self.response_template).substitute(result)
            else:
                response_content = result
            
            return response_content, result
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error requesting the custom LLM endpoint: {e}")
            return None, None
