# Memory & RAG Lab - Vellora Implementation Roadmap

## 📋 Project Status
- **Completed**: MCP Server & Database (من المرة اللي فاتت)
- **In Progress**: Memory implementation (بدايات)
- **Priority**: RAG architectures + Vector Database
- **Team Size**: Solo (1 person)

---

## 🎯 Strategic Implementation Order

### PHASE 1: Complete Memory System (الأساس)
**Timeline**: 3-4 أيام
**Why First**: RAG بتعتمد على episodic memory للـ retrieval history

#### 1.1 Short-term Buffer + Scratchpad
- [ ] Rolling message buffer (last N turns)
- [ ] Separate scratchpad (agent's current plan/state)
- [ ] Pruning logic (never destroys scratchpad)
- [ ] Test: 50-turn conversation, critical detail in turn 5 survives to turn 50

#### 1.2 Promote-or-Drop Router
- [ ] Decision logic: forget vs. episodic
- [ ] Logging: reasoning behind each decision
- [ ] Test cases with conflicting information

#### 1.3 Episodic Memory Store
- [ ] Store: Timestamped interaction records
- [ ] Structure: {timestamp, user_input, assistant_response, tool_calls, outcome}
- [ ] Query: By time range, by topic, by tool type

#### 1.4 Semantic Memory + Consolidation
- [ ] Consolidation trigger: Periodic pass (every 10 episodic events or daily)
- [ ] Conflict resolution: Explicit versioning, not silent overwrites
- [ ] Update/expiration handling
- [ ] Test case: Two contradictory facts → resolved with timestamp + version

**Deliverable**: `memory/` folder with all components

---

### PHASE 2: Context Window Management (الاختبار)
**Timeline**: 2-3 أيام
**Why After Memory**: Needs realistic long transcripts to test

#### 2.1 Implement All 4 Strategies
- [ ] Sliding window (last N turns)
- [ ] Observation masking (keep recent tool outputs only)
- [ ] Recursive summarization (compact every M turns)
- [ ] Zone-based pruning (divide transcript into zones)

#### 2.2 Build Test Suite
- [ ] Create 10 long-context test cases (40+ turns each)
- [ ] Embed critical detail in early turn
- [ ] Bury it under 30+ tool calls
- [ ] Test case example: Allergy mentioned in turn 3, needed in turn 40

#### 2.3 Evaluation & Comparison Table
Run each strategy against test suite:
```
| Strategy | Accuracy | Input Tokens | Output Tokens | Latency |
|----------|----------|--------------|---------------|---------|
| Sliding Window | ? | ? | ? | ? |
| Observation Masking | ? | ? | ? | ? |
| Recursive Summarization | ? | ? | ? | ? |
| Zone-based Pruning | ? | ? | ? | ? |
```

**Decision**: Pick ONE based on table, not intuition

**Deliverable**: `context_eval/` folder with scripts + comparison table

---

### PHASE 3: Vector Database + RAG (النواة)
**Timeline**: 4-5 أيام
**Why After Context**: Need stable memory before adding retrieval layer

#### 3.1 Vector Database Setup
- [ ] Choose: Chroma (local) OR Qdrant (prod-ready)
- [ ] Set up ANN index (HNSW)
- [ ] Add metadata payload store
- [ ] Add metadata index (for pre/mid-search filtering)
- [ ] Test: Filter by document type, date range, before similarity search

#### 3.2 Chunking + Embedding Pipeline
- [ ] Identify Vellora's knowledge sources (policies, FAQs, case history, etc.)
- [ ] Chunking strategy: Semantic chunks, not fixed token splits
- [ ] Embedding model: OpenAI `text-embedding-3-small` or `ollama` for local
- [ ] Metadata: Document type, date, version, source

#### 3.3 Implement 3 Required RAG Architectures

**A. Naive RAG** (Baseline)
```python
1. Retrieve top-k chunks (vector similarity)
2. Generate answer from chunks
3. No reranking, no multi-hop
```

**B. Hybrid Search** (Vector + BM25)
```python
1. Vector search (semantic)
2. BM25 search (keyword/exact match)
3. Merge results
4. Generate answer
```

**C. Agentic RAG** (Multi-hop with reasoning)
```python
1. Reason: What do I need?
2. Retrieve: Get initial chunks
3. Evaluate: Is this enough?
4. Retrieve again if needed
5. Generate answer
```

#### 3.4 Domain-Specific Test Questions
Design 12+ questions:
- 4 questions for naive RAG (simple retrieval)
- 4 questions for hybrid search (exact IDs, citations)
- 4 questions for agentic RAG (multi-part, decomposition needed)

Example for Vellora:
- Naive: "What's the fasting requirement before surgery?"
- Hybrid: "What does policy section 3.2 say about post-op care?"
- Agentic: "For a senior patient on anticoagulants needing cataract surgery, what pre-op screening and medication adjustments apply?"

#### 3.5 Evaluation & Comparison Table
```
| Architecture | Accuracy | Tokens/Query | Latency/Query | Notes |
|--------------|----------|--------------|---------------|-------|
| Naive RAG | ?/12 | ? | ? | Fast, misses complex |
| Hybrid Search | ?/12 | ? | ? | Better citations |
| Agentic RAG | ?/12 | ? | ? | Slower but thorough |
```

**Decision**: Pick ONE as default + routing logic

**Deliverable**: `rag/` and `retrieval_eval/` folders

---

### PHASE 4: Self-RAG Verification
**Timeline**: 1-2 أيام
**Why After RAG**: Need retrieval results to verify

- [ ] Post-retrieval check: Is chunk relevant to question?
- [ ] Post-generation check: Is answer supported by chunk?
- [ ] Apply to both RAG answers AND memory recalls
- [ ] Visible consequence: Reject low-confidence answers

---

### PHASE 5: Integration + Demo
**Timeline**: 2-3 أيام

#### 5.1 Wire Everything into Agent Loop
- [ ] Agent calls memory system (store interactions)
- [ ] Agent calls RAG when knowledge gap detected
- [ ] Agent uses Self-RAG verification
- [ ] Update existing `mpc_server/` and `agent/` minimally

#### 5.2 Demo Transcript
Show:
1. Short-term item → promote-or-drop → episodic
2. Consolidation resolving contradiction
3. All 4 context strategies running
4. All 3 RAG architectures on same question
5. Self-RAG catching/passing verification

#### 5.3 Documentation
- [ ] README with problem statement
- [ ] Embedded comparison tables (context + retrieval)
- [ ] Setup instructions
- [ ] How to run demo

---

## 📊 Total Effort Estimate (Solo)
- Phase 1: 3-4 days
- Phase 2: 2-3 days  
- Phase 3: 4-5 days
- Phase 4: 1-2 days
- Phase 5: 2-3 days
- **Total: ~15-20 days of focused work**

---

## 🚨 Critical Constraints

### Don't:
- ❌ Rebuild existing `mpc_server/` or `db/` from scratch
- ❌ Commit API keys or `.env` secrets
- ❌ Use fake test data (30-turn synthetic > 40-turn real)
- ❌ Silent overwrites in semantic memory (version everything)
- ❌ Skip comparison tables (numbers, not intuition)

### Do:
- ✅ Pick a real memory/knowledge gap in Vellora
- ✅ Make each concern earn its place
- ✅ Build fixed test suites (don't change between runs)
- ✅ Log all reasoning (promote-or-drop decisions, conflicts)
- ✅ Test with large realistic inputs (bury decisions under tokens)

---

## 📁 Repo Structure (Target)
```
vellora-mcp-server/
├── mpc_server/          (existing, minimal changes)
├── db/                  (existing)
├── agent/               (existing + integration)
│
├── memory/              (PHASE 1)
│   ├── short_term.py
│   ├── episodic_store.py
│   ├── semantic_store.py
│   ├── router.py        (promote-or-drop)
│   └── consolidation.py
│
├── context_eval/        (PHASE 2)
│   ├── strategies.py    (all 4)
│   ├── test_suite.py    (10+ long transcripts)
│   ├── evaluate.py      (run comparisons)
│   └── RESULTS.md       (comparison table)
│
├── rag/                 (PHASE 3a)
│   ├── chunking.py
│   ├── embedding.py
│   ├── vector_store.py  (ANN + metadata)
│   └── config.yaml
│
├── retrieval_eval/      (PHASE 3b)
│   ├── architectures.py (naive, hybrid, agentic)
│   ├── test_questions.py
│   ├── evaluate.py
│   └── RESULTS.md       (comparison table)
│
├── verification/        (PHASE 4)
│   └── self_rag.py      (relevance + support checks)
│
├── demo/                (PHASE 5)
│   ├── demo.py
│   └── TRANSCRIPT.md
│
├── README.md            (full documentation)
├── .env                 (secrets, in .gitignore ✅)
└── requirements.txt
```

---

## ⚡ Quick Start Next Step
1. Review your existing Vellora system (what memory/knowledge gap exists?)
2. Start PHASE 1: Build `memory/short_term.py` (rolling buffer)
3. Create at least one long test case for Phase 2
4. Then jump to vector DB setup

Ready to code? Let's start with Phase 1! 🚀
