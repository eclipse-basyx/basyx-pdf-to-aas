from preprocessor import DummyPDF2HTML

def test_dummy_pdf_2_html_convert():
    p = DummyPDF2HTML()
    assert p.convert([]) == "html"
