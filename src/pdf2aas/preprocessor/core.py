from abc import ABC, abstractmethod

class Preprocessor(ABC):
    @abstractmethod
    def convert(self, filepath: str) -> list[str] | str | None:
        raise NotImplementedError()
