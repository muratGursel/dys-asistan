"""DYS Asistan: Sağlık Bakanlığı DYS'nin yerel tarama/yazdırma asistanının
Pardus için uyumlu yeniden yazımı.

DYS web sayfası, Windows'taki EbysAsistan.jar ile http://localhost:62222 üzerinden
JSON ile konuşur. Bu paket aynı uç noktaları aynı biçimde sunar; taramayı SANE,
yazdırmayı CUPS ile yapar. DYS tarafında değişiklik gerektirmez.
"""

AD = "DYS Asistan"
UYGULAMA_KIMLIGI = "io.github.muratgursel.DysAsistan"
PAKET = "dys-asistan"
PORT = 62222
__version__ = "0.1.1"
