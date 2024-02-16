class Generator:
    output = None
    
    def generate(self, properties: str) -> str:
        raise NotImplementedError()
    def save(self, properties: str) -> str:
        raise NotImplementedError()

class AASSubmodel:
    pass

class TechnicalDataSubmodel(AASSubmodel):
    pass

class DummyTechnicalDataSubmodel():
    def generate(self, properties: str) -> str:
        return "<AASSubmodel>DUMMY</AASSubmodel>"

class CSV():
    def generate(self, properties: str) -> str:
        return "property, value, unit, datatype, semantic"
    def save(self, filepath: str):
        raise NotImplementedError()