import logging
import requests
from copy import deepcopy
import json

logger = logging.getLogger(__name__)

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

def evaluate_path(data, path):
    try:
        keys = path.replace('[', '.').replace(']', '').split('.')
        for key in keys:
            if isinstance(data, list):
                key = int(key)
            data = data[key]
    except (KeyError, ValueError, TypeError): 
        return None
    return data

class CustomLLMClientHTTP(CustomLLMClient):
    """
    Custom LLM client that communicates with an HTTP endpoint.
    
    This client sends requests to a specified HTTP endpoint to generate chat completions.
    """
    def __init__(self,
                 endpoint: str,
                 api_key: str = None,
                 request_template: str = None,
                 result_path: str = None,
                 headers: dict[str, str] = None,
                 retries: int  = 0,
    ) -> None:
        """
        A custom LLM client that uses http requests, which can be customized via string templates
        
        Parameters:
        - endpoint (str): The URL of the HTTP endpoint.
        - api_key (str, optional): The API key for authentication.
        - request_template (str, optional): The string template for the request payload. Supported placeholders:
          messages, message_system, message_user, model, temperature,max_tokens, response_format
        - result_path (str, optional): A simple path for extracting the result from the response after parsing it with json.loads, e.g. "choices[0].message.content"
        - headers (dict[str, str], optional): Overwrite headers. Default is "Content-Type": "application/json", "Accept": "application/json"
        - retries (int, optional): Number of retries, if request fails
        """
        super().__init__()
        self.endpoint = endpoint
        self.api_key = api_key
        if request_template is None:
            request_template = """{
    "model": "{model}",
    "messages": {messages},
    "max_tokens": {max_tokens},
    "temperature": {temperature},
    "response_format": {response_format},
}"""
        self.request_template = request_template
        self.result_path = result_path
        if headers is None:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        self.headers = headers
        self.retries = retries

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
        """
        request_payload = self.request_template.format(
            messages=json.dumps(messages),
            message_system=json.dumps(messages[0]['content']),
            message_user=json.dumps(messages[1]['content']),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        logger.debug(f"Custom LLM Client Request: {request_payload}")
        
        headers = deepcopy(self.headers)
        if self.api_key:
            headers['Authorization']=headers.get('Authorization', 'Bearer {api_key}').format(api_key=self.api_key)
        
        for attempt in range(self.retries+1):
            try:
                response = requests.post(self.endpoint, headers=headers, data=request_payload)
                response.raise_for_status()
                result = response.json()
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"Error requesting the custom LLM endpoint (attempt {attempt}): {e}")
                result = None
        if result is None:
            return None, None
        
        if self.result_path:
            result_content = evaluate_path(result, self.result_path)
        else:
            result_content = result

        return result_content, result
