import pytest
from pathlib import Path
from unittest.mock import patch

from  pdf2aas.evaluation import EvaluationAAS, EvaluationArticle

from test_generator import test_property_list2

class TestEvaluationAAS:

    @classmethod
    def setup_class(cls):
        cls.evaluation = EvaluationAAS()
        cls.evaluation.add_articles(
            aasx_list=["tests/assets/dummy-result-aas-template.aasx"],
            datasheet_list=["tests/assets/dummy-test-datasheet.pdf"]
        )
        with patch('pdf2aas.extractor.PropertyLLM.extract') as mock_extract:
            mock_extract.return_value = test_property_list2
            cls.evaluation.run_extraction()
            mock_extract.assert_called_once()
            cls.extract_args, _ = mock_extract.call_args

    def test_add_articles(self):
        assert len(self.evaluation.articles) == 1
        assert self.evaluation.articles[0].name == "dummy-result-aas-template"

    def test_run_extraction(self):
        assert self.extract_args[0] == self.evaluation.articles[0].datasheet_text
        assert self.extract_args[1] == self.evaluation.articles[0].definitions

        assert len(self.evaluation.extracted_properties) == 1
        extracted_properties = next(iter(self.evaluation.extracted_properties.values()))
        for property_ in test_property_list2:
            assert property_ in extracted_properties
        
        assert self.evaluation.counts_sum.compared == 3
        assert self.evaluation.counts_sum.correct == 3
        assert self.evaluation.counts_sum.different == 0
        assert self.evaluation.counts_sum.extra == 0
        assert self.evaluation.counts_sum.extracted == 3
        assert self.evaluation.counts_sum.ignored == 0
        assert self.evaluation.counts_sum.similar == 0
        assert self.evaluation.counts_sum.value == 3

    @staticmethod
    @pytest.mark.parametrize("submodel_id,property_parent,property_selection,expected_property_count", [
        (None, None, None, 9),
        # submodel filter
        ("TechnicalData", None, None, 9),
        ("UnknownSubmodel", None, None, 0),
        # parent filter
        (None, "GeneralInformation", None, 4),
        ("TechnicalData", "TechnicalProperties", None, 3),
        # property filter
        (None, None, [], 9),
        (None, None, ["property1"], 1),
        (None, None, ["property1", "property2"], 2),
        (None, None, ["property1", "unknownProperty"], 1),
        # property filter prescendence over parent filter
        ("TechnicalData", "GeneralInformation", ["property1"], 1),
    ])
    def test_filter_properties(
        submodel_id,
        property_parent,
        property_selection,
        expected_property_count
    ):
        evaluation = EvaluationAAS(
            submodel_id=submodel_id,
            property_selection=property_selection,
            property_parent=property_parent
        )
        evaluation.add_articles(
            aasx_list=["tests/assets/dummy-result-aas-template.aasx"],
            datasheet_list=["tests/assets/dummy-test-datasheet.pdf"]
        )
        article = evaluation.articles[0]
        assert len(article.definitions) == expected_property_count
        assert len(article.values) == expected_property_count

    @staticmethod
    def test_fill_eclass_etim_ids():
        evaluation = EvaluationAAS()
        evaluation.datasheet_class_id_pattern = {
            "ECLASS": r"ECLASS *([\d.]+): *(\d{2}-\d{2}-\d{2}-\d{2})",
            "ETIM": r"ETIM *([\d.]+): *(EC\d{6})",
        }
        article = EvaluationArticle(
                name="test_article",
                aasx_path="test.aasx",
                datasheet_path="datasheet.pdf",
                datasheet_text=\
"""
ECLASS    14.0:    27-27-40-01
ECLASS    13.0:    27-27-40-01
ETIM       9.0:    EC002714
"""
        )
        assert len(article.class_ids) == 0
        evaluation._fill_class_ids(article)
        assert len(article.class_ids) == 2
        assert article.class_ids == {
            "ECLASS": {"14.0": "27-27-40-01", "13.0": "27-27-40-01",},
            "ETIM": {"9.0": "EC002714",}
        }

    @staticmethod
    def test_test_cut_datasheet():
        evaluation = EvaluationAAS()
        evaluation.datasheet_cutoff_pattern = "# Heading 2"
        text = evaluation._cut_datasheet(["# Heading 1\ntext", "# Heading 2\ntext"])
        assert len(text) == 17
