"""Code 128 barkod kodlayıcı (harici bağımlılık olmadan). Künye projesinden alındı.

Çıktı, çubukla başlayıp çubuk/boşluk olarak sırayla ilerleyen modül
genişlikleri listesidir. Sayısal diziler için alt küme C'ye geçilerek
barkod kısaltılır (protokol numaraları genellikle tamamen rakamdır).
"""

PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312",
    "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222",
    "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321",
    "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224",
    "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112",
    "421211", "212141", "214121", "412121", "111143", "111341", "131141", "114113",
    "114311", "411113", "411311", "113141", "114131", "311141", "411131", "211412",
    "211214", "211232", "2331112",
]

START_B = 104
START_C = 105
CODE_B = 100
CODE_C = 99
STOP = 106


class Code128Error(ValueError):
    pass


def _digit_run(data: str, i: int) -> int:
    n = 0
    while i + n < len(data) and data[i + n].isdigit():
        n += 1
    return n


def encode_values(data: str) -> list[int]:
    """Veriyi kod değerlerine çevirir (başlangıç ve sağlama dahil, bitiş hariç)."""
    if not data:
        raise Code128Error("Barkod verisi boş olamaz.")
    for ch in data:
        if not 32 <= ord(ch) <= 126:
            raise Code128Error(
                f"Barkod yalnızca İngilizce harf, rakam ve işaret içerebilir: {ch!r}"
            )

    values: list[int] = []
    subset = None

    def switch(to: str) -> None:
        nonlocal subset
        if subset == to:
            return
        if subset is None:
            values.append(START_C if to == "C" else START_B)
        else:
            values.append(CODE_C if to == "C" else CODE_B)
        subset = to

    i = 0
    while i < len(data):
        run = _digit_run(data, i)
        if run >= 4 or (run >= 2 and run == len(data)):
            if run % 2:
                # Tek sayıdaki rakam dizisinin ilk hanesi B ile yazılır
                switch("B")
                values.append(ord(data[i]) - 32)
                i += 1
                run -= 1
            switch("C")
            for j in range(i, i + run, 2):
                values.append(int(data[j:j + 2]))
            i += run
        else:
            switch("B")
            values.append(ord(data[i]) - 32)
            i += 1

    checksum = values[0] + sum(v * pos for pos, v in enumerate(values[1:], start=1))
    values.append(checksum % 103)
    return values


def encode(data: str) -> list[int]:
    """Modül genişlikleri: çubuk, boşluk, çubuk, ... (bitiş deseni dahil)."""
    widths: list[int] = []
    for v in encode_values(data) + [STOP]:
        widths.extend(int(c) for c in PATTERNS[v])
    return widths
