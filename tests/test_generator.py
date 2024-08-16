import json
from datetime import datetime

from pdf2aas.generator import Generator, CSV, AASSubmodelTechnicalData

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
        # self.g.dump('tests/assets/dummy-result-technical-data-submodel-empty.json')
        self.g.add_properties(test_property_list)
        self.g.reset()
        expected = self.load_asset('dummy-result-technical-data-submodel-empty.json')
        assert expected == json.loads(self.g.dumps())
    
    def test_dumps(self):
        self.g.reset()
        self.g.add_properties(test_property_list)
        # self.g.dump('tests/assets/dummy-result-technical-data-submodel.json')
        expected = self.load_asset('dummy-result-technical-data-submodel.json')
        assert expected == json.loads(self.g.dumps())
