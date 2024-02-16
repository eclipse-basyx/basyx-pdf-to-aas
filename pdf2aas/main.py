from preprocessor import DummyPDF2HTML
from extractor import DummyPropertyLLM
from generator import DummyTechnicalDataSubmodel
from dictionary import DummyDictionary


def main():
    preprocessor = DummyPDF2HTML()
    preprocessed_datasheet = preprocessor.convert("file.pdf")

    dictionary = DummyDictionary()
    property_definitions = dictionary.getClassProperties("EC002714")

    extractor = DummyPropertyLLM()
    properties = []
    for property_definition in property_definitions:
        properties.append(extractor.extract(preprocessed_datasheet, property_definition))

    generator = DummyTechnicalDataSubmodel()
    result = generator.generate(result)

    print(result)
