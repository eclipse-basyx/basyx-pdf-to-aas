from preprocessor import PDF2HTMLEX, ReductionLevel
from dictionary import ECLASS
from extractor import PropertyLLMOpenAI
from generator import CSV

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDF2AAS:
    def __init__(self, preprocessor = PDF2HTMLEX(ReductionLevel.STRUCTURE), dictionary = ECLASS(), extractor = PropertyLLMOpenAI('gpt-3.5-turbo'), generator = CSV()) -> None:
        self.preprocessor = preprocessor
        self.dictionary = dictionary
        self.extractor = extractor
        self.generator = generator

    def convert(self, pdf_filepath: str, classification: str) -> str:
        logger.info(f"Start conversion of class {classification} from pdf: {pdf_filepath}")
        preprocessed_datasheet = self.preprocessor.convert(pdf_filepath)
        property_definitions = self.dictionary.get_class_properties(classification)
        properties = []
        for property_definition in property_definitions:
            properties.append(self.extractor.extract(preprocessed_datasheet, property_definition))
        generator = CSV()
        csv = generator.generate(properties)
        return csv
