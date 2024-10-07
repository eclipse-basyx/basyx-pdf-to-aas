"""Preprocessor using pdf2htmlEX library."""
import logging
import os.path
import re
import shutil
import subprocess
from enum import IntEnum
from pathlib import Path

from .core import Preprocessor

logger = logging.getLogger(__name__)


class ReductionLevel(IntEnum):
    """Level of HTML text reduction.

    Higher integer values resemble higher reduction.

    Attributes:
        NONE (0): No reduction, preserve all HTML content.
        BODY (1): Extract the complete HTML body.
        PAGES (2): Extract all HTML elements that represent pages.
        DIVS (3): Remove 'span' elements.
        STRUCTURE (4): Remove classes from 'div' elements.
        TEXT (5): Reduce to text content only, without any tags.

    """

    NONE = 0
    BODY = 1
    PAGES = 2
    DIVS = 3
    STRUCTURE = 4
    TEXT = 5


class PDF2HTMLEX(Preprocessor):
    """A preprocessor that converts PDF files to HTML using pdf2htmlEX.
     
      It additionally applies reductions to the HTML structure according to the
      configured `reduction_level`.

    Attributes:
        reduction_level (ReductionLevel): The default level of HTML reduction to apply after conversion.
        temp_dir (str): The directory where temporary HTML files will be stored.

    """

    def __init__(
            self,
            reduction_level=ReductionLevel.NONE,
            temp_dir="temp/html"
    ):
        """Initiliaze preprocessor with no reduction and 'temp/html' temp directory."""
        self.reduction_level = reduction_level
        self.temp_dir = temp_dir

    # TODO add possibility to specify pages
    def convert(self, filepath: str) -> list[str] | str | None:
        """Convert a PDF file at the given filepath to HTML text.

        Args:
            filepath (str): The file path to the PDF document to be converted.

        Returns:
            Union[List[str], str, None]: The whole html text as string
            or a list of strings, where each element represents a page of the pdf file if the ReductionLevel is greater or equal to PAGES
            or None if the conversion fails.

        """
        logger.info(f"Converting to html from pdf: {filepath}")
        filename = Path(filepath).stem
        dest_dir = Path(self.temp_dir, filename)
        try:
            pdf2htmlEX = subprocess.run(
                [
                    "pdf2htmlEX",
                    # '--heps', '1',
                    # '--veps', '1',
                    "--quiet",
                    "1",
                    "--embed-css",
                    "0",
                    "--embed-font",
                    "0",
                    "--embed-image",
                    "0",
                    "--embed-javascript",
                    "0",
                    "--embed-outline",
                    "0",
                    "--svg-embed-bitmap",
                    "0",
                    "--split-pages",
                    "0",
                    "--process-nontext",
                    "0",
                    "--process-outline",
                    "0",
                    "--printing",
                    "0",
                    "--embed-external-font",
                    "0",
                    "--optimize-text",
                    "1",
                    "--dest-dir",
                    dest_dir,
                    filepath,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            logger.error("pdf2htmlEX executable not found in path.")
            return None

        if pdf2htmlEX.stdout:
            logger.debug("pdf2htmlEX stdout:\n%s", pdf2htmlEX.stdout)
        if pdf2htmlEX.stderr:
            logger.warning("Call to pdf2htmlEX stderr:\n%s", pdf2htmlEX.stderr)

        if pdf2htmlEX.returncode != 0:
            logger.error(
                f"Call to pdf2htmlEX failed with returncode: {pdf2htmlEX.returncode}"
            )
            logger.debug(f"pdf2htmlEX arguments: {pdf2htmlEX.args}")
            # TODO raise custom PDF2HTML error instead
            return None

        return self.reduce_datasheet(Path(dest_dir, filename + ".html").read_text())

    def reduce_datasheet(self, datasheet: str, level: ReductionLevel = None) -> str:
        """Reduce the HTML content of a datasheet according to the specified reduction level.

        Args:
            datasheet (str): The HTML content of the datasheet to be reduced.
            level (Optional[ReductionLevel]): The level of reduction to apply. If not specified, uses the instance's default level.

        Returns:
            str: The reduced HTML content.

        """
        if level is None:
            level = self.reduction_level
        reduced_datasheet = datasheet
        if level >= ReductionLevel.BODY:
            logger.debug("Reducing datasheet to ReductionLevel.BODY")
            reduced_datasheet = re.search(
                r"<body>\n((?:.*\n)*.*)\n</body>", reduced_datasheet
            ).group(1)
        if level >= ReductionLevel.PAGES:
            logger.debug("Reducing datasheet to ReductionLevel.PAGES")
            reduced_datasheet = re.findall(r'<div id="pf.*', reduced_datasheet)
        if level >= ReductionLevel.DIVS:
            logger.debug("Reducing datasheet to ReductionLevel.DIVS")
            for idx, page in enumerate(reduced_datasheet):
                reduced_datasheet[idx] = re.sub(r"<span .*?>|</span>", "", page)
        if level >= ReductionLevel.STRUCTURE:
            logger.debug("Reducing datasheet to ReductionLevel.STRUCTURE")
            for idx, page in enumerate(reduced_datasheet):
                reduced_datasheet[idx] = re.sub(r"<div.*?>", "<div>", page)
        if level >= ReductionLevel.TEXT:
            logger.debug("Reducing datasheet to ReductionLevel.TEXT")
            for idx, page in enumerate(reduced_datasheet):
                reduced_datasheet[idx] = re.sub(r"<div.*?>|</div>", "", page)
        logger.info(f"Reduced datasheet to ReductionLevel {level.name}")
        logger.debug("reduced datasheet:\n" + str(reduced_datasheet))
        return reduced_datasheet

    def clear_temp_dir(self):
        """Clear the temporary directory used for storing intermediate HTML files."""
        if not os.path.isdir(self.temp_dir):
            return
        
        logger.info(f"Clearing temporary directory: {os.path.realpath(self.temp_dir)}")
        shutil.rmtree(self.temp_dir, ignore_errors=True)
