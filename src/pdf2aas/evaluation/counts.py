"""Classes to count common statistic values for an evaluation."""

from dataclasses import dataclass

import matplotlib.pyplot as plt


@dataclass
class EvaluationCounts:
    """A collection of statistics of an evaluation for extracted vs. defined properties.

    Attributes:
        extracted (int): Number of properties found and returned from the extractor.
        ignored (int): Number of properties that are in the ignore list.
        extra (int): Number of properties that were extracted but have no definition or value in
            submodel.
        value (int): Number of properties that have a value different from None.
        correct (int): Number of properties whose value is equal to the expected value.
        similar (int): Number of properties whose value is similar to the expected value within
            tolerances.
        different (int): Number of properties whose value is different from the expected value.
        compared (int): Number of properties that can be compared (extracted - ignored - exta)

    """

    extracted: int = 0
    ignored: int = 0
    extra: int = 0
    value: int = 0
    correct: int = 0
    similar: int = 0
    different: int = 0

    @property
    def compared(self) -> int:
        """Extracted values that can be compared."""
        return self.extracted - self.ignored - self.extra

    def print(self) -> str:
        """Print a summary of the evaluation counts."""
        return f"""{self.extracted:3d} properties extracted,
{self.extra:3d} / {self.extracted:3d} extra (no definition or value in submodel),
{self.ignored:3d} / {self.extracted-self.extra:3d} ignored,
{self.value:3d} / {self.compared:3d} extracted with value,
{self.correct:3d} / {self.compared:3d} have a correct value,
{self.similar:3d} / {self.compared:3d} have a similar value,
{self.different:3d} / {self.compared:3d} have a different not similar value"""

    def plot_bar_chart(self) -> plt.Figure:
        """Generate a horizontal stacked bar chart and return the figure handle."""
        categories = ["Correct", "Similar", "Different", "Ignored", "Extra"]
        counts = [self.correct, self.similar, self.different, self.ignored, self.extra]
        fig, ax = plt.subplots(figsize=(10, 2))
        left = 0
        for count, category in zip(counts, categories, strict=True):
            if count > 0:
                ax.barh(
                    ["Evaluation"],
                    [count],
                    left=left,
                    label=category,
                    color={
                        "Correct": "green",
                        "Similar": "orange",
                        "Different": "red",
                        "Ignored": "purple",
                        "Extra": "gray",
                    }[category],
                    edgecolor="black",
                )
                ax.text(
                    left + count / 2,
                    0,
                    f"{count}",
                    va="center",
                    ha="center",
                    color="white",
                    fontsize=10,
                    fontweight="bold",
                )
            left += count
        ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        ax.set_xlim(0, self.extracted)
        ax.set_title("Evaluation Counts")
        ax.set_xlabel("Count")
        ax.set_yticks([])
        plt.tight_layout()

        return fig
