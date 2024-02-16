from ..generator import DummyTechnicalDataSubmodel

def test_dummy_technical_data_submodel_generate():
    g = DummyTechnicalDataSubmodel()
    assert g.generate([]) == "<AASSubmodel>DUMMY</AASSubmodel>"
