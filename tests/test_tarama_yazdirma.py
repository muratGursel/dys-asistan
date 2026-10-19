import os
import subprocess

import pytest

from PIL import Image

from dysasistan import code128, pdf, yazdirma
from dysasistan.ayarlar import Ayarlar
from dysasistan.tarama import TaramaHatasi, TaramaYoneticisi, liste_ayristir, yetenek_ayristir

# Pardus 25 / sane-utils 1.3.1 üzerinde görülen gerçek biçimler
LISTE = (
    "airscan:e1e:Canon iR C3326\teSCL\tCanon iR C3326 ip=192.0.2.230\teSCL network scanner\n"
    "escl:http://192.0.2.230:80\tCanon\tiR C3326\tplaten,adf scanner\n"
    "escl:https://192.0.2.162:9096\tESCL\tKyocera ECOSYS MA4500ix\tplaten,adf scanner\n"
    "escl:https://192.0.2.117:9096\tESCL\tUTAX_TA P-4035 MFP\tplaten,adf scanner\n"
    "genesys:libusb:001:004\tCanon\tLiDE 220\tflatbed scanner\n"
)
GERCEK_CIKTI = (
    "404 Page Not Found 404 Page Not Foundescl:http://192.0.2.82:80\tCanon\tMF420 Series\tplaten scanner\n"
    "airscan:w6:Canon LBP226\tWSD\tCanon LBP226 ip=192.0.2.192\tWSD network scanner\n"
)


def test_bozuk_satir_ve_wsd():
    t = liste_ayristir(GERCEK_CIKTI)
    assert [(x.ad, x.cihaz) for x in t] == [("Canon MF420 Series (192.0.2.82)", "escl:http://192.0.2.82:80"),
                                           ("Canon LBP226 (192.0.2.192)", "airscan:w6:Canon LBP226")]


def test_liste_ayristir_tekillestirir():
    t = liste_ayristir(LISTE)
    adlar = [x.ad for x in t]
    assert adlar == ["Canon iR C3326 (192.0.2.230)", "Kyocera ECOSYS MA4500ix (192.0.2.162)",
                     "UTAX TA P-4035 MFP (192.0.2.117)", "Canon LiDE 220"]
    assert t[0].cihaz == "escl:http://192.0.2.230:80"     # eSCL tercih edilir


class Sonuc:
    def __init__(self, kod=0, cikti="", hata=""):
        self.returncode, self.stdout, self.stderr = kod, cikti, hata


# scanimage -A çıktısı biçimleri
KYOCERA_A = """  Scan mode:
    --mode Lineart|Gray|Color [Lineart]
    --resolution 200|300|400|600dpi [200]
    --source Flatbed|ADF|ADF Duplex [Flatbed]
  Geometry:
    -l 0..205.994mm [0]
    -t 0..346.033mm [0]
    -x 9.99066..215.985mm [215.985]
    -y 9.99066..356.023mm [356.023]
"""
# canon_dr (Canon DR-C225 gibi camsız, besleyicili tarayıcılar): tarama alanı sayfa
# boyuyla sınırlı, sayfa boyu varsayılan olarak Letter (279.364 mm)
CANON_DR_A = """  Standard:
    --source ADF Front|ADF Back|ADF Duplex [ADF Front]
    --mode Lineart|Halftone|Gray|Color [Lineart]
    --resolution 100..600dpi (in steps of 1) [600]
  Geometry:
    -t 0..279.364mm (in steps of 0.0211639) [0]
    -l 0..215.9mm (in steps of 0.0211639) [0]
    -x 0..215.9mm (in steps of 0.0211639) [215.872]
    -y 0..279.364mm (in steps of 0.0211639) [279.364]
    --page-width 0..215.9mm (in steps of 0.0211639) [215.872]
    --page-height 0..3000mm (in steps of 0.0211639) [279.364]
"""
TUKENDI = "scanimage: sane_start: Document feeder out of documents"


