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

def main(datasheet, eclass_class_id, property_range, model, endpoint, batch_mode):
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

    extractor = PropertyLLMOpenAI(model, endpoint, property_keys_in_prompt=['unit'])
    
    if batch_mode:
        properties = extractor.extract(preprocessed_datasheet, property_definitions[property_range[0]:property_range[1]])
    else:
        properties = []
        for property_definition in property_definitions[property_range[0]:property_range[1]]:
            properties.extend(
                extractor.extract(preprocessed_datasheet, property_definition)
            )
    with open("temp/properties.json", "w") as file:
        file.write(json.dumps(properties, indent=2))
        logger.info("Extracted properties written to: temp/properties.json")

    generator = CSV()
    generator.add_properties(properties)
    generator.dump(filepath="temp/properties.csv")
    logger.info("Generated csv written to: temp/properties.csv")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Example for toolchain pdfium + eclass --> LLM --> csv')
    parser.add_argument('--datasheet', type=str, help="Path to datasheet", default="tests/assets/dummy-test-datasheet.pdf")
    parser.add_argument('--eclass', type=str, help="ECLASS class id, e.g. 27274001", default="27274001")
    parser.add_argument('--range', type=int, nargs=2, help="Lower and upper range of properties to be send to the extractor. E.g. 0 1 extracts the first property only", default=[0, 1])
    parser.add_argument('--model', type=str, help="Model for the llm extractor, e.g. gpt-4o-mini.", default='gpt-4o-mini')
    parser.add_argument('--endpoint', type=str, help="Endpoint, if a local endpoint should be used for the LLM extractor or 'input' for dryrun with console input")
    parser.add_argument('--batch_mode', action="store_true", help="Create a single prompt for all properties per datasheet.")
    parser.add_argument('--debug', action="store_true", help="Print debug information.")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    logger = logging.getLogger()
    
    main(datasheet=args.datasheet, eclass_class_id=args.eclass, property_range=args.range, model=args.model, endpoint=args.endpoint, batch_mode=args.batch_mode)
