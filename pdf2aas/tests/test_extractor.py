from ..extractor import DummyPropertyLLM

def test_dummy_property_llm_extract():
    e = DummyPropertyLLM()
    assert e.extract("datasheet","property def") == '{"property_x":"12"}'
