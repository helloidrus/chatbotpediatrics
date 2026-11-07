import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from pypdf import PdfReader


def muat_teks_sumber(file_sumber_path):
    """Memuat teks lengkap dari dokumen pedoman rujukan asli."""
    file_sumber_path = Path(file_sumber_path)
    if file_sumber_path.suffix.casefold() == ".pdf":
        reader = PdfReader(str(file_sumber_path))
        return "".join(
            f"\n\n=== PAGE {page_number} ===\n\n{page.extract_text() or ''}"
            for page_number, page in enumerate(reader.pages, start=1)
        )

    with open(file_sumber_path, "r", encoding="utf-8") as file:
        return file.read()


def bersihkan_teks(teks):
    """Normalisasi format baris, spasi, dan kapitalisasi untuk pencocokan."""
    if not teks:
        return ""
    teks = re.sub(
        r"(?m)^=== PAGE \d+ ===[ \t]*\r?\n(?:[ \t]*\r?\n)*"
        r"(?:Pedoman Pelayanan Medis\s+\d{1,3}\b|\d{1,3}\s{2,}[^\r\n]+)"
        r"[ \t]*\r?\n?",
        " ",
        teks,
    )
    teks = re.sub(r"(?m)^=== PAGE \d+ ===\s*$", " ", teks)
    teks = teks.replace("\u0372", "-")
    teks = re.sub(r"(?<=\s)-[ \t]*\r?\n[ \t]*", " ", teks)
    teks = re.sub(r"\s+", " ", teks)
    return teks.strip().lower()


def normalisasi_tanpa_format(teks):
    """Hilangkan spasi dan tanda baca untuk menangani pemenggalan OCR."""
    teks = teks.replace("\u0372", "-")
    return "".join(karakter for karakter in teks.casefold() if karakter.isalnum())


def tokenisasi_bukti(teks):
    return re.findall(
        r"\d+(?:[.,]\d+)*|[^\W\d_]+|[<>≤≥]",
        teks.casefold(),
        flags=re.UNICODE,
    )


def ambil_halaman_buku(nomor_halaman, teks_sumber):
    if not isinstance(nomor_halaman, int):
        return ""

    penanda_halaman = list(
        re.finditer(r"(?m)^=== PAGE \d+ ===\s*$", teks_sumber)
    )
    for indeks, penanda in enumerate(penanda_halaman):
        awal_halaman = penanda.end()
        akhir_halaman = (
            penanda_halaman[indeks + 1].start()
            if indeks + 1 < len(penanda_halaman)
            else len(teks_sumber)
        )
        isi_halaman = teks_sumber[awal_halaman:akhir_halaman]
        for baris in isi_halaman.splitlines()[:8]:
            baris = baris.strip()
            nomor_ditemukan = re.match(
                r"^Pedoman Pelayanan Medis\s+(\d{1,3})\b",
                baris,
                flags=re.IGNORECASE,
            ) or re.match(r"^(\d{1,3})\s{2,}", baris)
            if nomor_ditemukan and int(nomor_ditemukan.group(1)) == nomor_halaman:
                return isi_halaman
    return ""


def cocokkan_kutipan_ocr_halaman(rule, teks_ocr):
    metadata = rule.get("metadata", {})
    kutipan = metadata.get("text", "")
    isi_halaman = ambil_halaman_buku(metadata.get("page"), teks_ocr)
    if not kutipan or not isi_halaman:
        return False

    teks_kutipan_normal = bersihkan_teks(kutipan)
    teks_halaman_normal = bersihkan_teks(isi_halaman)
    return bool(teks_kutipan_normal) and teks_kutipan_normal in teks_halaman_normal


