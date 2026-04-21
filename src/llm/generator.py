import os

from openai import OpenAI


groq_api_key = os.getenv("GROQ_API_KEY")
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
    def generate(self, query, context=""):
        prompt = f"""
        Anda adalah asisten kesehatan anak.
        Jawab pertanyaan dengan singkat, jelas, dan sesuai dengan pedoman klinis pediatri.
        Context:
        {context}
        Question:
        {query}
        Answer in Indonesian:
        """
        return self._chat(
            system_prompt="Anda adalah asisten kesehatan anak berbasis pedoman klinis.",
            user_prompt=prompt,
        )

    # Metode khusus untuk ekstraksi klaim dari jawaban LLM
    def generate_claim_extraction(self, answer_text):
        system_prompt = """
        Anda adalah sistem ekstraksi fakta klinis pediatri.

        Tugas Anda adalah mengekstrak fakta yang eksplisit dari teks medis ke dalam SATU objek JSON yang valid.

        Aturan ekstraksi:
        - Ekstrak hanya informasi yang tertulis eksplisit di teks.
        - Jangan menebak, jangan menambahkan inferensi, dan jangan melengkapi nilai yang tidak ada.
        - Hanya ekstrak field berikut:
          - condition.age_months
          - condition.weight_kg
          - condition.disease
          - claims
        - Hanya izinkan claim_type: dose, frequency, duration.
        - parameter harus berupa nama obat yang eksplisit di teks.
        - value_min dan value_max harus berupa angka atau null.
        - unit harus berupa string singkat atau null.
        - setiap claim wajib memiliki "evidence_text" berupa kutipan teks asli.

        Aturan normalisasi:
        - Jika hanya ada satu nilai, isi value_min dan value_max dengan angka yang sama.
        - Jika ada rentang, isi value_min dan value_max sesuai batas bawah dan batas atas.
        - Jika tidak ada angka yang jelas, jangan buat claim tersebut.
        - Jika umur atau berat badan tidak disebutkan, isi null.
        - Jika penyakit tidak disebutkan, isi null.

        Format output:
        {
          "condition": { "disease": null, "age_months": null, "weight_kg": null },
          "claims": [
            {
              "claim_type": "dose|frequency|duration",
              "parameter": "string",
              "value_min": null,
              "value_max": null,
              "unit": "string"
              "evidence_text": "string"
            }
          ]
        }

        Aturan output:
        - Keluarkan HANYA SATU objek JSON.
        - Jangan tambahkan narasi, penjelasan, markdown, atau code fence.
        - Output harus dimulai dengan { dan diakhiri dengan }.
        """

        user_prompt = f"""
        Ekstrak fakta dari teks berikut:

        {answer_text}
        """
        return self._chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0,
            max_tokens=700,
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
            Jawaban sebelumnya tidak sepenuhnya sesuai dengan pedoman klinis pediatri.
            Jawaban sebelumnya:
            {original_answer}
            Gunakan fakta guideline berikut:
            {guideline_facts_text}
            Tulis ulang jawaban singkat yang sepenuhnya sesuai dengan pedoman medis pediatri.
            """
        return self._chat(
            system_prompt="Anda adalah asisten kesehatan anak berbasis pedoman klinis.",
            user_prompt=user_prompt,
        )
