# SOP — D6 Kurslar jadvali

## Maqsad
Google Sheets'dagi (mock: `mock/sheets/jadval.csv`) kurslar/guruhlar jadvalini
o'qiydi, validatsiya qiladi va `data/courses.json` — 133 agent shundan
foydalanadigan yagona kurs/guruh manbasini yozadi.

## Kirish (nimadan o'qiydi)
- `adapter.ol("sheets").varaq(SHEETS_ID, "Jadval")` — 2D ro'yxat (sarlavha + qatorlar).
  Mock: `mock/sheets/jadval.csv`. Real: Google Sheets API v4 (`SHEETS_ID`,
  `SHEETS_SA_FAYL`).

## Ish (validatsiya)
Har qator: `kurs_id`/`guruh_id` regex, `format` enum, `narx > 0`, `sigim` butun son,
`boshlanish`/`tugash` haqiqiy sana, `tugash > boshlanish`. Butun jadval bo'yicha:
dublikat `guruh_id`, bir xil kun+vaqt slotida bir xil xona/ustoz to'qnashuvi
(ogohlantirish), `sigim >= band` (band — mockda deterministik hash, real
GetCourse guruh sonidan kelishi mumkin).

## Chiqish (nima yozadi)
- `data/courses.json` — faqat `validatsiya.holat != "xato"` bo'lsa (xato bo'lsa
  eskisi qoladi, `data/courses/<sana>.xato.json` yoziladi).
- `data/courses/<sana>.json` — kunlik tarix nusxasi.
- `uzatish(berdi, "data/courses.json", kimga="*")` — `courses.py` avtomat.
- KPI: `{qator, kurs, guruh, xato, ogohlantirish}`.
- `xato > 0` bo'lsa `shlyuz_client.yubor(S-902, direktor)`.

## Qanday ishga tushiriladi
```
bin/inplus ishga D6
# yoki
python3 agents/d6_jadval/main.py --bir-marta --sana 2026-09-19 --rejim mock
```
Jadval: `konfig/agentlar.json` dagi `05:50` (systemd timer). D1 dan oldin ishlaydi.

## Yiqilsa nima qilish
- `sheets.varaq()` bo'sh yoki adapter xato bersa — agent yiqiladi (heartbeat `xato`,
  exit != 0), `courses.json` **o'zgarmaydi**. X2 qayta yoqadi.
- Jadval qatorida xato (masalan noto'g'ri sana) — agent **yiqilmaydi**, faqat
  `courses.json` yangilanmaydi va S-902 ketadi — «odam tuzatadi, agent buzilgan
  jadvalni tarqatmaydi».

## Kimga aytish
- Egasi: `konfig/agentlar.json` dagi `D6.egasi`. Jadval xatosi — S-902 orqali
  to'g'ridan-to'g'ri direktorga (Telegram, `TG_ADMIN_ID`).
