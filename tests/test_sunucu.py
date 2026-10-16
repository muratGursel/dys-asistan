import json
import os
import threading
import urllib.error
import urllib.request

import pytest
from PIL import Image

from dysasistan import dosyalar, sunucu, yazdirma
from dysasistan.ayarlar import Ayarlar
from dysasistan.tarama import TaramaHatasi, Tarayici


class SahteTarayici:
    def __init__(self, kok, sayfa=2, hata=None):
        self.kok, self.sayfa, self.hata = kok, sayfa, hata

    def tarayicilar(self, yenile=False):
        return [Tarayici("escl:http://10.0.0.5:80", "Kyocera MA4500ix (10.0.0.5)"),
                Tarayici("airscan:e0:HP", "HP LaserJet (10.0.0.6)")]

    def tara(self, ad, devam_sor=None):
        if self.hata:
            raise self.hata
        d = os.path.join(self.kok, "dys-tarama-x")
        os.makedirs(d, exist_ok=True)
        yollar = []
        for i in range(self.sayfa):
            y = os.path.join(d, "s%d.png" % i)
            Image.new("L", (100, 140), 255).save(y)
            yollar.append(y)
        return yollar


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    tarama = tmp_path / "Taranan"
    tarama.mkdir()
    monkeypatch.setenv("DYS_ASISTAN_TARAMA_DIZINI", str(tarama))
    ayarlar = Ayarlar(str(tmp_path / "ayarlar.json"))
    yuklenen = {}

    def sahte_yukle(api, token, yol):
        yuklenen.update(api=api, token=token, yol=yol)
        return '{"id":"abc","success":true}'

    uyg = sunucu.Uygulama(ayarlar, SahteTarayici(str(tmp_path)), yukle=sahte_yukle)
    s = sunucu.sunucu_olustur(uyg, port=0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield {"port": s.server_address[1], "tarama": str(tarama), "uyg": uyg, "yuklenen": yuklenen}
    s.shutdown()


def iste(port, yol, govde, origin="https://ebys.saglik.gov.tr", yontem="POST"):
    veri = None if govde is None else (govde if isinstance(govde, bytes) else json.dumps(govde).encode())
    basliklar = {"Content-Type": "text/plain"}
    if origin:
        basliklar["Origin"] = origin
    r = urllib.request.Request("http://127.0.0.1:%d/%s" % (port, yol), data=veri, method=yontem, headers=basliklar)
    try:
        with urllib.request.urlopen(r, timeout=10) as y:
            return y.status, json.loads(y.read().decode() or "null"), y.headers
    except urllib.error.HTTPError as h:
        metin = h.read().decode()
        return h.code, (json.loads(metin) if metin else None), h.headers


def test_isalive(ortam):
    durum, gov, bas = iste(ortam["port"], "IsAlive", {"token": "t"})
    assert (durum, gov) == (200, "alive")
    assert bas["Content-Type"] == "application/json; charset=utf-8"
    assert bas["Access-Control-Allow-Origin"] == "https://ebys.saglik.gov.tr"


def test_govde_yok(ortam):
    assert iste(ortam["port"], "IsAlive", b"")[:2] == (400, "Body bulunamadı.")
    assert iste(ortam["port"], "IsAlive", b"bozuk")[:2] == (400, "Body bulunamadı.")


def test_yabanci_kaynak_reddedilir(ortam):
    assert iste(ortam["port"], "IsAlive", {"token": "t"}, origin="https://kotu.example.com")[0] == 403
    assert iste(ortam["port"], "IsAlive", {"token": "t"}, origin="null")[0] == 403
    assert iste(ortam["port"], "IsAlive", {"token": "t"}, origin="https://saglik.gov.tr.kotu.com")[0] == 403


def test_kaynaksiz_yerel_istemci(ortam):
    assert iste(ortam["port"], "IsAlive", {"token": "t"}, origin=None)[:2] == (200, "alive")


def test_on_ucus(ortam):
    r = urllib.request.Request("http://127.0.0.1:%d/StartScan" % ortam["port"], method="OPTIONS", headers={
        "Origin": "https://dys.saglik.gov.tr", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type", "Access-Control-Request-Private-Network": "true"})
    with urllib.request.urlopen(r, timeout=5) as y:
        assert y.status == 204
        assert y.headers["Access-Control-Allow-Private-Network"] == "true"
        assert "content-type" in y.headers["Access-Control-Allow-Headers"]


def test_tarayicilar(ortam):
    ortam["uyg"].ayarlar.yaz("DefaultScannerDevice", "HP LaserJet (10.0.0.6)")
    durum, gov, _ = iste(ortam["port"], "GetActiveScanners", {"token": "t"})
    assert durum == 200
    assert gov == [{"scannerName": "Kyocera MA4500ix (10.0.0.5)", "isDefault": False},
                   {"scannerName": "HP LaserJet (10.0.0.6)", "isDefault": True}]


def test_tarama_pdf_uretir_ve_listelenir(ortam):
    durum, yol, _ = iste(ortam["port"], "StartScan", {"token": "t", "scannerName": "Kyocera MA4500ix (10.0.0.5)"})
    assert durum == 200
    assert os.path.dirname(yol) == ortam["tarama"] and yol.endswith(".pdf")
    with open(yol, "rb") as f:
        assert f.read(5) == b"%PDF-"
    durum, liste, _ = iste(ortam["port"], "GetAllFileInfos", {"token": "t"})
    assert liste[0]["path"] == yol and liste[0]["size"].endswith(" MB")
    assert set(liste[0]) == {"size", "name", "path", "creationTime"}


def test_tarama_hatasi(ortam):
    ortam["uyg"].tarayici.hata = TaramaHatasi("cihaz meşgul")
    assert iste(ortam["port"], "StartScan", {"token": "t"})[:2] == (500, "Tarayıcıya erişilemedi")


def test_silme_klasor_disi_reddedilir(ortam, tmp_path):
    disari = tmp_path / "gizli.pdf"
    disari.write_bytes(b"x")
    assert iste(ortam["port"], "DeletePdf", {"token": "t", "path": str(disari)})[0] == 400
    assert disari.exists()
    kacak = os.path.join(ortam["tarama"], "..", "gizli.pdf")
    assert iste(ortam["port"], "DeletePdf", {"token": "t", "path": kacak})[0] == 400
    assert disari.exists()


def test_silme(ortam):
    yol = os.path.join(ortam["tarama"], "doc_1.pdf")
    open(yol, "wb").write(b"%PDF-1.4")
    assert iste(ortam["port"], "DeletePdf", {"token": "t", "path": yol})[:2] == (200, "done")
    assert not os.path.exists(yol)


def test_yukleme(ortam):
    yol = os.path.join(ortam["tarama"], "doc_2.pdf")
    open(yol, "wb").write(b"%PDF-1.4")
    durum, gov, _ = iste(ortam["port"], "UploadPdf", {"token": "T", "apiUrl": "https://x/api/file/", "path": yol})
    assert durum == 200 and gov == '{"id":"abc","success":true}'
    assert ortam["yuklenen"] == {"api": "https://x/api/file/", "token": "T", "yol": yol}


def test_yukleme_dosya_yok(ortam):
    yol = os.path.join(ortam["tarama"], "yok.pdf")
    assert iste(ortam["port"], "UploadPdf", {"token": "T", "path": yol})[:2] == (500, "Dosya bulunamadı.")


def test_bilinmeyen_uc(ortam):
    assert iste(ortam["port"], "Yok", {"token": "t"})[0] == 404


def test_yazdirma_icerik_yok(ortam, monkeypatch):
    durum, gov, _ = iste(ortam["port"], "StartPrint", {"token": "t", "contentType": "application/pdf"})
    assert (durum, gov) == (500, "File Id ve File Data bilgilerinden hiç biri gönderilmedi.")


def test_yazdirma_iptal(ortam, monkeypatch):
    monkeypatch.setattr(yazdirma, "yazicilar", lambda: [])
    ortam["uyg"].yazici_sec = lambda *a: None
    durum, gov, _ = iste(ortam["port"], "StartPrint", {"token": "t", "contentType": "barcode", "code": "1",
                                                         "printerDialog": True})
    assert (durum, gov) == (500, "Yazdırma iptal edildi.")


def test_kaynak_deseni():
    d = ["https://*.saglik.gov.tr"]
    assert sunucu.kaynak_izinli("https://ebys.saglik.gov.tr", d)
    assert sunucu.kaynak_izinli("https://a.b.saglik.gov.tr/", d)
    assert not sunucu.kaynak_izinli("http://ebys.saglik.gov.tr", d)
    assert not sunucu.kaynak_izinli("https://saglik.gov.tr.example.com", d)


def test_guvenli_yol(tmp_path):
    kok = str(tmp_path)
    assert dosyalar.guvenli_yol(os.path.join(kok, "a.pdf"), kok)
    with pytest.raises(dosyalar.YolHatasi):
        dosyalar.guvenli_yol(os.path.join(kok, "..", "b.pdf"), kok)
    with pytest.raises(dosyalar.YolHatasi):
        dosyalar.guvenli_yol(kok + "x/a.pdf", kok)
