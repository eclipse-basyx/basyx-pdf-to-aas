class Preprocessor:
    def convert(self, filepath: str) -> list[str] | str | None:
        raise NotImplementedError()


class DummyPDF2HTML(Preprocessor):
    def convert(self, filepath: str) -> str:
        return "html"