def cocokkan_obat_dengan_barisan_dosis(rule, rules_sehalaman, isi_halaman):
    claim = rule.get("claim", {})
    nama_obat = claim.get("medicine", "").replace("_", " ").strip()
    if not nama_obat:
        return False

    baris_halaman = isi_halaman.splitlines()
    awal_tabel = next(
        (
            indeks
            for indeks, baris in enumerate(baris_halaman)
            if "jenis obat" in bersihkan_teks(baris)
            and "dosis" in bersihkan_teks(baris)
        ),
        None,
    )
    if awal_tabel is None:
        return False

    akhir_tabel = next(
        (
            indeks
            for indeks in range(awal_tabel + 1, len(baris_halaman))
            if re.match(
                r"^\s*tabel\s+\d+\.",
                baris_halaman[indeks],
                flags=re.IGNORECASE,
            )
        ),
        len(baris_halaman),
    )
    teks_tabel = "\n".join(baris_halaman[awal_tabel:akhir_tabel])

    label_obat = {}
    for rule_lain in rules_sehalaman:
        label = (
            rule_lain.get("claim", {})
            .get("medicine", "")
            .replace("_", " ")
            .strip()
        )
        if not label:
            continue
        pola_kata = lambda kata: r"(?:-\s*)?".join(
            map(re.escape, kata.casefold())
        )
        pola_label = re.compile(
            r"(?<!\w)"
            + r"\s+".join(map(pola_kata, label.split()))
            + r"(?!\w)",
            flags=re.IGNORECASE,
        )
        kecocokan = pola_label.search(teks_tabel)
        if kecocokan:
            label_obat.setdefault(
                label.casefold(),
                (label, kecocokan.start(), kecocokan.end()),
            )

    target = nama_obat.casefold()
    if target not in label_obat:
        return False

    label_terurut = sorted(label_obat.values(), key=lambda item: item[1])
    indeks_target = next(
        (
            indeks
            for indeks, item in enumerate(label_terurut)
            if item[0].casefold() == target
        ),
        None,
    )
    if indeks_target is None:
        return False

    awal_grup = indeks_target
    while (
        awal_grup > 0
        and teks_tabel[label_terurut[awal_grup - 1][2] : label_terurut[awal_grup][1]]
        .strip()
        == ""
    ):
        awal_grup -= 1

    akhir_grup = indeks_target
    while (
        akhir_grup + 1 < len(label_terurut)
        and teks_tabel[label_terurut[akhir_grup][2] : label_terurut[akhir_grup + 1][1]]
        .strip()
        == ""
    ):
        akhir_grup += 1

    posisi_awal_data = label_terurut[akhir_grup][2]
    posisi_akhir_data = (
        label_terurut[akhir_grup + 1][1]
        if akhir_grup + 1 < len(label_terurut)
        else len(teks_tabel)
    )
    teks_data = teks_tabel[posisi_awal_data:posisi_akhir_data]
    kutipan_per_obat = {}
    for item in label_terurut[awal_grup : akhir_grup + 1]:
        alias = item[0].casefold()
        kutipan_unik = []
        for rule_lain in rules_sehalaman:
            if (
                rule_lain.get("claim", {})
                .get("medicine", "")
                .replace("_", " ")
                .strip()
                .casefold()
                != alias
            ):
                continue
            kutipan = rule_lain.get("metadata", {}).get("text", "")
            if kutipan and kutipan not in kutipan_unik:
                kutipan_unik.append(kutipan)
        kutipan_per_obat[alias] = kutipan_unik

    pola_awal_dosis = re.compile(
        r"(?im)^[ \t]*(?:"
        r"dosis\b(?!\s*maksimum)(?:\s*:|\s+(?=\d))"
        r"|dosis\s+awal\b"
        r"|anak\b"
        r"|[<>≤≥]?\s*\d+\s*(?:s/d|sampai)\s*\d+\s*tahun\b"
        r"|[<>≤≥]\s*\d+\s*tahun\b"
        r")"
    )
    awal_dosis = []
    for kecocokan in pola_awal_dosis.finditer(teks_data):
        if awal_dosis:
            teks_sebelumnya = teks_data[
                awal_dosis[-1].start() : kecocokan.start()
            ]
            if (
                awal_dosis[-1].group().strip().casefold().startswith("anak")
                and kecocokan.group().strip().casefold().startswith("dosis")
                and not re.search(r"\b(?:mg|ml|kg|hari)\b", teks_sebelumnya)
            ):
                continue
        awal_dosis.append(kecocokan)
    jumlah_dosis = sum(
        len(kutipan_per_obat[item[0].casefold()])
        for item in label_terurut[awal_grup : akhir_grup + 1]
    )
    if len(awal_dosis) != jumlah_dosis:
        return False

    alias_target = label_terurut[indeks_target][0].casefold()
    kutipan_target = rule.get("metadata", {}).get("text", "")
    kutipan_target_obat = kutipan_per_obat[alias_target]
    if kutipan_target not in kutipan_target_obat:
        return False
    indeks_dosis = sum(
        len(kutipan_per_obat[item[0].casefold()])
        for item in label_terurut[awal_grup:indeks_target]
    ) + kutipan_target_obat.index(kutipan_target)

    batas_awal = awal_dosis[indeks_dosis].start()
    batas_akhir = (
        awal_dosis[indeks_dosis + 1].start()
        if indeks_dosis + 1 < len(awal_dosis)
        else len(teks_data)
    )
    teks_dosis = teks_data[batas_awal:batas_akhir]
    token_kutipan = Counter(tokenisasi_bukti(rule["metadata"].get("text", "")))
    token_obat = Counter(tokenisasi_bukti(nama_obat))
    token_kutipan.subtract(token_obat)
    token_kutipan = +token_kutipan
    return not token_kutipan - Counter(tokenisasi_bukti(teks_dosis))


