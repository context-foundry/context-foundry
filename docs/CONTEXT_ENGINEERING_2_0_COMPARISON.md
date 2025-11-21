# Context Engineering 2.0 vs Context Foundry

**Status**: Work in Progress - To be continued
**Date**: 2025-11-17

---

## Article Summary

**Source**: "Shanghai's GAIR Research Just Reframed AI: Context Engineering 2.0 Replaces Prompt Engineering!" by Adham Khaled
**Research**: GAIR (Generative Artificial Intelligence Research Lab), Shanghai Jiao Tong University

### Core Thesis

> "We've been teaching AI to read. We haven't been teaching it how to remember."

The article argues that **context engineering** (not prompt engineering) is the differentiating skill for AI engineers in 2025. A perfect prompt cannot save you when the context is a mess.

---

## The 3-Pillar Framework

### Pillar 1: Collection & Storage (The Foundation)

**Old Way**: Dump everything into a vector database, hope for the best.

**Era 2.0 Way**: Layered architecture:

| Layer | Storage | Content | Relevance |
|-------|---------|---------|-----------|
| Short-term | In-token | Current conversation, immediate context | HIGH temporal |
| Medium-term | Redis/local cache | Session history, recent decisions | Fast retrieval |
| Long-term | Vector DB/cloud | Abstracted insights, patterns, compressed knowledge | HIGH importance |

**Why layers?** Cost and speed. The article claims:
- 40% cost reduction
- 30% accuracy improvement

---

### Pillar 2: Management (The "Self-Baking" Problem)

Raw context is entropy. The job is to compress it into wisdom.

**Four Compression Techniques**:

1. **Hierarchical Summarization**
   - Level 1: Raw logs (2,000 tokens)
   - Level 2: Key events (200 tokens)
   - Level 3: Patterns (50 tokens)
   - Level 4: Abstractions (20 tokens)

2. **Schema-Driven Extraction**
   - Structure context as metadata, changes, decisions, dependencies
   - 80% fewer tokens, same information

3. **Context Isolation (Sub-Agents)**
   - Each agent (reviewer, tester, writer) gets isolated context
   - 5k tokens per agent vs 50k for one fat agent
   - 87% reduction in hallucinations

4. **Progressive Compression**
   - Search → Summarize → Compress → Reason
   - 100k input → 500 output (0.5% compression ratio)

---

### Pillar 3: Usage (The Selection Problem)

**The Five Relevance Signals**:

1. **Semantic Relevance** - Vector similarity (cosine distance)
2. **Logical Dependency** - Does this reasoning step depend on this fact?
3. **Recency & Frequency** - Temporal decay, access counters
4. **Non-Redundancy** - Active deduplication (>90% overlap = keep one)
5. **User Preference** - Feedback signals, usage patterns, annotations

**Hybrid Ranking Example**:
```
Fact 1: "Refund policy: 30 days"
- Semantic sim: 0.92
- Logical dep: 0.95
- Recency: 0.70
- Redundancy: 0
- User pref: 0.85
→ COMPOSITE SCORE: 0.88 ⭐ RETRIEVE
```

---

## Context Foundry Analysis

> **TODO**: Complete this section by exploring the codebase

### Preliminary Mapping

| GAIR Concept | Context Foundry Feature | Status |
|--------------|------------------------|--------|
| **Layered Storage** | ? | To analyze |
| Short-term memory | In-conversation context | ? |
| Medium-term memory | ? (Redis/cache) | ? |
| Long-term memory | Codex (SQLite), Patterns (JSON/S3) | Likely |
| **Hierarchical Summarization** | Pattern compression? | To analyze |
| **Schema-Driven Extraction** | Pattern structure (severity, tags, project_types) | Likely |
| **Context Isolation** | Agent delegation (delegate_to_claude_code) | Yes |
| **Progressive Compression** | Scout → Architect → Builder phases? | To analyze |
| **Semantic Relevance** | codex_search (full-text search) | Partial |
| **Logical Dependency** | ? | To analyze |
| **Recency/Frequency** | Pattern frequency, last_seen | Yes |
| **Non-Redundancy** | merge_project_patterns (conflict resolution) | Likely |
| **User Preference** | ? | To analyze |

---

### Areas to Investigate

1. **Pattern System**
   - `~/.context-foundry/patterns/` - common-issues, scout-learnings, etc.
   - How are patterns stored, merged, and shared?
   - Is there hierarchical compression?

2. **Codex System**
   - `codex.db` - SQLite-based knowledge base
   - Search capabilities (full-text vs semantic)
   - Entry types: issues, patterns, learnings

3. **Agent Architecture**
   - `delegate_to_claude_code` / `delegate_to_claude_code_async`
   - How is context passed to sub-agents?
   - Is context isolated per agent?

4. **Storage Architecture**
   - Local: SQLite (Codex), JSON (patterns)
   - Cloud: S3 community patterns
   - Any Redis/cache layer?

5. **Retrieval Mechanisms**
   - How does Context Foundry decide what context to provide?
   - Multiple relevance signals or just keyword search?

---

## Comparison Questions to Answer

1. Does Context Foundry implement the layered memory architecture?
2. How does Context Foundry's pattern compression compare to hierarchical summarization?
3. Is there hybrid ranking with multiple relevance signals?
4. How effective is agent isolation in Context Foundry?
5. What gaps exist between the GAIR framework and Context Foundry?
6. What does Context Foundry do that the article doesn't cover?

---

## Key Quotes from Article

> "The problem isn't the prompt. It's the context."

> "Context engineering is the new prompt engineering. And it's 3x more powerful."

> "The future belongs to engineers who master context, not prompts."

> "Claude Code uses an AGENTS.md file to isolate context for sub-agents. Result? 40% fewer hallucinations."

> "The engineers winning right now? They don't argue about prompts. They ask: What context does this agent really need?"

---

## Challenges Mentioned

1. **Token Limits** - Quadratic complexity, need progressive compression
2. **Error Propagation** - Hallucinations bake into summaries over time
3. **Retrieval Imperfection** - May miss relevant facts or retrieve irrelevant ones
4. **Evaluation Difficulty** - Need real metrics:
   - Hallucination rate
   - Retrieval precision
   - Cost per query
   - Latency
   - Token efficiency

---

## Next Steps

- [ ] Explore Context Foundry pattern system implementation
- [ ] Analyze Codex database schema and search capabilities
- [ ] Review agent delegation and context isolation
- [ ] Map all Context Foundry features to GAIR 3-pillar framework
- [ ] Identify gaps and strengths
- [ ] Write final comparison and recommendations

---

*To be continued...*
