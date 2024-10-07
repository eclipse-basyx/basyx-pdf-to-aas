import json
from datetime import datetime
from copy import deepcopy

import pytest
import basyx.aas.model

from pdf2aas.generator import Generator, CSV, AASSubmodelTechnicalData, AASTemplate
from pdf2aas.model import Property, PropertyDefinition
from pdf2aas.dictionary import ECLASS, ETIM

from test_extractor import example_property_numeric, example_property_string, example_property_range

test_property_list = [example_property_numeric, example_property_string]
test_property_list2 = [example_property_numeric, example_property_string, example_property_range]

class TestGenerator:
    def setup_method(self) -> None:
        self.g = Generator()
    def test_reset(self):
        self.g.add_properties(test_property_list)
        self.g.reset()
        assert self.g.dumps() == "[]"
    def test_dumps(self):
        self.g.add_properties(test_property_list)
        assert self.g.dumps() == str(test_property_list)

class TestCSV:
    def setup_method(self) -> None:
        self.g = CSV()
    def test_reset(self):
        self.g.add_properties(test_property_list)
        self.g.reset()
        assert self.g.dumps() == f'"{'";"'.join(CSV.header)}"\n'
    def test_dumps(self):
        self.g.add_properties(test_property_list)
        with(open('tests/assets/dummy-result.csv') as file):
            assert self.g.dumps() == file.read()

class TestAASSubmodelTechnicalData:
    def setup_method(self) -> None:
        self.g = AASSubmodelTechnicalData("id1")
    
    @staticmethod
    def load_asset(filename):
        with(open('tests/assets/'+filename) as file):
            submodel = json.load(file)
        for element in submodel['submodelElements']:
            if element['idShort'] == 'FurtherInformation':
                for item in element['value']:
                    if item['idShort'] == 'ValidDate':
                        item['value'] = datetime.now().strftime('%Y-%m-%d')
                        break
                break
        return submodel

    def test_reset(self):
        self.g.add_properties(test_property_list)
        self.g.reset()
        # self.g.dump('tests/assets/dummy-result-technical-data-submodel-empty.json')
        expected = self.load_asset('dummy-result-technical-data-submodel-empty.json')
        assert expected == json.loads(self.g.dumps())
    
    def test_dumps(self):
        self.g.add_properties(test_property_list)
        # self.g.dump('tests/assets/dummy-result-technical-data-submodel.json')
        expected = self.load_asset('dummy-result-technical-data-submodel.json')
        assert expected == json.loads(self.g.dumps())
    
    @pytest.mark.parametrize("definition,value", [
        (None, None),
        (None, []),
        (None, [None, None]),
        (None, {'a': None, 'b': None}),
        (None, ""),
        (PropertyDefinition("my_definition", type="int"), None),
        (PropertyDefinition("my_definition", type="range"), None),
    ])
    def test_dump_without_none(self, definition, value):
        self.g.add_properties([Property("my_empty_property", value=value, definition=definition)])
        json_dump = self.g.dumps()
        assert "my_empty_property" in json_dump
        if definition:
            assert "my_definition" in json_dump
        
        self.g.remove_empty_submodel_elements()
        json_dump = self.g.dumps()
        assert "my_empty_property" not in json_dump
        if definition:
            assert "my_definition" not in json_dump

    @pytest.mark.parametrize("range,min,max", [
            ('5', 5 ,5),
            ('0 ... 5', 0 ,5),
            ('0..5', 0 ,.5),
            ('-5 .. 10', -5 ,10),
            ([-5,10], -5, 10),
            ([10,-5], -5, 10),
            ({'min':-5, 'max': 10}, -5, 10),
            ({'max':10, 'min': -5}, -5, 10),
            ('from 5 to 10', 5, 10),
            ('5 [m] .. 10 [m]', 5, 10),
            ('-10 - -5', -10 ,-5),
            ([5.0, 10.0], 5.0, 10.0),
            ('5_000.1 .. 10_000.2', 5000.1, 10000.2),
    ])
    def test_add_range_properties(self, range, min, max):
        aas_property = self.g._create_aas_property(Property(value=range, definition=PropertyDefinition('id1', type="range")))
        assert aas_property is not None
        assert isinstance(aas_property, basyx.aas.model.Range)
        assert aas_property.min == min
        assert aas_property.max == max

    def test_add_list_properties(self):
        value = [0,5,42.42]
        aas_property = self.g._create_aas_property(Property(value=value, definition=PropertyDefinition('id1', type="numeric")))
        assert aas_property is not None
        assert isinstance(aas_property, basyx.aas.model.SubmodelElementCollection)
        assert len(aas_property.value) == len(value)
        for idx, smc_property in enumerate(aas_property.value):
            assert isinstance(smc_property, basyx.aas.model.Property)
            assert smc_property.value == value[idx]
    
    def test_add_dict_properties(self):
        value = {'first': 0, 'second': 5, 'third': 42.42}
        aas_property = self.g._create_aas_property(Property(value=value, definition=PropertyDefinition('id1', type="numeric")))
        assert aas_property is not None
        assert isinstance(aas_property, basyx.aas.model.SubmodelElementCollection)
        assert len(aas_property.value) == len(value)
        for smc_property in aas_property.value:
            assert isinstance(smc_property, basyx.aas.model.Property)
            key = smc_property.id_short[4:] # remove 'id1_'
            assert key in value
            assert smc_property.value == value[key]
    
    def test_add_same_id_short(self):
        self.g.add_properties([
            Property('id1'),
        ])
        container = self.g.technical_properties.value
        assert "id2" == self.g._generate_next_free_id_short(container, "id1")

    @pytest.mark.parametrize("existing_id,new_id,expected_id", [
        ('id', 'id1', 'id1'),
        ('id', 'id', 'id_1'),
        ('id_42', 'id_42', 'id_43'),
        ('a'*128, 'a'*128, 'a'*126+'_1'),
        ('a'*127, 'a'*127, 'a'*126+'_1'),
        ('a'*127 +'1', 'a'*127+'1', 'a'*127+'2'),
        ('a'*127 +'9', 'a'*127+'9', 'a'*126+'10'),
    ])
    def test_add_same_id_short(self, existing_id, new_id, expected_id):
        self.g.add_properties([Property(existing_id)])
        next_id = self.g._generate_next_free_id_short(
            self.g.technical_properties.value, new_id)
        assert next_id == expected_id
        assert len(new_id) < 129
    
    @pytest.mark.parametrize("id,label", [
        ("0173-1#02-AAO677#002", None,),
        ("0173-1#02-AAO677#003", None,),
        (None, "ManufacturerName",),
        (None, "Manufacturer name",),
        ("other_id", "other_label")
    ])
    def test_update_general_information_properties(self, id, label):
        self.g.add_properties([Property(label=label, value="TheManufacturer", definition=PropertyDefinition(id))])
        manufacturer_name = self.g.general_information.value.get('id_short', "ManufacturerName")
        assert manufacturer_name is not None
        if id == "other_id":
            assert manufacturer_name.value == None
        else:
            assert manufacturer_name.value == "TheManufacturer"

    @pytest.mark.parametrize("dicts", [
        ([ECLASS(release="14.0")]),
        ([ETIM(release="9.0")]),
        ([ECLASS(release="13.0"), ETIM(release="8.0")]),
    ])
    def test_add_classification(self, dicts):
        for idx, dict in enumerate(dicts):
            assert len(self.g.product_classifications.value) == idx
            self.g.add_classification(dict, str(idx))
            assert len(self.g.product_classifications.value) == idx+1
            classification = self.g.product_classifications.value.get('id_short', f'ProductClassificationItem{idx+1:02d}')
            assert classification is not None
            system = classification.value.get('id_short', 'ProductClassificationSystem')
            assert system is not None
            assert system.value == dict.name
            version = classification.value.get('id_short', 'ClassificationSystemVersion')
            assert version is not None
            assert version.value == dict.release
            class_id = classification.value.get('id_short', 'ProductClassId')
            assert class_id is not None
            assert class_id.value == str(idx)

    @pytest.mark.xfail
    def test_basyx_aas_json_serialization_deserialization(self):
        self.g.add_properties(test_property_list)
        from basyx.aas.adapter.json import json_serialization, json_deserialization
        submodel : basyx.aas.model.Submodel = json.loads(json.dumps(self.g.submodel, cls=json_serialization.AASToJsonEncoder), cls=json_deserialization.AASFromJsonDecoder)        
        assert submodel == self.g.submodel

