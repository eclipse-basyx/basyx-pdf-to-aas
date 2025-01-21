import pytest
from pdf2aas.model import PropertyDefinition
from pdf2aas.dictionary import CDD, ECLASS

class TestCDD:
    @staticmethod
    @pytest.mark.xfail(reason="IEC CDD might not be available from CI environment.")
    def test_get_class_properties():
        d = CDD(release="V2.0018.0002")
        class_id = "0112/2///62683#ACC501#002"
        properties = d.get_class_properties(class_id)
        assert len(properties) == 45

        assert class_id in d.classes.keys()
        class_ = d.classes[class_id]
        assert class_.id == class_id
        assert class_.name == "Inductive proximity switch"
        # "definition" is no FREE ATTRIBUTE --> no description
        # class_.description == "proximity switch producing an electromagnetic field within a sensing zone for detecting objects and having a semiconductor switching element"
        assert class_.description == ""
        assert class_.keywords == []

        switching_distance = PropertyDefinition(
            id="0112/2///62683#ACE251#001",
            name={"en": "rated operating distance"},
            type="numeric",
            definition={
                "en": "conventional quantity used to designate the operating distances"
            },
            unit="mm",
            values=[],
        )
        assert switching_distance in properties
        assert CDD.properties["0112/2///62683#ACE251#001"] == switching_distance

        mounting_position_values = [
            {
                'value': 'flush mounting',
                'id': '0112/2///62683#ACH210#001',
                # "definition" is no FREE ATTRIBUTE
                # 'definition': 'embeddable mounting when any damping material can be placed around the sensing face plane without influencing its characteristics',
                'symbol': 'FLUSHMOUNT'
            }, {
                'value': 'not flush mounting',
                'id': '0112/2///62683#ACH211#001',
                # "definition" is no FREE ATTRIBUTE
                # 'definition': 'non-embeddable mounting when a specified free zone around its sensing face is necessary in order to maintain its characteristics.',
                'symbol': 'NOTFLUSH'
            }
        ]
        assert CDD.properties["0112/2///62683#ACE811#002"].values == mounting_position_values

class TestECLASS:
    @staticmethod
    @pytest.mark.xfail(reason="ECLASS Website might not be available from CI environment.")
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

        d2 = ECLASS(release="13.0")
        assert "27274001" not in d2.classes.keys()
