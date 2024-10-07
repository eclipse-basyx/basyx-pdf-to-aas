"""Core class with default toolchain for the PDF to AAS conversion."""
import logging
from .preprocessor import Preprocessor, PDFium
from .dictionary import Dictionary, ECLASS
from .extractor import Extractor, PropertyLLMSearch
from .generator import Generator, AASSubmodelTechnicalData

logger = logging.getLogger(__name__)

class PDF2AAS:
    """Convert PDF documents into Asset Administration Shell (AAS) submodels.

    Attributes:
        preprocessor (Preprocessor): A preprocessing object to handle PDF files.
            Defaults to PDFium.
        dictionary (Dictionary): A dictionary object for term mapping.
            Defaults to ECLASS in current release.
        extractor (Extractor): An extractor object to pull relevant information
            from the preprocessed PDF. Defaults to PropertyLLMSearch with 
            current openai model.
        generator (Generator): A generator object to create AAS submodels.
            Defaults to AASSubmodelTechnicalData.
        batch_size (int): The number of properties that are extracted in one
            batch. 0 (default) extracts all properties in one. 1 extracts each 
            property on its own.

    """

    def __init__(
        self,
        preprocessor: Preprocessor = None,
        dictionary: Dictionary = None,
        extractor: Extractor = None,
        generator: Generator = None,
        batch_size: int = 0
    ) -> None:
        """Initialize the PDF2AAS toolchain with optional custom components.

        Args:
            preprocessor (Preprocessor, optional): A preprocessing object to handle PDF files. Defaults to PDFium.
            dictionary (Dictionary, optional): A dictionary object for term mapping. Defaults to ECLASS.
            extractor (Extractor, optional): An extractor object to pull relevant information from the preprocessed PDF. Defaults to PropertyLLMSearch with the current openai model.
            generator (Generator, optional): A generator object to create AAS submodels. Defaults to AASSubmodelTechnicalData.
            batch_size (int, optional): The number of properties that are extracted in one batch. 0 (default) extracts all properties in one. 1 extracts each property on its own.

        """
        self.preprocessor = PDFium() if preprocessor is None else preprocessor
        self.dictionary = ECLASS() if dictionary is None else dictionary
        self.extractor = PropertyLLMSearch("gpt-4o-mini") if extractor is None else extractor
        self.generator = AASSubmodelTechnicalData() if generator is None else generator
        self.batch_size = batch_size

    def convert(
            self,
            pdf_filepath: str,
            classification: str,
            output_filepath: str = None
    ) -> None:
        """Convert a PDF document into an AAS submodel.

        Uses the configured preprocessor, dictionary, extractor to
        extract or search for the given properties of the `classification`. 
        Dumps the result using the configured generator to the given 
        'output_filepath' if provided.

        Args:
            pdf_filepath (str): The file path to the input PDF document.
            classification (str): The classification term for mapping properties, e.g. "27274001" when using ECLASS.
            output_filepath (str, optional): The file path to save the generated AAS submodel or configured generator output.

        """
        preprocessed_datasheet = self.preprocessor.convert(pdf_filepath)
        
        property_definitions = self.dictionary.get_class_properties(classification)
              
        if self.batch_size <= 0:
            properties = self.extractor.extract(preprocessed_datasheet, property_definitions)
        elif self.batch_size == 1:
            properties = [self.extractor.extract(preprocessed_datasheet, d) for d in property_definitions]
        else:
            properties = [] 
            for i in range(0, len(property_definitions), self.batch_size):
                properties.extend(self.extractor.extract(preprocessed_datasheet, property_definitions[i:i + self.batch_size]))
        
        self.generator.reset()
        if isinstance(self.generator, AASSubmodelTechnicalData):
            self.generator.add_classification(self.dictionary, classification)
        self.generator.add_properties(properties)
        if output_filepath is not None:
            self.generator.dump(filepath=output_filepath)
            logger.info(f"Generated result in: {output_filepath}")
