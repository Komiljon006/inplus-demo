# Agentlar reestri

| ID | Nom | Tur | Jadval/Unit | SLA (daq) | Egasi | Ijro |
|---|---|---|---|---|---|---|
| D1 | Sborshik dannyx | timer | *-*-* 06:00:00 | 30 | X-001 | И0 |
| D6 | Kurslar jadvali | timer | *-*-* 05:50:00 | 20 | — | И0 |
| N3 | Skript reestri + post-audit | timer | *-*-* 21:00:00 | 15 | — | И0 |
| S2 | Sotuv voronkasi hisoboti | timer | *-*-* 06:15:00 | 15 | X-001 | И0 |
| S4 | Menejer nazorati | timer | *-*-* 06:25:00 | 15 | X-001 | И0 |
| S6 | Qarzdorlar eslatmasi | timer | *-*-* 09:00:00 | 20 | X-001 | И1 |
| SHLYUZ | Xabar shlyuzi (N1+N2) | service | inplus-shlyuz | 2 | — | И1 |
| W1 | Xotira | timer | *-*-* 23:00:00 | 15 | — | И1 |
| X0 | Sinov agenti (X2 ni tekshirish uchun) | timer | *:0/5 | 7 | — | И0 |
| X1 | Zanjirlar auditori | timer | *-*-* 22:00:00 | 15 | — | И0 |
| X2 | Doktor | service | inplus-x2 | 2 | — | И1 |
| X3 | Analitika hisoboti | timer | *-*-* 06:20:00 | 15 | X-001 | И0 |