class TestAASTemplate:
    def setup_method(self) -> None:
        self.g = AASTemplate('tests/assets/dummy-result-aas-template.aasx')

    @staticmethod
    def create_assets():
        td_submodel = AASSubmodelTechnicalData('id1')
        td_submodel.add_properties(test_property_list2)
        td_submodel.save_as_aasx('tests/assets/dummy-result-aas-template.aasx')

    @pytest.mark.parametrize("property_", test_property_list2)
    def test_load_property_values(self, property_:Property):
        old_property, aas_property = self.g._properties.get('id1/TechnicalProperties/' + property_.label)
        if property_.definition.type == "range":
            assert aas_property.min == property_.value[0]
            assert aas_property.max == property_.value[1]
        else:
            assert aas_property.value == property_.value
        assert old_property.value == property_.value

    @pytest.mark.parametrize("property_,new_value", [
        (example_property_numeric, 42),
        (example_property_string, 'b'),
        (example_property_range, [42,43]),
    ])
    def test_add_properties(self, property_:Property, new_value):
        property_copy = deepcopy(property_)
        property_copy.value = new_value
        property_copy.id = 'id1/TechnicalProperties/' + property_.label
        self.g.add_properties([property_copy])
        updated_property, updated_aas_property = self.g._properties.get(property_copy.id)
        if property_copy.definition.type == "range":
            assert updated_aas_property.min == new_value[0]
            assert updated_aas_property.max == new_value[1]
        else:
            assert updated_aas_property.value == new_value
        assert updated_property.value == new_value


    @pytest.mark.parametrize("property_", test_property_list2)
    def test_get_properties(self, property_:Property):
        properties = self.g.get_properties()
        assert len(properties) == 9
        
        property_result = next((p for p in properties if p.label == property_.label), None)
        assert property_result is not None
        assert property_result.language == property_.language
        assert property_result.value == property_.value
        #Unit is currently not exported and thus not read
        # assert property_result.unit == property_.unit
        assert property_result.reference == property_.reference

        assert property_result.definition is not None
        assert property_result.definition.id == property_.definition.id
        assert property_result.definition.name == property_.definition.name
        assert property_result.definition.type == property_.definition.type
        assert property_result.definition.unit == property_.definition.unit
        assert property_result.definition.definition == property_.definition.definition
        #The definition.values might differ
        assert sorted(property_result.definition.values_list) == sorted(property_.definition.values_list)
