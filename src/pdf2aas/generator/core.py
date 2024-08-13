from pdf2aas.extractor import Property

class Generator:
    def __init__(self) -> None:
        self.properties: list[Property] = []

    def reset(self):
        self.properties: list[Property] = []
    
    def add_properties(self, properties: list[Property]):
        self.properties.extend(properties)
    
    def dumps(self) -> str:
        return str(self.properties)
    
    def dump(self, filepath:str):
        with open(filepath, 'w', encoding="utf-8") as file:
            file.write(self.dumps())