def cocokkan_obat_di_tabel_baris(rule, rules_sehalaman, isi_halaman):
    nama_obat = (
        rule.get("claim", {})
        .get("medicine", "")
        .replace("_", " ")
        .strip()
    )
    kutipan = rule.get("metadata", {}).get("text", "")
    if not nama_obat or not kutipan:
        return False

    pola_judul = re.compile(r"(?im)^[ \t]*tabel\s+\d+\.")
    judul = list(pola_judul.finditer(isi_halaman))
    for indeks, awal in enumerate(judul):
        akhir = judul[indeks + 1].start() if indeks + 1 < len(judul) else len(isi_halaman)
        teks_tabel = isi_halaman[awal.start() : akhir]
        kata_tabel = list(re.finditer(r"[^\W_]+", teks_tabel, flags=re.UNICODE))
        if not kata_tabel:
            continue

        cocok_obat = {}
        for rule_lain in rules_sehalaman:
            label = (
                rule_lain.get("claim", {})
                .get("medicine", "")
                .replace("_", " ")
                .strip()
            )
            if not label:
                continue
            kata_label = re.findall(r"[^\W_]+", label, flags=re.UNICODE)
            target_label = "".join(kata.casefold() for kata in kata_label)
            kandidat_terbaik = None
            for posisi_awal in range(len(kata_tabel)):
                lebar_maksimum = min(len(kata_label) + 2, len(kata_tabel) - posisi_awal)
                for lebar in range(1, lebar_maksimum + 1):
                    kata_kandidat = kata_tabel[posisi_awal : posisi_awal + lebar]
                    teks_kandidat = "".join(
                        kata.group().casefold() for kata in kata_kandidat
                    )
                    rasio = SequenceMatcher(
                        None,
                        target_label,
                        teks_kandidat,
                    ).ratio()
                    if kandidat_terbaik is None or rasio > kandidat_terbaik[0]:
                        kandidat_terbaik = (
                            rasio,
                            kata_kandidat[0].start(),
                            kata_kandidat[-1].end(),
                        )
            if kandidat_terbaik and kandidat_terbaik[0] >= 0.9:
                cocok_obat.setdefault(
                    label.casefold(),
                    (label, kandidat_terbaik[1], kandidat_terbaik[2]),
                )

        target = nama_obat.casefold()
        if target not in cocok_obat:
            continue

        label_terurut = sorted(cocok_obat.values(), key=lambda item: item[1])
        indeks_target = next(
            (
                i
                for i, item in enumerate(label_terurut)
                if item[0].casefold() == target
            ),
            None,
        )
        if indeks_target is None:
            continue

        batas_awal = label_terurut[indeks_target][2]
        batas_akhir = (
            label_terurut[indeks_target + 1][1]
            if indeks_target + 1 < len(label_terurut)
            else len(teks_tabel)
        )
        teks_baris = teks_tabel[batas_awal:batas_akhir]
        token_kutipan = Counter(tokenisasi_bukti(kutipan))
        token_nama = Counter(tokenisasi_bukti(nama_obat))
        token_kutipan.subtract(token_nama)
        token_kutipan = +token_kutipan
        token_bukti = Counter(tokenisasi_bukti(teks_baris))

        header_akhir = label_terurut[0][1]
        token_bukti.update(
            tokenisasi_bukti(teks_tabel[:header_akhir])
        )
        if not token_kutipan - token_bukti:
            return True

    return False


