# SOP — W1 Xotira

> W1 shu faylni ham `wiki/agentlar/W1.md` ga oladi (o'zi haqida o'zi yozadi).

## Maqsad
`konfig/`, har agentning `SOP.md`, kunlik KPI/insident/X1/N3 natijalarini
`wiki/` ga (Markdown + HTML) yig'adi; eski `data/` fayllarini arxivlaydi;
kechqurun S-901 kunlik xulosani direktorga yuboradi.

## Kirish
- `konfig/agentlar.json`, `konfig/skriptlar.json`
- `agents/<papka>/SOP.md` (har biri)
- `data/kpi/*/<sana>.json`, `data/insident/<sana>.jsonl`, `data/x1/<sana>.json`,
  `data/n3/<sana>.json` (bo'lsa), `paket.oqi()`

## Chiqish
- `wiki/reestr/agentlar.md`, `wiki/reestr/skriptlar.md`
- `wiki/agentlar/<id>.md` (har agent SOP nusxasi)
- `wiki/jurnal/<sana>.md` (kunlik xulosa), `wiki/insident/<sana>.md`
- `wiki/_html/**` (nginx shu yerdan beradi), `wiki/_html/index.html`
- `data/arxiv/<YYYY-MM>.tar.gz` (30 kundan eski uzatish/kpi/insident/jurnal),
  `data/paket/arxiv/` (14 kundan eski paketlar)
- S-901 xabari (direktor, TG)

## Qanday ishga tushiriladi
```
bin/inplus ishga W1
python3 agents/w1_xotira/main.py --bir-marta --sana 2026-09-19
bin/inplus arxiv oqi kpi/X0/2026-08-01.json     # arxivga tushgan faylni o'qish
```
Jadval: `23:00` (timer). Har ishga tushishda hamma wiki fayli **qayta**
yoziladi (keshlash yo'q) — shuning uchun `SOP.md` o'zgarsa keyingi ishga
tushishda avtomat yangilanadi.

## Yiqilsa nima qilish
- Heartbeat `xato`, exit != 0, X2 qayta yoqadi.
- Arxivlash xato bersa ham (masalan disk to'la) — `ish()` xatoni yutmaydi,
  Agent skeleti heartbeat/KPI `xato` deb yozadi.

## Kimga aytish
- Egasi: direktor (X-001). Kunlik xulosa S-901 har kuni avtomat boradi.
