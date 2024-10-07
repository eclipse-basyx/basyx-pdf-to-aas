"""Abstract definitions for preprocessors."""
from abc import ABC, abstractmethod

class Preprocessor(ABC):
    """Abstract base class for preprocessing files for the PDF2AAS workflow.

    Methods:
        convert(filepath: str) -> list[str] | str | None:
            Convert the given PDF file into a preprocessed format.

    """

    @abstractmethod
    def convert(self, filepath: str) -> list[str] | str | None:
        """Convert the given PDF file into a preprocessed format.

        Args:
            filepath (str): The file path to the input document.

        Returns:
            list[str] | str | None: The preprocessed content of the document. The format of the return value can vary depending on the implementation. A list typically represents page or table values.

        """