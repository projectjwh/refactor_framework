"""Refactored module with reduced complexity."""

from dataclasses import dataclass, field


@dataclass
class ProcessorConfig:
    """Configuration for data processing."""

    mode: str = "transform"
    threshold: int = 10
    flag: bool = False


@dataclass
class ProcessResult:
    """Result of data processing."""

    output: list = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.output)

    @property
    def positive_count(self) -> int:
        return sum(1 for r in self.output if _is_positive(r))

    @property
    def ratio(self) -> float:
        return self.positive_count / self.total if self.total > 0 else 0.0


def _is_positive(value) -> bool:
    """Check if a value is positive (bool True or numeric > 0)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return False


def transform(item, config: ProcessorConfig):
    """Apply transformation logic."""
    if config.flag and item > config.threshold:
        return float(item) * 2 if not isinstance(item, int) else item * 2
    if config.flag:
        return item
    return item + 1 if item > 0 else 0


def filter_item(item, config: ProcessorConfig) -> tuple[bool, None]:
    """Filter logic — returns (keep, value) tuple."""
    if config.flag:
        return item >= config.threshold, item
    return item >= 0, item


def validate(item) -> tuple[bool, str | None]:
    """Validate a single item. Returns (valid, error_message)."""
    if not isinstance(item, (int, float)):
        return False, f"Not numeric: {item}"
    if item < 0:
        return False, f"Negative: {item}"
    if item > 1000:
        return False, f"Too large: {item}"
    return True, None


_PROCESSORS = {
    "transform": lambda item, cfg: (True, transform(item, cfg)),
    "filter": lambda item, cfg: filter_item(item, cfg),
    "validate": lambda item, cfg: validate(item),
}


def process_data(data: list, config: ProcessorConfig) -> ProcessResult:
    """Process data using the configured mode."""
    result = ProcessResult()
    processor = _PROCESSORS.get(config.mode)

    for item in data:
        if processor:
            keep, value = processor(item, config)
            if keep:
                result.output.append(value)
            if isinstance(value, str):
                result.errors.append(value)
        else:
            result.output.append(item)

    return result
