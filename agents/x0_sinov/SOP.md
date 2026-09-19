# SOP — X0 Sinov agenti (kanareyka)

## Maqsad
X2/X1/W1 monitoringni haqiqiy agentlarsiz ham har kuni sinab turish. 10% ehtimol
bilan ataylab yiqiladi — X2 uni davolashi kerak.

## Kirish
Yo'q (manba o'qimaydi).

## Chiqish
- `data/sinov/<sana>.jsonl` — bitta satr
- KPI `{sinov: 1}`, uzatish(berdi -> X1)

## Qanday ishga tushiriladi
```
bin/inplus ishga X0
bin/inplus ishga X0 --yiqil     # ataylab yiqitish (X2 demo)
```
Jadval: har 5 daqiqa (`*:0/5`).

## Yiqilsa nima qilish
- Bu KUTILGAN. X2 30-60 s ichida `HB_XATO` -> restart. 3 martadan oshsa `RESTART_MAX`.

## Kimga aytish
- Egasi yo'q — sof texnik kanareyka. RESTART_MAX bo'lsa X2 direktorga S-900.
