# SOP — S4 Menejer nazorati

> W1 shu faylni `wiki/agentlar/S4.md` ga oladi.

## Maqsad
Mijozning ASOSIY dardi: «lid keladi-yu menejer ishlamaydi / javobsiz
qoladi» — buni ko'rish uchun oldin CRM'ga qo'lda kirib, filtr qo'yib,
sanash kerak edi. S4 har kuni avtomat: har menejerning necha lidi bor,
qanchasiga aloqa qilingan, qanchasi butunlay javobsiz qolgan, va o'rtacha
qancha vaqtda javob beradi — bittasini ham qo'ldan o'tkazib yubormaydi.

## Kirish (nimadan o'qiydi)
- `paket.oqi("S4")` — joriy paket (`data/paket/joriy.json`): `lidlar`
  (`bosqich`, `yaratildi`, `oxirgi_aloqa`, `menejer_id`, `manba_kanal`) va
  `xodimlar` (`ism`, `rol`) bo'limlari. Boshqa hech narsa o'qilmaydi.

## Chiqish (nima yozadi)
- `data/nazorat.json` — joriy hisobot:
  - `menejerlar[]` — har menejer uchun `lid` (biriktirilgan lidlar soni),
    `ishlangan` (`oxirgi_aloqa > yaratildi` — kamida bitta aloqa),
    `javobsiz` (`bosqich=="yangi"` va tegilmagan), `reaksiya_soat`
    (`ishlangan` lidlar bo'yicha o'rtacha yaratildi→oxirgi_aloqa soat).
  - `javobsiz_lidlar[]` — barcha javobsiz lidlar, eng ko'p kun
    tegmagandan boshlab (top 15): `lid_id`, `ism`, `menejer_id`,
    `menejer_ism`, `kanal`, `kun_javobsiz`.
  - `jami.javobsiz_jami`, `jami.ortacha_reaksiya_soat`.
- KPI: `menejerlar`, `javobsiz_jami`, `ortacha_reaksiya_soat`,
  `javobsiz_lidlar_royxatda` (+ `kirdi.lidlar/xodimlar`,
  `chiqdi.menejerlar/javobsiz_lidlar`).
- Xabar YUBORMAYDI (И0 — faqat hisobot/nazorat, kontrolyor rol).

## Hisoblash mantig'i (qisqacha)
- `javobsiz` (lid darajasida) — `bosqich=="yangi"` VA (`oxirgi_aloqa`
  yo'q YOKI `oxirgi_aloqa == yaratildi`). Boshqa bosqichga o'tgan lidga
  kamida bitta aloqa bo'lgan deb hisoblanadi — shuning uchun faqat
  "yangi" da tekshiriladi.
- `ishlangan` — `oxirgi_aloqa > yaratildi` (bosqichdan qat'iy nazar).
- `reaksiya_soat` — faqat `ishlangan` lidlar bo'yicha, real vaqt farqi
  (soatda), o'rtachasi.
- `kun_javobsiz` — paket sanasi bilan lidning `yaratildi` sanasi orasidagi
  farq (kun). Ro'yxat shu bo'yicha kamayish tartibida (eng eski — eng
  uzoq kutgan — birinchi).

## Qanday ishga tushiriladi
```
bin/inplus ishga S4
# yoki
python3 agents/s4_nazorat/main.py --bir-marta --sana 2026-09-19 --rejim mock
```
Jadval: `konfig/agentlar.json` → `S4.jadval` (D1 dan keyin).

## Yiqilsa nima qilish
- Sabab deyarli doim: `data/paket/joriy.json` yo'q yoki schema xato — avval
  D1 ni ishga tushiring (`bin/inplus ishga D1`).
- Heartbeat `xato`, exit != 0. X2 avtomat qayta yoqadi.
- Log: `data/jurnal/agent/S4/<sana>.log`.

## Kimga aytish
- Egasi: `konfig/agentlar.json` → `S4.egasi` (X-001). Kritik holat yo'q
  (И0, faqat hisobot) — S-900 yubormaydi.
