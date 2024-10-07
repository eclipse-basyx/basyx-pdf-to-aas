"""Generic generator class to export property lists to different formats."""
from pdf2aas.model import Property


class Generator:
    """Generic and simple generator class.
    
    Holds a list of extracted properties. Allows to dump them via str
    representation. More specific generators derived from this class are available.
    """

    def __init__(self) -> None:
        """Initialize the Generator with an empty list of properties."""
        self._properties: list[Property] = []

    def reset(self):
        """Reset the list of properties to an empty list."""
        self._properties: list[Property] = []

    def add_properties(self, properties: list[Property]) -> None:
        """Add a list of properties to the generator."""
        self._properties.extend(properties)

    def get_properties(self) -> list[Property]:
        """Get the list of properties stored in the generator."""
        return self._properties

    def dumps(self) -> str:
        """Get a string representation of the list of properties."""
        return str(self._properties)

    def dump(self, filepath:str) -> None:
        """Write the string representation of the properties to a file."""
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(self.dumps())
