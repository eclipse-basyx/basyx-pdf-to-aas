from ..aas_submodel_generator import SimpleAASSubmodelGenerator


def test_simple_aas_submodel_generator():
    g = SimpleAASSubmodelGenerator()
    assert g.generate("input") == "<AASSubmodel>DUMMY</AASSubmodel>"
