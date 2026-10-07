# RAG Evaluation Report — Clinical Analytics

## 1. Evaluation Overview

This report documents the baseline evaluation of the Retrieval-Augmented Generation (RAG) subsystem within the Clinical Analytics platform. The evaluation assesses the quality of knowledge retrieval and clinical query answering using the **DeepEval** framework (v4.2.8) with **Google Gemini (`gemini-3.5-flash-lite`)** serving as the evaluation LLM judge.

- **Framework**: DeepEval 4.2.8
- **Judge Model**: `gemini-3.5-flash-lite`
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Store**: FAISS (L2 index)
- **Document Store**: Concept-level chunks derived from `clinical_reference.txt`
- **Execution Mode**: Sequential asynchronous evaluation (`max_concurrent=1`, `throttle_value=1`)

---

## 2. Test Cases

The evaluation suite consists of 3 curated clinical benchmark test cases defined in `evals/datasets/rag_test_cases.json`:

| Test Case ID | Clinical Concept | Evaluation Question |
| :--- | :--- | :--- |
| **`rag_001`** | Average Length of Stay | *What is average length of stay and how is it calculated in clinical analytics?* |
| **`rag_002`** | Readmission | *What is readmission rate in clinical analytics?* |
| **`rag_003`** | Total Cost | *What is total cost in healthcare analytics?* |

---

## 3. Metric Results

Each test case was evaluated across three core RAG dimensions with a passing threshold of **0.70**:

### A. Contextual Relevancy
Measures whether the retrieved context contains only information relevant to answering the clinical question, without extraneous or distracting concepts.
- **Average Score**: `1.00` (100%)
- **Pass Rate**: `100%` (3/3 passed)
- **Threshold**: `0.70`

### B. Faithfulness
Measures whether the generated answer is strictly grounded in the retrieved reference context and free from hallucinations or unsupported medical claims.
- **Average Score**: `1.00` (100%)
- **Pass Rate**: `100%` (3/3 passed)
- **Threshold**: `0.70`

### C. Answer Relevancy
Measures how directly, concisely, and completely the generated answer addresses the user's specific clinical query.
- **Average Score**: `1.00` (100%)
- **Pass Rate**: `100%` (3/3 passed)
- **Threshold**: `0.70`

---

## 4. Overall Results

Across all three test cases and metrics:

| Metric | rag_001 | rag_002 | rag_003 | Average Score | Pass Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Contextual Relevancy** | 1.00 ✅ | 1.00 ✅ | 1.00 ✅ | **1.00** | **100%** |
| **Faithfulness** | 1.00 ✅ | 1.00 ✅ | 1.00 ✅ | **1.00** | **100%** |
| **Answer Relevancy** | 1.00 ✅ | 1.00 ✅ | 1.00 ✅ | **1.00** | **100%** |

- **Total Metric Evaluations**: `9`
- **Total Passed**: `9`
- **Total Failed**: `0`
- **Overall Evaluation Pass Rate**: `100%` (on the current 3-case benchmark set)

---

## 5. Interpretation

The evaluation results demonstrate strong baseline performance for the current benchmark queries:

1. **Concept-Level Retrieval Precision**: Following paragraph-level semantic chunking of the clinical reference corpus, the retriever returns concise, targeted text passages (`top_k=2`) directly matching the requested clinical definition, achieving perfect Contextual Relevancy (`1.00`).
2. **Strict Grounding & Safety**: Generated responses strictly adhere to the retrieved passages with zero hallucinated statistics or unverified clinical guidance, satisfying Faithfulness criteria (`1.00`).
3. **Clinical Intent Alignment**: Generated answers address the core question directly and succinctly without redundant boilerplate, achieving full Answer Relevancy (`1.00`).

---

## 6. Limitations & Scope

> **Important Notice on Scope:**  
> These evaluation results apply **strictly to the current 3-case benchmark evaluation set** (`rag_001`, `rag_002`, `rag_003`). They do **not** imply that the entire RAG subsystem has 100% accuracy across arbitrary clinical queries or unverified edge cases.

Key limitations include:
- **Sample Size**: The evaluation dataset is currently limited to 3 curated queries and serves as a baseline smoke/regression benchmark.
- **Corpus Breadth**: The current reference corpus (`clinical_reference.txt`) covers foundational clinical analytics concepts (length of stay, readmission, healthcare costs, data dictionaries). It does not yet encompass complex multi-specialty clinical guidelines or full EHR billing taxonomies.
- **Query Complexity**: The benchmark questions test direct conceptual definitions. They do not evaluate multi-hop reasoning, ambiguous phrasing, adversarial inputs, or out-of-domain medical queries where retrieval rejection is required.
- **Future Work**: Expansion of the evaluation suite to include 20+ diverse test cases, negative/out-of-scope prompts, hallucination stress tests, and automated continuous evaluation in CI/CD pipelines.
