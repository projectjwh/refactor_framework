"""Legacy module with intentionally high complexity for testing."""


class DataProcessor:
    """Monolithic processor with nested conditionals."""

    def __init__(self, mode, threshold=10, flag=False):
        self.mode = mode
        self.threshold = threshold
        self.flag = flag
        self.results = []
        self.errors = []

    def process(self, data):
        """Process data with deeply nested logic."""
        output = []
        for item in data:
            if self.mode == "transform":
                if self.flag:
                    if item > self.threshold:
                        if isinstance(item, int):
                            output.append(item * 2)
                        else:
                            output.append(float(item) * 2)
                    else:
                        output.append(item)
                else:
                    if item > 0:
                        output.append(item + 1)
                    else:
                        output.append(0)
            elif self.mode == "filter":
                if self.flag:
                    if item > self.threshold:
                        output.append(item)
                    elif item == self.threshold:
                        output.append(item)
                    else:
                        pass
                else:
                    if item >= 0:
                        output.append(item)
            elif self.mode == "validate":
                if isinstance(item, (int, float)):
                    if item >= 0:
                        if item <= 1000:
                            output.append(True)
                        else:
                            output.append(False)
                            self.errors.append(f"Too large: {item}")
                    else:
                        output.append(False)
                        self.errors.append(f"Negative: {item}")
                else:
                    output.append(False)
                    self.errors.append(f"Not numeric: {item}")
            else:
                output.append(item)
        self.results = output
        return output

    def get_summary(self):
        """Return processing summary."""
        total = len(self.results)
        if total == 0:
            return {"total": 0, "positive": 0, "ratio": 0.0}
        positive = 0
        for r in self.results:
            if isinstance(r, bool):
                if r:
                    positive += 1
            elif isinstance(r, (int, float)):
                if r > 0:
                    positive += 1
        return {
            "total": total,
            "positive": positive,
            "ratio": positive / total if total > 0 else 0.0,
        }
