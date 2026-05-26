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
    def __init__(self, model_name="llama-3.1-8b-instant"):
        self.model_name = model_name

    # --- INTERNAL METHODS ---
    def _chat(self, system_prompt, user_prompt, temperature=0.2, max_tokens=300):
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
        Anda adalah asisten kesehatan anak berbasis pedoman klinis.
        """

        user_prompt = f"""
        Jawab pertanyaan dengan singkat, jelas, dan sesuai dengan pedoman klinis pediatri.
        
        Context:
        {context}

        Question:
        {query}

        Answer in Indonesian:
        """
        return self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    # Metode khusus untuk ekstraksi klaim dari jawaban LLM
    def generate_claim_extraction(self, answer_text):
        # Load few-shot examples colocated with this generator module.
        few_shot_path = Path(__file__).parent / "few_shot_extractor.jsonl"
        examples_str = ""
        if few_shot_path.exists():
            try:
                with open(few_shot_path, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        ex = json.loads(line)
                        examples_str += f"\nCONTOH {i}:\nTEXT: \"{ex['text']}\"\nJSON: {json.dumps(ex['json'], indent=2)}\n"
            except Exception as e:
                # Fallback jika gagal baca file (logging internal)
                print(f"Warning: Gagal memuat few-shot file: {e}")

        system_prompt = """
        Ekstrak fakta klinis pediatri ke JSON. Tanpa markdown, tanpa inferensi, hanya yang eksplisit tertulis.

        ATURAN:
        - Setiap kondisi unik maka buat entry terpisah.
        - Satu obat + satu kondisi maka satu set claims.
        - Ekstrak masing-masing dose, frequency, interval, dan duration sebagai claim terpisah.
        - medicine harus atomik, hanya satu obat/cairan per field.
        - medicine adalah nama obat persis seperti di teks, tanpa disingkat atau dinormalisasi.
        - Jika nilai tunggal maka min=max, jika rentang isi keduanya.
        - Unit wajib diisi jika value_min atau value_max tidak null.
        - Jika claim_type: contraindication maka prohibited: true.
        - evidence_text harus berupa kutipan verbatim pendek yang langsung mendukung claim.
        - Jika suatu field tidak memiliki nilai, OMIT field tersebut dari output JSON.
        - Jika teks menyebutkan dosis "per kali" DAN frekuensi terpisah, ekstrak keduanya sebagai claim terpisah dengan unit yang tepat.
        - "10 mg/kg 3 kali sehari" → dose: 10 mg/kgbb/kali + frequency: 3 kali/hari, BUKAN dose: 30 mg/kgbb/hari

        ENUM:
        - severity: ringan|ringa_sedang|sedang|berat|besar|resisten_cairan|tersangka|refrakter
        - phase: initial|continuation|acute|intensive|maintenance
        - complication: malnutrisi|ensefalopati|bronkopneumonia|meningitis|gangguan_fungsi_jantung|hamil_trimester_akhir|hipernatremia|refraktori|krisis_hipertensi|rawat_inap|rawat_jalan|perdarahan_saluran_kemih|efusi_perikardium|diabetes_mellitus
        - claim_type: dose|frequency|duration|interval|contraindication

        OUTPUT:
        {
        "entries": [{
            "condition": { "disease": string, "age_month_min": float, "age_month_max": float, "weight_kg_min": float, "weight_kg_max": float, "phase": string, "severity": string, "complication": string },
            "claims": [{ "claim_type": string, "medicine": string, "value_min": float, "value_max": float, "unit": string, "prohibited": true, "evidence_text": string }]
            }]
        }
        """ + examples_str

        user_prompt = f"TEXT:{answer_text}"
        
        return self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0,
            max_tokens=999,
        )

    # Metode untuk meregenerasi jawaban berdasarkan pelanggaran pedoman
    def regenerate_answer(self, original_answer, violations):
        guideline_facts = []
        for violation in violations:
            if "allowed_range" in violation:
                fact = (
                    f"{violation['rule_id']}: nilai yang benar berada pada "
                    f"{violation['allowed_range']}."
                )
            elif "expected" in violation:
                fact = (
                    f"{violation['rule_id']}: nilai yang benar adalah "
                    f"{violation['expected']}."
                )
            else:
                fact = f"{violation['rule_id']} dilanggar."

            guideline_facts.append(fact)
        guideline_facts_text = "\n".join(guideline_facts)
        user_prompt = f"""
        Jawaban sebelumnya:
        {original_answer}

        Koreksi guideline:
        {guideline_facts_text}

        Tulis ulang jawaban final dalam bahasa Indonesia.

        Aturan:
        - Pertahankan singkatnya.
        - Ubah hanya bagian yang salah.
        - Tanpa permintaan maaf, pembuka, penjelasan, atau proses verifikasi.
        - Keluarkan hanya jawaban final.
        """
        return self._chat(
            system_prompt=(
                "Anda editor klinis pediatri."
                "Perbaiki jawaban agar sesuai guideline dengan perubahan seminimal mungkin."
            ),
            user_prompt=user_prompt,
            temperature=0,
        )
