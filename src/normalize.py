#!/usr/bin/env python3
import csv
import sys
import re
import unicodedata
from unidecode import unidecode

#   CURRENT PROBLEMS:
#   1. All the following are grouped together under root 'kral':
#   Janka Kráľa:28284.6; Fraňa Kráľa:16369.3; J. Kráľa:13926.8; Kráľovská cesta:3223.4; Kráľovská:3211.3; Fr. Kráľa:2068.2; Kráľová:1177.7; Malá Kráľová:1050.0; Nábrežie Janka Kráľa:694.1; Námestie Krista Kráľa:644.3; Kráľova:577.1; F. Kráľa:563.0; Námestie J. Kráľa:340.8; Kráľovská ulica:165.1; Sad Janka Kráľa:120.4; Kráľov most:8.1
#   TODO: Differentiate between different people and possibly adjectives

#   2. All the following are grouped together under the root "armada":
#   Československej armády:23722.1; Čsl. armády:14856.6; Červenej armády:13876.5; Sovietskej armády:2721.1; Čsl. Armády:2070.8; Červenej Armády:1737.6; Slovenskej armády:1633.3; Rumunskej armády:1234.6; Sovietskej Armády:1073.1; Česko-slovenskej armády:660.0; Cesta armády:644.5; Česko Slovenskej Armády:479.2; Čsľ. armády:432.6
#   Similar happens to "hrdinov":
#   Dukelských hrdinov:4966.7; Námestie hrdinov:3936.9; Duklianskych hrdinov:3095.6; Sov. Hrdinov:2485.6; Sídlisko duklianskych hrdinov:1787.2; Padlých hrdinov:1678.1; Námestie padlých hrdinov:1533.3; Nábrežie dukelských hrdinov:1053.8; Hrdinov:973.9; Trieda dukelských hrdinov:680.6; Duklianskych Hrdinov:676.2; Dukel. hrdinov:632.8; Námestie Hrdinov:611.8; Dargovských hrdinov:553.2; Dukelských Hrdinov:445.6; Darg. hrdinov:376.2; Sad duklianskych hrdinov:257.2; Námestie Padlých hrdinov:229.6; Kragujevackých hrdinov:210.6; Duk. hrdinov:177.0; Sov. hrdinov:156.6
#   TODO: Differentiate between names referring to different groups

#   3. All the following are grouped together under the root "hora":
#   Horská:15971.3; Červená hora:9366.9; Stará hora:6517.3; Horská cesta:5066.7; Petecká Hora:3110.8; Nová hora:3081.5; Pavla Horova:2197.3; Chodník Hradská hora:1633.6; Okrúhla hora:1191.4; Kravie hory:1078.2; Staré hory:873.3; Horovská:861.0; Hajná hora:855.3; Malá Hora:766.7; P. Horova:765.5; Suchá hora:619.3; Zadná hora:567.8; Vysoká hora:284.8; Na vrchnú horu:230.3; Mariánska hora:18.8
#   Similar happens to "dvor", "rad", "signalka" etc.:
#   TODO: Differentiate between different places - many unrelated places share the same common noun root

#   4. Dlhá:71887.1; Čučmianska dlhá:2512.2; Dlhovského:1123.9 are grouped under "dlha"
#   TODO: Handle possessive forms better

#   5. All the following are grouped together under root "II":
#   Zelená voda II.:5248.3; Jurava II:3965.1; Centrum II.:3007.8; Jána Pavla II.:2916.1; Alej Jána Pavla II.:2834.9; Hlavná II:1864.8; Rúbanisko II:1297.9; Kotelnicova II.:1076.5; Klinec II.:1008.6; Nábrežie Jána Pavla II:787.3; Cesta svätého pápeža Jána Pavla II.:703.5; Rokošova II.:691.6; Námestie Jána Pavla II.:646.1; Školská II.:630.5; Most Sverepec II:627.9; Sv. Jána Pavla II.:625.9; Čeladická II:618.2; Sliváš II.:575.1; Tatranská cesta II:541.1; Nábrežie Jána Pavla II.:508.9; Tri vody II:500.8; Kajsa II:376.5; F. Rákócziho II.:344.1; Sadová II.:316.5; Proletárska II:291.6; Záhradkárska osada Kuľbová II.:289.7; Radovka II:282.7; Ostredky II:262.7; Sídlisko II:255.6; Za školou II.:226.7; Dlhé diely II:225.5; Záhumnie II.:209.1; Slnečná II:182.9; Roveň II:163.4; Riečna II:160.6; Nové záhrady II:148.0; Dymácka II.:142.4; Kolónia II.:139.6; Zemianske II.:118.7; Borovicová II.:114.4; Nad Zábrehom II.:79.0; Na Hlinách II.:52.3; Námestie Jána Pavla II:41.2; Most Jána Pavla II.:37.2; Na Kope II:31.3
#   TODO: handle roman numerals better

