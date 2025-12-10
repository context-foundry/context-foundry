"""
Conversation Memory System

Stores compacted conversation summaries for long-term context.
Implements recency weighting so recent conversations are "brighter".
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Memory storage location
MEMORY_DIR = Path.home() / ".context-foundry" / "memory"
MEMORY_DB = MEMORY_DIR / "conversations.db"


@dataclass
class ConversationEntry:
    """A compacted conversation memory entry."""

    id: str
    timestamp: str  # ISO format
    summary: str  # 1-3 sentence summary
    topics: List[str]  # Key topics/themes
    sentiment: str  # positive, neutral, negative, frustrated
    outcome: str  # what was accomplished or decided
    source: str  # "sidekick", "build", "cli"
    raw_exchange: Optional[str] = None  # First 500 chars of actual exchange

    def age_days(self) -> float:
        """Get age in days."""
        ts = datetime.fromisoformat(self.timestamp)
        return (datetime.now() - ts).total_seconds() / 86400

    def relevance_score(self, query_topics: List[str] = None) -> float:
        """
        Calculate relevance score (0-1) based on recency and topic match.
        Recent = brighter, Topic match = brighter.
        """
        # Recency factor: exponential decay over 30 days
        age = self.age_days()
        recency = max(0, 1 - (age / 30))  # 0-1, linear decay over 30 days

        # Topic match factor
        topic_match = 0.0
        if query_topics and self.topics:
            matches = len(
                set(t.lower() for t in self.topics)
                & set(t.lower() for t in query_topics)
            )
            topic_match = min(1.0, matches / max(1, len(query_topics)))

        # Combine: 60% recency, 40% topic match
        return 0.6 * recency + 0.4 * topic_match


class ConversationMemory:
    """Manages long-term conversation memory."""

    def __init__(self, db_path: Path = MEMORY_DB):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Create database and tables if needed."""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                summary TEXT NOT NULL,
                topics TEXT NOT NULL,  -- JSON array
                sentiment TEXT DEFAULT 'neutral',
                outcome TEXT,
                source TEXT DEFAULT 'sidekick',
                raw_exchange TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                examples TEXT  -- JSON array of conversation IDs
            )
        """)
        conn.commit()
        conn.close()

    def save_conversation(self, entry: ConversationEntry) -> None:
        """Save a conversation entry."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO conversations
            (id, timestamp, summary, topics, sentiment, outcome, source, raw_exchange)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry.id,
                entry.timestamp,
                entry.summary,
                json.dumps(entry.topics),
                entry.sentiment,
                entry.outcome,
                entry.source,
                entry.raw_exchange,
            ),
        )
        conn.commit()
        conn.close()

        # Update patterns
        self._update_patterns(entry)

    def _update_patterns(self, entry: ConversationEntry) -> None:
        """Track recurring topics/patterns."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()

        for topic in entry.topics:
            topic_lower = topic.lower()
            existing = conn.execute(
                "SELECT id, frequency, examples FROM patterns WHERE pattern = ?",
                (topic_lower,),
            ).fetchone()

            if existing:
                pattern_id, freq, examples_json = existing
                examples = json.loads(examples_json or "[]")
                examples.append(entry.id)
                examples = examples[-10:]  # Keep last 10

                conn.execute(
                    """
                    UPDATE patterns
                    SET frequency = ?, last_seen = ?, examples = ?
                    WHERE id = ?
                """,
                    (freq + 1, now, json.dumps(examples), pattern_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO patterns (pattern, frequency, first_seen, last_seen, examples)
                    VALUES (?, 1, ?, ?, ?)
                """,
                    (topic_lower, now, now, json.dumps([entry.id])),
                )

        conn.commit()
        conn.close()

    def get_recent(self, days: int = 7, limit: int = 20) -> List[ConversationEntry]:
        """Get recent conversations."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT id, timestamp, summary, topics, sentiment, outcome, source, raw_exchange
            FROM conversations
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (cutoff, limit),
        ).fetchall()
        conn.close()

        return [self._row_to_entry(r) for r in rows]

    def get_relevant(
        self, topics: List[str], limit: int = 10
    ) -> List[ConversationEntry]:
        """Get conversations relevant to given topics, weighted by recency."""
        # Get last 60 days of conversations
        cutoff = (datetime.now() - timedelta(days=60)).isoformat()

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT id, timestamp, summary, topics, sentiment, outcome, source, raw_exchange
            FROM conversations
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 100
        """,
            (cutoff,),
        ).fetchall()
        conn.close()

        entries = [self._row_to_entry(r) for r in rows]

        # Score and sort by relevance
        scored = [(e, e.relevance_score(topics)) for e in entries]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [e for e, score in scored[:limit] if score > 0.1]

    def get_patterns(self, min_frequency: int = 3) -> List[Dict[str, Any]]:
        """Get recurring patterns/topics."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT pattern, frequency, first_seen, last_seen
            FROM patterns
            WHERE frequency >= ?
            ORDER BY frequency DESC
            LIMIT 20
        """,
            (min_frequency,),
        ).fetchall()
        conn.close()

        return [
            {
                "topic": r[0],
                "occurrences": r[1],
                "first_seen": r[2],
                "last_seen": r[3],
                "span_days": (
                    datetime.fromisoformat(r[3]) - datetime.fromisoformat(r[2])
                ).days,
            }
            for r in rows
        ]

    def _row_to_entry(self, row) -> ConversationEntry:
        return ConversationEntry(
            id=row[0],
            timestamp=row[1],
            summary=row[2],
            topics=json.loads(row[3]),
            sentiment=row[4],
            outcome=row[5],
            source=row[6],
            raw_exchange=row[7],
        )

    def format_for_prompt(
        self,
        current_topics: List[str] = None,
        max_recent: int = 5,
        max_relevant: int = 5,
    ) -> str:
        """
        Format conversation memory for inclusion in a prompt.
        Returns a compact, readable summary.
        """
        sections = []

        # Recent conversations (last 3 days, full detail)
        recent = self.get_recent(days=3, limit=max_recent)
        if recent:
            sections.append("📅 RECENT CONVERSATIONS:")
            for entry in recent:
                age = entry.age_days()
                age_str = "today" if age < 1 else f"{int(age)}d ago"
                sections.append(f"  [{age_str}] {entry.summary}")
                if entry.outcome:
                    sections.append(f"    → {entry.outcome}")

        # Relevant older conversations (if topics provided)
        if current_topics:
            relevant = self.get_relevant(current_topics, limit=max_relevant)
            # Filter out ones already in recent
            recent_ids = {e.id for e in recent}
            relevant = [e for e in relevant if e.id not in recent_ids]

            if relevant:
                sections.append("\n🔗 RELATED PAST CONVERSATIONS:")
                for entry in relevant:
                    age = entry.age_days()
                    age_str = f"{int(age)}d ago" if age < 30 else f"{int(age/30)}mo ago"
                    sections.append(f"  [{age_str}] {entry.summary}")

        # Recurring patterns
        patterns = self.get_patterns(min_frequency=3)
        if patterns:
            recurring = [p for p in patterns if p["span_days"] > 7]
            if recurring:
                sections.append("\n🔄 RECURRING THEMES:")
                for p in recurring[:5]:
                    sections.append(
                        f"  • {p['topic']} ({p['occurrences']}x over {p['span_days']}d)"
                    )

        return "\n".join(sections) if sections else ""


