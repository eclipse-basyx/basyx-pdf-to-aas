"""Core class with default toolchain for the PDF to AAS conversion."""

import logging

from .dictionary import ECLASS, Dictionary
from .extractor import Extractor, PropertyLLMSearch
from .generator import AASSubmodelTechnicalData, AASTemplate, Generator
from .model import Property, PropertyDefinition
from .preprocessor import PDFium, Preprocessor, Text

logger = logging.getLogger(__name__)


class PDF2AAS:
    """Convert PDF documents into Asset Administration Shell (AAS) submodels.

    Attributes:
        preprocessor (Preprocessor, list[Preprocessor], optional):
            A preprocessing object to handle input files. Defaults to PDFium
            for files with pdf extension and Text for other files.
            If a list is given, the preprocessed datasheet is
            passed through each preprocessor in the list.
        dictionary (Dictionary): A dictionary object defining properties to
            search for.Defaults to ECLASS. Alternatively this can be an AAS
            (Template).
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
        preprocessor: Preprocessor | list[Preprocessor] = None,
        dictionary: Dictionary | AASTemplate = None,
        extractor: Extractor = None,
        generator: Generator = None,
        batch_size: int = 0,
    ) -> None:
        """Initialize the PDF2AAS toolchain with optional custom components.

        Args:
            preprocessor (Preprocessor, list[Preprocessor], optional):
                A preprocessing object to handle input files. Defaults to PDFium
                for files with pdf extension and Text for other files.
                If a list is given, the preprocessed datasheet is
                passed through each preprocessor in the list.
            dictionary (Dictionary, AASTemplate, optional): A dictionary object
                defining properties to search for. Defaults to ECLASS.
                Alternatively this can be an AAS (Template).
            extractor (Extractor, optional): An extractor object to pull
                relevant information from the preprocessed PDF. Defaults to
                PropertyLLMSearch with the current openai model.
            generator (Generator, optional): A generator object to create AAS
                submodels. Defaults to AASSubmodelTechnicalData.
            batch_size (int, optional): The number of properties that are
                extracted in one batch. 0 (default) extracts all properties
                in one. 1 extracts each property on its own.

        """
        self.preprocessor = preprocessor
        self.dictionary = ECLASS() if dictionary is None else dictionary
        self.extractor = PropertyLLMSearch("gpt-4o-mini") if extractor is None else extractor
        self.generator = AASSubmodelTechnicalData() if generator is None else generator
        self.batch_size = batch_size

    def convert(
        self,
        pdf_filepath: str,
        classification: str | None = None,
        output_filepath: str | None = None,
    ) -> list[Property]:
        """Convert a PDF document into an AAS submodel.

        Uses the configured preprocessor, dictionary and extractor to
        extract or search for the given properties of the `classification`.
        Dumps the result using the configured generator to the given
        'output_filepath' if provided.

        Args:
            pdf_filepath (str): The file path to the input document. Can also
                be another format, if the corresponding preprocessor (chain) is
                configured.
            classification (str, optional): The classification id for mapping
                properties, e.g. "27274001" when using ECLASS.
            output_filepath (str, optional): The file path to save the generated
                AAS submodel or configured generator output.

        Returns:
            properties (list[Property]): the extracted properties. The formated
                results can be obtained from the generator object, e.g. via
                `generator.dump` or by specifying `output_filepath`.

        """
        text = self.preprocess(pdf_filepath)
        definitions = self.definitions(classification)
        properties = self.extract(text, definitions)
        self.generate(classification, properties, output_filepath)
        return properties

    def preprocess(self, filepath: str) -> list[str] | str:
        """Preprocess the document at the filepath using the configured preprocessors.

        Opens .pdf / .PDF documents with PDFium and other files with Text preprocessor,
        if preprocessor is None.
        """
        if self.preprocessor is None:
            preprocessors = [PDFium()] if filepath.lower().endswith(".pdf") else [Text()]
        elif isinstance(self.preprocessor, Preprocessor):
            preprocessors = [self.preprocessor]
        preprocessed_datasheet = filepath
        for preprocessor in preprocessors:
            preprocessed_datasheet = preprocessor.convert(preprocessed_datasheet)
        return preprocessed_datasheet

    def definitions(self, classification: str | None = None) -> list[PropertyDefinition]:
        """Get the definitions from the configured dictionary or aas template."""
        if isinstance(self.dictionary, AASTemplate):
            return self.dictionary.get_property_definitions()
        if self.dictionary is not None and classification is not None:
            return self.dictionary.get_class_properties(classification)
        return []

    def extract(
        self, text: list[str] | str, definitions: list[PropertyDefinition],
        raw_prompts: list | None = None,
        raw_results: list | None = None,
    ) -> list[Property]:
        """Extract the defined properties from the text using the configured extractor."""
        if self.batch_size <= 0:
            properties = self.extractor.extract(text, definitions, raw_prompts, raw_results)
        elif self.batch_size == 1:
            properties = [
                self.extractor.extract(text, d, raw_prompts, raw_results) for d in definitions
            ]
        else:
            properties = []
            for i in range(0, len(definitions), self.batch_size):
                properties.extend(
                    self.extractor.extract(
                        text,
                        definitions[i : i + self.batch_size],
                        raw_prompts,
                        raw_results,
                    ),
                )
        return properties

    def generate(
        self,
        classification: str | None,
        properties: list[Property],
        filepath: str | None,
    ) -> None:
        """Export properties using the given generator."""
        if self.generator is None:
            return

        self.generator.reset()
        if classification and isinstance(self.generator, AASSubmodelTechnicalData):
            self.generator.add_classification(self.dictionary, classification)
        self.generator.add_properties(properties)
        if filepath is not None:
            self.generator.dump(filepath)
            logger.info("Generated result in: %s", filepath)
