import json
from datetime import datetime

import pytest
import basyx.aas.model

from pdf2aas.generator import Generator, CSV, AASSubmodelTechnicalData
from pdf2aas.extractor import Property
from pdf2aas.dictionary import PropertyDefinition

from test_extractor import example_property_value1, example_property_value2

test_property_list = [example_property_value1, example_property_value2]

class TestGenerator:
    g = Generator()
    def test_reset(self):
        self.g.add_properties(test_property_list)
        self.g.reset()
        assert self.g.dumps() == "[]"
    def test_dumps(self):
        self.g.reset()
        self.g.add_properties(test_property_list)
        assert self.g.dumps() == str(test_property_list)

class TestCSV:
    g = CSV()
    def test_reset(self):
        self.g.add_properties(test_property_list)
        self.g.reset()
        assert self.g.dumps() == f'"{'";"'.join(CSV.header)}"\n'
    def test_dumps(self):
        self.g.reset()
        self.g.add_properties(test_property_list)
        with(open('tests/assets/dummy-result.csv') as file):
            assert self.g.dumps() == file.read()

class TestAASSubmodelTechnicalData:
    g = AASSubmodelTechnicalData("id1")
    
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
        self.g.reset()
        self.g.add_properties(test_property_list)
        # self.g.dump('tests/assets/dummy-result-technical-data-submodel.json')
        expected = self.load_asset('dummy-result-technical-data-submodel.json')
        assert expected == json.loads(self.g.dumps())
    
    @pytest.mark.parametrize("range,min,max", [
            ('5', 5 ,5),
            ('0 ... 5', 0 ,5),
            ('0..5', 0 ,.5),
            ('-5 .. 10', -5 ,10),
            ([-5,10], -5, 10),
            ({'5':'km', '10':'km'}, 5, 10),
            ('from 5 to 10', 5, 10),
            ('5 [m] .. 10 [m]', 5, 10),
            ('-10 - -5', -10 ,-5),
            ([5.0, 10.0], 5.0, 10.0),
            ('5_000.1 .. 10_000.2', 5000.1, 10000.2),
    ])
    def test_add_range_properties(self, range, min, max):
        self.g.reset()
        aas_property = self.g.create_aas_property(Property(value=range, definition=PropertyDefinition('id1', type="range")))
        assert aas_property is not None
        assert isinstance(aas_property, basyx.aas.model.Range)
        assert aas_property.min == min
        assert aas_property.max == max

    def test_add_list_properties(self):
        value = [0,5,42.42]
        self.g.reset()
        aas_property = self.g.create_aas_property(Property(value=value, definition=PropertyDefinition('id1', type="numeric")))
        assert aas_property is not None
        assert isinstance(aas_property, basyx.aas.model.SubmodelElementCollection)
        assert len(aas_property.value) == len(value)
        for idx, smc_property in enumerate(aas_property.value):
            assert isinstance(smc_property, basyx.aas.model.Property)
            assert smc_property.value == value[idx]
    
    def test_add_dict_properties(self):
        value = {'first': 0, 'second': 5, 'third': 42.42}
        self.g.reset()
        aas_property = self.g.create_aas_property(Property(value=value, definition=PropertyDefinition('id1', type="numeric")))
        assert aas_property is not None
        assert isinstance(aas_property, basyx.aas.model.SubmodelElementCollection)
        assert len(aas_property.value) == len(value)
        for smc_property in aas_property.value:
            assert isinstance(smc_property, basyx.aas.model.Property)
            key = smc_property.id_short[4:] # remove 'id1_'
            assert key in value
            assert smc_property.value == value[key]
