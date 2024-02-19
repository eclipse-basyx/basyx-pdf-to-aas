from preprocessor.core import Preprocessor
from pathlib import Path
import subprocess
from enum import IntEnum
import re
import os.path
import shutil

class ReductionLevel(IntEnum):
    NONE=0 # No Reduction
    BODY=1 # Complete html body
    PAGES=2 # Complete html elements representing pages
    DIVS=3 # Span elements removed 
    STRUCTURE=4 # Div elements without classes
    TEXT=5 # Only return Text

class PDF2HTMLEX(Preprocessor):
    temp_dir = "temp/html"
    reduction_level: ReductionLevel = ReductionLevel.NONE

    #TODO add possibility to specify pages
    def convert(self, filepath: str) -> list[str] | str | None:
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
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)