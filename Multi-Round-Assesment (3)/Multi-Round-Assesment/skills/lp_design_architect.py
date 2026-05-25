class LPArchitectEvaluator:
    name = "lp_architect_evaluator"

    def run(self, landing_page_json):
        prompt = f"""
        You are a Landing Page Architect.

        Evaluate this landing page for conversion optimization.

        Check for:
        - Headline strength
        - CTA effectiveness
        - Value proposition clarity
        - Trust signals
        - Social proof quality
        - Missing sections
        - Conversion gaps

        Landing Page:
        {landing_page_json}

        Return STRICT JSON:
        {{
            "score": 0-10,
            "missing_elements": [],
            "weak_sections": [],
            "improvements": []
        }}
        """

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content