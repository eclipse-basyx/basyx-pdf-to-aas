class AASSubmodel:
    def generate(self, properties: str) -> str:
        raise NotImplementedError()

class TechnicalDataSubmodel(AASSubmodel):
    pass

class DummyTechnicalDataSubmodel():
    def generate(self, properties: str) -> str:
        return "<AASSubmodel>DUMMY</AASSubmodel>"