class SahteScanimage:
    """-f (liste), -A (seçenekler), -o (tek sayfa) ve --batch (besleyici) çağrılarını taklit eder."""

    def __init__(self, secenekler="", kagit=0, gri_coker=False):
        self.secenekler, self.kagit, self.komutlar = secenekler, kagit, []
        self.gri_coker = gri_coker    # DR-C225 / canon_dr: gri ve siyah-beyaz kipte scanimage çöker

    def __call__(self, komut, **_):
        self.komutlar.append(komut)
        if "-f" in komut:
            return Sonuc(cikti=LISTE)
        if "-A" in komut:
            return Sonuc(cikti=self.secenekler)
        renkli = "--mode" in komut and komut[komut.index("--mode") + 1] == "Color"
        if self.gri_coker and not renkli:
            return Sonuc(-8, hata="Floating point exception")
        kip, renk = ("RGB", (200, 120, 40)) if renkli else ("L", 255)
        if "-o" in komut:
            Image.new(kip, (10, 10), renk).save(komut[komut.index("-o") + 1], "PNG")
            return Sonuc()
        desen = next(k for k in komut if k.startswith("--batch="))[len("--batch="):]
        bas = int(next(k for k in komut if k.startswith("--batch-start="))[len("--batch-start="):])
        for i in range(self.kagit):
            Image.new(kip, (10, 10), renk).save(desen % (bas + i), "PNG")
        self.kagit = 0
        return Sonuc(7, hata=TUKENDI)

    def taramalar(self):
        return [k for k in self.komutlar if "-o" in k or any(a.startswith("--batch=") for a in k)]


