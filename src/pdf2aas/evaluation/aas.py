"""Classes for the evaluation of pdf2aas conversion using Asset Administration Shells as input."""

import json
import logging
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from pdf2aas import PDF2AAS
from pdf2aas.generator import AASTemplate

from .article import EvaluationArticle
from .core import Evaluation
from .prompt import EvaluationPrompt

logger = logging.getLogger(__name__)


class EvaluationAAS(Evaluation):
    """Class to evaluate the pdfd2aas conversion using Asset Administration Shells (AAS).

    Uses AASX files as property dictionary and datasheet container to compare against
    the extraction with pdf2aas library.

    Attributes:
        datasheet_submodel (str | None): Specifies the submodel containing the
            datasheet within the aas to be used for evaluation. Default is
            "HandoverDocumentation". If None, no specific submodel is targeted.
        datasheet_classification (str | None): Classification name of the datasheet,
            which can be used to categorize or identify the datasheet. Default is None.
            E.g. "Datasheet" or "Technical specification".
        overwrite_dataspec (bool): Flag indicating whether the embedded_data_specification
            should be overwriten by the property display name and description. Default is False.
            Usefull, when the embedded_data_specification of the property or it's concept
            description is less descriptive than the property display name and description.

    Inherits all attributes from the Evaluation class, including:
        - ignored_properties
        - float_tolerance
        - char_tolerance
        - case_sensitive
        - true_values
        - false_values
        - ignored_values
        - value_datasheet_regex
        - equal_str_values
        - table_header
        - definitions_table_header

    """

    datasheet_submodel: str | None = "HandoverDocumentation"
    datasheet_classification: str | None = None
    overwrite_dataspec: bool = False

    def __init__(
        self,
        submodel_id: str | None = None,
        property_selection: list[str] | None = None,
        property_parent: str | None = None,
        eval_path: str | None = None,
    ) -> None:
        """Initialize the Evaluation with default converter and values.

        Arguments:
            submodel_id (str | None, optional): id short for the submodel defining the
                properties to be extracted and evaluated. If None, all submodels in
                the aasx package are considered.
            property_selection (list[str] | None, optional): List of property names to be
                included in the evaluation. If None, all properties are considered.
                Defaults to None.
            property_parent (str | None, optional): Alternative to `property_selection`.
                Define the id_short of the submodel element collection under which the evaluation
                properties fall. If None, no parent is filtered. Defaults to None.
            eval_path (str | None, optional): Path to the evaluation output.
                If None, defaults to a "temp/eval".

        """
        super().__init__()
        self.converter = PDF2AAS(
            dictionary=AASTemplate(),
        )
        self.converter.generator = None
        if submodel_id is not None:
            self.converter.dictionary.submodel_filter = lambda s: s.id_short == submodel_id
        if property_selection is not None and len(property_selection) > 0:
            self.converter.dictionary.submodel_element_filter = (
                lambda e: e.id_short in property_selection
            )
        elif property_parent is not None:

            def _submodel_element_has_parent(element) -> bool:  # noqa: ANN001
                while element.parent is not None:
                    element = element.parent
                    if element.id_short == property_parent:
                        return True
                return False

        self.converter.dictionary.submodel_element_filter = _submodel_element_has_parent

        self.eval_path = Path(eval_path if eval_path else "temp/eval")

    def add_articles(
        self,
        aasx_list: list[str],
        datasheet_list: list[str] | None = None,
    ) -> None:
        """Turn a list of aasx files into articles and add them to the evaluation.

        Searches for datasheets in the aasx package if no datasheet_list ist given.
        The datasheet_list has to have the same size as the aasx_list or None.
        """
        if datasheet_list is not None and len(aasx_list) != len(datasheet_list):
            logger.error("Datasheet list with different length than aasx list given.")
            return

        for idx, aasx in enumerate(aasx_list):
            aasx_name = Path(aasx).stem
            article = EvaluationArticle(
                name=aasx_name,
                aasx_path=aasx,
                datasheet_path=str(datasheet_list[idx]) if datasheet_list else None,
            )
            self.add_article(article)

    def add_article(self, article: EvaluationArticle) -> None:
        """Add an article to the evlaluation.

        Will try get the datasheet and property definitions from the aasx file,
        if none is set.
        """
        aas_template: AASTemplate = self.converter.dictionary
        aas_template.aasx_path = article.aasx_path

        # Get datasheet from aasx, if not provided
        if article.datasheet_path is None:
            aasx_datasheet_name = aas_template.search_datasheet(
                language=self.language,
                submodel_id_short=self.datasheet_submodel,
                classification=self.datasheet_classification,
            )
            if aasx_datasheet_name is not None:
                datasheet_path = Path(article.aasx_path).parent / Path(aasx_datasheet_name).name
                aas_template.file_store.write_file(aasx_datasheet_name, datasheet_path.open("wb"))
                logger.info(
                    "Export datasheet for article '%s' from aasx to: %s",
                    article.name,
                    datasheet_path,
                )
                article.datasheet_path = str(datasheet_path)
            else:
                logger.error("No datasheet found for article %s.", article.name)
                return

        # Get the property definitions from the aasx using specified filters
        for definition in aas_template.get_property_definitions(
            overwrite_dataspec=self.overwrite_dataspec,
        ):
            property_ = aas_template.get_property(definition.id)
            if property_.definition_id in article.values:
                logger.warning(
                    "Article %s contains multiple properties with same definition id: %s",
                    article.name,
                    property_.definition_id,
                )
                continue
            definition.id = property_.definition_id
            article.values[definition.id] = property_.value
            article.definitions.append(definition)

        self.articles.append(article)

    def run_extraction(self) -> Path | None:
        """Extract defined properties for all added articles and evaluate."""
        run_path = self.eval_path / datetime.now(tz=datetime.timezone.utc).strftime(
            "%Y-%m-%d_%H-%M-%S",
        )
        run_path.mkdir(parents=True, exist_ok=True)

        for idx, article in enumerate(self.articles):
            logger.info("[%i] Processing %s", idx, article.name)
            datasheet_text = self.converter.preprocess(article.datasheet_path)
            raw_results = []
            raw_prompts = []
            properties = self.converter.extract(
                datasheet_text,
                article.definitions,
                raw_prompts=raw_prompts,
                raw_results=raw_results,
            )

            self.extracted_properties[article.name] = properties
            self.datasheet_texts[article.name] = str(datasheet_text)
            self.prompts.extend(EvaluationPrompt.from_raw_results(raw_results))
            Path(run_path / article.name).with_name("raw_prompts.json").write_text(
                json.dumps(raw_prompts),
            )
            Path(run_path / article.name).with_name("raw_results.json").write_text(
                json.dumps(raw_results),
            )

        self.evaluate()
        logger.info(self.summary())
        self.export_excel(
            run_path / "results.xlsx",
            sheets=["extracted", "definitions"],
        )
        self.plot_extraction_property_frequency()
        plt.tight_layout()
        plt.savefig(run_path / "extraction_property_frequency.pdf")
        return run_path
