class Dictionary:
    def getClassProperties(self, class_id: str) -> str:
        raise NotImplementedError()

class ECLASS(Dictionary):
    pass
    
class ETIM(Dictionary):
    pass

# CDD, UNSPSC, ...

class DummyDictionary(Dictionary):
    def getClassProperties(self, class_id: str) -> str:
        # e.g.: https://prod.etim-international.com/Feature/Details/EF003647?local=False
        return [{'id': 'EF003647', 'name': 'Switching distance', 'type': 'N'}]
    