def cocokkan_obat_di_tabel_kolom(rule, rules_sehalaman, isi_halaman):
    nama_target = (
        rule.get("claim", {})
        .get("medicine", "")
        .replace("_", " ")
        .strip()
    )
    kutipan_target = rule.get("metadata", {}).get("text", "")
    if not nama_target or not kutipan_target:
        return False

    judul_tabel = list(re.finditer(r"(?im)^[ \t]*tabel\s+\d+\.", isi_halaman))
    segmen_tabel = [
        (
            judul.start(),
            judul_tabel[indeks + 1].start()
            if indeks + 1 < len(judul_tabel)
            else len(isi_halaman),
        )
        for indeks, judul in enumerate(judul_tabel)
    ]
    batas_awal_tabel_lanjutan = (
        judul_tabel[0].start() if judul_tabel else len(isi_halaman)
    )
    awalan_halaman = isi_halaman[:batas_awal_tabel_lanjutan]
    if (
        re.search(r"\bjenis\s+obat\b", bersihkan_teks(awalan_halaman))
        and re.search(r"\bdosis\s+dan\s+interval\b", bersihkan_teks(awalan_halaman))
    ):
        segmen_tabel.insert(0, (0, batas_awal_tabel_lanjutan))

    for awal_tabel, akhir_tabel in segmen_tabel:
        teks_tabel = isi_halaman[awal_tabel:akhir_tabel]
        baris = []
        posisi = 0
        for teks_baris in teks_tabel.splitlines(keepends=True):
            teks_bersih = teks_baris.strip()
            if teks_bersih:
                baris.append((posisi, teks_bersih))
            posisi += len(teks_baris)

        pola_awal_dosis = re.compile(
            r"^(?:dosis\b(?!\s*maksimum)(?:\s*:|\s+(?=\d))|"
            r"anak\b|[<>≤≥]\s*\d+|"
            r"\d+\s*(?:s/d|sampai)\s*\d+\s*tahun\b)",
            flags=re.IGNORECASE,
        )
        pola_dosis_inline = re.compile(
            r"\bdosis\b(?!\s*maksimum)(?:\s*:|\s+(?=\d))",
            flags=re.IGNORECASE,
        )
        pola_kondisi_usia_inline = re.compile(
            r"\banak\s*[<>≤≥]\s*\d+",
            flags=re.IGNORECASE,
        )
        awal_dosis = []
        for indeks_baris, (posisi, teks_baris) in enumerate(baris):
            awal_teks = len(teks_baris) - len(teks_baris.lstrip())
            teks_bersih = teks_baris.strip()
            awal_garis = posisi + awal_teks
            if pola_awal_dosis.match(teks_bersih):
                awal_dosis.append(
                    (awal_garis, teks_bersih.casefold().startswith("anak"))
                )
                continue

            kondisi_usia_inline = pola_kondisi_usia_inline.search(teks_baris)
            dosis_di_baris_berikutnya = (
                indeks_baris + 1 < len(baris)
                and pola_awal_dosis.match(baris[indeks_baris + 1][1])
            )
            if kondisi_usia_inline and dosis_di_baris_berikutnya:
                awal_dosis.append(
                    (posisi + kondisi_usia_inline.start(), True)
                )
                continue

            dosis_inline = pola_dosis_inline.search(teks_baris)
            if dosis_inline:
                awal_dosis.append((posisi + dosis_inline.start(), False))

        awal_dosis = sorted(set(awal_dosis))
        awal_dosis_tanpa_duplikat = []
        for posisi, konteks_usia in awal_dosis:
            if awal_dosis_tanpa_duplikat:
                posisi_sebelumnya, konteks_usia_sebelumnya = (
                    awal_dosis_tanpa_duplikat[-1]
                )
                teks_di_antara = teks_tabel[posisi_sebelumnya:posisi]
                if (
                    konteks_usia_sebelumnya
                    and not re.search(r"\b(?:mg|ml|kg|hari)\b", teks_di_antara)
                ):
                    continue
            awal_dosis_tanpa_duplikat.append((posisi, konteks_usia))
        awal_dosis = [posisi for posisi, _ in awal_dosis_tanpa_duplikat]
        if not awal_dosis:
            continue

        kata_tabel = list(re.finditer(r"[^\W_]+", teks_tabel, flags=re.UNICODE))
        obat_ditemukan = {}
        for aturan in rules_sehalaman:
            nama_obat = (
                aturan.get("claim", {})
                .get("medicine", "")
                .replace("_", " ")
                .strip()
            )
            nama_normalisasi = nama_obat.casefold()
            if not nama_obat or nama_normalisasi in obat_ditemukan:
                continue
            kata_nama = re.findall(r"[^\W_]+", nama_obat, flags=re.UNICODE)
            nama_normal = "".join(kata.casefold() for kata in kata_nama)
            kandidat_terbaik = None
            for awal in range(len(kata_tabel)):
                for lebar in range(
                    max(1, len(kata_nama) - 1),
                    min(len(kata_nama) + 2, len(kata_tabel) - awal) + 1,
                ):
                    potongan = kata_tabel[awal : awal + lebar]
                    teks_potongan = "".join(
                        kata.group().casefold() for kata in potongan
                    )
                    skor = SequenceMatcher(
                        None,
                        nama_normal,
                        teks_potongan,
                    ).ratio()
                    posisi_awal = potongan[0].start()
                    if kandidat_terbaik is None or skor > kandidat_terbaik[0]:
                        kandidat_terbaik = (skor, posisi_awal)
                    elif skor == kandidat_terbaik[0]:
                        kandidat_terbaik = (
                            skor,
                            min(posisi_awal, kandidat_terbaik[1]),
                        )
            if kandidat_terbaik and kandidat_terbaik[0] >= 0.82:
                obat_ditemukan[nama_normalisasi] = kandidat_terbaik[1]

        obat_terurut = sorted(
            (posisi, nama_obat)
            for nama_obat, posisi in obat_ditemukan.items()
        )
        if not obat_terurut:
            continue

        kutipan_per_obat = {}
        for aturan in rules_sehalaman:
            nama_obat = (
                aturan.get("claim", {})
                .get("medicine", "")
                .replace("_", " ")
                .strip()
                .casefold()
            )
            kutipan = aturan.get("metadata", {}).get("text", "")
            if nama_obat and kutipan:
                daftar = kutipan_per_obat.setdefault(nama_obat, [])
                if kutipan not in daftar:
                    daftar.append(kutipan)

        kelompok_obat = []
        for posisi_obat, nama_obat in obat_terurut:
            if not kelompok_obat or any(
                kelompok_obat[-1]["akhir_obat"] < posisi_dosis < posisi_obat
                for posisi_dosis in awal_dosis
            ):
                kelompok_obat.append(
                    {
                        "obat": [],
                        "awal_obat": posisi_obat,
                        "akhir_obat": posisi_obat,
                    }
                )
            kelompok_obat[-1]["obat"].append(nama_obat)
            kelompok_obat[-1]["akhir_obat"] = posisi_obat

        for indeks_kelompok, kelompok in enumerate(kelompok_obat):
            posisi_awal_blok = kelompok["akhir_obat"]
            posisi_akhir_blok = (
                kelompok_obat[indeks_kelompok + 1]["awal_obat"]
                if indeks_kelompok + 1 < len(kelompok_obat)
                else len(teks_tabel)
            )
            blok_kelompok = [
                posisi
                for posisi in awal_dosis
                if posisi_awal_blok < posisi < posisi_akhir_blok
            ]
            jumlah_blok_diharapkan = sum(
                len(kutipan_per_obat.get(nama_obat, []))
                for nama_obat in kelompok["obat"]
            )
            if jumlah_blok_diharapkan != len(blok_kelompok):
                continue

            if nama_target.casefold() not in kelompok["obat"]:
                continue
            indeks_obat_target = kelompok["obat"].index(nama_target.casefold())
            try:
                indeks_kutipan_target = kutipan_per_obat[
                    nama_target.casefold()
                ].index(kutipan_target)
            except (KeyError, ValueError):
                continue

            indeks_blok_target = (
                sum(
                    len(kutipan_per_obat[nama_obat])
                    for nama_obat in kelompok["obat"][:indeks_obat_target]
                )
                + indeks_kutipan_target
            )
            awal_blok = blok_kelompok[indeks_blok_target]
            akhir_blok = (
                blok_kelompok[indeks_blok_target + 1]
                if indeks_blok_target + 1 < len(blok_kelompok)
                else posisi_akhir_blok
            )
            teks_blok = teks_tabel[awal_blok:akhir_blok]

            awal_kutipan = re.search(
                r"(?:dosis\b|anak\b|[<>≤≥]\s*\d+|"
                r"\d+\s*(?:s/d|sampai)\s*\d+\s*tahun\b)",
                kutipan_target,
                flags=re.IGNORECASE,
            )
            teks_klaim = (
                kutipan_target[awal_kutipan.start() :]
                if awal_kutipan
                else kutipan_target
            )
            if not (
                Counter(tokenisasi_bukti(teks_klaim))
                - Counter(tokenisasi_bukti(teks_blok))
            ):
                return True

    return False


