# SOP — S6 Qarzdorlar eslatmasi

## Maqsad
Joriy paketdagi qarzdor talabalarni topadi va har biriga shlyuz orqali (S-001
skripti bilan) to'lov eslatmasi yuboradi. Dublikat/limit/oq-qora ro'yxat/vaqt
oynasi — HAMMASI SHLYUZDA hal bo'ladi, S6 faqat so'raydi.

## Kirish (nimadan o'qiydi)
- `paket.oqi("S6")` — joriy paket, faqat `talabalar` bo'limi (`tolov.qarz`,
  `tolov.keyingi_sana`, `ism`, `kurs_id`, `telefon`, `telegram_id`).

## Chiqish (nima yozadi)
- `data/qarz/<sana>.json` — kunlik tarix nusxa.
- `data/qarz.json` — joriy.
- Xabar: `shlyuz_client.yubor(skript_id="S-001", kanal="tg", kimga={"tur":"talaba", ...})`
  — har qarzdorga bitta so'rov, idempotent kalit `S6:S-001:<talaba_id>:<sana>`
  (bir kunda ikki marta ishga tushirilsa ikkinchisi shlyuzda `dublikat` bo'ladi).
- KPI: `qarzdorlar_soni`, `qarz_jami`, `xabar_<holat>` (masalan `xabar_navbatda`,
  `xabar_rad`, `xabar_shlyuz_yoq`).

## Qanday ishga tushiriladi
```
bin/inplus ishga S6
# yoki (shlyuz ishlab turishi kerak, aks holda "shlyuz_yoq" bilan davom etadi)
python3 agents/shlyuz/main.py &
python3 agents/s6_qarz/main.py --bir-marta --sana 2026-09-19 --rejim mock
```
Jadval: `konfig/agentlar.json` → `S6.jadval` (09:00, S-001 vaqt oynasi
09:00-20:00 bilan mos).

## Yiqilsa nima qilish
- Shlyuz o'chiq bo'lsa agent YIQILMAYDI — har eslatma `xabar_holati: shlyuz_yoq`
  bilan yoziladi, keyinroq shlyuz yoqilgach qayta ishga tushirish yetarli.
- Haqiqiy xato (masalan `data/paket/joriy.json` yo'q) — heartbeat `xato`,
  exit != 0, X2 qayta yoqadi.
- Log: `data/jurnal/agent/S6/<sana>.log`.

## Kimga aytish
- Egasi: `konfig/agentlar.json` → `S6.egasi` (X-001). Ko'p xabar `rad`
  bo'lsa (masalan `OQ_ROYXAT`) — bu mock rejimda normal (real rejimda
  paketdagi haqiqiy manzillar ishlatiladi, §7.1).
