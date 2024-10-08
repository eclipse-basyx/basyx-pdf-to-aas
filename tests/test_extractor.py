import pytest
from unittest.mock import patch, MagicMock
import json
import requests

from pdf2aas.model import PropertyDefinition, Property
from pdf2aas.extractor import CustomLLMClient, CustomLLMClientHTTP, PropertyLLMSearch

example_property_definition_numeric = PropertyDefinition("p1", {'en': 'property1'}, 'numeric', {'en': 'definition of p1'}, 'T')
example_property_definition_string = PropertyDefinition("p2", {'en': 'property2'}, 'string', {'en': 'definition of p2'}, values=['a', 'b'])
example_property_definition_range = PropertyDefinition("p3", {'en': 'property3'}, 'range', {'en': 'definition of p3'})

example_property_numeric = Property('property1', 1, 'kT', 'p1 is 1Nm', example_property_definition_numeric)
example_property_string = Property('property2', 'a', None, 'p2 is a', example_property_definition_string)
example_property_range = Property('property3', [5,10], None, 'p3 is 5 .. 10', example_property_definition_range)

example_accepted_llm_response = [
        '[{"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}]',
        '{"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}',
        '{"result": [{"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}]}',
        '{"property": [{"label": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}]}',
        '{"mykey": {"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}}',
        '{"property1": {"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}}',
        'My result is\n```json\n[{"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}]```',
    ]

example_accepted_llm_response_multiple = [
    '[{"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"},{"property": "property2", "value": "a", "unit": null, "reference": "p2 is a"}]',
    '{"property1": {"property": "property1", "value": 1, "unit": "kT", "reference": "p1 is 1Nm"}, "property2": {"property": "property2", "value": "a", "unit": null, "reference": "p2 is a"}}',
]

class DummyLLMClient(CustomLLMClient):
    def __init__(self) -> None:
        self.response = ""
        self.raw_response = ""
    def create_completions(self, messages: list[dict[str, str]], model: str, temperature: float, max_tokens: int, response_format: dict) -> tuple[str, str]:
        return self.response, self.raw_response

class TestPropertyLLMSearch():
    llm = PropertyLLMSearch('test', client=DummyLLMClient())

    @pytest.mark.parametrize("response", example_accepted_llm_response)
    def test_parse_accepted_llm_response(self, response):
        self.llm.client.response = response
        properties = self.llm.extract("datasheet", example_property_definition_numeric)
        assert properties == [example_property_numeric]
        properties = self.llm.extract("datasheet", [example_property_definition_numeric])
        assert properties == [example_property_numeric]
    
    def test_parse_null_llm_response(self):
        self.llm.client.response = '{}'
        properties = self.llm.extract("datasheet", example_property_definition_numeric)
        assert properties == []

        self.llm.client.response = '{"property": null, "value": null, "unit": null, "reference": null}'
        properties = self.llm.extract("datasheet", example_property_definition_numeric)
        assert properties == [Property(definition=example_property_definition_numeric)]
    
    @pytest.mark.parametrize("response", example_accepted_llm_response)
    def test_parse_accepted_incomplete_llm_response(self, response):
        self.llm.client.response = response
        properties = self.llm.extract("datasheet", [example_property_definition_numeric, example_property_definition_numeric])
        assert properties == [example_property_numeric]
    
    @pytest.mark.parametrize("response", example_accepted_llm_response_multiple)
    def test_parse_accepted_multiple_llm_response(self, response):
        self.llm.client.response = response
        properties = self.llm.extract("datasheet", [example_property_definition_numeric, example_property_definition_string])
        assert properties == [example_property_numeric, example_property_string]
    
    def test_parse_accepted_multiple_incomplete_llm_response(self):
        self.llm.client.response = example_accepted_llm_response[0]
        properties = self.llm.extract("datasheet", [example_property_definition_string, example_property_definition_numeric])
        assert properties == [example_property_numeric]

class TestCustomLLMClientHttp():
    mock_result = {"result": {"value": 42}, "status": 200}
    endpoint = "http://localhost:12345"
    messages = [
        {'role': 'system', 'content': 'system\nmessage'},
        {'role': 'user', 'content': 'user\nmessage'},
    ]
    model_identifier = 'test'
    temperature = 0.5
    max_tokens = 1000
    response_format = {"format": "json"}
    
    default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
    }
    default_payload = json.dumps({
        "model": model_identifier,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": response_format
    })

    def test_create_completions_post(self):
        client=CustomLLMClientHTTP(self.endpoint)
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: self.mock_result)
            result_content, result = client.create_completions(
                self.messages,
                self.model_identifier,
                self.temperature,
                self.max_tokens,
                self.response_format
            )

            mock_post.assert_called_once_with(
                self.endpoint,
                headers=self.default_headers,
                data=self.default_payload,
                verify=None,
                timeout=client.timeout,
            )
            assert result_content == self.mock_result
            assert result == self.mock_result
    
    def test_request_template(self):
        client=CustomLLMClientHTTP(self.endpoint)
        client.request_template = """{{"name": "{model}", "texts": [{message_system}, {message_user}], "t": {temperature} }}"""
        expected_payload = json.dumps({
            "name": self.model_identifier,
            "texts": [self.messages[0]['content'], self.messages[1]['content']],
            "t" : self.temperature,
        })
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: self.mock_result)
            client.create_completions(
                self.messages,
                self.model_identifier,
                self.temperature,
                self.max_tokens,
                self.response_format
            )

            mock_post.assert_called_once()
            called_args, called_kwargs = mock_post.call_args
            assert "data" in called_kwargs
            assert called_kwargs['data'] == expected_payload

    def test_result_path(self):
        client=CustomLLMClientHTTP(self.endpoint)
        client.result_path = "result.value"
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: self.mock_result)
            result_content, result = client.create_completions(
                self.messages,
                self.model_identifier,
                self.temperature,
                self.max_tokens,
                self.response_format
            )

            mock_post.assert_called_once()
            assert result_content == str(self.mock_result['result']['value'])
            assert result == self.mock_result
    
    def test_api_key_is_added_as_bearer(self):
        client=CustomLLMClientHTTP(self.endpoint)
        client.api_key = "my_api_key"
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: self.mock_result)
            client.create_completions(
                self.messages,
                self.model_identifier,
                self.temperature,
                self.max_tokens,
                self.response_format
            )

            mock_post.assert_called_once()
            called_args, called_kwargs = mock_post.call_args
            assert "headers" in called_kwargs
            assert "Authorization" in called_kwargs['headers']
            assert called_kwargs['headers']['Authorization'] == "Bearer my_api_key"
    
    def test_api_key_is_inserted(self):
        client=CustomLLMClientHTTP(self.endpoint)
        client.api_key = "my_api_key"
        client.headers = {'Authorization': 'here is {api_key}'}
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: self.mock_result)
            client.create_completions(
                self.messages,
                self.model_identifier,
                self.temperature,
                self.max_tokens,
                self.response_format
            )

            mock_post.assert_called_once()
            called_args, called_kwargs = mock_post.call_args
            assert "headers" in called_kwargs
            assert "Authorization" in called_kwargs['headers']
            assert called_kwargs['headers']['Authorization'] == "here is my_api_key"

    def test_retries(self):
        client=CustomLLMClientHTTP(self.endpoint)
        client.retries = 2
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=400, json=lambda: self.mock_result)
            mock_post.side_effect = requests.exceptions.RequestException("Mocked exception")
            client.create_completions(
                self.messages,
                self.model_identifier,
                self.temperature,
                self.max_tokens,
                self.response_format
            )
            assert mock_post.call_count == 3