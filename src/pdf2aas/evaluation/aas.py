"""Classes for the evaluation of pdf2aas conversion using Asset Administration Shells as input."""

import datetime
import json
import logging
import re
import shutil
from pathlib import Path

import matplotlib.pyplot as plt

from pdf2aas import PDF2AAS
from pdf2aas.generator import AASTemplate

from .article import EvaluationArticle
from .core import Evaluation
from .prompt import EvaluationPrompt

logger = logging.getLogger(__name__)


class EvaluationAAS(Evaluation):
    r"""Class to evaluate the pdfd2aas conversion using Asset Administration Shells (AAS).

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
        datasheet_cutoff_pattern (str | re.Pattern, optional): regex pattern that is used to
            cut off the datasheet text, if given.
        datasheet_eclass_pattern (str | re.Pattern, optional): regex pattern with two groups to
            search the datasheet for an ECLASS class. First group needs to find the release,
            second group needs to find the class. Example:
            `re.compile(r"eCl@ss ([\d.]+) (\d{2}-\d{2}-\d{2}-\d{2})")`
        datasheet_eclass_pattern (str | re.Pattern, optional): regex pattern with two groups to
            search the datasheet for an ETIM class. First group needs to find the release,
            second group needs to find the class. Example:
            `re.compile(r"ETIM ([\d.]+) (EC\d{6})")`

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
    datasheet_cutoff_pattern: str | re.Pattern | None = None
    datasheet_eclass_pattern: str | re.Pattern | None = None
    datasheet_etim_pattern: str | re.Pattern | None = None

    def __init__(
        self,
        submodel_id: str | None = None,
        property_selection: list[str] | None = None,
        property_parent: str | None = None,
        eval_path: str | None = None,
    ) -> None:
        """Initialize the Evaluation with default converter and values.

        Arguments:
            submodel_id (str, optional): id short for the submodel defining the
                properties to be extracted and evaluated. If None, all submodels in
                the aasx package are considered.
            property_selection (list[str], optional): List of property names to be
                included in the evaluation. If None, all properties are considered.
                Defaults to None.
            property_parent (str, optional): Alternative to `property_selection`.
                Define the id_short of the submodel element collection under which the evaluation
                properties fall. If None, no parent is filtered. Defaults to None.
            eval_path (str, optional): Path to save the evaluation output.
                No output is dumped to file, if set to None.

        """
        super().__init__()
        self.aas_template = AASTemplate()
        self.converter = PDF2AAS(
            dictionary=self.aas_template,
        )
        self.converter.generator = None
        if submodel_id is not None:
            self.aas_template.submodel_filter = lambda s: s.id_short == submodel_id
        if property_selection is not None and len(property_selection) > 0:
            self.aas_template.submodel_element_filter = lambda e: e.id_short in property_selection
        elif property_parent is not None:
            def _submodel_element_has_parent(element) -> bool:  # noqa: ANN001
                while element.parent is not None:
                    element = element.parent
                    if element.id_short == property_parent:
                        return True
                return False
            self.aas_template.submodel_element_filter = _submodel_element_has_parent
        self.eval_path = Path(eval_path) if eval_path else None

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

    def _fill_datasheet_path(self, article: EvaluationArticle) -> str | None:
        aasx_datasheet_name = self.aas_template.search_datasheet(
            language=self.language,
            submodel_id_short=self.datasheet_submodel,
            classification=self.datasheet_classification,
        )
        if aasx_datasheet_name is None:
            return None
        datasheet_path = Path(article.aasx_path).parent / Path(aasx_datasheet_name).name
        self.aas_template.file_store.write_file(aasx_datasheet_name, datasheet_path.open("wb"))
        logger.info(
            "Export datasheet for article '%s' from aasx to: %s",
            article.name,
            datasheet_path,
        )
        return str(datasheet_path)

    def _fill_definitions(self, article: EvaluationArticle) -> None:
        for definition in self.aas_template.get_property_definitions(
            overwrite_dataspec=self.overwrite_dataspec,
        ):
            property_ = self.aas_template.get_property(definition.id)
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

    def _fill_class_ids(self, article: EvaluationArticle) -> None:
        if len(article.class_ids) == 0:
            eclass_ids = []
            etim_ids = []
            if self.datasheet_eclass_pattern:
                eclass_ids.extend(
                    re.findall(self.datasheet_eclass_pattern, article.datasheet_text),
                )
            if self.datasheet_etim_pattern:
                etim_ids.extend(re.findall(self.datasheet_etim_pattern, article.datasheet_text))
            article.class_ids = {
                "ECLASS": {eclass[0]: eclass[1] for eclass in eclass_ids},
                "ETIM": {etim[0]: etim[1] for etim in etim_ids},
            }

    def add_article(self, article: EvaluationArticle) -> None:
        """Add an article to the evlaluation.

        Try get the datasheet and property definitions from the aasx file,
        if none is set.
        Preprocess the datasheet using configured preprocessor and
        `datasheet_cutoff_heading` setting.
        """
        self.aas_template.aasx_path = article.aasx_path

        if article.datasheet_path is None:
            article.datasheet_path = self._fill_datasheet_path(article)
        if article.datasheet_path is None:
            logger.error("No datasheet found for article %s.", article.name)
            return

        if article.datasheet_text is None:
            datasheet = self.converter.preprocess(article.datasheet_path)
            article.datasheet_text = self._cut_datasheet(datasheet)
        if article.datasheet_text is None or len(article.datasheet_text) == 0:
            logger.error("Preprocessed datasheet is empty. Source: %s", article.datasheet_path)
            return

        self._fill_class_ids(article)

        self._fill_definitions(article)
        self.articles.append(article)

    def run_extraction(self) -> Path | None:
        """Extract defined properties for all added articles and evaluate.

        Returns:
            run_path(Path | None): the output path, where results and some
                intermediate files were stored, if `eval_path` is configured.

        """
        run_path = None
        if self.eval_path:
            run_path = self.eval_path / datetime.datetime.now(tz=datetime.UTC).strftime(
                "%Y-%m-%d_%H-%M-%S",
            )
            run_path.mkdir(parents=True, exist_ok=True)

        for idx, article in enumerate(self.articles):
            logger.info("[%i] Processing %s", idx, article.name)
            raw_results = []
            raw_prompts = []
            properties = self.converter.extract(
                article.datasheet_text,
                article.definitions,
                raw_prompts=raw_prompts,
                raw_results=raw_results,
            )

            self.extracted_properties[article.name] = properties
            self.prompts.extend(EvaluationPrompt.from_raw_results(raw_results))
            if run_path:
                try:
                    article_path = run_path / article.name
                    article_path.mkdir(exist_ok=True)
                    shutil.copy(article.datasheet_path, article_path)
                    shutil.copy(article.aasx_path, article_path)
                    (article_path / "datasheet.txt").write_text(
                        article.datasheet_text,
                        encoding="utf-8",
                    )
                    (article_path / "raw_prompts.json").write_text(json.dumps(raw_prompts))
                    (article_path / "raw_results.json").write_text(json.dumps(raw_results))
                except (
                    FileNotFoundError,
                    PermissionError,
                    IsADirectoryError,
                    OSError,
                    TypeError,
                    UnicodeEncodeError,
                ):
                    logger.exception("Couldn't save raw results for article %s.", article.name)

        self.evaluate()
        logger.info(self.summary())
        self.plot_extraction_property_frequency()
        if run_path:
            self.export_excel(
                run_path / "results.xlsx",
                sheets=["extracted", "definitions"],
            )
            plt.tight_layout()
            plt.savefig(run_path / "extraction_property_frequency.pdf")
        return run_path

    def _cut_datasheet(self, datasheet: list[str] | str) -> str:
        if isinstance(datasheet, list):
            datasheet = "\n".join(datasheet)
        if self.datasheet_cutoff_pattern is None:
            return datasheet

        split_match = re.search(self.datasheet_cutoff_pattern, datasheet)
        if split_match is None:
            return datasheet
        logger.debug(
            "Cliping datasheet after '%s' (char %i)",
            split_match.group(),
            split_match.start(),
        )
        return datasheet[: split_match.start()]
