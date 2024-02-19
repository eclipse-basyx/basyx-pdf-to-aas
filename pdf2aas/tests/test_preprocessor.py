from preprocessor import DummyPDF2HTML, PDF2HTMLEX

def test_dummy_pdf_2_html_convert():
    p = DummyPDF2HTML()
    assert p.convert([]) == "html"

def test_pdf2htmlEX_convert():
    p = PDF2HTMLEX()
    html_converted = p.convert("tests/assets/dummy-test-datasheet.pdf")
    with open('tests/assets/dummy-test-datasheet.html') as html_file:
        html_expected = html_file.read()
        assert(html_converted == html_expected)