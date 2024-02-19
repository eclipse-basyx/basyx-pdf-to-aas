from dictionary import DummyDictionary, PropertyDefinition

def test_dummy_property_llm_extract():
    d = DummyDictionary()
    assert d.get_class_properties('EC002714') == [PropertyDefinition('EF003647', 'Switching distance', 'numeric')]
