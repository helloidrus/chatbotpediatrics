from dotenv import load_dotenv
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
        system_prompt = """
        Ekstrak fakta klinis pediatri ke JSON. Tanpa markdown, tanpa inferensi, hanya yang eksplisit tertulis.

        ATURAN:
        - Setiap kondisi unik maka buat entry terpisah.
        - Jika phase, severity, dan complication tidak disebutkan verbatim maka null.
        - Satu obat + satu kondisi maka satu set claims.
        - Ekstrak masing-masing dose, frequency, interval, atau duration sebagai claim terpisah.
        - Jika field tidak disebut maka null.
        - parameter adalah nama obat persis seperti di teks, tanpa disingkat atau dinormalisasi.
        - Jika claim_type: dose maka dose_context harus diisi.
        - Jika nilai tunggal maka min=max, jika rentang isi keduanya.
        - Unit wajib diisi jika value_min atau value_max tidak null.
        - Jika claim_type: contraindication maka prohibited: true dan lainnya null.
        - evidence_text: kutipan verbatim dari teks.

        ENUM:
        - severity: ringan|ringan-sedang|sedang|berat|besar|resisten_cairan|tersangka|refrakter
        - phase: initial|continuation|acute|intensive|maintenance
        - complication: malnutrisi|ensefalopati|bronkopneumonia|meningitis|gangguan_fungsi_jantung|hamil_trimester_akhir|hipernatremia|refraktori|krisis_hipertensi|rawat_inap|rawat_jalan|perdarahan_saluran_kemih|asma_atau_gagal_jantung|efusi_perikardium
        - claim_type: dose|frequency|duration|interval|contraindication
        - route: oral|iv|im|sc|rektal|inhalasi|intranasal|intratracheal|oral_ngt|iv_bolus|iv_infusion
        - dose_context: per_dose|per_day|per_hour|per_week|total_dose

        OUTPUT:
        {
        "entries": [{
            "condition": {
                "disease": string,
                "age_month_min": float, "age_month_max": float,
                "weight_kg_min": float, "weight_kg_max": float,
                "phase": string, "severity": string, "complication": string },
            "claims": [{
                "claim_type": string, "parameter": string, "route": string,
                "value_min": float, "value_max": float, "unit": string, "dose_context": string, "prohibited": true,
                "evidence_text": string }]
            }]
        }

        """

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
