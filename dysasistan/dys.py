"""DYS dosya API istemcisi (orijinaldeki FileApiClient).

Yükleme : POST {apiUrl}upload/save   gövde {data: base64, fileName, contentType}
İndirme : GET  {apiUrl}data/{fileId}/download
Her iki istekte Authorization başlığı DYS'nin verdiği token'dır.
"""

import base64
import json
import os
import ssl
import urllib.request

VARSAYILAN_API = "https://testebys.saglik.gov.tr/api/file/"   # orijinaldeki varsayılan
ZAMAN_ASIMI = 120


class TokenHatasi(ValueError):
    pass


def _baglam():
    # SBA iç sertifikaları sistem deposuna (ca-certificates) eklenmiş olmalı
    ca = os.environ.get("DYS_ASISTAN_CA")
    return ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()


def _api(api_url):
    api = api_url or VARSAYILAN_API
    return api if api.endswith("/") else api + "/"


def yukle(api_url, token, yol, ac=urllib.request.urlopen):
    """PDF'i DYS'ye gönderir; sunucunun yanıt gövdesini metin olarak döndürür."""
    if not token:
        raise TokenHatasi("Token is invalid or empty")
    with open(yol, "rb") as f:
        veri = base64.b64encode(f.read()).decode("ascii")
    govde = json.dumps({"data": veri.strip(), "fileName": os.path.basename(yol),
                        "contentType": "application/pdf"}).encode("utf-8")
    istek = urllib.request.Request(_api(api_url) + "upload/save", data=govde, method="POST", headers={
        "Authorization": token, "Content-Type": "application/json", "Accept": "application/json"})
    with ac(istek, timeout=ZAMAN_ASIMI, context=_baglam()) as yanit:
        return yanit.read().decode("utf-8", "replace")


def indir(api_url, token, dosya_kimligi, ac=urllib.request.urlopen):
    """(icerik_bayt, content_type) döndürür."""
    if not token:
        raise TokenHatasi("Token is invalid or empty")
    istek = urllib.request.Request(_api(api_url) + "data/%s/download" % dosya_kimligi, method="GET",
                                   headers={"Authorization": token})
    with ac(istek, timeout=ZAMAN_ASIMI, context=_baglam()) as yanit:
        return yanit.read(), yanit.headers.get("content-type", "")
