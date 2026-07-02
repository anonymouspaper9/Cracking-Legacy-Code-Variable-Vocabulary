# Cracking the Legacy Code — COBOL Variable Description Generation

This repository accompanies the research paper on **semantic interpretation of cryptic variables in legacy COBOL applications**. We address the problem of generating an application-level vocabulary that captures the meaning and purpose of each variable, expressed as concise **short** and **long descriptions**.

Legacy codebases contain rich but hidden clues, database schemas, screen map labels, code comments, common knowledge, and domain knowledge, that can be leveraged to infer variable semantics. We propose a novel **variable grouping mechanism** that maximises the contextual expressivity of variables while adhering to model size and token constraints. The approach is evaluated across **8 models**, **9 configurations**, and **7 enterprise-level applications**, with 1 code assistant serving as a reference baseline. We demonstrate that with proper context gathering and grouping, **smaller open-source models can match the performance of closed-source models and code assistants** with significantly fewer tokens. We also propose a **robust data generation pipeline** for producing high-quality evaluation benchmarks in low-resource settings.

---

## Table of Contents

- [Overview](#overview)
- [Benchmark Applications](#benchmark-applications)
- [Repository Structure](#repository-structure)
- [Methodology](#methodology)
  - [Experimental Setting](#experimental-settings)
  - [Context Extraction Approaches](#context-extraction-approaches)
  - [Batching Strategies](#batching-strategies)
- [Models Supported](#models-supported)
- [Core Modules](#core-modules)
- [Evaluation Framework](#evaluation-framework)
- [Configuration](#configuration)
- [Getting Started](#getting-started)
- [Data](#data)
- [Output Format](#output-format)

---

## Overview

Legacy COBOL codebases contain thousands of cryptic variable names (e.g., `WS-ACCT-BAL-01`, `EIBTRNID`, `CA-RESP-CODE`) that are nearly impossible to understand without domain expertise. This project addresses that problem by:

1. **Extracting contextual source code snippets** for each variable using multiple strategies (full source file, paragraph-level, k-lines around occurrences), leveraging clues hidden in the code such as database schemas, screen map labels, and code comments.
2. **Grouping related variables** using a novel k-hop co-occurrence mechanism and record-level hierarchy to maximise context expressivity within token constraints.
3. **Evaluating results** using a specialised agentic judge that cross-references both an expert-authored ground truth and the actual COBOL repository.

The output for each variable is a structured JSON entry:

```json
{
  "input": "WS-ACCT-BAL-01",
  "short description": "Working-Storage Account Balance 01",
  "long description": "A variable defined in Working-Storage representing the balance of an account..."
}
```

---

## Benchmark Applications

The system is evaluated across **7 enterprise-level COBOL applications** spanning diverse industry domains. Only a **sampled subset** of the complete annotation data is included in this repository.

| Application | Domain | Programs | KLOC | Selected Variables |
|---|---|---|---|---|
| AWS CardDemo | Banking | 106 | 40.82 | 59 |
| GenApp | Insurance | 47 | 11.45 | 87 |
| CRYPTOCOB | Security | 23 | 7.55 | 20 |
| DEBINIX | Telecom | 12 | 6.72 | 17 |
| ETALAB | Government | 23 | 4.47 | 67 |
| Z390DEV | Assembler tool | 78 | 23.55 | 36 |
| ZECS | E-Commerce | 7 | 4.08 | 14 |

> **Note:** Only a sampled set of the complete data is presented in this repository. Full annotation data will be publicly released after publication (if accepted).

---

## Repository Structure

```
.
├── Evaluation-Aaaj/
│   ├── judge.py                                     # Agentic-as-a-judge implementation
│   └── judge_prompt.txt                             # Detailed judge system prompt
├── data/
│   └── sampled_data_for_submission.csv              # Sampled benchmark dataset
├── expt/
│   ├── Batch_Creation Record with Paragraph and Variable Occurence.ipynb
│   ├── Disagreement_Analysis.ipynb                  # Cross-model disagreement analysis
│   ├── Experiments-app_name_only_inference.ipynb
│   ├── Experiments-full_source_code_inference.ipynb
│   ├── Experiments-full_source_code_with_k_hop_batching_inference.ipynb
│   ├── Experiments-full_source_code_with_record_level_batching_inference.ipynb
│   ├── Experiments-paragraph_code_inference.ipynb
│   ├── Experiments-paragraph_code_with_k_hop_batching_inference.ipynb
│   ├── Experiments-paragraph_code_with_record_level_batching_inference.ipynb
│   ├── Experiments-variable_k_lines_code_inference.ipynb
│   ├── Experiments-variables_k_lines_code_with_k_hop_batching_inference.ipynb
│   └── Experiments-variables_k_lines_code_with_record_level_batching_inference.ipynb
├── prompts/
│   ├── app_name_only_prompts.py                     # Prompt: app name as sole context
│   ├── icl_source_code_prompts.py                   # Prompts (v3) full source code context (single variable)
│   ├── icl_source_code_prompts_batched.py           # Prompt: full source code context (batched variables)
│   ├── icl_paragraph_code_prompts.py                # Prompt: paragraph-level context (single variable)
│   └── icl_paragraph_code_prompts_batched.py        # Prompt: paragraph-level context (batched variables)
└── src/
    ├── args.py                                      # Central configuration (credentials, paths, hyperparameters)
    ├── api_endpoints.py                             # Model API endpoint registry (masked for security)
    ├── Batch_Creation k-hop-optimized_paragraph_occurence.py   # k-hop batch builder using paragraph occurrences
    ├── Batch_Creation k-hop-optimized_var_occurence.py         # k-hop batch builder using variable-line occurrences
    ├── snippet_creation.py                          # COBOL data-division snippet builder from a variable DataFrame
    └── utils.py                                     # Inference engine, output parsers, and utility functions
```

---

## Methodology

### Experimental Settings

Each experimental setting varies the *context* provided to the LLM alongside the variable name:

| Strategy | Description | Prompt file |
|---|---|---|
| **App Name Only** | (Baseline) Uses only the application name to infer domain semantics | `app_name_only_prompts.py` |
| **Full Source Code** | Provides the entire COBOL source file for the variable's application | `icl_source_code_prompts.py` |
| **Paragraph Code** | Provides only the code paragraphs in which the variable appears | `icl_paragraph_code_prompts.py` |
| **Variable k-Lines** | Provides a fixed window of lines around each occurrence of the variable | *(notebook-level)* |

All experiments use **in-context learning (ICL)** with two high quality annotated COBOL examples (`AG-COMBO-HFILL`, `EIBTRNID`) to guide the output format and quality.

In general the prompt used for experiments instructs the model to:
- Expand all COBOL-specific abbreviations (`WS`, `DFH`, `FD`, `RESP`, `CA`, `EIB`).
- Produce a short description that is purely the expanded abbreviation form.
- Produce a long description that aggregates all occurrences, is faithful to the code, and is concise and non-redundant.
- Output strictly valid JSON with no extra text.

### Context Extraction Approaches

Context is extracted for each variable from its COBOL source file. Two main granularities are used:

- **Paragraph-level** — all paragraphs that contain the variable, assembled via `Batch_Creation k-hop-optimized_paragraph_occurence.py`.
- **Variable-occurrence-level (k-lines)** — a sliding window of k lines around each line where the variable appears.


### Batching Strategies

To improve throughput and potentially leverage inter-variable context, two batching strategies are explored:

| Strategy | Description |
|---|---|
| **Record-level batching** | Groups variables that belong to the same COBOL data record (parent-child hierarchy) into one LLM call |
| **k-hop batching** | Groups variables that are related via k-hop co-occurrence in COBOL statements into one LLM call |

The `snippet_creation.py` module builds human-readable COBOL-style data-division snippets from a variable DataFrame, preserving the hierarchical record structure (level numbers, `PIC` clauses, `VALUE` clauses) for use as structured context.

---

## Models Supported

Models are registered in [`api_endpoints.py`](api_endpoints.py) and selected via [`args.py`](args.py).

### Platform: `llm_provider_1` (OpenAI-compatible)

| Key | Model ID |
|---|---|
| `llama3_3_70b` | `meta-llama/llama-3-3-70b-instruct` |
| `llama4_17b_16e` | `meta-llama/Llama-4-Scout-17B-16E-Instruct` |
| `gpt_oss_120b` | `openai/gpt-oss-120b` |
| `gpt_oss_20b` | `openai/gpt-oss-20b` |
| `qwen_3_30b_a3b_thinking` | `Qwen/Qwen3-30B-A3B-Thinking-2507` |
| `gemma_4_31B_it` | `google/gemma-4-31B-it` |
| `qwen_3_8B` | `Qwen/Qwen3-8B` |

### Platform: `litellm`

| Key | Model ID |
|---|---|
| `claude_sonnet_4_5` | `aws/claude-sonnet-4-5` |

To switch the active model or platform, edit [`args.py`](args.py):

```python
platform = ["llm_provider_1", "litellm"][0]   # 0 = llm_provider_1, 1 = litellm
```

---

## Core Modules

### [`args.py`](args.py)

Central configuration class. Holds credentials, file paths, model selections, and generation hyperparameters.

```python
class args:
    llm_provider_1_API_KEY = "..."     # API key for provider 1
    litellm_api_key        = "..."     # API key for LiteLLM

    saving_path            = "../saved_data/inference/"
    evaluation_data_path   = "../saved_data/evaluation_results/"

    temperature = 0.0
    top_p       = 1
    max_tokens  = 16384

    platform = ["llm_provider_1", "litellm"][0]
```

### [`utils.py`](utils.py)

Contains:

- **`Inference`** — main inference class with `llm_provider_1_inference()` and `litellm_inference()` methods. Callable via `inference(prompt, platform, model_name)`.
- **`get_model_platform(model_name)`** — resolves which platform a model belongs to.
- **`process_inference_json(output)`** — extracts the last valid JSON object/array from raw LLM output.
- **`clean_string(text)`** — strips special characters and normalises whitespace.
- **`update_file_name(filename)`** — avoids overwriting existing output files by auto-incrementing a run number.
- **`validate_api_endpoints()`** — asserts all configured model names have registered API endpoints.
- **`create_save_directories()`** / **`ensure_exp_dirs_exist()`** — creates required output directories.

### [`snippet_creation.py`](snippet_creation.py)

`SnippetCreation` class builds COBOL-style data-division listings from a pandas DataFrame of variables. It reconstructs the full hierarchical record structure by traversing parent-child relationships recursively.

Expected DataFrame columns: `var_id`, `var_name`, `pic`, `sz_values`, `i_level`, `father`.

```python
from snippet_creation import create_snippets_from_dataframe

snippets = create_snippets_from_dataframe(df)
# Returns: {var_id: "01    RECORD-NAME\n    05    FIELD-A    PIC X(10).\n..."}
```

### [`api_endpoints.py`](api_endpoints.py)

Registry of model API endpoints. Endpoint URLs are masked (`"....."`) in this repository for security.

---

## Evaluation Framework

The evaluation is located in [`Evaluation-Aaaj/`](Evaluation-Aaaj/).

### Judge Prompt ([`judge_prompt.txt`](Evaluation-Aaaj/judge_prompt.txt))

A detailed agentic judge prompt instructs the LLM to:

1. **Explore the COBOL repository** at a given path using file-system tools.
2. **Review the manual ground truth** (expert annotations).
3. **Evaluate each model's output** against both the GT and the repository evidence.

#### Short Description — Binary evaluation

| Criterion | Acceptable | Not Acceptable |
|---|---|---|
| Language | English | Non-English |
| Words | All significant GT words present | Missing significant GT words |
| Numerals | Not expanded | Incorrectly expanded (e.g., "01" → "zero one") |
| Additions | No significant incorrect words | Significant incorrect expansions |

#### Long Description — 3-parameter rubric (scored 1–3)

| Parameter | Score 3 | Score 2 | Score 1 |
|---|---|---|---|
| **Correctness** | All claims GT-aligned and repo-confirmed | 1–2 minor inaccuracies | Multiple errors / hallucinations |
| **Comprehensiveness** | Covers GT level or better (repo-verified extras rewarded) | Misses 1–2 GT aspects | Misses critical GT aspects |
| **Conciseness** | Clear, focused, every word adds value | Minor redundancy | Excessively verbose or too brief |

### Judge Orchestrator ([`judge.py`](Evaluation-Aaaj/judge.py))

`VariableJudge` processes a dataset of variables in parallel (`num_workers=15`), retries up to 3 times per variable, tracks costs, and writes structured JSON evaluation output.

### Disagreement Analysis ([`Disagreement_Analysis.ipynb`](Disagreement_Analysis.ipynb))

Analyses inter-model disagreement across all inference outputs — identifying variables where models systematically diverge and supporting qualitative analysis.

---

## Configuration

### 1. API Keys

Set credentials directly in [`args.py`](args.py) or via environment variables.

### 2. Model Selection

Edit [`args.py`](args.py) to choose the active platform and model list:

```python
platform = ["llm_provider_1", "litellm"][0]
llm_provider_1 = ["llama3_3_70b", "gpt_oss_120b", ...]
```

### 3. Saving Paths

```python
saving_path          = "../saved_data/inference/"
evaluation_data_path = "../saved_data/evaluation_results/"
```

---

## Getting Started

### 1. Validate your configuration

```python
from utils import validate_api_endpoints, create_save_directories

create_save_directories()
validate_api_endpoints()
```

### 2. Run an inference experiment

Open any of the `Experiments-*.ipynb` notebooks that matches your desired strategy:

| Notebook | Strategy |
|---|---|
| `Experiments-app_name_only_inference.ipynb` | No source code — app name only |
| `Experiments-full_source_code_inference.ipynb` | Full source file as context |
| `Experiments-paragraph_code_inference.ipynb` | Paragraph-level context |
| `Experiments-variable_k_lines_code_inference.ipynb` | k-lines around variable occurrences |
| `Experiments-full_source_code_with_k_hop_batching_inference.ipynb` | Full source + k-hop batching |
| `Experiments-full_source_code_with_record_level_batching_inference.ipynb` | Full source + record-level batching |
| `Experiments-paragraph_code_with_k_hop_batching_inference.ipynb` | Paragraph context + k-hop batching |
| `Experiments-paragraph_code_with_record_level_batching_inference.ipynb` | Paragraph context + record-level batching |
| `Experiments-variables_k_lines_code_with_k_hop_batching_inference.ipynb` | k-lines + k-hop batching |
| `Experiments-variables_k_lines_code_with_record_level_batching_inference.ipynb` | k-lines + record-level batching |

### 3. Build context batches (if using batching strategies)

```bash
# For paragraph-level k-hop batching
python "Batch_Creation k-hop-optimized_paragraph_occurence.py"

# For variable-line-level k-hop batching
python "Batch_Creation k-hop-optimized_var_occurence.py"

### For Record Level Batching (applicable for both the context types) use:
Batch_Creation Record with Paragraph and Variable Occurence.ipynb

```



### 4. Run evaluation

Configure paths in [`Evaluation-Aaaj/judge.py`](Evaluation-Aaaj/judge.py) and run:

```bash
python Evaluation-Aaaj/judge.py
```

---

## Data

| File | Description |
|---|---|
| `data/sampled_data_for_submission.csv` | Benchmark dataset of sampled COBOL variables with expert-annotated ground truth descriptions |

The dataset includes the variable name, its application name, source file path, and expert-authored short and long descriptions used as ground truth during evaluation.

---

## Output Format

All inference outputs are saved as CSV and/or JSON files under `./saved_data/inference/`. Each record contains:

```json
{
  "input": "EIBTRNID",
  "short description": "Execute Interface Block Transaction Identifier",
  "long description": "A CICS Execute Interface Block field that holds the transaction identifier..."
}
```

Evaluation outputs (from the judge) are written to `./saved_data/evaluation_results/` and include per-model scores for correctness, comprehensiveness, and conciseness alongside evidence-grounded justifications.

---

## Experiment Design Decisions

- **Greedy decoding** (`temperature=0.0`) is used throughout to maximise reproducibility.
- **In-context learning** with two high-quality COBOL examples is included in every prompt to anchor the output format and quality bar.
- **JSON output enforcement** — the `process_inference_json()` utility extracts the last valid JSON block from model output, making the pipeline robust to models that emit preamble or postamble text.
- **File-name versioning** — `update_file_name()` auto-increments output filenames to avoid overwriting prior runs.
- **Agentic evaluation** — the judge has direct file-system access to the COBOL source repository, giving it the option to verify model claims against the actual code rather than relying solely on the ground truth, which is instructed to serve as the primary reference for evaluation.
