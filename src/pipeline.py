import json
from pathlib import Path
from src.retrieval.retriever import Retriever
from src.llm.generator import Generator
from src.verification.claim_extractor import extract_claims
from src.verification.decision_layer import apply_decision
from src.verification.rule_engine import (verify_claims, load_rules)
import time


class Pipeline:
    ## --- INITIALIZATION ---
    def __init__(self, debug=True):
        self.debug = debug
        self.retriever = Retriever()
        self.generator = Generator()
        rules_path = Path(__file__).parent / "verification" / "rule_pediatrics.json"
        self.rules = load_rules(str(rules_path))

    ## --- DEBUGGING ---
    def _debug_print(self, *args):
        if self.debug:
            print(*args)

    #-- CONTEXT RETRIEVAL ---
    def _retrieve_context(self, query):
        start = time.time()
        retrieved_docs, scores = self.retriever.search(query)
        context = "\n".join(retrieved_docs)
        score_values = scores[0] if len(scores) > 0 else []
        self._debug_print("\n=== RETRIEVED DOCS ===")
        for i, (doc, score) in enumerate(zip(retrieved_docs, score_values), start=1):
            preview = doc[:150].replace("\n", " ")
            self._debug_print(f"[{i}] score={score} | {preview}")
        self._debug_print("Retrieval time:", time.time() - start)
        return retrieved_docs, scores, context
    
    #-- LLM GENERATION ---
    def run_llm(self, query):
        start = time.time()
        llm_response = self.generator.generate(query)
        self._debug_print("LLM generation time:", time.time() - start)
        return llm_response

    #-- RAG GENERATION ---
    def run_rag(self, query):
        retrieved_docs, scores, context = self._retrieve_context(query)
        start = time.time()
        rag_response = self.generator.generate(query, context)
        self._debug_print("RAG generation time:", time.time() - start)
        return {
            "rag_response": rag_response,
            "retrieved_docs": retrieved_docs,
            "scores": scores,
        }

    #-- RAG WITH RULE VERIFICATION ---
    def run_rag_rule(self, query):
        rag_result = self.run_rag(query)
        start = time.time()
        claim_extraction = self.generator.generate_claim_extraction(rag_result["rag_response"])
        claim_doc = extract_claims(claim_extraction)
        self._debug_print("Claim extraction time:", time.time() - start)
        start = time.time()
        violations = verify_claims(claim_doc, self.rules)
        self._debug_print("Claim verification time:", time.time() - start)

        start = time.time()
        verified_response, decision = apply_decision(
            original_answer=rag_result["rag_response"],
            verification_results=violations,
            generator=self.generator
        )
        self._debug_print("Decision application time:", time.time() - start)

        # Debug output
        self._debug_print("\n=== CLAIM EXTRACTION PROMPT ===\n", claim_extraction),
        self._debug_print("\n=== EXTRACTED CLAIMS ===\n", json.dumps(claim_doc, indent=2, ensure_ascii=False))
        self._debug_print("\n=== VIOLATIONS ===\n", violations)
        self._debug_print("\n=== DECISION ===\n", decision)

        return {
            **rag_result,
            "verified_response": verified_response,
            "violations": violations,
            "decision": decision,
        }
    
    # --- MAIN PIPELINE METHOD ---
    def run(self, query):
        llm_response = self.run_llm(query)
        rag_rule_result = self.run_rag_rule(query)
        return {
            "llm_response": llm_response,
            **rag_rule_result,
        }
