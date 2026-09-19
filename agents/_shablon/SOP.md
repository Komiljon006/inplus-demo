# SOP — <AGENT_ID> <nom>

> W1 shu faylni `wiki/agentlar/<id>.md` ga oladi. Har agent papkasida bo'lishi SHART.

## Maqsad
Bu agent nima qiladi (1-2 gap).

## Kirish (nimadan o'qiydi)
- `paket.oqi()` / `courses.oqi()` / `adapter.ol("...")` — sanab bering.

## Chiqish (nima yozadi)
- `data/...` fayli, KPI kalitlari, uzatish(berdi) kimga.

## Qanday ishga tushiriladi
```
bin/inplus ishga <ID>
# yoki
python3 agents/<papka>/main.py --bir-marta --sana 2026-09-19 --rejim mock
```
Jadval: `konfig/agentlar.json` dagi `jadval` (systemd timer).

## Yiqilsa nima qilish
- Heartbeat `xato` bo'ladi, exit != 0. X2 avtomat qayta yoqadi (`qayta_yoqish.max`).
- Log: `data/jurnal/agent/<ID>/<sana>.log`.

## Kimga aytish
- Egasi: `konfig/agentlar.json` dagi `egasi` (X-...). Kritik holatda S-900.
