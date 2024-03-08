class Generator:
    def generate(self, properties: list) -> str:
        raise NotImplementedError()


class AASSubmodel:
    pass


class TechnicalDataSubmodel(AASSubmodel):
    pass


class DummyTechnicalDataSubmodel:
    def generate(self, properties: list) -> str:
        return "<AASSubmodel>DUMMY</AASSubmodel>"