def compact_conversation(
    messages: List[Dict[str, str]], outcome: str = None, source: str = "sidekick"
) -> ConversationEntry:
    """
    Compact a conversation into a memory entry.
    Uses simple heuristics (can be upgraded to use LLM later).
    """
    import uuid
    import re

    # Extract raw text
    full_text = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages
    )

    # Simple topic extraction (words that appear multiple times, excluding common words)
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "have",
        "has",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "it",
        "this",
        "that",
        "i",
        "you",
        "we",
        "they",
        "my",
        "your",
        "our",
        "and",
        "or",
        "but",
        "if",
    }

    words = re.findall(r"\b[a-z]{4,}\b", full_text.lower())
    word_freq = {}
    for w in words:
        if w not in stop_words:
            word_freq[w] = word_freq.get(w, 0) + 1

    topics = [
        w
        for w, count in sorted(word_freq.items(), key=lambda x: -x[1])[:5]
        if count >= 2
    ]

    # Simple summary (first user message + outcome hint)
    user_messages = [m["content"] for m in messages if m.get("role") == "user"]
    first_msg = user_messages[0][:100] if user_messages else "Unknown request"

    summary = f"User asked about: {first_msg}"
    if outcome:
        summary = f"{first_msg[:80]}... → {outcome}"

    # Detect sentiment
    sentiment = "neutral"
    negative_words = {
        "error",
        "fail",
        "broken",
        "bug",
        "issue",
        "problem",
        "wrong",
        "frustrated",
    }
    positive_words = {
        "thanks",
        "great",
        "perfect",
        "works",
        "success",
        "awesome",
        "done",
    }

    text_lower = full_text.lower()
    if any(w in text_lower for w in negative_words):
        sentiment = "frustrated" if "frustrat" in text_lower else "negative"
    elif any(w in text_lower for w in positive_words):
        sentiment = "positive"

    return ConversationEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        summary=summary,
        topics=topics,
        sentiment=sentiment,
        outcome=outcome or "",
        source=source,
        raw_exchange=full_text[:500],
    )
