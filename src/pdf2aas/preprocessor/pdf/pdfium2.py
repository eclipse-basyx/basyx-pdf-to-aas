"""Preprocessor using pypdfium2 library."""

import logging

from pypdfium2 import PdfDocument, PdfiumError

from pdf2aas.preprocessor import Preprocessor

logger = logging.getLogger(__name__)


class PDFium(Preprocessor):
    """PDFium Preprocessor class for extracting text from PDF files.

    This class is a simple preprocessor that uses the PDFium library to extract
    text from PDF documents without layout information.

    Note:
        - Best text extraction quality based on simple benchmark: https://github.com/py-pdf/benchmarks

    """

    def convert(self, filepath: str) -> list[str] | str | None:
        """Convert the content of a PDF file into a list of strings.

        Each string in the list represents the text of a page.
        If an error occurs during the reading of the PDF file, it logs the error
        and returns None.

        """
        logger.debug("Converting to text from pdf: %s", {filepath})
        try:
            doc = PdfDocument(filepath, autoclose=True)
        except (PdfiumError, FileNotFoundError):
            logger.exception("Error reading filepath: %s.", filepath)
            return None
        return [
            page.get_textpage().get_text_bounded().replace("\r\n", "\n").replace("\r", "\n")
            for page in doc
        ]
