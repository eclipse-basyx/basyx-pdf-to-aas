from pdf2aas.dictionary import ECLASS, DummyDictionary, PropertyDefinition


def test_dummy_dictionary_get_class_properties():
    d = DummyDictionary()
    assert d.get_class_properties("EC002714") == [
        PropertyDefinition("EF003647", "Switching distance", "numeric")
    ]


def test_get_class_properties():
    d = ECLASS(release="14.0")
    properties = d.get_class_properties("27274001")
    assert len(properties) == 108

    assert "27274001" in d.classes.keys()
    eclass_class = d.classes["27274001"]
    assert eclass_class.id == "27274001"
    assert eclass_class.name == "Inductive proximity switch"
    assert (
        eclass_class.description
        == "Inductive proximity switch producing an electromagnetic field within a sensing zone and having a semiconductor switching element"
    )
    assert eclass_class.keywords == [
        "Transponder switch",
        "Inductive sensor",
        "Inductive proximity sensor",
    ]
    assert len(eclass_class.properties) == 108

    switching_distance = PropertyDefinition(
        id="0173-1#02-BAD815#009",
        name={"en": "switching distance sn"},
        type="numeric",
        definition={
            "en": "Conventional size for defining the switch distances for which neither production tolerances nor changes resulting from external influences, such as voltage and temperature, need to be taken into account"
        },
        unit="mm",
        values=[],
    )
    assert switching_distance in properties
    assert ECLASS.properties["0173-1#02-BAD815#009"] == switching_distance

    d.release = "13.0"
    assert "27274001" not in d.classes.keys()
