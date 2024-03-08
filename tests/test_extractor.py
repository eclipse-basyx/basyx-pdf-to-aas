from pdf2aas.dictionary import PropertyDefinition
from pdf2aas.extractor import DummyPropertyLLM


def test_dummy_property_llm_extract():
    e = DummyPropertyLLM()
    assert (
        e.extract("datasheet", PropertyDefinition("EC002714")) == '{"property_x":"12"}'
    )