def cocokkan_kutipan_tabel_isk(rule, rules_sehalaman, isi_halaman):
    baris = isi_halaman.splitlines()
    judul = next(
        (
            indeks
            for indeks, teks in enumerate(baris)
            if "tabel 2. dosis antibiotika parenteral" in bersihkan_teks(teks)
            and "pengobatan isk" in bersihkan_teks(teks)
        ),
        None,
    )
    if judul is None:
        return False

    awal_parenteral = next(
        (
            indeks
            for indeks in range(judul + 1, len(baris))
            if bersihkan_teks(baris[indeks]) == "(a) parenteral"
        ),
        None,
    )
    awal_oral = next(
        (
            indeks
            for indeks in range(judul + 1, len(baris))
            if bersihkan_teks(baris[indeks]) == "(b) oral"
        ),
        None,
    )
    awal_profilaksis = next(
        (
            indeks
            for indeks in range(judul + 1, len(baris))
            if re.search(
                r"\(c\)\s*terapi\s*profilaksis",
                bersihkan_teks(baris[indeks]),
            )
        ),
        None,
    )
    if (
        awal_parenteral is None
        or awal_oral is None
        or awal_profilaksis is None
    ):
        return False

    aturan_obat = [
        item
        for item in rules_sehalaman
        if item.get("claim", {}).get("medicine")
    ]
    aliases = {
        normalisasi_tanpa_format(
            item["claim"]["medicine"].replace("_", " ")
        ): item["claim"]["medicine"].replace("_", " ")
        for item in aturan_obat
    }

    def baris_obat(section):
        hasil = []
        for indeks, teks in enumerate(section):
            nama = normalisasi_tanpa_format(teks.rstrip("*"))
            if nama in aliases:
                hasil.append((indeks, aliases[nama]))
        return hasil

    def baris_dosis(section, obat):
        if not obat:
            return []
        indeks_akhir_obat = max(indeks for indeks, _ in obat)
        hasil = []
        pola_dosis = re.compile(
            r"^\s*\d+(?:\s*[-–]\s*\d+)?"
            r"(?:\s*mg/kg(?:/hari)?)?\s*$",
            flags=re.IGNORECASE,
        )
        pola_frekuensi = re.compile(
            r"\b(?:tiap|dibagi|sekali\s+sehari|q\s*\d)",
            flags=re.IGNORECASE,
        )
        for indeks in range(indeks_akhir_obat + 1, len(section)):
            teks = section[indeks].strip()
            if pola_frekuensi.search(teks):
                break
            if pola_dosis.fullmatch(teks):
                hasil.append((indeks, teks))
        return hasil

    def nilai_klaim_cocok(claim, teks_dosis):
        minimum = claim.get("value_min")
        maksimum = claim.get("value_max")
        if minimum is None:
            return False
        angka_dosis = [
            float(angka.replace(",", "."))
            for angka in re.findall(r"\d+(?:[.,]\d+)?", teks_dosis)
        ]
        nilai_harapan = [float(minimum)]
        if maksimum is not None and float(maksimum) != float(minimum):
            nilai_harapan.append(float(maksimum))
        return all(nilai in angka_dosis for nilai in nilai_harapan)

    def kutipan_obat_pada_dosis(nama_obat, teks_dosis):
        kandidat = []
        for item in aturan_obat:
            if (
                item["claim"]["medicine"].replace("_", " ").casefold()
                != nama_obat.casefold()
                or item.get("claim", {}).get("claim_type") != "dose"
                or not nilai_klaim_cocok(item["claim"], teks_dosis)
            ):
                continue
            kutipan = item.get("metadata", {}).get("text", "")
            if kutipan and kutipan not in kandidat:
                kandidat.append(kutipan)
        return kandidat

    def cocokkan_section(section, header, tipe):
        obat = baris_obat(section)
        dosis = baris_dosis(section, obat)
        if len(obat) != len(dosis):
            return False

        if tipe == "parenteral":
            kutipan_per_obat = []
            for posisi, (_, nama) in enumerate(obat):
                kutipan = kutipan_obat_pada_dosis(nama, dosis[posisi][1])
                if not kutipan:
                    return False
                kutipan_per_obat.append(kutipan[0])
            pola_frekuensi = re.compile(
                r"\b(?:tiap\s+\d+(?:\s*-\s*\d+)?\s*jam"
                r"|dibagi\s+(?:setiap\s+)?\d+(?:\s*-\s*\d+)?\s*jam"
                r"|sekali\s+sehari)\b",
                flags=re.IGNORECASE,
            )
            awal_frekuensi = next(
                (
                    indeks
                    for indeks in range(max(i for i, _ in obat) + 1, len(section))
                    if pola_frekuensi.search(section[indeks])
                ),
                None,
            )
            if awal_frekuensi is None:
                return False
            frekuensi = [
                teks.strip()
                for teks in section[awal_frekuensi:]
                if pola_frekuensi.search(teks)
            ]
            jumlah_per_obat = [
                len(pola_frekuensi.findall(kutipan))
                for kutipan in kutipan_per_obat
            ]
        else:
            pola_frekuensi = re.compile(
                r"\bq\s*\d+(?:\s*-\s*\d+)?\s*h\b",
                flags=re.IGNORECASE,
            )
            bagian_frekuensi = section[
                max(i for i, _ in obat) + 1 :
            ]
            frekuensi = [
                kecocokan.group()
                for teks in bagian_frekuensi
                for kecocokan in pola_frekuensi.finditer(teks)
            ]
            jumlah_per_obat = [1] * len(obat)

        if sum(jumlah_per_obat) != len(frekuensi):
            return False

        posisi_frekuensi = 0
        for indeks_obat, ((_, nama_obat), (_, teks_dosis)) in enumerate(
            zip(obat, dosis)
        ):
            jumlah = jumlah_per_obat[indeks_obat]
            bukti_frekuensi = frekuensi[
                posisi_frekuensi : posisi_frekuensi + jumlah
            ]
            posisi_frekuensi += jumlah
            claim_target = rule.get("claim", {})
            nama_target = (
                claim_target.get("medicine", "")
                .replace("_", " ")
                .casefold()
            )
            if nama_obat.casefold() != nama_target:
                continue
            if claim_target.get("claim_type") == "dose" and not nilai_klaim_cocok(
                claim_target,
                teks_dosis,
            ):
                return False
            token_bukti = Counter(
                tokenisasi_bukti(
                    " ".join(
                        [
                            header,
                            nama_obat,
                            teks_dosis,
                            *bukti_frekuensi,
                        ]
                    )
                )
            )
            token_kutipan = Counter(
                tokenisasi_bukti(rule.get("metadata", {}).get("text", ""))
            )
            if not token_kutipan - token_bukti:
                return True
        return False

    section_a = baris[awal_parenteral + 1 : awal_oral]
    baris_header = " ".join(baris[judul:awal_parenteral])
    if cocokkan_section(section_a, baris_header, "parenteral"):
        return True

    akhir_tabel = next(
        (
            indeks
            for indeks in range(awal_oral + 1, len(baris))
            if re.match(r"^\s*tabel\s+\d+\.", baris[indeks], re.IGNORECASE)
        ),
        len(baris),
    )
    section_b = baris[awal_oral + 1 : akhir_tabel]
    teks_marker_profilaksis = baris[awal_profilaksis]
    if cocokkan_section(section_b, baris_header, "oral"):
        return True

    teks_kutipan = rule.get("metadata", {}).get("text", "")
    if not re.search(r"\(c\)\s*terapi\s*profilaksis", teks_kutipan, re.I):
        return False

    obat_oral = baris_obat(section_b)
    if len(obat_oral) < 4:
        return False
    indeks_obat_profilaksis = next(
        (
            indeks
            for indeks, (_, nama) in enumerate(obat_oral[-4:])
            if nama.casefold()
            == rule.get("claim", {})
            .get("medicine", "")
            .replace("_", " ")
            .casefold()
        ),
        None,
    )
    if indeks_obat_profilaksis is None:
        return False

    baris_c = [
        teks.strip()
        for teks in baris[awal_profilaksis + 1 :]
        if re.search(r"\d+(?:\s*-\s*\d+)?\s*mg/kg", teks, re.I)
    ]
    if len(baris_c) != 4:
        return False
    teks_dosis = baris_c[indeks_obat_profilaksis]
    if not nilai_klaim_cocok(rule.get("claim", {}), teks_dosis):
        return False
    bukti = " ".join(
        [
            baris_header,
            teks_marker_profilaksis,
            *baris[
                max(awal_profilaksis - 1, 0) : min(awal_profilaksis + 2, len(baris))
            ],
            teks_dosis,
        ]
    )
    return not Counter(tokenisasi_bukti(teks_kutipan)) - Counter(
        tokenisasi_bukti(bukti)
    )


