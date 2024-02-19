import pytest
from preprocessor import DummyPDF2HTML, PDF2HTMLEX, ReductionLevel

def test_dummy_pdf_2_html_convert():
    p = DummyPDF2HTML()
    assert p.convert([]) == "html"


class TestPDF2HTMLEX:
    preprocessor = PDF2HTMLEX()
    datasheet_prefix = 'tests/assets/dummy-test-datasheet'

    def dummy_datasheet_html(self):
        with open(f'{self.datasheet_prefix}.html') as html_file:
            return html_file.read()

    def test_pdf2htmlEX_convert(self):
        html_converted = self.preprocessor.convert(f'{self.datasheet_prefix}.pdf')
        assert(html_converted == self.dummy_datasheet_html())

    @pytest.mark.parametrize("reduction_level", [l for l in ReductionLevel])
    def test_pdf2htmlEX_reduce(self, reduction_level):
        html_reduced = self.preprocessor.reduce_datasheet(self.dummy_datasheet_html(), reduction_level)
        if reduction_level >= ReductionLevel.PAGES:
            assert(isinstance(html_reduced, list))
            html_reduced = str.join('\n', html_reduced)
        with open(f'{self.datasheet_prefix}_{reduction_level.value}_{reduction_level.name}.html') as html_file:
            html_expected = html_file.read()
            assert(html_reduced == html_expected)