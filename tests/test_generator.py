import json

from pdf2aas.generator import DummyTechnicalDataSubmodel, CSV, AASSubmodelTechnicalData
from pdf2aas.extractor import DummyPropertyLLM
from pdf2aas.dictionary import PropertyDefinition

def test_dummy_technical_data_submodel_generate():
    g = DummyTechnicalDataSubmodel()
    assert g.generate([]) == "<AASSubmodel>DUMMY</AASSubmodel>"

test_property_list = DummyPropertyLLM.empty_property_result(PropertyDefinition("id1", {'en': 'name1'})) + [{
    "property": "property2",
    "value": 1,
    "unit": "kg",
    "reference": "property1 is one kg",
    "id": "id2",
    "name": "name2"
}]

def test_csv_generate():
    g = CSV()
    csv = g.generate(test_property_list)
    with(open('tests/assets/dummy-result.csv') as file):
        assert csv == file.read()

def test_submodel_technical_data_generate():
    g = AASSubmodelTechnicalData("id1")
    submodel = g.generate(test_property_list)
    with(open('tests/assets/dummy-result-technical-data-submodel.json') as file):
        assert json.load(file) == json.loads(submodel)