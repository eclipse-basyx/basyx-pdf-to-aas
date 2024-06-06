import logging

from pypdfium2 import PdfDocument, PdfiumError

from .core import Preprocessor

logger = logging.getLogger(__name__)

class PDFium(Preprocessor):
    """
    PDFium Preprocessor class for extracting text from PDF files.

    This class is a simple preprocessor that uses the PDFium library to extract text from PDF documents without layout information.

    Note:
        - Best text extraction quality based on simple benchmark: https://github.com/py-pdf/benchmarks
    """
    def convert(self, filepath: str) -> list[str] | str | None:
        """
        Converts the content of a PDF file into a list of strings, where each string represents the text of a page.
            If an error occurs during the reading of the PDF file, it logs the error and returns None.
        """
        logger.debug(f"Converting to text from pdf: {filepath}")
        try:
            doc = PdfDocument(filepath, autoclose=True)
        except (PdfiumError, FileNotFoundError) as e:
            logger.error(f"Error reading {filepath}: {e}")
            return None
        return [page.get_textpage().get_text_bounded().replace('\r\n', '\n').replace('\r', '\n') for page in doc]
