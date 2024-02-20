from preprocessor.core import Preprocessor
from pathlib import Path
import subprocess
from enum import IntEnum
import re
import os.path
import shutil

class ReductionLevel(IntEnum):
    """
    An enumeration to define the levels of HTML text reduction.
    
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
    """
    A preprocessor that converts PDF files to HTML using pdf2htmlEX and applies reductions to the HTML structure.
    
    Attributes:
        temp_dir (str): The directory where temporary HTML files will be stored.
        reduction_level (ReductionLevel): The default level of HTML reduction to apply after conversion.
    """
    temp_dir = "temp/html"
    reduction_level: ReductionLevel = ReductionLevel.NONE

    #TODO add possibility to specify pages
    def convert(self, filepath: str) -> list[str] | str | None:
        """
        Converts a PDF file at the given filepath to HTML text.

        Args:
            filepath (str): The file path to the PDF document to be converted.
        
        Returns:
            Union[List[str], str, None]: The whole html text as string
            or a list of strings, where each element represents a page of the pdf file if the ReductionLevel is greater or equal to PAGES
            or None if the conversion fails.
        """
        filename = Path(filepath).stem
        dest_dir = Path(self.temp_dir, filename)
        pdf2htmlEX = subprocess.run(['pdf2htmlEX',
            # '--heps', '1',
            # '--veps', '1',
            '--quiet', '0',
            '--embed-css', '0',
            '--embed-font', '0',
            '--embed-image', '0',
            '--embed-javascript', '0',
            '--embed-outline', '0',
            '--svg-embed-bitmap', '0',
            '--split-pages', '0',
            '--process-nontext', '0',
            '--process-outline', '0',
            '--printing', '0',
            '--embed-external-font', '0',
            '--optimize-text', '1',
            '--dest-dir', dest_dir,
            filepath])
        #TODO log stdout/stderr from subprocess

        if pdf2htmlEX.returncode != 0:
            print("Call to pdf2htmlEX failed:" + str(pdf2htmlEX))
            #TODO raise custom PDF2HTML error instead
            return None
        
        return self.reduce_datasheet(Path(dest_dir, filename + '.html').read_text())

    def reduce_datasheet(self, datasheet: str, level: ReductionLevel = None) -> str:
        """
        Reduces the HTML content of a datasheet according to the specified reduction level.

        Args:
            datasheet (str): The HTML content of the datasheet to be reduced.
            level (Optional[ReductionLevel]): The level of reduction to apply. If not specified, uses the instance's default level.
        
        Returns:
            str: The reduced HTML content.
        """
        if level == None:
            level = self.reduction_level
        reduced_datasheet = datasheet
        if level >= ReductionLevel.BODY:
            reduced_datasheet = re.search(r'<body>\n((?:.*\n)*.*)\n</body>', reduced_datasheet).group(1)
        if level >= ReductionLevel.PAGES:
            reduced_datasheet = re.findall(r'<div id="pf.*', reduced_datasheet)
        if level >= ReductionLevel.DIVS:
            for idx, page in enumerate(reduced_datasheet):
                reduced_datasheet[idx] = re.sub(r'<span .*?>|</span>', '', page)
        if level >= ReductionLevel.STRUCTURE:
            for idx, page in enumerate(reduced_datasheet):
                reduced_datasheet[idx] = re.sub(r'<div.*?>', '<div>', page)
        if level >= ReductionLevel.TEXT:
            for idx, page in enumerate(reduced_datasheet):
                reduced_datasheet[idx] = re.sub(r'<div.*?>|</div>', '', page)
        return reduced_datasheet
    
    def clear_temp_dir(self):
        """
        Clears the temporary directory used for storing intermediate HTML files.
        """
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)