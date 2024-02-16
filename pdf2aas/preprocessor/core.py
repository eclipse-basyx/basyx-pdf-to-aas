class PDF2HTML:
    def convert(self, filepath: str) -> str:
        raise NotImplementedError()


class DummyPDF2HTML(PDF2HTML):
    def convert(self, filepath: str) -> str:
        return "html"