def cocokkan_kutipan_tabel_isk_kolom(rule, isi_halaman):
    kutipan = rule.get("metadata", {}).get("text", "")
    if not kutipan:
        return False

    baris = isi_halaman.splitlines()
    judul = next(
        (
            indeks
            for indeks, teks in enumerate(baris)
            if "tabel 2. dosis antibiotika parenteral" in bersihkan_teks(teks)
            and "pengobatan isk" in bersihkan_teks(teks)
        ),
        None,
    )
    if judul is None:
        return False

    awal_oral = next(
        (
            indeks
            for indeks in range(judul + 1, len(baris))
            if bersihkan_teks(baris[indeks]) == "(b) oral"
        ),
        None,
    )
    akhir_tabel = next(
        (
            indeks
            for indeks in range(judul + 1, len(baris))
            if re.match(r"^\s*tabel\s+\d+\.", baris[indeks], re.IGNORECASE)
        ),
        len(baris),
    )
    if awal_oral is None:
        return False

    bagian_oral = baris[awal_oral + 1 : akhir_tabel]
    pola_dosis = re.compile(r"^\s*\d+(?:\s*[-–]\s*\d+)?(?:\s|$)")
    indeks_dosis = next(
        (
            indeks
            for indeks, teks in enumerate(bagian_oral)
            if pola_dosis.match(teks)
        ),
        None,
    )
    if indeks_dosis is None:
        return False

    indeks_frekuensi = next(
        (
            indeks
            for indeks in range(indeks_dosis, len(bagian_oral))
            if re.search(r"\bq\s*\d+(?:\s*-\s*\d+)?\s*h\b", bagian_oral[indeks], re.I)
        ),
        None,
    )
    if indeks_frekuensi is None:
        return False

    teks_obat = bagian_oral[:indeks_dosis]
    teks_dosis = bagian_oral[indeks_dosis:indeks_frekuensi]
    teks_frekuensi = bagian_oral[indeks_frekuensi:]
    pola_label = re.compile(
        r"^\s*([^\d:]+?)\s+(?=(?:\d|[(*]))",
        flags=re.IGNORECASE,
    )
    label_kutipan = pola_label.match(kutipan)
    if not label_kutipan:
        return False
    label_normal = normalisasi_tanpa_format(
        label_kutipan.group(1).rstrip("* ")
    )
    if not label_normal:
        return False

    awal_daftar_obat = next(
        (
            indeks
            for indeks, teks in enumerate(teks_obat)
            if "antibiotik oral" in bersihkan_teks(teks)
        ),
        None,
    )
    if awal_daftar_obat is None:
        return False

    baris_obat = [
        (indeks, teks.strip())
        for indeks, teks in enumerate(teks_obat[awal_daftar_obat + 1 :])
        if teks.strip()
    ]
    posisi_obat = []
    for indeks, teks in baris_obat:
        teks_normal = normalisasi_tanpa_format(teks.rstrip("* "))
        skor = SequenceMatcher(None, label_normal, teks_normal).ratio()
        if label_normal in teks_normal or skor >= 0.9:
            posisi_obat.append((indeks, teks.strip()))
    if len(posisi_obat) != 1:
        return False

    indeks_obat = posisi_obat[0][0]
    dosis = [
        teks.strip()
        for teks in teks_dosis
        if pola_dosis.match(teks)
    ]
    frekuensi = [
        teks.strip()
        for teks in teks_frekuensi
        if re.search(r"\bq\s*\d+(?:\s*-\s*\d+)?\s*h\b", teks, re.I)
    ]
    if len(dosis) != len(baris_obat) or len(frekuensi) != len(baris_obat):
        return False

    bukti = " ".join(
        (posisi_obat[0][1], dosis[indeks_obat], frekuensi[indeks_obat])
    )
    return not Counter(tokenisasi_bukti(kutipan)) - Counter(
        tokenisasi_bukti(bukti)
    )


