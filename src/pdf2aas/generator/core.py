from pdf2aas.extractor import Property

class Generator:
    def __init__(self) -> None:
        self._properties: list[Property] = []

    def reset(self):
        self._properties: list[Property] = []

    def add_properties(self, properties: list[Property]) -> None:
        self._properties.extend(properties)

    def get_properties(self) -> list[Property]:
        return self._properties

    def dumps(self) -> str:
        return str(self._properties)

    def dump(self, filepath:str) -> None:
        with open(filepath, 'w', encoding="utf-8") as file:
            file.write(self.dumps())
