"""Preprocessor using camelot library."""

import logging
from typing import Literal

import camelot

from pdf2aas.preprocessor import Preprocessor

logger = logging.getLogger(__name__)


class Camelot(Preprocessor):
    """Extract tables from PDF files using camelot library.

    Args:
        output_format (Literal['html', 'markdown', 'json', 'csv']): The format
            in which the extracted tables should be output. Default is 'html'.
        accuracy_level (float): The minimum accuracy level required for tables
            to be included in the output. Default is 0.8.

    Note:
        - Needs to have ghostscript installed.
        - Best table extraction quality based on camelot benchmark: https://github.com/camelot-dev/camelot/wiki/Comparison-with-other-PDF-Table-Extraction-libraries-and-tools

    """

    def __init__(
        self,
        output_format: Literal["html", "markdown", "json,", "csv"] = "html",
        accuracy_limit: float = 0.8,
    ) -> None:
        """Initilialize preprocessor with html format and accuracy limit 0.8."""
        self.output_format = output_format
        self.accuracy_limit = accuracy_limit

    def convert(self, filepath: str) -> list[str] | str | None:
        """Convert the content of a PDF file into a list of tables as strings.

        Each string represents a table from the pdf in the desired `output_format`
        (default html). If an error occurs during the reading of the PDF file,
        it logs the error and returns None.
        """
        logger.debug("Extracting tables from PDF: %s", filepath)
        try:
            tables = camelot.read_pdf(filepath, pages="all", strip_text=" ")
        except FileNotFoundError:
            logger.exception("File not found: %s", filepath)
            return None

        result = []
        for table in tables:
            if table.accuracy < self.accuracy_limit:
                continue
            match self.output_format:
                case "html":
                    result.append(table.df.to_html())
                case "json":
                    result.append(table.df.to_json())
                case "csv":
                    result.append(table.df.to_csv())
                case "markdown":
                    result.append(table.df.to_markdown())
        return result
