from pdf2aas.dictionary import DummyDictionary
from pdf2aas.extractor import DummyPropertyLLM
from pdf2aas.generator import Generator
from pdf2aas.preprocessor import DummyPDF2HTML

def main():
    preprocessor = DummyPDF2HTML()
    preprocessed_datasheet = preprocessor.convert("file.pdf")

    dictionary = DummyDictionary()
    property_definitions = dictionary.get_class_properties("EC002714")

    extractor = DummyPropertyLLM()
    properties = extractor.extract(preprocessed_datasheet, property_definitions)

    generator = Generator()
    generator.add_properties(properties)
    result = generator.dumps(properties)

    print(result)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='This is just a dummy example to illustrate the toolchain sequence in code.')
    args = parser.parse_args()

    main()