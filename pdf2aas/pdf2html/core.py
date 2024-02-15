class PDF2HTML:
    def generate(self, input: str) -> str:
        raise NotImplementedError()


class SimplePDF2HTML(PDF2HTML):
    def generate(self, input: str) -> str:
        return "html"
