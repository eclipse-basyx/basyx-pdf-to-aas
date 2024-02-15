from pdf2html import SimplePDF2HTML
from property_extractor import SimplePropertyExtractor
from aas_submodel_generator import SimpleAASSubmodelGenerator


def main():
    sp2h = SimplePDF2HTML()
    result: str = sp2h.generate(54354)

    spe = SimplePropertyExtractor()
    result = spe.extract(result)

    sasg = SimpleAASSubmodelGenerator()
    result = sasg.generate(result)

    print(result)