def test_tarama_komutu_ve_cok_sayfa(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    s = SahteScanimage()
    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    y = TaramaYoneticisi(ayarlar, calistir=s)
    sayfalar = y.tara("Canon LiDE 220", devam_sor=lambda n: n < 3)
    assert len(sayfalar) == 3
    tarama = s.taramalar()[0]
    assert tarama[:3] == ["scanimage", "-d", "genesys:libusb:001:004"]
    assert "--resolution" in tarama and "--mode" in tarama
    assert tarama[tarama.index("-x"):tarama.index("-x") + 4] == ["-x", "210", "-y", "297"]
    assert ayarlar.oku("DefaultScannerDevice") == "Canon LiDE 220"
    cikti = str(tmp_path / "x.pdf")
    pdf.sayfalardan_pdf(sayfalar, cikti)
    assert open(cikti, "rb").read(5) == b"%PDF-"
    pdf.gecici_temizle(sayfalar)
    assert not os.path.exists(os.path.dirname(sayfalar[0]))


def test_basarisizlikta_en_az_secenekle_yeniden_dener(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    s = SahteScanimage()
    asil = s.__call__

    def calistir(komut, **kw):
        if "--mode" in komut and "-o" in komut:
            s.komutlar.append(komut)
            return Sonuc(1, hata="scanimage: rounded value of br-y from 297 to 279.364\n"
                                 "scanimage: sane_start: Error during device I/O")
        return asil(komut, **kw)

    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    ayarlar.yaz("ScanMorePagesDialog", False)
    assert len(TaramaYoneticisi(ayarlar, calistir=calistir).tara("")) == 1
    taramalar = s.taramalar()
    assert len(taramalar) == 2 and "--mode" not in taramalar[1]


def test_hata_iletisi_bilgi_satirini_atlar(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)

    def calistir(komut, **_):
        if "-f" in komut:
            return Sonuc(cikti=LISTE)
        if "-A" in komut:
            return Sonuc(cikti="")
        return Sonuc(1, hata="scanimage: rounded value of br-y from 297 to 279.364\n"
                             "scanimage: open of device genesys:libusb:001:004 failed: "
                             "Access to resource has been denied\n"
                             "scanimage: rounded value of br-x from 210 to 209.9")

    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    with pytest.raises(TaramaHatasi) as h:
        TaramaYoneticisi(ayarlar, calistir=calistir).tara("Canon LiDE 220")
    # bilgi satırı değil asıl hata ("denied") Türkçe iletiye çevrilir
    assert str(h.value) == "Tarayıcıya erişim izni yok. Oturumu kapatıp açın."


def test_alan_cihaz_sinirina_kirpilir():
    y = yetenek_ayristir(KYOCERA_A)
    assert (y.x_max, y.y_max, y.sayfa_yuk_max) == (215.985, 356.023, None)
    assert y.kaynaklar == ["Flatbed", "ADF", "ADF Duplex"] and y.kaynak_varsayilan == "Flatbed"
    assert y.alan_secenekleri(210, 297) == ["-x", "210", "-y", "297"]
    letter = yetenek_ayristir("    -x 0..215.9mm [215.9]\n    -y 0..279.4mm [279.4]\n")
    assert letter.alan_secenekleri(210, 297) == ["-x", "210", "-y", "279.4"]


def test_canon_dr_sayfa_boyu_ve_besleyici(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    y = yetenek_ayristir(CANON_DR_A)
    assert y.kaynak_varsayilan == "ADF Front" and y.sayfa_yuk_max == 3000
    # sayfa boyu -y'den önce büyütülmeli; yoksa -y 279.364'e yuvarlanır
    assert y.alan_secenekleri(210, 297) == ["--page-width", "210", "--page-height", "297",
                                            "-x", "210", "-y", "297"]

    s = SahteScanimage(CANON_DR_A, kagit=3)
    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    sorular = []

    def devam(n):
        sorular.append(n)
        return False

    sayfalar = TaramaYoneticisi(ayarlar, calistir=s).tara("genesys:libusb:001:004", devam_sor=devam)
    assert len(sayfalar) == 3 and sorular == [3]          # besleyicideki 3 sayfa tek seferde
    tarama = s.taramalar()[0]
    assert "--batch-start=1" in tarama and "-o" not in tarama
    assert tarama.index("--page-height") < tarama.index("-y")


def test_gri_kipte_coken_surucu_renkli_taranir(tmp_path, monkeypatch):
    # Canon DR-C225 (canon_dr, SANE 1.3.1): gri ve siyah-beyaz kipte scanimage çöküyor,
    # renkli kipte tarıyor; renkli taranıp yazılımda griye çevrilmeli
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    s = SahteScanimage(CANON_DR_A, kagit=2, gri_coker=True)
    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    yonetici = TaramaYoneticisi(ayarlar, calistir=s)
    sayfalar = yonetici.tara("genesys:libusb:001:004")
    assert len(sayfalar) == 2
    taramalar = s.taramalar()
    assert len(taramalar) == 2                                    # önce gri (çöktü), sonra renkli
    assert taramalar[1][taramalar[1].index("--mode") + 1] == "Color"
    assert "--resolution" in taramalar[1] and "--page-height" in taramalar[1]
    for yol in sayfalar:
        with Image.open(yol) as g:
            assert g.mode == "L"                                  # istenen kip: gri
    assert ayarlar.oku("ColorOnlyScanners") == ["genesys:libusb:001:004"]

    # sonraki taramada önce çöktürmeden doğrudan renkli taranır
    s.kagit, s.komutlar = 1, []
    assert len(yonetici.tara("genesys:libusb:001:004")) == 1
    assert len(s.taramalar()) == 1 and "Color" in s.taramalar()[0]


def test_siyah_beyaz_istenirse_renkliden_cevrilir(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    s = SahteScanimage(CANON_DR_A, kagit=1, gri_coker=True)
    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    ayarlar.yaz("Mode", "Lineart")
    (yol,) = TaramaYoneticisi(ayarlar, calistir=s).tara("genesys:libusb:001:004")
    with Image.open(yol) as g:
        assert g.mode == "1"


def test_kagit_sikismasi_yinelenmez(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    s = SahteScanimage(CANON_DR_A)

    def calistir(komut, **kw):
        if "--batch-start=1" in komut:
            s.komutlar.append(komut)
            return Sonuc(6, hata="scanimage: rounded value of br-y from 297 to 296.994\n"
                                 "scanimage: sane_start: Document feeder jammed")
        return s(komut, **kw)

    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    with pytest.raises(TaramaHatasi, match="Kağıt sıkıştı"):
        TaramaYoneticisi(ayarlar, calistir=calistir).tara("genesys:libusb:001:004")
    assert len(s.taramalar()) == 1


def test_besleyici_bos(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    with pytest.raises(TaramaHatasi, match="Besleyicide kağıt yok"):
        TaramaYoneticisi(ayarlar, calistir=SahteScanimage(CANON_DR_A, kagit=0)).tara("genesys:libusb:001:004")


def test_besleyicide_ikinci_deste(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    s = SahteScanimage(CANON_DR_A, kagit=2)
    ayarlar = Ayarlar(str(tmp_path / "a.json"))

    def devam(n):
        if n == 2:
            s.kagit = 1          # kullanıcı ikinci desteyi koydu
            return True
        return False

    sayfalar = TaramaYoneticisi(ayarlar, calistir=s).tara("genesys:libusb:001:004", devam_sor=devam)
    assert [os.path.basename(p) for p in sayfalar] == ["sayfa001.png", "sayfa002.png", "sayfa003.png"]
    assert "--batch-start=3" in s.taramalar()[1]


def test_code128_sonu():
    m = code128.encode("2026-123456")
    assert m[-7:] == [2, 3, 3, 1, 1, 1, 2]     # dur karakteri
    assert sum(m) % 11 == 2                     # 11'li karakterler + 13'lük dur


def test_etiket_ciz():
    g = yazdirma.etiket_ciz({"generalDepartmentName": "SAĞLIK BAKANLIĞI", "detsisDepartmentName": "Bilgi İşlem",
                             "documentDate": "17.10.2026", "documentNumber": "E-12345678-000-999",
                             "code": "ABC123456", "creatorDepartmentName": "Hastane Müdürlüğü"})
    assert g.size == (850, 425)
    assert g.getextrema()[0] == 0          # siyah piksel var


def test_etiket_sayisal_alanlar():
    # DYS'den gelen gerçek istekte code sayıdır
    g = yazdirma.etiket_ciz({"code": 987654321, "documentNumber": "E-12345678-000-987654321",
                             "documentDate": "15.10.2026 16:58:22", "copyCount": 1, "printerDialog": True})
    assert g.getextrema()[0] == 0


def test_lp_komutu(monkeypatch, tmp_path):
    cagrilar = []
    monkeypatch.setattr(yazdirma.shutil, "which", lambda ad: "/usr/bin/" + ad)
    monkeypatch.setattr(yazdirma.subprocess, "run",
                        lambda k, **_: cagrilar.append(k) or subprocess.CompletedProcess(k, 0, "", ""))
    import base64
    yazdirma.yazdir({"fileData": base64.b64encode(b"%PDF-1.4").decode(), "contentType": "application/pdf",
                     "fileName": "evrak.pdf", "printerName": "Ofis", "copyCount": 2})
    k = cagrilar[0]
    assert k[:3] == ["lp", "-n", "2"] and k[k.index("-d") + 1] == "Ofis"
    assert k[-1].endswith("evrak.pdf")


def test_yazicilar(monkeypatch):
    cikti = {"-d": "system default destination: Ofis\n", "-e": "Ofis\nEtiket\n"}
    monkeypatch.setattr(yazdirma, "_lpstat", lambda a: cikti[a])
    assert yazdirma.yazicilar() == [{"printerName": "Ofis", "isDefault": True},
                                    {"printerName": "Etiket", "isDefault": False}]
