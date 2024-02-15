class AASSubmodelGenerator:
    def generate(self, input: str) -> str:
        raise NotImplementedError()


class SimpleAASSubmodelGenerator:
    def generate(self, input: str) -> str:
        return "<AASSubmodel>DUMMY</AASSubmodel>"
