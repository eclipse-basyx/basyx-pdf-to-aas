import json
import logging

from dotenv import load_dotenv

from pdf2aas.dictionary import ECLASS, dictionary_serializer
from pdf2aas.extractor import PropertyLLMOpenAI
from pdf2aas.generator import CSV
from pdf2aas.preprocessor import PDFium

logger = logging.getLogger(__name__)

# Load the .env file with openai API Key
load_dotenv()

def main(datasheet, eclass_class_id, property_range, dummy_extractor):
    preprocessor = PDFium()
    preprocessed_datasheet = preprocessor.convert(datasheet)
    with open("temp/preprocessed_datasheet.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(preprocessed_datasheet))

    dictionary = ECLASS()
    dictionary.load_from_file()
    property_definitions = dictionary.get_class_properties(eclass_class_id)
    dictionary.save_to_file()
    with open("temp/eclass-properties.json", "w") as file:
        file.write(
            json.dumps(property_definitions, indent=2, default=dictionary_serializer)
        )
    with open("temp/eclass-classes.json", "w") as file:
        file.write(
            json.dumps(dictionary.classes, indent=2, default=dictionary_serializer)
        )

    if dummy_extractor:
        from pdf2aas.extractor import DummyPropertyLLM
        extractor = DummyPropertyLLM()
    else:
        extractor = PropertyLLMOpenAI("gpt-3.5-turbo")
        # extractor = PropertyLLMOpenAI('llama2', 'http://localhost:11434/v1/')
    properties = []
    for property_definition in property_definitions[property_range[0]:property_range[1]]:
        properties.append(
            extractor.extract(preprocessed_datasheet, property_definition)
        )
    logger.info(f"Extracted properties: {properties}")
    with open("temp/properties.json", "w") as file:
        file.write(json.dumps(properties, indent=2))

    generator = CSV()
    csv = generator.generate(properties)
    with open("temp/properties.csv", "w") as file:
        file.write(csv)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Example for toolchain pdfium + eclass --> openaiGPT3 --> csv')
    parser.add_argument('--datasheet', type=str, help="Path to datasheet", default="tests/assets/dummy-test-datasheet.pdf")
    parser.add_argument('--eclass', type=str, help="ECLASS class id, e.g. 27274001", default="27274001")
    parser.add_argument('--range', type=int, nargs=2, help="Lower and upper range of properties to be send to the extractor. E.g. 0 1 extracts the first property only", default=[0, 1])
    parser.add_argument('--dummy_extractor', action="store_true", help="Use the dummy extractor instead of openaiGPT3")
    parser.add_argument('--debug', action="store_true", help="Print debug information.")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    logger = logging.getLogger()
    
    main(datasheet=args.datasheet, eclass_class_id=args.eclass, property_range=args.range, dummy_extractor=args.dummy_extractor)
