"""Preprocessor to use text files."""

import logging

from .core import Preprocessor

logger = logging.getLogger(__name__)


class Text(Preprocessor):
    """Text preprocessor for loading text from txt, csv, html files.

    This class is a simple preprocessor that opens the filepath as text file.
    """

    def __init__(
        self,
        encoding: str | None = None,
        newline: str | None = None,
    ) -> None:
        r"""Init preprocessor.

        C.f. open() function for parameter description.

        Args:
            encoding: encoding used to open the file, e.g. utf-8
            newline: char to split new lines, e.g. \n

        """
        super().__init__()
        self.encoding: str | None = encoding
        self.newline: str | None = newline

    def convert(self, filepath: str) -> list[str] | str | None:
        """Open the filepath and return it as txt.

        If an error occurs during the reading of the file, it logs the error
        and returns None.

        """
        logger.debug("Loading text from pdf: %s", filepath)
        try:
            with open(filepath, encoding=self.encoding, newline=self.newline) as file:
                text = file.read()
        except (OSError, FileNotFoundError, PermissionError, IsADirectoryError):
            logging.exception("Couldn't load file.")
            return None
        return text
