import re


def clean_text(raw_text):
    cleaned = re.sub(r"\n{3,}", "\n\n", raw_text)
    cleaned = re.sub(r"Ikatan Dokter Anak Indonesia.*", "", cleaned)
    return cleaned


def clean_text_file(
    input_text_path="data/processed/ppm_raw.txt",
    output_text_path="data/processed/ppm_clean.txt",
):
    with open(input_text_path, "r", encoding="utf-8") as input_file:
        raw_text = input_file.read()

    cleaned_text = clean_text(raw_text)

    with open(output_text_path, "w", encoding="utf-8") as output_file:
        output_file.write(cleaned_text)

    return output_text_path


def main():
    output_path = clean_text_file(
        input_text_path="data/processed/ppm_raw.txt",
        output_text_path="data/processed/ppm_clean.txt",
    )
    print(f"Cleaning complete: {output_path}")


if __name__ == "__main__":
    main()
