# Verifying Numeric Claims in RAG Answers: pipeline code

Code for the paper "Verifying Numeric Claims in RAG Answers with a Rule Base Extracted from a Narrative Guideline: A Pediatric Case Study" by Muh. Idrus and Zulkifli Tahir (Hasanuddin University), submitted to *Data Intelligence*.

A RAG chatbot answers Indonesian pediatric questions from the *Pedoman Pelayanan Medis IDAI, Vol. I* (the guideline). A Claim Extractor splits each draft answer into atomic numeric claims (dose, frequency, duration, interval), a Rule Engine checks them against a rule base of 697 rules extracted from the guideline, and an answer with a violation is regenerated once.

The data (rule base, prompts, queries, outputs, labels, rule audit) are in the ScienceDB deposit: [PERSISTENT WEB LINK / DOI]. This repository holds the code that produced and evaluated them.

## Repository layout

```
.
├── data/
│   ├── raw/             Guideline PDF (you provide it, see below)
│   ├── processed/       Text produced from the PDF by src/ingestion/
│   └── rules/           rule_base.json, rule_schema.json, normalization_dictionary.json
├── index/               chunks.pkl and faiss.index, built by src/ingestion/build_index.py
├── src/
│   ├── ingestion/       extract_ppm.py, clean_ppm.py, chunk_ppm.py, build_index.py
│   ├── retrieval/       retriever.py: top-3 search over the FAISS index
│   ├── llm/             generator.py and the prompt files
│   ├── verification/    claim_extractor.py, rule_engine.py, decision_layer.py
│   ├── evaluation/      evaluation scripts and result files
│   ├── pipeline.py      Retrieval, generation, verification and regeneration end to end
│   └── run_chat.py      Interactive entry point
├── requirements.txt
├── requirements-lock.txt
├── .env.example
└── LICENSE
```

| Component | Role |
|---|---|
| `src/ingestion/` | Extracts text from the PDF, cleans it, splits it at paragraph boundaries without overlap, and builds the index |
| `src/retrieval/retriever.py` | Embeds the query with BAAI/bge-m3 (SentenceTransformers) and returns the top 3 chunks from a FAISS `IndexFlatIP` |
| `src/llm/generator.py` | Calls GPT-OSS-120B through the Groq API (OpenAI-compatible client) with the prompts in `src/llm/` |
| `src/verification/claim_extractor.py` | Atomic claim extraction (same model, T = 0, few-shot) |
| `src/verification/rule_engine.py` | Candidate-rule matching and the compliance check |
| `src/verification/decision_layer.py` | Turns claim verdicts into `PASS`, `PASS_WITH_WARNINGS`, `REGENERATE` or `NO_CLAIMS_EXTRACTED` |
| `src/evaluation/` | See "Reproducing the results" |

## Setup

Developed and run with Python 3.12.10 in a virtual environment (pandas 3.x needs Python 3.11 or later).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements-lock.txt` pins every package, including transitive ones, for an exact copy of the environment used for the paper.

The first run downloads BAAI/bge-m3, which needs an internet connection and several GB of disk space.

Create a `.env` file from the template and add your Groq API key. Never commit `.env`.

```bash
cp .env.example .env               # then edit it
```

## Data to put in place

1. **Rule base.** Download `rule_base.json`, `rule_schema.json` and `normalization_dictionary.json` from the ScienceDB deposit into `data/rules/`.
2. **Guideline PDF.** The guideline is copyrighted and is not distributed. Obtain a copy of *PPM IDAI Vol. I* (2009) and save it as `data/raw/buku pedoman pelayanan medis.pdf`.
3. **Evaluation files.** Download `queries_outputs.csv`, `claims.csv` and `audit_100_aturan.csv` from the deposit into `src/evaluation/` if you want to reproduce the reported numbers without rerunning the models.

## Building the index

Run from the repository root, in this order:

```bash
python src/ingestion/extract_ppm.py
python src/ingestion/clean_ppm.py
python src/ingestion/chunk_ppm.py
python src/ingestion/build_index.py
```

This writes `data/processed/` and `index/`. The outputs are derived from the guideline, so keep them out of version control.

## Running the pipeline

```bash
python -m src.run_chat
```

`src/pipeline.py` implements the flow of the paper: retrieve the top 3 chunks, generate a draft (T = 0.2), extract claims (T = 0), verify them against the rule base, and regenerate once (T = 0) if there is a violation. The regenerated answer is returned without a second verification.

## Reproducing the results

From the repository root, with the data in place:

```bash
python src/evaluation/evaluation_results.py     # Table 1
python src/evaluation/bootstrap_ci_rfr.py       # Rule Faithfulness Rate and 95% bootstrap interval
python src/evaluation/scr_val.py                # Schema Conformance Rate
python src/evaluation/grounding_val.py          # Grounding Rate (needs the guideline PDF)
```

Expected output: Table 1 as in the paper (489 items, 317 covered, TP/FN/FP/TN = 35/3/15/264, hallucinated queries 48/44/32 of 187, McNemar p = 0.0015 and 0.57); `RFR = 92.5%`, 95% CI 88.5-96.0%; `SCR = 100.00%`.

`generate_audit_sheet.py` draws the 100 rules of the semantic audit (simple random sampling, seed 42). `uji_regenerate_query_draft_context.py` and `uji_regenerate_tanpa_rule.py` rerun the regeneration experiments without rule feedback. Rerunning them calls the Groq API.

### What cannot be reproduced exactly

- **Rule extraction.** The rules were produced with Google NotebookLM, which exposes no model version or sampling parameters. The released `rule_base.json` is the fixed input of all experiments.
- **Model runs.** Outputs were generated with GPT-OSS-120B through Groq on [execution date], one run per configuration. Hosted models can change, so a rerun may differ. The released outputs are the data behind the paper.
- **Labels.** Ground-truth labels and the rule audit come from the first author and have not been validated by clinicians or a second rater.

## Notes

This is research code. The rule base and the pipeline are not clinical guidance and must not be used to make treatment decisions; the paper states that clinical validation is required first.

No human subjects were involved, and the evaluation queries contain no patient data.

## License

The code is released under the MIT license (see `LICENSE`). The data in the ScienceDB deposit are released under CC BY 4.0, except the quoted guideline sentences in `metadata.text`, which remain the property of Ikatan Dokter Anak Indonesia.

## Citation

> M. Idrus and Z. Tahir, "Verifying numeric claims in RAG answers with a rule base extracted from a narrative guideline: A pediatric case study," *Data Intelligence*, [year]. doi: [paper DOI]

Code release: https://github.com/helloidrus/chatbotpediatrics, v1.0.0, doi: 10.5281/zenodo.24025776.

## Contact

Zulkifli Tahir (corresponding author), zulkifli@unhas.ac.id.
