from ..dictionary import DummyDictionary

def test_dummy_property_llm_extract():
    d = DummyDictionary()
    assert d.get_class_properties('EC002714') == [{'id': 'EF003647', 'name': 'Switching distance', 'type': 'N'}]
