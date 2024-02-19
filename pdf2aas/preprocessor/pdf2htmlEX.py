from preprocessor.core import Preprocessor
from pathlib import Path
import subprocess

class PDF2HTMLEX(Preprocessor):
    temp_dir = "temp/html"

    def convert(self, filepath: str) -> str | None:
        filename = Path(filepath).stem
        dest_dir = Path(self.temp_dir, filename)
        pdf2htmlEX = subprocess.run(['pdf2htmlEX',
            '--embed-css', '0',
            '--embed-font', '0',
            '--embed-image', '0',
            '--embed-javascript', '0',
            '--embed-outline', '0',
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
            return None
        
        return Path(dest_dir, filename + '.html').read_text()