def cocokkan_kutipan_tabel_krisis_hipertensi(rule, isi_halaman):
    kutipan = rule.get("metadata", {}).get("text", "")
    if not kutipan:
        return False

    baris = isi_halaman.splitlines()
    judul = next(
        (
            indeks
            for indeks, teks in enumerate(baris)
            if re.search(
                r"tabel\s+5\.\s+obat-obat\s+antihipertensi",
                bersihkan_teks(teks),
            )
            and "krisis hipertensi" in bersihkan_teks(teks)
        ),
        None,
    )
    if judul is None:
        return False

    akhir_tabel = next(
        (
            indeks
            for indeks in range(judul + 1, len(baris))
            if re.match(r"^\s*tabel\s+\d+\.", baris[indeks], re.I)
        ),
        len(baris),
    )
    baris_tabel = baris[judul:akhir_tabel]
    label_kutipan = re.match(r"\s*([^\d:]+?)\s+(?=\w)", kutipan)
    if not label_kutipan:
        return False

    label_normal = normalisasi_tanpa_format(label_kutipan.group(1))
    baris_header = []
    baris_obat = []
    for indeks, teks in enumerate(baris_tabel):
        teks_normal = normalisasi_tanpa_format(teks)
        if label_normal and label_normal in teks_normal:
            baris_obat.append(teks)
            break
        baris_header.append(teks)
    if len(baris_obat) != 1:
        return False

    return not Counter(tokenisasi_bukti(kutipan)) - Counter(
        tokenisasi_bukti(" ".join([*baris_header, *baris_obat]))
    )


def cocokkan_kutipan_struktural_di_halaman(rule, rules, teks_sumber):
    metadata = rule.get("metadata", {})
    isi_halaman = ambil_halaman_buku(metadata.get("page"), teks_sumber)
    if not isi_halaman:
        return False

    claim = rule.get("claim", {})
    if claim.get("medicine"):
        rules_sehalaman = [
            rule_lain
            for rule_lain in rules
            if rule_lain.get("metadata", {}).get("page")
            == metadata.get("page")
        ]
        return cocokkan_obat_dengan_barisan_dosis(
            rule,
            rules_sehalaman,
            isi_halaman,
        ) or cocokkan_obat_di_tabel_baris(
            rule,
            rules_sehalaman,
            isi_halaman,
        ) or cocokkan_obat_di_tabel_kolom(
            rule,
            rules_sehalaman,
            isi_halaman,
        ) or cocokkan_kutipan_tabel_isk(
            rule,
            rules_sehalaman,
            isi_halaman,
        ) or cocokkan_kutipan_tabel_isk_kolom(
            rule,
            isi_halaman,
        ) or cocokkan_kutipan_tabel_krisis_hipertensi(
            rule,
            isi_halaman,
        )

    token_kutipan = Counter(tokenisasi_bukti(metadata.get("text", "")))
    if not token_kutipan:
        return False

    token_halaman = Counter(tokenisasi_bukti(isi_halaman))
    return not token_kutipan - token_halaman


