# Isi dengan draft jawaban yang ingin diuji.
DRAFT_RESPONSE = """

Durasi olahraga yang direkomendasikan untuk anak dengan diabetes tipe 1 adalah sekitar tiga puluh menit per sesi—termasuk pemanasan selama 10 menit diikuti oleh 20 menit latihan aerobik (misalnya berjalan atau bersepeda). Sesi ini sebaiknya dilakukan minimal tiga kali dalam seminggu pada waktu yang konsisten, dengan penyesuaian intensitas sesuai toleransi anak serta pemantauan gula darah untuk mencegah hipoglikemia. Jika diperlukan, asupan karbohidrat sebelum atau sesudah aktivitas dapat disesuaikan agar kadar glukosa tetap stabil.


"""


def main():
    if not DRAFT_RESPONSE.strip():
        raise ValueError(
            "Isi variabel DRAFT_RESPONSE sebelum menjalankan skrip."
        )

    from src.llm.generator import Generator

    generator = Generator()
    system_prompt, user_template = generator._load_prompt_sections(
        "self_correction_prompt.txt"
    )
    user_prompt = user_template.replace("__DRAFT_RESPONSE__", DRAFT_RESPONSE)
    regenerated_response = generator._chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0,
    )

    print("\nJAWABAN SETELAH REGENERASI (TANPA VERIFIKASI RULE BASE):")
    print(regenerated_response)


if __name__ == "__main__":
    main()
