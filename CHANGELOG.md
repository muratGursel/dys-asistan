# Değişiklikler

## Yayınlanmamış

- Besleyicili tarayıcılar (Canon DR-C225 gibi camsız cihazlar): sayfa boyu
  A4'e ayarlanır, besleyicideki sayfalar tek seferde taranır, besleyici
  boşsa anlaşılır ileti verilir. Önceden "rounded value of br-y from 297 to
  279.364" iletisiyle tarama başarısız oluyordu.
- Tarama alanı her cihazda cihazın sınırına kırpılır.
- Hata iletisinde scanimage'ın bilgi satırları yerine asıl hata gösterilir;
  her başarısızlıkta tarama en az seçenekle yeniden denenir.
- Tanılama aracı (`tools/dys-tani.sh`): tarayıcı sorunlarının olası
  sebeplerini inceler, sonucu `~/dys-tani.txt` dosyasına yazar.

## 0.1.0 — 2026-10-17

İlk sürüm.

- DYS'nin yerel yardımcıyla konuştuğu adresler (`http://localhost:62222`):
  `IsAlive`, `GetActiveScanners`, `StartScan`, `GetAllFileInfos`, `OpenPdf`,
  `OpenDirectory`, `DeletePdf`, `UploadPdf`, `GetActivePrinters`,
  `StartPrint`. Yanıtlar, durum kodları ve Türkçe iletiler Windows'taki
  yardımcıyla aynı.
- SANE ile tarama: USB, eSCL, AirScan ve WSD cihazları. Aynı cihazın
  birden çok arka uçta görünmesi tekilleştirilir; eSCL tercih edilir.
- Çok sayfalı tarama ("bir sayfa daha?"), belge besleyici (ADF) desteği,
  A4 / A5 / tüm alan seçimi, çözünürlük ve renk ayarı. Cihaz bir seçeneği
  reddederse tarama en az seçenekle yinelenir.
- Taranan sayfalar tek PDF'te birleşir ve DYS'ye yüklenir.
- CUPS ile belge ve barkod etiketi (72×36 mm, Code 128) yazdırma; yazıcı ve
  kopya seçim penceresi.
- Sistem çekmecesi simgesi, ayarlar penceresi, oturum açılışında başlama.
- Güvenlik: yalnızca `127.0.0.1`, yalnızca `*.saglik.gov.tr` kaynakları,
  dosya işlemleri yalnızca tarama klasöründe, token diske yazılmaz.
- `tools/sahte_dys.html`: DYS olmadan deneme sayfası.
