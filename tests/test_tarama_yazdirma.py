import os
import subprocess

from PIL import Image

from dysasistan import code128, pdf, yazdirma
from dysasistan.ayarlar import Ayarlar
from dysasistan.tarama import TaramaYoneticisi, liste_ayristir

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


def test_tarama_komutu_ve_cok_sayfa(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    komutlar = []

    def calistir(komut, **_):
        komutlar.append(komut)
        if "-f" in komut:
            return Sonuc(cikti=LISTE)
        Image.new("L", (10, 10), 255).save(komut[komut.index("-o") + 1], "PNG")
        return Sonuc()

    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    y = TaramaYoneticisi(ayarlar, calistir=calistir)
    sayfalar = y.tara("Canon LiDE 220", devam_sor=lambda n: n < 3)
    assert len(sayfalar) == 3
    tarama = komutlar[1]
    assert tarama[:3] == ["scanimage", "-d", "genesys:libusb:001:004"]
    assert "--resolution" in tarama and "--mode" in tarama
    assert tarama[tarama.index("-x"):tarama.index("-x") + 4] == ["-x", "210", "-y", "297"]
    assert ayarlar.oku("DefaultScannerDevice") == "Canon LiDE 220"
    cikti = str(tmp_path / "x.pdf")
    pdf.sayfalardan_pdf(sayfalar, cikti)
    assert open(cikti, "rb").read(5) == b"%PDF-"
    pdf.gecici_temizle(sayfalar)
    assert not os.path.exists(os.path.dirname(sayfalar[0]))


def test_gecersiz_secenekte_en_az_secenekle_yeniden_dener(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda ad: "/usr/bin/" + ad)
    denemeler = []

    def calistir(komut, **_):
        if "-f" in komut:
            return Sonuc(cikti=LISTE)
        denemeler.append(komut)
        if "--mode" in komut:
            return Sonuc(1, hata="scanimage: setting of option --mode failed (Invalid argument)")
        Image.new("L", (10, 10), 255).save(komut[komut.index("-o") + 1], "PNG")
        return Sonuc()

    ayarlar = Ayarlar(str(tmp_path / "a.json"))
    ayarlar.yaz("ScanMorePagesDialog", False)
    assert len(TaramaYoneticisi(ayarlar, calistir=calistir).tara("")) == 1
    assert len(denemeler) == 2 and "--mode" not in denemeler[1]


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
