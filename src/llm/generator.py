import json
from dotenv import load_dotenv
from pathlib import Path
import os

from openai import OpenAI

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY","").strip()

if not groq_api_key:
    raise RuntimeError("GROQ_API_KEY environment variable is not set.")

client = OpenAI(
    api_key=groq_api_key,
    base_url="https://api.groq.com/openai/v1",
)


class Generator:
    def __init__(self, model_name="openai/gpt-oss-120b"): # "llama-3.1-8b-instant" | "openai/gpt-oss-20b" | "openai/gpt-oss-120b"
        self.model_name = model_name
        self._few_shot_examples = None

    # --- INTERNAL METHODS ---
    def _load_prompt_sections(self, filename):
        prompt_path = Path(__file__).parent / filename
        prompt_text = prompt_path.read_text(encoding="utf-8")
        sections = prompt_text.split("=== USER ===", maxsplit=1)
        if len(sections) != 2 or not sections[0].startswith("=== SYSTEM ==="):
            raise ValueError(f"Prompt must contain SYSTEM and USER sections: {prompt_path}")
        return sections[0].removeprefix("=== SYSTEM ===").strip(), sections[1].strip()

    def _load_few_shot_examples(self):
        if self._few_shot_examples is not None:
            return self._few_shot_examples

        few_shot_path = Path(__file__).parent / "claim_extractor_fewshot.txt"
        examples = []

        if few_shot_path.exists():
            try:
                with open(few_shot_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            examples.append(json.loads(line))
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Gagal memuat few-shot file: {e}")

        self._few_shot_examples = examples
        return self._few_shot_examples

    def _chat(self, system_prompt, user_prompt, temperature=0.2, max_tokens=4096):
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    # --- PUBLIC METHODS ---
    # Metode utama untuk menghasilkan jawaban berdasarkan pertanyaan dan konteks
    def generate(self, query, context=""):
        system_prompt, user_template = self._load_prompt_sections("generator_prompt.txt")
        user_prompt = (
            user_template.replace("__CONTEXT__", context)
            .replace("__QUERY__", query)
        )
        return self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

    # Metode khusus untuk ekstraksi klaim dari jawaban LLM
    def generate_claim_extraction(self, answer_text):
        examples = self._load_few_shot_examples()
        examples_str = ""
        for i, ex in enumerate(examples, 1):
            examples_str += f"\nCONTOH {i}:\nTEXT: \"{ex['text']}\"\nJSON: {json.dumps(ex['json'], indent=2)}\n"

        system_template, user_prompt = self._load_prompt_sections(
            "claim_extraction_prompt.txt"
        )
        system_prompt = system_template.replace("__FEW_SHOT_EXAMPLES__", examples_str)
        user_prompt = user_prompt.replace("__ANSWER_TEXT__", answer_text)
        
        return self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0,
        )

    # Metode untuk meregenerasi jawaban berdasarkan pelanggaran pedoman
    def regenerate_answer(self, original_answer, violations):
        guideline_facts = []
        for violation in violations:
            if "allowed_range" in violation:
                fact = (
                    f"{violation['rule_id']}: the correct value is within "
                    f"{violation['allowed_range']}."
                )
            elif "expected" in violation:
                fact = (
                    f"{violation['rule_id']}: the correct value is "
                    f"{violation['expected']}."
                )
            else:
                fact = f"{violation['rule_id']} was violated."

            guideline_facts.append(fact)
        guideline_facts_text = "\n".join(guideline_facts)
        system_prompt, user_template = self._load_prompt_sections(
            "regeneration_prompt.txt"
        )
        user_prompt = (
            user_template.replace("__ORIGINAL_ANSWER__", original_answer)
            .replace("__GUIDELINE_CORRECTIONS__", guideline_facts_text)
        )
        return self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0,
        )
