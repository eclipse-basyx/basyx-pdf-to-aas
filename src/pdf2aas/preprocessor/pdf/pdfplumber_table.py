"""Preprocessor using pdfplumber library."""

import logging

import pdfplumber
from tabulate import tabulate

from pdf2aas.preprocessor import Preprocessor

logger = logging.getLogger(__name__)


class PDFPlumberTable(Preprocessor):
    """Extract tables from PDF files using pdfplumber library.

    Args:
        output_format (str, optional): The format in which the extracted tables should be output.
            Default is 'html'. Other possibilities are defined by tabulate, c.f.
            `tabulate.tabulate_formats". Examples are: 'github', 'html', 'simple', 'tsv'.
            None retuns a list (table) of list (row) of list (cell) of string.

    Note:
        - Not so good extraction quality based on camelot benchmark:
        https://github.com/camelot-dev/camelot/wiki/Comparison-with-other-PDF-Table-Extraction-libraries-and-tools
        - Does not require Ghostscript (camelot) or Java (tabula). It relies on PyPDF2 for
          PDF parsing.

    """

    def __init__(
        self,
        output_format: str | None = "html",
    ) -> None:
        """Initialize preprocessor with html format."""
        self.output_format = output_format

    def convert(self, filepath: str) -> list[str] | None:
        """Convert the content of a PDF file into a list of tables as strings.

        Each string represents a table from the pdf in the desired `output_format`
        (default html, c.f. `tabulate.tabulate_formats` for more). If an error
        occurs during the reading of the PDF file, it logs the error and returns None.
        """
        logger.debug("Extracting tables from PDF: %s", filepath)
        try:
            pdf = pdfplumber.open(filepath)
        except FileNotFoundError:
            logger.exception("File not found: %s", filepath)
            return None

        with pdf:
            return [
                tabulate(table, tablefmt=self.output_format) if self.output_format else table
                for page in pdf.pages
                for table in page.extract_tables()
            ]
