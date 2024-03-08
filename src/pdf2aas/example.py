import json
import logging

from dotenv import load_dotenv

from .dictionary import ECLASS, dictionary_serializer
from .extractor import PropertyLLMOpenAI
from .generator import CSV
from .preprocessor import PDF2HTMLEX, ReductionLevel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Load the .env file with openai API Key
load_dotenv()


def main():
    datasheet = "tests/assets/dummy-test-datasheet.pdf"
    eclass_class_id = "27274001"

    preprocessor = PDF2HTMLEX()
    preprocessor.reduction_level = ReductionLevel.STRUCTURE
    preprocessed_datasheet = preprocessor.convert(datasheet)
    # preprocessor.clear_temp_dir()

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

    extractor = PropertyLLMOpenAI("gpt-3.5-turbo")
    # extractor = PropertyLLMOpenAI('llama2', 'http://localhost:11434/v1/')
    properties = []
    for idx, property_definition in enumerate(property_definitions):
        if idx > 5:
            break  # filter for first 5 properties
        if (
            "upplier" in property_definition.name["en"]
        ):  # filter supplier properties, as they are not inside datasheets
            logger.info(
                f"Skipping {property_definition.id}: {property_definition.name['en']}"
            )
            continue
        properties.append(
            extractor.extract(preprocessed_datasheet, property_definition)
        )
    print(properties)
    with open("temp/properties.json", "w") as file:
        file.write(json.dumps(properties, indent=2))

    generator = CSV()
    csv = generator.generate(properties)
    with open("temp/properties.csv", "w") as file:
        file.write(csv)


if __name__ == "__main__":
    main()
