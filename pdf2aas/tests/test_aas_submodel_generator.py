from ..generator import DummyTechnicalDataSubmodel


def test_dummy_technical_data_submodel_generator():
    g = DummyTechnicalDataSubmodel()
    assert g.generate([]) == "<AASSubmodel>DUMMY</AASSubmodel>"