def cocokkan_kutipan_tabel(teks_kutipan, teks_sumber):
    """Cocokkan kutipan ringkas dengan bukti pada tabel bernomor di sumber."""
    tokenisasi = lambda teks: re.findall(
        r"[^\W_]+|[<>≤≥]",
        bersihkan_teks(teks),
        flags=re.UNICODE,
    )
    token_kutipan = tokenisasi(teks_kutipan)
    if len(token_kutipan) < 4 or token_kutipan[0] != "tabel":
        return False

    nomor_tabel = token_kutipan[1]
    baris_sumber = teks_sumber.splitlines()
    for awal, baris in enumerate(baris_sumber):
        token_judul_sumber = tokenisasi(baris)
        if (
            len(token_judul_sumber) < 3
            or token_judul_sumber[:2] != ["tabel", nomor_tabel]
        ):
            continue

        if token_kutipan[: len(token_judul_sumber)] != token_judul_sumber:
            continue

        bukti_token = token_kutipan[len(token_judul_sumber) :]
        if not bukti_token:
            continue

        akhir = next(
            (
                index
                for index in range(awal + 1, len(baris_sumber))
                if re.match(
                    r"^\s*tabel\s+\d+\.",
                    baris_sumber[index],
                    flags=re.IGNORECASE,
                )
            ),
            len(baris_sumber),
        )
        token_tabel = tokenisasi("\n".join(baris_sumber[awal:akhir]))
        if all(token in token_tabel for token in bukti_token):
            return True

    return False


def hitung_grounding_rate(
    file_json_ai,
    file_sumber_path,
    similarity_threshold=0.95,
):
    raw_source_text = muat_teks_sumber(file_sumber_path)
    normalized_source_text = bersihkan_teks(raw_source_text)
    compact_source_text = normalisasi_tanpa_format(raw_source_text)
    file_ocr_gambar = (
        Path(file_sumber_path).resolve().parent.parent
        / "processed"
        / "ppm_image_ocr.txt"
    )
    image_ocr_text = (
        muat_teks_sumber(file_ocr_gambar)
        if file_ocr_gambar.is_file()
        else ""
    )

    with open(file_json_ai, "r", encoding="utf-8") as file:
        data = json.load(file)

    ai_rules = data.get("rules", data)
    total_rules = len(ai_rules)
    exact_match_count = 0
    normalized_match_count = 0
    format_match_count = 0
    fuzzy_match_count = 0
    table_match_count = 0
    page_match_count = 0
    image_ocr_match_count = 0
    unmatched_logs = []

    for index, rule in enumerate(ai_rules):
        rule_id = rule.get("rule_id", f"Index_{index}")
        metadata = rule.get("metadata", {})
        quoted_text = metadata.get("text", "")

        if not quoted_text:
            unmatched_logs.append(
                f"[{rule_id}] ERROR: Field 'metadata.text' kosong/tidak ada."
            )
            continue

        if quoted_text in raw_source_text:
            exact_match_count += 1
            normalized_match_count += 1
            continue

        normalized_quoted_text = bersihkan_teks(quoted_text)
        if (
            normalized_quoted_text
            and normalized_quoted_text in normalized_source_text
        ):
            normalized_match_count += 1
            continue

        compact_quoted_text = normalisasi_tanpa_format(quoted_text)
        if (
            compact_quoted_text
            and compact_quoted_text in compact_source_text
        ):
            format_match_count += 1
            normalized_match_count += 1
            continue

        if cocokkan_kutipan_tabel(quoted_text, raw_source_text):
            table_match_count += 1
            normalized_match_count += 1
            continue

        if cocokkan_kutipan_ocr_halaman(rule, image_ocr_text):
            image_ocr_match_count += 1
            normalized_match_count += 1
            continue

        if cocokkan_kutipan_struktural_di_halaman(
            rule,
            ai_rules,
            raw_source_text,
        ):
            page_match_count += 1
            normalized_match_count += 1
            continue

        if normalized_quoted_text:
            matcher = SequenceMatcher(
                None,
                normalized_quoted_text,
                normalized_source_text,
            )
            match = matcher.find_longest_match(
                0,
                len(normalized_quoted_text),
                0,
                len(normalized_source_text),
            )
            if match.size / len(normalized_quoted_text) >= similarity_threshold:
                fuzzy_match_count += 1
                normalized_match_count += 1
                continue

        unmatched_logs.append(
            f"[{rule_id}] UNGROUNDED: Teks rujukan "
            f"'{quoted_text[:50]}...' tidak ditemukan pada dokumen rujukan."
        )

    if total_rules == 0:
        print("File JSON kosong.")
        return

    exact_grounding_rate = exact_match_count / total_rules * 100
    overall_grounding_rate = normalized_match_count / total_rules * 100

    print("==========================================")
    print("       HASIL EVALUASI GROUNDING RATE")
    print("==========================================")
    print(f"Total Aturan Diekstrak             : {total_rules}")
    print(
        f"Exact Verbatim Match               : "
        f"{exact_match_count} ({exact_grounding_rate:.2f}%)"
    )
    print(f"Total Grounded (termasuk fuzzy)     : {normalized_match_count}")
    print(f"Kecocokan setelah normalisasi format: {format_match_count}")
    print(f"Kecocokan kutipan dengan tabel      : {table_match_count}")
    print(f"Kecocokan struktural per halaman    : {page_match_count}")
    print(f"Kecocokan transkripsi OCR gambar    : {image_ocr_match_count}")
    print(f"Fuzzy Match                         : {fuzzy_match_count}")
    print(f"GROUNDING RATE AKHIR                : {overall_grounding_rate:.2f}%")

    if unmatched_logs:
        print(
            "\n--- SAMPEL ATURAN TIDAK TERLACAK "
            "(UNGROUNDED / HALUSINASI RUJUKAN) ---"
        )
        for log in unmatched_logs[:10]:
            print(log)


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[2] / "data"
    rules_path = data_dir / "rules" / "rule_base.json"
    source_path = data_dir / "raw" / "buku pedoman pelayanan medis.pdf"
    hitung_grounding_rate(rules_path, source_path)