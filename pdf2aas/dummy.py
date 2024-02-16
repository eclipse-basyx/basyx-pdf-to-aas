from preprocessor import DummyPDF2HTML
from extractor import DummyPropertyLLM
from generator import DummyTechnicalDataSubmodel
from dictionary import DummyDictionary

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
    main()