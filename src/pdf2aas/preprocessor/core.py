class Preprocessor:
    def convert(self, filepath: str) -> str:
        raise NotImplementedError()


class DummyPDF2HTML(Preprocessor):
    def convert(self, filepath: str) -> str:
        return "html"
