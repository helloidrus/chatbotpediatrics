from pypdf import PdfReader


def extract_pdf_text(
    input_pdf_path="data/raw/Buku-PPM.pdf",
    output_text_path="data/processed/ppm_raw.txt",
):
    reader = PdfReader(input_pdf_path)
    full_text = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text:
            full_text.append(f"\n\n=== PAGE {page_number} ===\n\n{text}")

    with open(output_text_path, "w", encoding="utf-8") as output_file:
        output_file.write("".join(full_text))

    return output_text_path


def main():
    output_path = extract_pdf_text(
        input_pdf_path="data/raw/Buku-PPM.pdf",
        output_text_path="data/processed/ppm_raw.txt",
    )
    print(f"Extraction complete: {output_path}")


if __name__ == "__main__":
    main()
