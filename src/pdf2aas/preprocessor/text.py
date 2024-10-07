"""Preprocessor to use text files."""
import logging

from .core import Preprocessor

logger = logging.getLogger(__name__)

class Text(Preprocessor):
    """Text preprocessor for loading text from txt, csv, html files.

    This class is a simple preprocessor that opens the filepath as text file.
    """

    def __init__(self, encoding=None, newline=None) -> None:
        """Init preprocessor with default encoding and newline settings.
        
        C.f. open() function for parameter description.

        """
        super().__init__()
        self.encoding: str | None = encoding
        self.newline: str | None = newline

    def convert(self, filepath: str) -> list[str] | str | None:
        """Open the filepath and return it as txt.
        
        If an error occurs during the reading of the file, it logs the error
        and returns None.

        """
        logger.debug(f"Loading text from pdf: {filepath}")
        try:
            with open(filepath, encoding=self.encoding, newline=self.newline) as file:
                text = file.read()
        except (FileNotFoundError, PermissionError, IsADirectoryError, IOError) as e:
            logging.error(f"Couldn't load file: {e}")
            return None
        return text