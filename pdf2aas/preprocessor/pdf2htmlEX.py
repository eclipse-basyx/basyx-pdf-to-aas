from core import Preprocessor
import subprocess
subprocess.call("pdf2htmlEX /path/to/foobar.pdf", shell=True)

class PDF2HTMLEX():
    def convert(self, filepath: str) -> str:
        return "html"
