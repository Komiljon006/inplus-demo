# SOP — X1 Zanjirlar auditori

> W1 shu faylni `wiki/agentlar/X1.md` ga oladi.

## Maqsad
"A berdi = B oldi" sverkasi — `data/uzatish/<sana>.jsonl` va `data/kpi/*/<sana>.json`
ni `konfig/agentlar.json` bilan solishtiradi, kod daraxtini shlyuzni chetlab
o'tishga tekshiradi (statik grep).

## Kirish
- `uzatish.oqi(sana)` — `data/uzatish/<sana>.jsonl`
- `kpi.oqi(<agent>, sana)` — har agent uchun
- `konfig/agentlar.json`, `agents/**/*.py` (grep)

## Chiqish
- `data/x1/<sana>.json` — agent × tekshiruv matritsasi
- `data/insident/<sana>.jsonl` — kodlar: `UZ_KUTILDI, UZ_HASH, UZ_SONI,
  UZ_YETIM, KPI_YOQ, KPI_NISBAT, KPI_XATO, SHLYUZ_CHETLAB, HB_YOQ`
- `wiki/jurnal/zanjir_<sana>.md` — jadval (agent · berdi · oldi · farq · holat)
- KPI `X1`: `{uzatish_jami, buzilgan, agent_tekshirildi, yashil}`
- `buzilgan > 0` bo'lsa — 1 ta S-900 xabar direktorga (hammasi bitta xabarda).

## Qanday ishga tushiriladi
```
bin/inplus ishga X1
python3 agents/x1_auditor/main.py --bir-marta --sana 2026-09-19
```
Jadval: `konfig/agentlar.json` → `X1.jadval` (`22:00`, timer). `audit(sana)`
funksiyasi to'g'ridan-to'g'ri ham chaqiriladi (testlar, boshqa kunlar uchun).

## Muhim moslashtirish
`lib/inplus/uzatish.oldi()` bitta `obyekt` uchun ENG OXIRGI `berdi`ning
`uzatish_id`sini oladi — bir kunda bir faylga bir necha marta yozilganda
(masalan X0 sinov jurnali) bu noaniqlik yaratadi. X1 shuning uchun
`berdi`/`oldi`ni **`uzatish_id`** bo'yicha moslaydi (`obyekt` emas) va X0'dan
o'ziga (`kimga: "X1"`) kelgan har bir xabarni alohida "oldi" qiladi
(`_oldi_yoz`, `lib`ni o'zgartirmasdan).

## Yiqilsa nima qilish
- Heartbeat `xato`, exit != 0, X2 qayta yoqadi.
- Log: `data/jurnal/agent/X1/<sana>.log`.

## Kimga aytish
- Egasi: direktor (X-001). Buzilgan topilsa avtomat S-900.
