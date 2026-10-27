# FUTSIM WEB

Ücretsiz GitHub Pages üzerinden yayımlanan futbol tahmin simülatörü.

- Web: https://ahmetsake123-collab.github.io/futsim-web/
- 500 zaman sıralı maç testi ve 331 korner testi: `docs/data/model_validation.json`
- Açık fikstür / gol / korner kaynakları: `scripts/update_cc0.py`
- Ayrı model testi: `scripts/validate_walkforward.py`
- Yayın, Python ve JS kontrolü: `scripts/check_site.py`

## Ücretsiz API-Football bağlantısı (isteğe bağlı)

**Fiyat:** API-Football Free = $0/ay, gün başına 100 istek. Ücretsiz planda erişilebilir sezonlar sınırlıdır. 2026/27 sezonunun görünmesi garanti değildir. Resmî belgeler: https://www.api-football.com/pricing ve https://www.api-football.com/documentation_v3

1. https://dashboard.api-football.com üzerinden ücretsiz hesap açıp `API-Key` değerini al.
2. GitHub deposunda `Settings > Secrets and variables > Actions > New repository secret` yolunu aç: https://github.com/ahmetsake123-collab/futsim-web/settings/secrets/actions
3. **Name:** `APISPORTS_KEY`. **Secret:** API-Football kontrol panelindeki anahtarın kendisi. Kaydet.
4. GitHub'da `Actions > FUTSIM Daily Football Data & Pages > Run workflow` ile yeni bir manuel çalıştırma başlat.
5. Çalışma günlüğünde `Get optional free API-Football injuries and lineups` adımına bak. Gizli anahtar veya anahtarın tamamı web sayfasına yazılmaz.
6. Sonuçlar uygun ve hesap erişimi varsa `docs/data/api_football.json` içine temizlenmiş sakatlık/ilk 11 durumları yazılır.

Anahtarı **README, HTML, JS veya ChatGPT sohbet mesajına yapıştırma**. Yalnızca GitHub **repository secret** olarak kullan.

Günlük planlama çalışmasında isteğe bağlı API adımı çalışır; kodu her push edişinde istemsiz kota harcamaz. Bir çalıştırmada en fazla **18 istek**, iki güne yayılan fikstürler ile en fazla sekiz maçın sakatlık ve dört maçın ilk 11 sorgusuna ayrılır. API erişimi başarısızsa eski sistem devam eder ve uygulama doğrulanmamış veriyi güncel gibi göstermez.

**Veri kapsamı ve lisans:** Ücretsiz hesabın verdiği sezon bilgisi değişebilir. Sonuçlar boşsa API'nin aktif olduğu veya güncel sezonu desteklediği sonucuna varma. API-Football xG/xA doğruluğunu veya sakatlık kapsamını ayrıca doğrulamadan ileri istatistik diye sunma. API-Football şartları (https://www.api-football.com/terms) üçüncü taraf lig hakları ve yayınlama yükümlülüklerini kullanıcıya bırakır; ticari bir bahis/haber uygulamasına dönüşecekse lisansların ayrıca değerlendirilmesi gerekir.

## Tahmin kalitesi

Sitede gösterilen 100.000 örnekli simülatör ile tarihsel walk-forward test motoru ayrı uygulamalardır. Testte referanstan iyi sonuç almak, kârlı bahis veya gelecek maçlarda aynı performans garantisi değildir. Tamamlanmamış ilk 11/xG/xA/veri eksiklikleri modelin güven düzeyini sınırlar.

## 100.000 maç örneklemi

Her tahminde tarayıcıda 100.000 iki yarılı Monte Carlo maçı üretilir. Ayrı panelde ham simülasyon sayımlarıyla 1-X-2 sonuçları, en sık skorlar, devre/maç geçişleri, tam devre→final skor yolları, toplam gol sayıları ve olaylar sıralanır. Bir olay başka olayla çakışabilir ve yüzdeleri toplanmaz. Bunlar gerçek 100.000 maçın testi değil; model örneklemidir. Geriye dönük doğrulama ayrıca yapılır. Mobil cihazlarda hesaplama birkaç saniye sürebilir.
