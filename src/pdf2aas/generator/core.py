class Generator:
    def generate(self, properties: list) -> str:
        raise NotImplementedError()

class DummyTechnicalDataSubmodel:
    def generate(self, properties: list) -> str:
        return "<AASSubmodel>DUMMY</AASSubmodel>"
