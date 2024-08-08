class Generator:
    def __init__(self) -> None:
        self.properties = []

    def reset(self):
        self.properties = []
    
    def add_properties(self, properties: list):
        self.properties.extend(properties)
    
    def dumps(self) -> str:
        return str(self.properties)
    
    def dump(self, filepath:str):
        with open(filepath, 'w', encoding="utf-8") as file:
            file.write(self.dumps())
