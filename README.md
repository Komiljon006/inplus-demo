# IN PLUS — 1-blok «Poydevor»

Ta'lim markazi uchun agentlar poydevori. Bitta ma'lumot paketi (`data/paket/joriy.json`),
qat'iy **kontraktlar** (JSON Schema), va agent skeletlari. Hamma agent
`heartbeat → ish → kpi → uzatish` tartibida ishlaydi, manbaga faqat `adapter/` orqali
kiradi, xabarni faqat shlyuz orqali yuboradi.

Bu repozitoriyda **Oqim A** (poydevor/skelet) qurilgan: kontraktlar, `lib/inplus/`,
konfiglar, mock generatori + ЕТС serveri, X0 sinov agenti, CLI, systemd shablonlari,
testlar. Haqiqiy agentlar (D1 · D6 · shlyuz · N3 · X2 · X1 · W1) keyingi oqimlarda
qo'shiladi — interfeyslar tayyor.

## Tez boshlash

```bash
cd inplus-demo
python3 -m venv .venv
.venv/bin/pip install jsonschema requests pytest

export INPLUS_ILDIZ="$PWD"          # ildiz (hardcode yo'q)

# 1) Deterministik mock ma'lumot (3 manba)
.venv/bin/python mock/generator.py --lid 400 --talaba 260 --urug 42 --kun 0

# 2) Kontrakt testlari
.venv/bin/python -m pytest tests/ -q

# 3) Sinov agentini ishga tushirish (Mac'da systemd kerak emas)
.venv/bin/python bin/inplus ishga X0        # heartbeat + kpi + uzatish
.venv/bin/python bin/inplus ishga X0 --yiqil  # ataylab yiqilish (exit != 0)
.venv/bin/python bin/inplus rejim
.venv/bin/python bin/inplus holat
```

Chiqadigan fayllar:
- `run/heartbeat/X0.json` — yurak urishi
- `data/kpi/X0/<sana>.json` — KPI (kun bloki agregat)
- `data/uzatish/<sana>.jsonl` — kim kimga nima berdi/oldi

## Struktura

```
konfig/     inplus.env, agentlar.json, skriptlar.json, oq/qora_royxat, amocrm_bosqich
kontrakt/   8 *.schema.json (draft-07) + namuna/<nom>_{ok,xato}.json
lib/inplus/ konfig, kontrakt, fayl, jurnal, heartbeat, kpi, uzatish, paket, courses,
            shlyuz_client, agent + adapter/{amocrm,getcourse,sheets,sms_ets,telegram}
agents/     x0_sinov/ (kanareyka), _shablon/ (yangi agent uchun)
mock/       generator.py (deterministik), ets_server.py (127.0.0.1:8472 mock SMS)
data/       runtime (git'da yo'q)   run/heartbeat/   wiki/   www/   systemd/   bin/   tests/
```

## Rejim: mock ↔ real

Bitta env — `INPLUS_REJIM=mock|real`. `adapter.ol("amocrm")` rejimga qarab
`MockAmoCRM` yoki `RealAmoCRM` qaytaradi; agent kodi rejimni bilmaydi.
Telegram uchun `TG_REAL=1` kanal darajasidagi override. SMS `Real` — `INPLUS_REJIM=real`
va `ETS_TOKEN` ikkalasisiz `RuntimeError` (adashib real SMS ketmasin).

## Yangi agent qanday yoziladi

1. `agents/_shablon/` ni `agents/<id>/` ga nusxalang (masalan `agents/n5_tabrik/`).
2. `agent_id` ni o'rnating, faqat `ish(self) -> dict` ni yozing. Skelet
   (`lib/inplus/agent.py`) heartbeat/KPI/uzatish/xatoni o'zi boshqaradi.
   `ish()` qaytaradi: `{"kirdi": {...}, "chiqdi": {...}, "kpi": {...}}`.
3. `konfig/agentlar.json` ga bitta yozuv qo'shing (X1/X2/W1 tegilmaydi).
4. Papkaga `SOP.md` yozing (W1 uni wiki'ga oladi).
5. Serverda: `systemd/inplus-<id>.{service,timer}` shablonidan foydalaning.

Qoidalar: manbaga faqat `adapter.ol(...)`; boshqa agent faylini faqat `paket.oqi()` /
`courses.oqi()` orqali (uzatish `oldi` avtomat yoziladi); xabar faqat
`shlyuz_client.yubor(...)`; xatoni yutmaslik.

## Vaqt

Hamma joyda `Asia/Tashkent` (`konfig.hozir()`), ISO-8601. `utcnow()` taqiq.
