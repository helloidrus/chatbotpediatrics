def chunk_text(text, min_chunk_length=300):
    sections = text.split("\n\n")
    chunks = [section.strip() for section in sections if len(section.strip()) > min_chunk_length]
    return chunks


def chunk_text_file(
    input_text_path="data/processed/ppm_clean.txt",
    output_text_path="data/processed/ppm_chunks.txt",
    min_chunk_length=300,
):
    with open(input_text_path, "r", encoding="utf-8") as input_file:
        text = input_file.read()

    chunks = chunk_text(text, min_chunk_length=min_chunk_length)

    with open(output_text_path, "w", encoding="utf-8") as output_file:
        for chunk in chunks:
            output_file.write(chunk + "\n\n---\n\n")

    return output_text_path, len(chunks)


def main():
    output_path, chunk_count = chunk_text_file(
        input_text_path="data/processed/ppm_clean.txt",
        output_text_path="data/processed/ppm_chunks.txt",
        min_chunk_length=300,
    )
    print(f"Chunks created: {chunk_count} -> {output_path}")


if __name__ == "__main__":
    main()
