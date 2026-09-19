# SOP — D1 Sborshik dannyx

## Maqsad
Har ertalab (D6 dan keyin) amoCRM + GetCourse + `courses.json` dan ma'lumot
yig'ib, yagona **paket** (`data/paket/<sana>.json`) yaratadi — 2-N blokdagi 133
agent shu paketdan o'qiydi, hech kim CRM'ga o'zi kirmaydi.

## Kirish (nimadan o'qiydi)
- `adapter.ol("amocrm").lidlar(-90)` / `.xodimlar()`
- `adapter.ol("getcourse").talabalar()` / `.tolovlar(-30)`
- `courses.oqi("D1")` — D6 chiqishi (kurs_id/guruh_id tekshiruvi uchun)

## Ish
Har manba **alohida** `try` ichida. Biri yiqilsa — o'sha bo'lim **oldingi
muvaffaqiyatli paketdan** (`data/paket/joriy.json`) qayta ishlatiladi,
`manbalar.<x>.holat = "eski"` bo'ladi. Uchalasi ham yiqilib, oldingi paket ham
bo'lmasa — agent yiqiladi (paket yozilmaydi). Normalizatsiya: telefon E.164
(`+998XXXXXXXXX`, bo'lmasa `null`), ID prefikslash (`amo:`/`gc:`),
`amocrm_bosqich.json` orqali bosqich xaritasi, `kurs_id`/`guruh_id`
courses'da yo'q bo'lsa `null` + KPI hisoblagich.

## Chiqish (nima yozadi)
- `data/paket/<sana>.json` + `joriy.json` symlink (`paket.yoz` — atomik + hash + idempotent).
- `uzatish(berdi, "data/paket/<sana>.json", kimga="*")` — `paket.py` avtomat.
- KPI: `{manba_ok, manba_eski, manba_xato, telefon_normalizatsiya_xato, kurs_id_topilmadi, guruh_id_topilmadi}`.
- Biror manba `eski`/`xato` bo'lsa `shlyuz_client.yubor(S-900, direktor)`.

## Qanday ishga tushiriladi
```
bin/inplus ishga D1
# yoki
python3 agents/d1_sborshik/main.py --bir-marta --sana 2026-09-19 --rejim mock

# bitta manbani sun'iy yiqitish (demo/test):
INPLUS_MOCK_YIQIL=getcourse bin/inplus ishga D1
```
Jadval: `konfig/agentlar.json` dagi `06:00` (systemd: `After=inplus-d6.service`).

## Yiqilsa nima qilish
- Bitta-ikkita manba yiqilsa — **kutilgan holat**, paket baribir yoziladi (`qisman`),
  S-900 ketadi, exit 0.
- Uchala manba ham yiqilsa (va oldingi paket yo'q) — agent yiqiladi, heartbeat
  `xato`, `joriy.json` o'zgarmaydi. X2 qayta yoqadi.

## Kimga aytish
- Egasi: `konfig/agentlar.json` dagi `D1.egasi` (X-001).
- Manba muammosi — S-900 orqali direktorga (xodimlar ro'yxatidagi `rol=="direktor"`,
  topilmasa `TG_ADMIN_ID`).
