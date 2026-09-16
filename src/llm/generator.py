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
    def _load_few_shot_examples(self):
        if self._few_shot_examples is not None:
            return self._few_shot_examples

        few_shot_path = Path(__file__).parent / "few_shot_extractor.jsonl"
        examples = []

        if few_shot_path.exists():
            try:
                with open(few_shot_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            examples.append(json.loads(line))
            except Exception as e:
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
        system_prompt = """
        You are a clinical guideline-based pediatric medical assistant.
        """

        user_prompt = f"""
        Answer the question concisely, clearly, and in accordance with pediatric clinical guidelines.
        Use only information that is directly relevant to the question.
        Avoid using bulleted lists whenever possible, except for highly specific dosages.
        If the context mentions conditions/diseases and population criteria (e.g., age or weight) that are relevant to the question, explicitly state those conditions and criteria in your response.

        Context:
        {context}

        Question:
        {query}

        Answer in Indonesian:
        """
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

        system_prompt = """
        Role: Clinical rule extractor for pediatric medical text.

        Task: Extract explicit therapeutic parameters from the provided text into a pure, valid JSON output without markdown formatting. Do NOT add external knowledge or assumptions. If no therapeutic parameters exist, return {"entries": []}.

        Extraction Rules:
        1. Extract ONLY information that is explicitly stated in the source text. Do not infer.
        2. OMIT all fields that are not mentioned in the text (e.g., age, weight, phase, severity). Do not include fields with null values.
        3. Each unique combination of condition (disease/weight/age/phase/severity/complication/care_setting) must become ONE separate object in the `entries` array.
        4. Each unique condition-medicine combination equals one entry.
        5. Separate dose, frequency, interval, and duration into distinct, INDIVIDUAL claim objects within the `claim` array. 
        - Note: Do NOT multiply values (e.g., "10 mg/kg 3 kali sehari" must be split into -> dose: 10 mg/kgbb/kali AND frequency: 3 kali/hari).
        6. Use numeric values (float/int) for bounds. If a single value is specified, set value_min = value_max. For a range, populate both.
        7. Unit is mandatory if there is a numeric value.
        8. Use lowercase and snake_case strings for disease, phase, severity, complication, care_setting, and medicine.
        9. `weight_kg` represents weight in kilograms; `age_month` represents age in months.
        10. `phase` is mandatory if a treatment phase is stated in the text.

        Output Format (MUST BE PURE JSON, NO MARKDOWN):
        {
        "entries": [
            {
            "condition": {
                "disease": "<string>",
                "age_month_min": <float>,
                "age_month_max": <float>,
                "weight_kg_min": <float>,
                "weight_kg_max": <float>,
                "phase": "<MUST BE: initial|maintenance|continuation|stabilization|transition|rehabilitation|relaps_intensive|relaps_maintenance>",
                "severity": "<MUST BE: ringan|sedang|ringan_sedang|berat|krisis>",
                "complication": "<snake_case standard term, e.g., ensefalopati>",
            },
            "claim": [
                {
                "claim_type": "<MUST BE: dose|frequency|interval|duration>",
                "medicine": "<string>",
                "value_min": <float>,
                "value_max": <float>,
                "unit": "<string>"
                }
            ]
            }
        ]
        }

        Examples:
        """ + examples_str + """

        Instruction:
        Extract rules from the provided text below based on the schema and rules above.        

        """

        user_prompt = f"TEXT:{answer_text}"
        
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
        user_prompt = f"""
        Previous answer:
        {original_answer}

        Guideline corrections:
        {guideline_facts_text}

        Rewrite the final answer in Indonesian. Without explaining the verification process.
        """
        return self._chat(
            system_prompt=(
                "You are a pediatric clinical editor."
                "Correct the answer to comply with the guidelines using the minimal necessary changes."
            ),
            user_prompt=user_prompt,
            temperature=0,
        )
