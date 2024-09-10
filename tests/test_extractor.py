import pytest

from pdf2aas.dictionary import PropertyDefinition
from pdf2aas.extractor import CustomLLMClient, PropertyLLMSearch, Property

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
    
        