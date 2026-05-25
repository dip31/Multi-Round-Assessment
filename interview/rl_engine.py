"""
Q-Learning engine for interview difficulty adaptation.
"""
import random
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Hyperparameters
ALPHA = 0.1  # Learning rate
GAMMA = 0.9  # Discount factor
EPSILON_START = 0.2  # Initial exploration rate
EPSILON_MIN = 0.1  # Minimum exploration rate
EPSILON_DECAY = 0.995  # Decay rate per update


class InterviewRLEngine:
    """Q-Learning engine for interview difficulty selection."""

    def __init__(self):
        """Initialize with empty Q-table and starting epsilon."""
        self.q_table: Dict = {}
        self.epsilon: float = EPSILON_START
        self.followup_count: int = 0
        self.irrelevant_count: int = 0
        self.negative_count: int = 0
        self.silence_count: int = 0
        self.asked_question_ids: List = []
        self.current_question_text: str = ""
        self.current_question_difficulty: str = "MEDIUM"
        self.current_question_id: Optional[str] = None
        self.conversation_history: List[Dict] = []

    def _state_key(self, state: Dict) -> str:
        """Convert state dict to a string key for Q-table lookup."""
        last_score = state.get("last_score", 0.5)
        turn = state.get("turn", 0)

        # Bucket score into low/mid/high
        score_bucket = (
            "low" if last_score < 0.4 else
            "high" if last_score > 0.7 else
            "mid"
        )

        # Bucket turn into groups of 3
        turn_bucket = min(turn // 3, 3)

        return f"{score_bucket}_{turn_bucket}"

    def select_difficulty(self, state: Dict) -> str:
        """Select difficulty level using epsilon-greedy exploration."""
        state_key = self._state_key(state)
        actions = ["EASY", "MEDIUM", "HARD"]

        # Epsilon-greedy
        if random.random() < self.epsilon:
            return random.choice(actions)

        # Exploit: best Q-value
        if state_key not in self.q_table:
            return random.choice(actions)

        q_values = self.q_table[state_key]
        best_action = max(
            (action for action in actions),
            key=lambda action: q_values.get(action, 0.0)
        )
        return best_action

    def update(self, state: Dict, action: str, reward: float, next_state: Dict) -> None:
        """Update Q-table using Bellman equation."""
        state_key = self._state_key(state)
        next_state_key = self._state_key(next_state)
        actions = ["EASY", "MEDIUM", "HARD"]

        # Initialize Q(s,a) if needed
        if state_key not in self.q_table:
            self.q_table[state_key] = {a: 0.0 for a in actions}

        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = {a: 0.0 for a in actions}

        current_q = self.q_table[state_key].get(action, 0.0)
        max_next_q = max(self.q_table[next_state_key].values())

        # Bellman update
        new_q = current_q + ALPHA * (reward + GAMMA * max_next_q - current_q)
        self.q_table[state_key][action] = new_q

        # Decay epsilon
        self.epsilon = max(EPSILON_MIN, self.epsilon * EPSILON_DECAY)

    def compute_reward(
        self,
        final_score: float,
        quality: str,
        intent: str,
        difficulty: str,
        content_score: float,
    ) -> float:
        """Compute reward from the deterministic formula."""
        reward = final_score

        # Quality penalties
        if quality == "IRRELEVANT":
            reward -= 0.3

        if intent == "NEGATIVE":
            reward -= 0.2

        # Difficulty adjustment
        if difficulty == "EASY" and content_score > 0.8:
            reward -= 0.2  # Too easy
        if difficulty == "HARD" and content_score < 0.3:
            reward -= 0.3  # Too hard
        if 0.4 <= content_score <= 0.8:
            reward += 0.1  # Good challenge zone

        # Clamp to valid range
        return max(-1.0, min(1.0, reward))

    def to_dict(self) -> Dict:
        """Serialize RL state to JSON-compatible dict."""
        return {
            "q_table": self.q_table,
            "epsilon": self.epsilon,
            "followup_count": self.followup_count,
            "irrelevant_count": self.irrelevant_count,
            "negative_count": self.negative_count,
            "silence_count": self.silence_count,
            "asked_question_ids": self.asked_question_ids,
            "current_question_text": self.current_question_text,
            "current_question_difficulty": self.current_question_difficulty,
            "current_question_id": self.current_question_id,
            "conversation_history": self.conversation_history,
        }

    def from_dict(self, data: Dict) -> None:
        """Deserialize RL state from dict."""
        try:
            self.q_table = data.get("q_table", {})
            self.epsilon = data.get("epsilon", EPSILON_START)
            self.followup_count = data.get("followup_count", 0)
            self.irrelevant_count = data.get("irrelevant_count", 0)
            self.negative_count = data.get("negative_count", 0)
            self.silence_count = data.get("silence_count", 0)
            self.asked_question_ids = data.get("asked_question_ids", [])
            self.current_question_text = data.get("current_question_text", "")
            self.current_question_difficulty = data.get("current_question_difficulty", "MEDIUM")
            self.current_question_id = data.get("current_question_id", None)
            self.conversation_history = data.get("conversation_history", [])
        except Exception as e:
            logger.error(f"Failed to restore RL state: {str(e)}")
            self.__init__()  # Reset to defaults
