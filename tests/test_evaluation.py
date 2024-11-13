import re
import pytest

from  pdf2aas.evaluation import EvaluationAAS, EvaluationArticle

class TestEvaluation:
    ...
    # TODO test comparision: ignored Properties, case sensitive, ...

class TestEvaluationAAS:

    def test_add_articles(self):
        evaluation = EvaluationAAS()
        evaluation.add_articles(
            aasx_list=["tests/assets/dummy-result-aas-template.aasx"],
            datasheet_list=["tests/assets/dummy-test-datasheet.pdf"]
        )
        assert len(evaluation.articles) == 1
        assert evaluation.articles[0].name == "dummy-result-aas-template"

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
        self,
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

    def test_fill_eclass_etim_ids(self):
        evaluation = EvaluationAAS()
        evaluation.datasheet_eclass_pattern = r"ECLASS *([\d.]+): *(\d{2}-\d{2}-\d{2}-\d{2})"
        evaluation.datasheet_etim_pattern = r"ETIM *([\d.]+): *(EC\d{6})"
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
    
    def test_test_cut_datasheet(self):
        evaluation = EvaluationAAS()
        evaluation.datasheet_cutoff_pattern = "# Heading 2"
        text = evaluation._cut_datasheet(["# Heading 1\ntext", "# Heading 2\ntext"])
        assert len(text) == 17
