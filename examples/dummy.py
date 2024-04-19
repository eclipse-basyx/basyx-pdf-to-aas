from pdf2aas.dictionary import DummyDictionary
from pdf2aas.extractor import DummyPropertyLLM
from pdf2aas.generator import DummyTechnicalDataSubmodel
from pdf2aas.preprocessor import DummyPDF2HTML

def main():
    preprocessor = DummyPDF2HTML()
    preprocessed_datasheet = preprocessor.convert("file.pdf")

    dictionary = DummyDictionary()
    property_definitions = dictionary.get_class_properties("EC002714")

    extractor = DummyPropertyLLM()
    properties = []
    for property_definition in property_definitions:
        properties.append(extractor.extract(preprocessed_datasheet, property_definition))

    generator = DummyTechnicalDataSubmodel()
    result = generator.generate(properties)

    print(result)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='This is just a dummy example to illustrate the toolchain sequence in code.')
    args = parser.parse_args()

    main()