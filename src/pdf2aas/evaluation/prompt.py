"""Classes to represent prompt results for their evaluation."""

from typing import ClassVar


class EvaluationPrompt:
    """Represent statistics of a single prompt."""

    token_prices: ClassVar[dict[str, tuple[float, float]]] = {
        "gpt-3.5-turbo-0125": (0.5, 1.5),
        "gpt-3.5-turbo-instruct": (1.5, 2.0),
        "gpt-4o": (5, 15),
        "gpt-4-turbo": (10, 30),
        "gpt-4o-mini": (0.15, 0.6),
        "gpt-4o-mini-2024-07-18": (0.15, 0.6),
    }

    def __init__(
        self,
        input_token: int = 0,
        output_token: int = 0,
        model: str | None = None,
    ) -> None:
        """Initialize Evaluation prompt with zero values."""
        self.input_tokens: int = input_token
        self.output_tokens: int = output_token
        self.model: str | None = model

    @staticmethod
    def from_raw_results(raw_results: list) -> list["EvaluationPrompt"]:
        """Construct an EvaluationPrompt from list of OpenAI API results."""
        prompts: list = []
        if not isinstance(raw_results, list) or len(raw_results) == 0:
            return prompts
        for result in raw_results:
            if not isinstance(result, dict):
                continue
            prompts.append(
                EvaluationPrompt(
                    result.get("usage", {}).get("prompt_tokens", 0),
                    result.get("usage", {}).get("completion_tokens", 0),
                    result.get("model"),
                ),
            )
        return prompts

    def calc_costs(self) -> float:
        """Calculate the total cost of the processed input and output tokens."""
        if self.model is None or self.model not in self.token_prices:
            return 0.0
        return (
            (self.input_tokens * self.token_prices[self.model][0])
            + (self.output_tokens * self.token_prices[self.model][1])
        ) * 1e-6

    @staticmethod
    def summarize(costs: list["EvaluationPrompt"]) -> str:
        """Return a summary string for the total tokens and costs."""
        if len(costs) == 0:
            return ""
        models = set()
        input_tokens = 0
        output_tokens = 0
        costs_sum: float = 0
        for cost in costs:
            models.add(cost.model)
            input_tokens += cost.input_tokens
            output_tokens += cost.output_tokens
            costs_sum += cost.calc_costs()
        return f"models: {list(set(models))}\nprompts: {len(costs):3d}\ntokens: {input_tokens:,d} -> {output_tokens:,d}\ncosts: {costs_sum:.4f} $"  # noqa: E501
