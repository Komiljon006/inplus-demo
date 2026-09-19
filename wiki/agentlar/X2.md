# SOP — X2 Doktor

> W1 shu faylni `wiki/agentlar/X2.md` ga oladi.

## Maqsad
Barcha agentlarning heartbeat'ini (`run/heartbeat/<id>.json`) kuzatadi, muammoni
aniqlaydi, qayta yoqadi (yoki Mac'da simulyatsiya qiladi), insident yozadi va
`data/dashboard.json` ni yangilaydi (`www/index.html` shundan o'qiydi).

## Kirish
- `konfig/agentlar.json` — kuzatiladigan agentlar ro'yxati, `sla_daq`, `tur`,
  `qayta_yoqish.{max,oraliq_daq}`, `unit`.
- `run/heartbeat/<id>.json` — har agentning yurak urishi.
- `data/kpi/<id>/<sana>.json` — dashboard uchun kunlik hisob.

## Chiqish
- `data/insident/<sana>.jsonl` — kod: `HB_XATO | HB_ESKI | RESTART_MAX`.
- `data/x2/restart.json` — qayta yoqish hisobi (`{agent: {soni, oxirgi}}`) va
  `_ochiq` — hozir ochiq turgan insidentlar ro'yxati (bir agentga bitta,
  spam bo'lmasin uchun).
- `data/dashboard.json` — har sikl oxirida qayta yoziladi.
- KPI `X2`: `{sikllar, restartlar, insidentlar, ochiq_insident}`.
- Kritik holatda (`RESTART_MAX`) yoki oddiy insidentda shlyuz orqali `S-900`
  direktorga.

## Qanday ishga tushiriladi
```
bin/inplus ishga X2                        # bitta sikl (--bir-marta majburiy bin/inplus da)
python3 agents/x2_doktor/main.py --sikl 3 --oraliq 5
python3 agents/x2_doktor/main.py --bir-marta --simulyatsiya   # Mac uchun majburiy simulyatsiya
```
Prodda (Linux, systemd bor): `python3 agents/x2_doktor/main.py` argumentsiz —
abadiy 30 s siklda ishlaydi, `systemctl restart inplus-<unit>` bilan qayta yoqadi.
Mac'da (`systemctl` topilmasa) avtomatik simulyatsiya rejimiga o'tadi: agentni
`agents/<papka>/main.py --bir-marta` bilan to'g'ridan-to'g'ri qayta ishga
tushiradi — natija heartbeat'dan darhol ko'rinadi.

## Yiqilsa nima qilish
- X2 ning o'zi yiqilsa — heartbeat `xato` yoziladi, exit != 0. Prodda
  `Restart=always` + `WatchdogSec=120` (`sd_notify`) uni qayta ko'taradi.
- Bitta agent 3 martadan ortiq qayta yoqilsa (`qayta_yoqish.max`) — `RESTART_MAX`
  kritik, X2 uni qayta yoqishni TO'XTATADI, odamga S-900 kritik xabar ketadi.

## Kimga aytish
- Har agentning `egasi` (`konfig/agentlar.json`); topilmasa direktor (X-001),
  `S-900` orqali.

## Demo/mock cheklovi
- Heartbeat fayli umuman yo'q bo'lsa (agent hali bir marta ham ishlamagan yoki
  boshqa oqim — masalan SHLYUZ — hali qurilmagan) — bu insident deb hisoblanmaydi
  (haqiqiy systemd bo'lganda `NextElapseUSecRealtime` bilan aniqlanadi; Mac
  demo'da soddalashtirilgan).
- `holat: tugadi` uchun `keyingi_kutilgan` hozircha `lib/inplus/agent.py` da
  doim `null` yoziladi — shuning uchun timer agentlar uchun oxirgi
  `tugadi`dan SLA daqiqadan ko'p o'tganini zaxira mezon sifatida ishlatamiz.
