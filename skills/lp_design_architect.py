class LPDesignArchitect:
    """Minimal local stub of the LP design skill used by tests.

    This file provides a lightweight, deterministic implementation so
    unit tests can import and exercise the skill without external
    LLM dependencies.
    """

    def __init__(self):
        self.name = "lp_design_architect"

    def run(self, product: str, audience: str) -> str:
        # Return a small human-readable evaluation summary suitable for tests.
        return (
            f"Product: {product}\n"
            f"Audience: {audience}\n"
            "Recommendation: Improve headline clarity and add a focused CTA."
        )