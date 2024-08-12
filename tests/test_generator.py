import json
from datetime import datetime

from pdf2aas.generator import Generator, CSV, AASSubmodelTechnicalData
from pdf2aas.extractor import DummyPropertyLLM
from pdf2aas.dictionary import PropertyDefinition

test_property_list = DummyPropertyLLM.empty_property_result(PropertyDefinition("id1", {'en': 'name1'})) + [{
    "property": "property2",
    "value": 1,
    "unit": "kg",
    "reference": "property1 is one kg",
    "id": "id2",
    "name": "name2"
}]

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