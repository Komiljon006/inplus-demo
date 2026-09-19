# SOP — N3 Skript reestri + post-audit

> W1 shu faylni `wiki/agentlar/N3.md` ga oladi.

## Maqsad
Ikki mustaqil vazifa: (1) `konfig/skriptlar.json` o'zgarganda sintaksisini
tekshiradi (reestr buzilsa shlyuz eski nusxani ishlatadi), (2) har kuni
21:00 da kunlik xabar trafigini sverka qiladi (jurnal x reestr x shlyuz.db).

## Kirish (nimadan o'qiydi)
- `konfig/skriptlar.json` — `tekshir` uchun.
- `data/jurnal/xabar/<sana>.jsonl`, `data/shlyuz.db` (`xabarlar` jadvali,
  to'g'ridan-to'g'ri SQLite o'qiladi, faqat SELECT) — `audit` uchun.

## Chiqish (nima yozadi)
- `data/n3/<sana>.json` — to'liq audit natijasi (kpi, kesim, nomuvofiqliklar).
- `wiki/reestr/xabar_audit_<sana>.md` — inson o'qiydigan hisobot.
- KPI `{xabar_jami, yuborildi, yetkazildi, rad, xato, narx_som, nomuvofiq}`.
- `nomuvofiq > 0` bo'lsa `shlyuz_client.yubor(..., "S-900", ...)` direktorga.

## Qanday ishga tushiriladi
```
python3 agents/n3_reestr/main.py tekshir [--fayl konfig/skriptlar.json]
python3 agents/n3_reestr/main.py audit --bir-marta --sana 2026-09-19
bin/inplus ishga N3          # subkomandasiz -> audit (Agent skeleti)
```
Jadval: `konfig/agentlar.json` → `N3.jadval` (21:00).

## Yiqilsa nima qilish
`audit` — Agent skeleti orqali heartbeat `xato` + exit != 0, X2 qayta
yoqadi. `tekshir` — git-hook/qo'lda ishlatiladi, muvaffaqiyatsizlikda
exit 1 (CI/deploy to'xtaydi, `konfig/skriptlar.json` qo'lda tuzatiladi).

## Kimga aytish
Egasi: `konfig/agentlar.json` yo'q (N3 uchun `egasi` maydoni ko'rsatilmagan) —
amalda X-001. Nomuvofiqlik topilsa S-900 orqali xodimga avtomat boradi.