#   6. The representative name should be chosen better, not just by length
#   M. R. Štefánika vs Hviezdoslavova


NONLETTER = re.compile(r"[^a-z0-9\s\-]", re.IGNORECASE)
ORDINAL = re.compile(r"^\d+[\.\-]?$")
INITIAL = re.compile(r"^[a-z]\.?$", re.IGNORECASE)

STREET_TYPES = {
    "ulica", "ul", "ul.", "cesta", "namestie", "nam", "námestie", "trieda",
    "aleja", "park", "sady", "most", "nabr", "nabrezie", "chodnik", "plac", "ut", "utca", "dolina"
}

SUFFIXES = ["ovska", "ovske", "ovskeho", "ovskej", "ov", "ova", "ovo", "sky", "ska", "ske", "ski", "eho", "ej", "a",
            "o", "u", "y", "i"]
SUFFIXES = sorted(set(SUFFIXES), key=lambda x: -len(x))


def ascii_norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = unidecode(s)
    s = NONLETTER.sub(" ", s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def strip_suffix(token: str) -> str:
    for suf in SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def normalize_key(name: str) -> str:
    s = ascii_norm(name)
    tokens = s.split()
    if not tokens:
        return ""

    # detect ordinals = dates like  1. maja, 9. maja,  etc.
    for i in range(len(tokens) - 1):
        if ORDINAL.match(tokens[i]):
            nxt = tokens[i + 1]
            # skip if next token is a street-type or an initial or too short
            if nxt not in STREET_TYPES and not INITIAL.match(nxt) and len(nxt) >= 2:
                # normalize ordinal to digits only (strip '.' or '-')
                number = re.sub(r"\D", "", tokens[i])
                return f"{number}_{nxt}"

    # preserve ordinals/numeric-prefixed streets that start the name (keep prior behavior)
    if ORDINAL.match(tokens[0]) or tokens[0].isdigit():
        return "_".join(tokens)

    # remove street-type tokens
    tokens = [t for t in tokens if t not in STREET_TYPES]
    if not tokens:
        return ""

    # remove single-letter initials (and single letters with dot already removed by ascii_norm)
    tokens = [t for t in tokens if not INITIAL.match(t)]
    if not tokens:
        return ""

    last = tokens[-1]
    stem = strip_suffix(last)
    return stem


def main(input_csv, output_csv):
    rows = []
    with open(input_csv, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)
        for line in reader:
            if len(line) < 3:
                continue
            name = line[0].strip()
            length = float(line[1])
            count = int(line[2])
            rows.append((name, length, count))

    groups = {}
    for name, length, count in rows:
        root = normalize_key(name)
        if not root:
            continue
        if root not in groups:
            groups[root] = {
                "root": root,
                "total_length": 0.0,
                "total_count": 0,
                "variants": {}
            }
        g = groups[root]
        g["total_length"] += length
        g["total_count"] += count
        g["variants"][name] = g["variants"].get(name, 0.0) + length

    # choose representative: variant with the highest length
    for g in groups.values():
        g["representative"] = max(
            g["variants"].items(), key=lambda x: x[1]
        )[0]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["root", "representative", "total_length", "variant_count", "variants"])
        for g in sorted(groups.values(), key=lambda x: x["total_length"], reverse=True):
            variants_str = "; ".join(f"{v}:{l:.1f}" for v, l in g["variants"].items())
            writer.writerow([
                g["root"],
                g["representative"],
                f"{g['total_length']:.3f}",
                len(g["variants"]),
                variants_str
            ])

    print(f"Wrote normalized data to {output_csv}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python normalize.py input.csv output.csv")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
