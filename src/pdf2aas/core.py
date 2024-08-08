from .preprocessor import Preprocessor, PDFium
from .dictionary import Dictionary, ECLASS
from .extractor import PropertyLLM, PropertyLLMOpenAI
from .generator import Generator, AASSubmodelTechnicalData

class PDF2AAS:
    def __init__(
        self,
        preprocessor: Preprocessor = PDFium(),
        dictionary: Dictionary = ECLASS(),
        extractor: PropertyLLM = PropertyLLMOpenAI("gpt-4o-mini"),
        generator: Generator = AASSubmodelTechnicalData(),
        batch_size: int = 0
    ) -> None:
        self.preprocessor = preprocessor
        self.dictionary = dictionary
        self.extractor = extractor
        self.generator = generator
        self.batch_size = batch_size

    def convert(self, pdf_filepath: str, classification: str, output_filepath: str = None):
        preprocessed_datasheet = self.preprocessor.convert(pdf_filepath)
        property_definitions = self.dictionary.get_class_properties(classification)
              
        if self.batch_size <= 0:
            properties = self.extractor.extract(preprocessed_datasheet, property_definitions)
        elif self.batch_size == 1:
            properties = [self.extractor.extract(preprocessed_datasheet, d) for d in property_definitions]
        else:
            properties = [self.extractor.extract(preprocessed_datasheet, property_definitions[i:i + self.batch_size])
                          for i in range(0, len(property_definitions), self.batch_size)]
        
        if isinstance(self.generator, AASSubmodelTechnicalData):
            self.generator.dictionary = self.dictionary
            self.generator.class_id = classification
        self.generator.reset()
        self.generator.add_properties(properties)
        self.generator.dump(filepath=output_filepath)
