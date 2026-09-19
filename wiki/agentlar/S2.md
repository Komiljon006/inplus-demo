# SOP — S2 Sotuv voronkasi hisoboti

## Maqsad
Joriy paketdagi lidlarni sotuv bosqichi (voronka) bo'yicha sanaydi va summa/kanal
kesimini chiqaradi — «bugun voronkada nima bor?» degan savolga bitta faylda javob.

## Kirish (nimadan o'qiydi)
- `paket.oqi("S2")` — joriy paket (`data/paket/joriy.json`), faqat `lidlar` bo'limi
  ishlatiladi (`bosqich`, `summa`, `manba_kanal`).

## Chiqish (nima yozadi)
- `data/voronka/<sana>.json` — kunlik tarix nusxa.
- `data/voronka.json` — joriy (dashboard/keyingi agentlar shundan o'qiydi).
- `wiki/voronka_<sana>.md` — ixtiyoriy, W1 index'ga olishi mumkin (xato bo'lsa
  agent yiqilmaydi, jim o'tkazib yuboriladi).
- KPI: `jami_lid`, `jami_summa`, `ortacha_chek`, `sotildi` (+ `kirdi.lidlar`,
  `chiqdi.voronka/bosqich_faol/kanal`).
- Xabar YUBORMAYDI (И0 — faqat hisobot).

## Qanday ishga tushiriladi
```
bin/inplus ishga S2
# yoki
python3 agents/s2_voronka/main.py --bir-marta --sana 2026-09-19 --rejim mock
```
Jadval: `konfig/agentlar.json` → `S2.jadval` (D1 dan keyin, 06:15).

## Yiqilsa nima qilish
- Sabab deyarli doim: `data/paket/joriy.json` yo'q yoki schema xato — avval D1 ni
  ishga tushiring (`bin/inplus ishga D1`).
- Heartbeat `xato`, exit != 0. X2 avtomat qayta yoqadi.
- Log: `data/jurnal/agent/S2/<sana>.log`.

## Kimga aytish
- Egasi: `konfig/agentlar.json` → `S2.egasi` (X-001). Kritik holat yo'q (И0,
  faqat hisobot) — S-900 yubormaydi.
