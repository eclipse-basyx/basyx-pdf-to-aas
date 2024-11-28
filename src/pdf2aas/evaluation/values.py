"""Classes to handle expected and extracted property values."""
from dataclasses import dataclass, field


@dataclass
class EvaluationValues:
    """A collection of values, expected values and their calculated difference.

    Attributes:
        extracted (List): The values that were extracted.
        expected (list): The values as used for comparision (e.g. casted).
        difference (list): list of calculated differences between extracted and expected values.
        similar(list): list of bool decisions, wheter the value was considered similar.
        article(list): list of the corresponding article names as back reference.
        unit(list): The extracted unit of measure.
        submodel(list): The original value as defined in the submodel.

    """

    extracted: list = field(default_factory=list)
    expected: list = field(default_factory=list)
    difference: list[float] = field(default_factory=list)
    similar: list[bool] = field(default_factory=list)
    articles: list[str] = field(default_factory=list)
    unit: list[str] = field(default_factory=list)
    submodel: list = field(default_factory=list)
