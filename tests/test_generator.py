import json
from datetime import datetime

from pdf2aas.generator import Generator, CSV, AASSubmodelTechnicalData
from pdf2aas.extractor import Property
from pdf2aas.dictionary import PropertyDefinition

from test_extractor import example_property_value1, example_property_value2

test_property_list = [example_property_value1, example_property_value2]

def test_generator_dumps():
    g = Generator()
    assert g.dumps() == "[]"
    g.add_properties(test_property_list)
    assert g.dumps() == str(test_property_list)

def test_csv_dumps():
    g = CSV()
    assert g.dumps() == f'"{'";"'.join(CSV.header)}"\n'
    g.add_properties(test_property_list)
    with(open('tests/assets/dummy-result.csv') as file):
        assert g.dumps() == file.read()

def test_submodel_technical_data_generate():
    g = AASSubmodelTechnicalData("id1")
    g.add_properties(test_property_list)
    with(open('tests/assets/dummy-result-technical-data-submodel.json') as file):
        expected = json.load(file)
        for element in expected['submodelElements']:
            if element['idShort'] == 'FurtherInformation':
                for item in element['value']:
                    if item['idShort'] == 'ValidDate':
                        item['value'] = datetime.now().strftime('%Y-%m-%d')
                        break
                break
        assert expected == json.loads(g.dumps())