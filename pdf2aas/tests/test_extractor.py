from extractor import DummyPropertyLLM
from dictionary import PropertyDefinition

def test_dummy_property_llm_extract():
    e = DummyPropertyLLM()
    assert e.extract("datasheet",PropertyDefinition('EC002714')) == '{"property_x":"12"}'
