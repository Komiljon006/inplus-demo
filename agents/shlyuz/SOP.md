# SOP — SHLYUZ Xabar shlyuzi (N1 SMS + N2 Telegram)

> W1 shu faylni `wiki/agentlar/SHLYUZ.md` ga oladi.

## Maqsad
Tizimdagi HAR BIR tashqi xabar (SMS yoki Telegram) shu bitta eshikdan o'tadi:
skript tasdiqlangan matn, oq/qora ro'yxat, dublikat/limit nazorati, retry.
Boshqa hech qanday agent bevosita `sendMessage`/SMS API'ga chiqmaydi
(X1 buni statik grep bilan tekshiradi — `SHLYUZ_CHETLAB`).

## Kirish (nimadan o'qiydi)
- HTTP `POST /yubor` — `kontrakt/xabar.schema.json` bo'yicha so'rov.
- `konfig/skriptlar.json` (har so'rovda qayta o'qiladi — N3 tasdiqlagan reestr).
- `konfig/oq_royxat.json`, `konfig/qora_royxat.json`.
- Real rejimda: `data/paket/joriy.json` (talaba/lid/xodim manzillari).
- `adapter.ol("sms")`, `adapter.ol("telegram")` — hech qachon to'g'ridan-to'g'ri emas.

## Chiqish (nima yozadi)
- `data/shlyuz.db` (`xabarlar` jadvali) — ish holati.
- `data/jurnal/xabar/<sana>.jsonl` — o'zgarmas tarix (N3 audit shundan).
- `uzatish.berdi(kimdan_agent, xabar_id, ..., kimga="N1"|"N2")` har muvaffaqiyatli
  navbatga qo'yilgan xabar uchun.
- Heartbeat `run/heartbeat/SHLYUZ.json` har 30 s (`ishlayapti`).

## Qanday ishga tushiriladi
```
python3 agents/shlyuz/main.py [--port 8471]
# yoki
bin/inplus ishga SHLYUZ
```
Mock ЕТС serveri alohida kerak: `python3 mock/ets_server.py &` (port 8472).
CLI: `bin/inplus shlyuz yubor|jurnal|statistika` (`bin/inplus shlyuz` ga qarang).

Muhim env: `INPLUS_SHLYUZ_PORT` (8471), `TG_REAL` (1 = real Telegram),
`ETS_MOCK_URL`/`ETS_MOCK_REJIM`, `INPLUS_SHLYUZ_YETKAZISH_S` (SMS yetkazilganlik
tekshiruvi kutish vaqti, sekund — demo/test uchun kichraytiriladi, standart 600),
`INPLUS_SHLYUZ_TEZ=1` (retry backoff birligi daqiqa o'rniga sekund — faqat sinov).

## Yiqilsa nima qilish
`Restart=always` (systemd) — X2 heartbeat orqali kuzatadi (`sla_daq: 2`,
servis turi). Navbatda qolgan xabarlar SQLite'da saqlanadi, qayta ishga
tushganda ishchi davom etadi (holat=`navbatda` bo'lganlar yo'qolmaydi).

## Kimga aytish
`data/insident`ga o'zi yozmaydi (bu X2/X1 ishi). O'zining tuzatib bo'lmas
ichki xatolarini (masalan SMS 5 urinishdan keyin xato) S-900 orqali xodimga
yuboradi — bu uchun `konfig/skriptlar.json` dagi S-900 `ruxsat_agentlar`
ro'yxatiga **"SHLYUZ"** minimal, hujjatlashtirilgan qo'shimcha sifatida
qo'shilgan (frozen konfigga yagona tegilgan joy — pastga qarang).

## Muzlatilgan konfigga tegilgan joy (hisobot)
`konfig/skriptlar.json`: `S-900.ruxsat_agentlar` ro'yxatiga `"SHLYUZ"` qo'shildi
(`["X2","X1","D1","D6","N3"]` -> `[...,"SHLYUZ"]`). Sabab: shlyuzning o'z ichki
kritik xatosini (masalan SMS provayder butunlay javob bermay qolishi) xodimga
yetkazishning yagona yo'li — shlyuz o'zi shlyuz orqali yuboradi, aks holda bu
holat hech qayerga ko'rinmaydi. Boshqa hech qanday konfig/kontrakt/lib fayli
o'zgartirilmagan.
