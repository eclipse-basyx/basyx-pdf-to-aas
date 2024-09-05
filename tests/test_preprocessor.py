import sys
import pytest
from pdf2aas.preprocessor import PDF2HTMLEX, ReductionLevel, PDFium

@pytest.mark.skipif(sys.platform == "win32", reason="pdf2htmlEx not easily supported for windows")
class TestPDF2HTMLEX:
    preprocessor = PDF2HTMLEX()
    datasheet_prefix = "tests/assets/dummy-test-datasheet"

    def dummy_datasheet_html(self):
        with open(f"{self.datasheet_prefix}.html") as html_file:
            return html_file.read()

    def test_convert(self):
        html_converted = self.preprocessor.convert(f"{self.datasheet_prefix}.pdf")
        assert html_converted == self.dummy_datasheet_html()

    @pytest.mark.parametrize("reduction_level", [l for l in ReductionLevel])
    def test_reduce(self, reduction_level):
        html_reduced = self.preprocessor.reduce_datasheet(
            self.dummy_datasheet_html(), reduction_level
        )
        if reduction_level >= ReductionLevel.PAGES:
            assert isinstance(html_reduced, list)
            html_reduced = str.join("\n", html_reduced)
        with open(
            f"{self.datasheet_prefix}_{reduction_level.value}_{reduction_level.name}.html"
        ) as html_file:
            html_expected = html_file.read()
            assert html_reduced == html_expected

class TestPDFium:
    preprocessor = PDFium()
    datasheet_prefix = "tests/assets/dummy-test-datasheet"

    def dummy_datasheet_txt(self):
        with open(f"{self.datasheet_prefix}.txt") as txt:
            return txt.read()
    
    def test_convert(self):
        text_converted = self.preprocessor.convert(f"{self.datasheet_prefix}.pdf")
        assert "\n".join(text_converted) == self.dummy_datasheet_txt()