"""Preprocessor using pdfplumber library."""

import logging
from typing import Literal

import pandas as pd
import pdfplumber

from pdf2aas.preprocessor import Preprocessor

logger = logging.getLogger(__name__)


class PDFPlumberTable(Preprocessor):
    """Extract tables from PDF files using pdfplumber library.

    Args:
        output_format (Literal['html', 'markdown', 'json', 'csv']): The format
            in which the extracted tables should be output. Default is 'html'.

    Note:
        - Not so good extraction quality based on camelot benchmark:
        https://github.com/camelot-dev/camelot/wiki/Comparison-with-other-PDF-Table-Extraction-libraries-and-tools
        - Does not require Ghostscript (camelot) or Java (tabula). It relies on PyPDF2 for
          PDF parsing and pandas for handling extracted data.

    """

    def __init__(
        self,
        output_format: Literal["html", "markdown", "json", "csv"] = "html",
    ) -> None:
        """Initialize preprocessor with html format."""
        self.output_format = output_format

    def convert(self, filepath: str) -> list[str] | str | None:
        """Convert the content of a PDF file into a list of tables as strings.

        Each string represents a table from the pdf in the desired `output_format`
        (default html). If an error occurs during the reading of the PDF file,
        it logs the error and returns None.
        """
        logger.debug("Extracting tables from PDF: %s", filepath)
        try:
            pdf = pdfplumber.open(filepath)
        except FileNotFoundError:
            logger.exception("File not found: %s", filepath)
            return None

        result = []
        with pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    dataframe = pd.DataFrame(table[1:], columns=table[0])
                    match self.output_format:
                        case "html":
                            result.append(dataframe.to_html(index=False))
                        case "json":
                            result.append(dataframe.to_json(orient="records"))
                        case "csv":
                            result.append(dataframe.to_csv(index=False))
                        case "markdown":
                            result.append(dataframe.to_markdown(index=False))
        return result
