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

    def _chat(self, system_prompt, user_prompt, temperature=0.2, max_tokens=2048):
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
        Gunakan hanya informasi yang relevan dengan pertanyaan.
        Hindari penggunaan daftar poin jika memungkinkan, kecuali untuk dosis yang sangat spesifik.
        
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
        Ekstrak parameter terapi klinis dari teks pediatri ke JSON murni. Tanpa markdown.

        PRINSIP:
        1. Hanya ekstrak yang tersurat eksplisit. Jangan inferensi atau tambah informasi.
        2. OMIT semua field yang tidak disebutkan di teks (usia, berat, fase, severity, dll).
        3. Jika tidak ada parameter terapi, kembalikan {"entries": []}.

        ATURAN KLAIM:
        - Setiap kombinasi kondisi-obat yang unik = satu entry.
        - Pisahkan dosis, frekuensi, durasi, dan interval sebagai klaim terpisah.
        - "10 mg/kg 3 kali sehari" → dose: 10 mg/kgbb/kali + frequency: 3 kali/hari (JANGAN dikalikan).
        - Nilai tunggal: min = max. Nilai rentang: isi keduanya.
        - Unit wajib diisi bila ada nilai numerik.
        - contraindication → prohibited: true.

        ENUM (gunakan tepat seperti tertulis):
        - severity: ringan | ringan_sedang | sedang | berat | besar | resisten_cairan | tersangka | refrakter
        - phase: initial | continuation | acute | intensive | maintenance
        - complication: malnutrisi | ensefalopati | bronkopneumonia | meningitis | gangguan_fungsi_jantung | hamil_trimester_akhir | hipernatremia | refraktori | krisis_hipertensi | rawat_inap | rawat_jalan | perdarahan_saluran_kemih | efusi_perikardium | diabetes_mellitus

        SKEMA:
        {"entries": [{"condition": {"disease": str, "age_month_min": float, "age_month_max": float, "weight_kg_min": float, "weight_kg_max": float, "phase": str, "severity": str, "complication": str}, "claim": [{"claim_type": str, "medicine": str, "value_min": float, "value_max": float, "unit": str, "prohibited": true}]}]}
        
        """ + examples_str

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
