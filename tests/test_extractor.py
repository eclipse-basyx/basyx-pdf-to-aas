from pdf2aas.dictionary import PropertyDefinition
from pdf2aas.extractor import DummyPropertyLLM


def test_dummy_property_llm_extract():
    e = DummyPropertyLLM()
    p = PropertyDefinition("EC002714")
    r = DummyPropertyLLM.empty_property_result(p)
    assert(e.extract("datasheet", p) == r)
