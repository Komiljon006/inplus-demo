# IN PLUS — 1-BLOK «POYDEVOR» BUILD-REJASI

> 8 agent: D1 · D6 · N1 · N2 · N3 · X2 · X1 · W1
> Stek: Python 3.11+ (stdlib + `requests`, `jsonschema`), systemd timer/service, JSON + SQLite, Telegram Bot API, nginx (static).
> Rejim: `INPLUS_REJIM=mock|real` — bitta env o'zgaruvchi, hamma adapter shunga qaraydi.
> Sana: 2026-09-19. Vaqt zonasi hamma joyda `Asia/Tashkent`, ISO-8601 (`2026-09-19T06:00:12+05:00`).

---

## 0. Bir sahifada

| Nima | Qaror |
|---|---|
| Kontrakt qayerda | `/opt/inplus/kontrakt/*.schema.json` (JSON Schema draft-07) + `lib/inplus/kontrakt.py` (validator). Hamma agent `kontrakt.tekshir()` dan o'tmagan faylni **yozmaydi va o'qimaydi**. |
| Ma'lumot oqimi | fayl orqali (`/opt/inplus/data/`), HTTP faqat shlyuzda (N1/N2 — `127.0.0.1:8471`). Bazalar yo'q, brokerlar yo'q. |
| Agent = nima | bitta papka `agents/<id>/main.py` + `inplus-<id>.service` (+ `.timer`). Har ishga tushish: `heartbeat → ish → kpi → uzatish(berdi) → heartbeat(tugadi)`. Bu skelet `lib/inplus/agent.py` da, agent faqat `ish()` ni yozadi. |
| Mock ↔ real | `lib/inplus/adapter/<manba>.py` ichida `Mock<Manba>` va `Real<Manba>` — bitta interfeys. `adapter.ol("amocrm")` rejimga qarab qaytaradi. Agent kodi rejimni bilmaydi. |
| Xabar | faqat `shlyuz_client.yubor(...)` → HTTP → navbat (SQLite) → kanal adapteri. Bevosita `requests.post(api.telegram.org)` **taqiq** (X1 audit buni grep bilan tutadi). |
| Monitoring | heartbeat fayllari (`run/heartbeat/<id>.json`) + KPI (`data/kpi/<id>/<sana>.json`) + uzatish jurnali (`data/uzatish/<sana>.jsonl`). X2 = doktor (qayta yoqadi), X1 = auditor (sverka), W1 = wiki. |
| Muddat | Oqim A 2 ish kuni → B/C/D parallel 4 ish kuni → E integratsiya+demo 2 ish kuni = **8 ish kuni, 3–4 ishchi** (yoki 1 ishchi ~14 kun). |

---

## 1. Arxitektura

```
                 ┌───────────────── MANBALAR (Nuqta A) ─────────────────┐
                 │  amoCRM API   │  GetCourse API  │  Google Sheets API  │
                 │  (mock: json) │  (mock: json)   │  (mock: csv)        │
                 └──────┬────────┴────────┬────────┴─────────┬──────────┘
                        │ adapter/amocrm  │ adapter/getcourse│ adapter/sheets
                        ▼                 ▼                  ▼
   06:00  ┌─────────────────────┐              ┌────────────────────────┐  05:50
          │ D1 Sborshik (ETL)   │ ◄── o'qiydi ─│ D6 Jadval o'quvchi     │
          │ → data/paket/       │   kurs_id    │ → data/courses.json    │
          │   2026-09-19.json   │              │   + validatsiya xatolari│
          │ → data/paket/joriy.json (symlink)  └────────────────────────┘
          └──────────┬──────────┘
                     │  KONTRAKT: paket.schema.json  (133 agent shundan o'qiydi)
                     ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │              QOLGAN 127 AGENT (2–N bloklar)  — faqat o'qiydi          │
   │   har biri: heartbeat + kpi + uzatish(berdi/oldi) + shlyuz_client     │
   └──────────────┬───────────────────────────────────────┬───────────────┘
                  │ shlyuz_client.yubor()                  │ heartbeat / kpi / uzatish
                  ▼                                        ▼
   ┌──────────────────────────────┐        ┌───────────────────────────────┐
   │  XABAR SHLYUZI  127.0.0.1:8471│        │  ORKESTR / NAZORAT             │
   │  POST /yubor  (idempotent)    │        │  X2 Doktor  — heartbeat, restart│
   │   ├ N3 reestr: skript_id? ✔   │        │             insident jurnali   │
   │   ├ oq ro'yxat ✔  qora ✔      │        │             dashboard.json/html│
   │   ├ dublikat/limit/vaqt oynasi│        │  X1 Auditor — «A berdi = B oldi»│
   │   ├ navbat  shlyuz.db         │        │             KPI sverka, grep   │
   │   ├ N1 SMS (ЕТС)  mock|real   │        │  W1 Xotira  — wiki/*.md, SOP,  │
   │   └ N2 Telegram   mock|real   │        │             jurnal arxivi      │
   │  jurnal: data/jurnal/xabar/   │        └───────────────┬───────────────┘
   │  N3 post-audit 21:00          │                        │ nginx static
   └──────────────┬───────────────┘                        ▼
                  ▼                              http://<server>/inplus/  (dashboard + wiki)
        mijoz / xodim telefoni
```

Bog'lanish qoidasi (5 ta, buzilmaydi):
1. Manbaga faqat `adapter/` orqali. Agent kodida `requests` bo'lmasin.
2. Agentlar bir-biri bilan **fayl** orqali gaplashadi (`data/`), HTTP yo'q. Istisno — shlyuz.
3. Har yozilgan fayl uchun `uzatish(berdi)`, har o'qilgan fayl uchun `uzatish(oldi)` yoziladi (lib avtomat qiladi).
4. Xabar faqat shlyuz orqali, faqat `skript_id` bilan.
5. Agent yiqilsa — exit code ≠ 0 + heartbeat `xato`. Yutib yubormaydi (`try/except Exception: pass` taqiq).

---

## 2. KONTRAKTLAR (Oqim A — hammadan oldin)

Hammasi `/opt/inplus/kontrakt/` da: `*.schema.json` + `namuna/*.json`. Versiya `"versiya": "1.0"` — har fayl bosh qismida. Maydon **qo'shish** mumkin (1.1), **o'chirish/nomini o'zgartirish** = 2.0 va migratsiya.

### 2.1 `paket.schema.json` — D1 chiqishi (ENG MUHIM KONTRAKT)

Fayl: `data/paket/<YYYY-MM-DD>.json`, symlink `data/paket/joriy.json` → oxirgi muvaffaqiyatli. Atomik yoziladi (`tmp` → `os.replace`).

```json
{
  "versiya": "1.0",
  "paket_id": "2026-09-19",
  "yaratildi": "2026-09-19T06:01:44+05:00",
  "rejim": "mock",
  "hash": "sha256:9f2c…",
  "manbalar": {
    "amocrm":    {"holat": "ok",    "olindi": "2026-09-19T06:00:10+05:00", "qator": 412, "davomiylik_s": 8.2, "xato": null},
    "getcourse": {"holat": "ok",    "olindi": "2026-09-19T06:00:31+05:00", "qator": 268, "davomiylik_s": 19.7, "xato": null},
    "sheets":    {"holat": "eski",  "olindi": "2026-09-18T06:00:12+05:00", "qator": 14,  "davomiylik_s": 0,   "xato": "429 quota; kechagi nusxa ishlatildi"}
  },
  "kurslar_ref": {"fayl": "data/courses.json", "hash": "sha256:1b7e…", "versiya": "1.0"},

  "lidlar": [
    {
      "lid_id": "amo:48213",
      "manba": "amocrm",
      "ism": "Dilnoza Karimova",
      "telefon": "+998901234567",
      "telegram_id": null,
      "bosqich": "konsultatsiya",
      "bosqich_kodi": 142,
      "kurs_id": "K-BUX-01",
      "menejer_id": "X-003",
      "yaratildi": "2026-09-17T14:20:00+05:00",
      "oxirgi_aloqa": "2026-09-18T11:05:00+05:00",
      "manba_kanal": "instagram",
      "summa": 2400000,
      "teglar": ["sentyabr", "chegirma"],
      "xom": {"pipeline_id": 7712, "status_id": 142}
    }
  ],

  "talabalar": [
    {
      "talaba_id": "gc:10877",
      "ism": "Bekzod Rahimov",
      "telefon": "+998935550011",
      "telegram_id": 123456789,
      "email": "b.rahimov@mail.ru",
      "kurs_id": "K-BUX-01",
      "guruh_id": "G-BUX-01-SEN",
      "holat": "faol",
      "boshladi": "2026-09-01",
      "tolov": {"jami": 2400000, "tolandi": 1200000, "qarz": 1200000, "keyingi_sana": "2026-10-01", "valyuta": "UZS"},
      "davomat_foiz": 83,
      "oxirgi_dars": "2026-09-18",
      "progress_foiz": 27,
      "xom": {"user_id": 10877, "group": "Бухгалтер с нуля — сентябрь"}
    }
  ],

  "tolovlar": [
    {"tolov_id": "gc:p:55120", "talaba_id": "gc:10877", "summa": 1200000, "valyuta": "UZS", "sana": "2026-09-01", "usul": "payme", "kurs_id": "K-BUX-01", "izoh": "1-qism"}
  ],

  "xodimlar": [
    {"xodim_id": "X-003", "ism": "Madina", "rol": "menejer", "telefon": "+998901112233", "telegram_id": 987654321, "faol": true},
    {"xodim_id": "X-001", "ism": "Direktor", "rol": "direktor", "telefon": "+998900000001", "telegram_id": 111111111, "faol": true}
  ],

  "statistika": {"lidlar": 412, "talabalar": 268, "faol_talabalar": 201, "qarzdorlar": 37, "qarz_jami": 44400000, "tolovlar_kecha": 6}
}
```

Qoidalar (schema `required` + `additionalProperties:false` yuqori darajada):
- `*_id` — `manba:raqam` prefiksli satr (`amo:`, `gc:`, `sh:`), hech qachon oddiy int. Bu 133 agentni «qaysi bazaning ID si?» dan qutqaradi.
- `telefon` — faqat E.164 (`+998XXXXXXXXX`), normalizatsiya adapterda. Normalizatsiya bo'lmasa → `null` + `manbalar.<x>.ogohlantirish[]` ga yoziladi.
- `holat` enum: `faol | tugatdi | tashladi | muzlatilgan | kutmoqda`. `bosqich` enum D1 `adapter/amocrm.py` ichidagi `BOSQICH_XARITA` orqali amoCRM status_id → 8 ta ichki kod (`yangi · aloqa · konsultatsiya · sinov_dars · tolov_kutish · sotildi · yoqotildi · qayta`). Xarita `konfig/amocrm_bosqich.json` — mijoz voronkasi ko'rilgach to'ldiriladi.
- `xom` — manbaning asl maydonlari (2-N bloklar uchun zaxira), schemada `object`, tekshirilmaydi.
- `manbalar.<x>.holat` enum: `ok | eski | xato`. Bitta manba yiqilsa paket **baribir** yoziladi (`eski` = kechagi nusxa), lekin `paket_id` ostidagi `holat_umumiy: "qisman"` qo'yiladi va X2 ga insident ketadi. Uchalasi ham yiqilsa — paket yozilmaydi, `joriy.json` kechagiga qoladi.
- Hajm chegarasi: 20 MB. Undan katta bo'lsa — `lidlar` faqat 90 kunlik, qolgani `data/paket/arxiv/`.

### 2.2 `courses.schema.json` — D6 chiqishi

Fayl: `data/courses.json` (+ `data/courses/<sana>.json` tarix).

```json
{
  "versiya": "1.0",
  "yaratildi": "2026-09-19T05:50:08+05:00",
  "manba": {"tur": "sheets", "id": "1AbC…", "varaq": "Jadval", "qator": 14},
  "validatsiya": {
    "holat": "ogohlantirish",
    "xatolar": [
      {"qator": 9,  "maydon": "boshlanish", "qiymat": "31.09.2026", "xabar": "sana mavjud emas", "daraja": "xato"},
      {"qator": 12, "maydon": "xona",       "qiymat": "A-2",        "xabar": "G-BUX-02 bilan bir vaqtda bir xona", "daraja": "ogohlantirish"}
    ]
  },
  "kurslar": [
    {
      "kurs_id": "K-BUX-01",
      "nom": "Buxgalter noldan",
      "format": "offline",
      "narx": 2400000,
      "valyuta": "UZS",
      "davomiylik_oy": 3,
      "ustoz_id": "X-010",
      "faol": true,
      "guruhlar": [
        {"guruh_id": "G-BUX-01-SEN", "boshlanish": "2026-09-01", "tugash": "2026-11-30",
         "kunlar": ["du", "chor", "ju"], "vaqt": "18:30-20:30", "xona": "A-1",
         "sigim": 20, "band": 17, "holat": "davom"}
      ]
    }
  ]
}
```

- `kurs_id`, `guruh_id` formati: `^K-[A-Z]{2,5}-\d{2}$`, `^G-[A-Z]{2,5}-\d{2}-[A-Z]{3}$`. D1 `lidlar[].kurs_id` va `talabalar[].guruh_id` **shu faylda bo'lishi shart** — bo'lmasa `null` + ogohlantirish.
- `validatsiya.holat`: `ok | ogohlantirish | xato`. `xato` bo'lsa `data/courses.json` **yangilanmaydi** (eskisi qoladi), lekin `data/courses/<sana>.xato.json` yoziladi va shlyuz orqali `S-902` skript bilan direktorga ketadi. Sinf: «jadval xatosini odam tuzatadi, agent buzilgan jadvalni tarqatmaydi».

### 2.3 Uzatish (peredacha) formati — X1 uchun

Fayl: `data/uzatish/<YYYY-MM-DD>.jsonl`, **append-only**, har agent `lib` orqali yozadi (`fcntl.flock`). Bitta uzatish = ikkita satr, bitta `uzatish_id`:

```json
{"uzatish_id":"u-2026-09-19-D1-0001","vaqt":"2026-09-19T06:01:44+05:00","yonalish":"berdi","kimdan":"D1","kimga":"*","tur":"fayl","obyekt":"data/paket/2026-09-19.json","hash":"sha256:9f2c…","soni":{"lidlar":412,"talabalar":268},"kutish_daq":180}
{"uzatish_id":"u-2026-09-19-D1-0001","vaqt":"2026-09-19T07:00:03+05:00","yonalish":"oldi","kimdan":"D1","kimga":"S3","tur":"fayl","obyekt":"data/paket/2026-09-19.json","hash":"sha256:9f2c…","soni":{"lidlar":412,"talabalar":268}}
```

- `kimga: "*"` — broadcast (paket). X1 `agentlar.json` dagi `oqiydi: ["paket"]` ro'yxatidan **kim olishi kerak** edi, deb biladi.
- `hash` — `berdi` va `oldi` da tenglashishi shart. Farq = «A berdi ≠ B oldi» insidenti (`UZ-HASH`).
- `soni` — obyekt turiga qarab erkin dict, lekin `berdi.soni == oldi.soni` bo'lishi shart (`UZ-SONI`).
- `kutish_daq` — shu vaqt ichida `oldi` kelmasa → `UZ-KUTILDI` (jim agent).
- `tur` enum: `fayl | xabar | buyruq`. Shlyuz `xabar` turi uchun o'zi yozadi (`kimdan: <agent>, kimga: N1|N2, obyekt: xabar_id`).
- `oldi` ni agent qo'lda yozmaydi — `paket.oqi()` / `courses.oqi()` funksiyasi o'zi yozadi. Shuning uchun «unutdi» bo'lmaydi.

### 2.4 KPI sxemasi — `kpi.schema.json`

Fayl: `data/kpi/<agent_id>/<YYYY-MM-DD>.json` — kun bo'yicha **bitta** fayl, har ishga tushish `ishlar[]` ga qo'shiladi:

```json
{
  "versiya": "1.0", "agent": "D1", "sana": "2026-09-19",
  "ishlar": [
    {"boshlandi": "2026-09-19T06:00:02+05:00", "tugadi": "2026-09-19T06:01:44+05:00", "davomiylik_s": 102.3,
     "holat": "ok", "xato_soni": 0, "xato_oxirgi": null,
     "kirdi": {"amocrm": 412, "getcourse": 268, "sheets": 14},
     "chiqdi": {"lidlar": 412, "talabalar": 268, "paket": 1},
     "kpi": {"paket_yaratildi": 1, "manba_ok": 2, "manba_eski": 1, "telefon_normalizatsiya_xato": 3}}
  ],
  "kun": {"ishlar_soni": 1, "ok": 1, "xato": 0, "davomiylik_s_jami": 102.3, "kpi": {"paket_yaratildi": 1}}
}
```

- Har agentda `kpi` dict **majburiy 3 kalit** + o'zining maxsuslari: `holat`, `kirdi`, `chiqdi`. X1 `kirdi`→`chiqdi` nisbatini `agentlar.json` dagi `kutilgan_nisbat` bilan solishtiradi (masalan D1: `chiqdi.lidlar == kirdi.amocrm`).
- `kun` blokini `lib` har yozishda qayta hisoblaydi (agregat). Dashboard shu `kun` ni o'qiydi.

### 2.5 Heartbeat — `heartbeat.schema.json`

Fayl: `run/heartbeat/<agent_id>.json` (tmpfs, `/run/inplus/` ga symlink):

```json
{"agent":"D1","vaqt":"2026-09-19T06:01:44+05:00","holat":"tugadi","pid":48122,"boshlandi":"2026-09-19T06:00:02+05:00","xabar":"","keyingi_kutilgan":"2026-09-20T06:00:00+05:00"}
```

`holat` enum: `boshladi | ishlayapti | tugadi | xato`. Uzoq ishlaydigan agent (shlyuz, X2) har 30 s `ishlayapti` yozadi. X2 qoidasi: `now - vaqt > agentlar[id].sla_daq` **yoki** `holat == xato` → insident.

### 2.6 Agent reestri — `konfig/agentlar.json` (X1/X2/W1 manbasi)

```json
{
  "D1": {"nom": "Sborshik dannyx", "blok": 1, "tur": "timer", "jadval": "*-*-* 06:00:00", "sla_daq": 30,
         "unit": "inplus-d1", "yozadi": ["paket"], "oqiydi": ["courses"], "kutilgan_uzatish": {"paket": "*"},
         "qayta_yoqish": {"max": 3, "oraliq_daq": 5}, "egasi": "X-001", "ijro": "И0"},
  "D6": {"nom": "Kurslar jadvali", "blok": 1, "tur": "timer", "jadval": "*-*-* 05:50:00", "sla_daq": 20, "unit": "inplus-d6", "yozadi": ["courses"], "oqiydi": [], "ijro": "И0"},
  "SHLYUZ": {"nom": "Xabar shlyuzi (N1+N2)", "tur": "service", "sla_daq": 2, "unit": "inplus-shlyuz", "port": 8471, "ijro": "И1"},
  "N3": {"nom": "Skript reestri + post-audit", "tur": "timer", "jadval": "*-*-* 21:00:00", "sla_daq": 15, "unit": "inplus-n3", "oqiydi": ["jurnal_xabar", "skriptlar"], "ijro": "И0"},
  "X2": {"nom": "Doktor", "tur": "service", "sla_daq": 2, "unit": "inplus-x2", "ijro": "И1"},
  "X1": {"nom": "Zanjirlar auditori", "tur": "timer", "jadval": "*-*-* 22:00:00", "sla_daq": 15, "unit": "inplus-x1", "oqiydi": ["uzatish", "kpi"], "ijro": "И0"},
  "W1": {"nom": "Xotira", "tur": "timer", "jadval": "*-*-* 23:00:00", "sla_daq": 15, "unit": "inplus-w1", "oqiydi": ["kpi", "insident", "jurnal_xabar"], "ijro": "И1"},
  "X0": {"nom": "Sinov agenti (X2 ni tekshirish uchun)", "tur": "timer", "jadval": "*:0/5", "sla_daq": 7, "unit": "inplus-x0", "ijro": "И0"}
}
```

Yangi agent = shu faylga bitta yozuv + papka. X2/X1/W1 ni **o'zgartirish shart emas**.

### 2.7 Skript reestri — `konfig/skriptlar.json` (N3)

```json
{
  "versiya": "1.0",
  "skriptlar": [
    {
      "skript_id": "S-001", "nom": "tolov_eslatma_3kun", "maqsad": "qarzdor talabaga 3 kun oldin eslatma",
      "kanallar": ["sms", "tg"],
      "matn": {"uz": "Assalomu alaykum, {ism}! {kurs} kursi uchun {summa} so'm to'lov muddati {sana}. IN PLUS", "ru": "Здравствуйте, {ism}! Оплата {summa} сум за курс {kurs} до {sana}. IN PLUS"},
      "ozgaruvchilar": ["ism", "kurs", "summa", "sana"],
      "sms_uzunlik_max": 160,
      "kimga_turi": "talaba",
      "limit": {"bir_odamga_kunlik": 1, "dublikat_soat": 72, "kunlik_jami": 300},
      "vaqt_oynasi": "09:00-20:00",
      "tasdiqlagan": "X-001", "tasdiq_sana": "2026-09-19", "holat": "faol",
      "ruxsat_agentlar": ["*"]
    },
    {"skript_id": "S-900", "nom": "insident_xodimga", "kanallar": ["tg"], "matn": {"uz": "⚠️ {agent}: {xabar} ({vaqt})"}, "ozgaruvchilar": ["agent","xabar","vaqt"], "kimga_turi": "xodim", "limit": {"bir_odamga_kunlik": 50, "dublikat_soat": 1}, "vaqt_oynasi": "00:00-24:00", "holat": "faol", "ruxsat_agentlar": ["X2","X1","D1","D6"]},
    {"skript_id": "S-901", "nom": "kunlik_xulosa_direktor", "kanallar": ["tg"], "matn": {"uz": "📊 {sana}: lid {lidlar}, faol {faol}, qarzdor {qarzdor}, agent ok {ok}/{jami}"}, "kimga_turi": "xodim", "holat": "faol", "ruxsat_agentlar": ["W1"]},
    {"skript_id": "S-902", "nom": "jadval_xatosi", "kanallar": ["tg"], "matn": {"uz": "📋 Jadvalda {soni} xato: {royxat}"}, "kimga_turi": "xodim", "holat": "faol", "ruxsat_agentlar": ["D6"]},
    {"skript_id": "S-999", "nom": "test", "kanallar": ["sms","tg"], "matn": {"uz": "IN PLUS test: {matn}"}, "kimga_turi": "xodim", "limit": {"bir_odamga_kunlik": 100}, "holat": "faol", "ruxsat_agentlar": ["*"]}
  ]
}
```

Qoidalar: matndagi `{…}` lar `ozgaruvchilar` bilan **aynan** teng (N3 `tekshir` buni ushlaydi). `holat: arxiv` skript bilan yuborish rad. Mijoz skriptni o'zgartirsa — **yangi ID** (`S-001` → `S-001a` emas, `S-002`), eski `arxiv`. Jurnal shunda tarixga mos qoladi.

### 2.8 Xabar so'rovi va jurnali — shlyuz kontrakti

**So'rov** (`POST http://127.0.0.1:8471/yubor`, header `X-Idempotency-Key`):
```json
{"kimdan_agent":"S3","kanal":"tg","kimga":{"tur":"talaba","id":"gc:10877","telegram_id":123456789,"telefon":"+998935550011"},
 "skript_id":"S-001","til":"uz","ozgaruvchilar":{"ism":"Bekzod","kurs":"Buxgalter noldan","summa":"1 200 000","sana":"1-oktyabr"},
 "idempotent_kalit":"S3:S-001:gc:10877:2026-10-01","muhimlik":"oddiy"}
```
**Javob**: `{"xabar_id":"x-2026-09-19-000412","holat":"navbatda"}` yoki `{"holat":"rad","sabab":"DUBLIKAT|OQ_ROYXAT|LIMIT_KUNLIK|VAQT_OYNASI|SKRIPT_YOQ|SKRIPT_ARXIV|OZGARUVCHI_YETISHMAYDI|AGENT_RUXSAT_YOQ|KANAL_YOQ"}`. Rad ham jurnalga yoziladi (holat `rad`).

**SQLite `data/shlyuz.db`** jadval `xabarlar`:
```
xabar_id TEXT PK · idempotent_kalit TEXT UNIQUE · kimdan_agent · kanal · kimga_tur · kimga_id · manzil (telefon|tg_id)
skript_id · til · ozgaruvchilar JSON · matn_tayyor · holat (navbatda|yuborilmoqda|yuborildi|yetkazildi|rad|xato)
rad_sabab · yaratildi · yuborildi · provayder_id · urinish INT · keyingi_urinish · narx_som · rejim (mock|real)
```
Indekslar: `(manzil, skript_id, yaratildi)` — dublikat/limit uchun; `(holat, keyingi_urinish)` — navbat uchun.

**Jurnal** `data/jurnal/xabar/<YYYY-MM-DD>.jsonl` — SQLite'dagi har holat o'zgarishi bitta satr (append). N3 post-audit va W1 arxiv shundan. SQLite = ish holati, jsonl = o'zgarmas tarix.

### 2.9 Insident — `insident.schema.json` (X2/X1 yozadi)

`data/insident/<YYYY-MM-DD>.jsonl`:
```json
{"insident_id":"i-2026-09-19-0007","vaqt":"…","kim":"X2","agent":"D1","kod":"HB_ESKI|HB_XATO|UZ_KUTILDI|UZ_HASH|UZ_SONI|KPI_NISBAT|SHLYUZ_CHETLAB|RESTART_MAX","daraja":"ogoh|jiddiy|kritik","xabar":"heartbeat 47 daq eski (SLA 30)","harakat":"systemctl restart inplus-d1","natija":"ok","yopildi":"…"}
```

---

## 3. Papka / fayl strukturasi

Demo (Mac): `~/inplus-demo/` — aynan shu daraxt, `INPLUS_ILDIZ` env orqali. Serverda `/opt/inplus/`. Kod ildizni **hech qayerda hardcode qilmaydi**.

```
/opt/inplus/
├── konfig/
│   ├── inplus.env                 # INPLUS_REJIM=mock|real, INPLUS_ILDIZ, TZ, TG_BOT_TOKEN, TG_ADMIN_ID, AMO_*, GC_*, SHEETS_*, ETS_*
│   ├── agentlar.json              # §2.6
│   ├── skriptlar.json             # §2.7
│   ├── oq_royxat.json             # mock: {"telefon":["+99890…"],"telegram_id":[111…]}; real: "manba":"paket" + qo'shimcha
│   ├── qora_royxat.json           # opt-out (mijoz "to'xtat" desa)
│   └── amocrm_bosqich.json        # status_id → ichki bosqich
├── kontrakt/
│   ├── paket.schema.json · courses.schema.json · uzatish.schema.json · kpi.schema.json
│   ├── heartbeat.schema.json · skript.schema.json · xabar.schema.json · insident.schema.json
│   └── namuna/                    # har schema uchun 1 to'g'ri + 1 noto'g'ri namuna (test)
├── lib/inplus/
│   ├── __init__.py · konfig.py    # env o'qish, ildiz, rejim, TZ
│   ├── kontrakt.py                # tekshir(nom, obj) → jsonschema; xato → KontraktXato
│   ├── agent.py                   # class Agent: run() skeleti = heartbeat→ish()→kpi→uzatish; CLI --bir-marta --sana
│   ├── heartbeat.py · kpi.py · uzatish.py · jurnal.py (jsonl append+flock) · fayl.py (atomik yozish, symlink)
│   ├── paket.py                   # oqi() (+uzatish oldi avtomat), yoz()
│   ├── courses.py                 # oqi(), yoz()
│   ├── shlyuz_client.py           # yubor(...) → HTTP; mock rejimda ham HTTP (shlyuz o'zi mock qiladi)
│   └── adapter/
│       ├── __init__.py            # ol(nom) → rejimga qarab Mock*/Real*
│       ├── amocrm.py              # class AmoCRM(ABC): lidlar(kundan) · xodimlar() · bosqichlar()  → MockAmoCRM / RealAmoCRM
│       ├── getcourse.py           # talabalar() · tolovlar(kundan) · guruhlar()
│       ├── sheets.py              # varaq(id, nom) → list[list[str]]
│       ├── sms_ets.py             # yubor(telefon, matn) → {provayder_id, holat, narx}; holat(provayder_id)
│       └── telegram.py            # yubor(chat_id, matn) · yangiliklar() (opt-in /start uchun)
├── agents/
│   ├── d1_sborshik/main.py
│   ├── d6_jadval/main.py
│   ├── shlyuz/main.py             # N1+N2 bitta servis: HTTP + navbat ishchisi (2 thread)
│   ├── n3_reestr/main.py          # `tekshir` (reestr sintaksisi) + `audit` (kunlik sverka)
│   ├── x2_doktor/main.py
│   ├── x1_auditor/main.py
│   ├── w1_xotira/main.py
│   └── x0_sinov/main.py           # 5 daqiqada 1 marta, 10% ehtimol bilan ataylab yiqiladi (X2 demo)
├── mock/                          # Oqim A yozadi
│   ├── amocrm/leads.json · users.json · pipelines.json
│   ├── getcourse/users.json · payments.json · groups.json
│   ├── sheets/jadval.csv          # 14 qator, 2 ta ataylab xato (§2.2)
│   ├── generator.py               # `--lid 400 --talaba 260 --urug 42` → yuqoridagilarni yasaydi (deterministik)
│   └── ets_server.py              # 127.0.0.1:8472 — ЕТС API taqlidi (200/429/500 rejimlari)
├── data/                          # runtime; git'da yo'q
│   ├── paket/  <sana>.json · joriy.json → · arxiv/
│   ├── courses.json · courses/<sana>.json
│   ├── uzatish/<sana>.jsonl · kpi/<agent>/<sana>.json · insident/<sana>.jsonl
│   ├── jurnal/xabar/<sana>.jsonl · jurnal/agent/<agent>/<sana>.log
│   ├── shlyuz.db
│   └── dashboard.json
├── run/heartbeat/                 # → /run/inplus/heartbeat (tmpfs)
├── wiki/                          # W1 egasi; Markdown
│   ├── index.md · agentlar/<id>.md (SOP) · reestr/skriptlar.md · reestr/agentlar.md
│   ├── jurnal/<sana>.md (kunlik xulosa) · insident/<sana>.md · arxiv/
│   └── _html/                     # W1 md→html; nginx shu yerdan beradi
├── www/                           # nginx root: index.html (dashboard, dashboard.json ni fetch qiladi) + wiki/ → ../wiki/_html
├── systemd/                       # inplus-*.service / .timer; `install.sh` /etc/systemd/system ga ko'chiradi
├── bin/
│   ├── inplus                     # CLI: rejim | ishga <agent> | holat | shlyuz yubor … | x1 audit | demo
│   ├── install.sh · demo.sh · reset_mock.sh
├── tests/                         # pytest: kontrakt_test.py · adapter_mock_test.py · shlyuz_test.py · x1_test.py
└── README.md
```

nginx: `location /inplus/ { alias /opt/inplus/www/; }` — faqat static. Shlyuz porti (8471) tashqariga **ochilmaydi** (`127.0.0.1` bind).

---

## 4. PARALLEL OQIMLAR

```
Kun:   1     2     3     4     5     6     7     8
       ├─ A ─┤
             ├──────── B (D6→D1) ───────┤
             ├──────── C (N2→N1→N3) ────┤
             ├──────── D (X2→X1→W1) ────┤
                                        ├── E ──┤
```

| Oqim | Kim | Kutadi | Chiqishi | «Tayyor» belgisi |
|---|---|---|---|---|
| **A — Kontraktlar + skelet** | 1 arxitektor (eng kuchli) | — | `kontrakt/`, `lib/inplus/` (agent.py, adapter ABC + Mock*, uzatish/kpi/heartbeat), `konfig/*.json`, `mock/generator.py`, `systemd/` shablon, `bin/inplus`, `x0_sinov` | `pytest tests/kontrakt_test.py` yashil; `inplus ishga X0` heartbeat+kpi+uzatish yozadi; `mock/generator.py` deterministik 3 manbani yasaydi |
| **B — Data** | ishchi 1 | A | D6, D1 | §5 D6/D1 qabul mezonlari |
| **C — Shlyuz** | ishchi 2 | A | shlyuz (N1+N2), N3 | §5 N1/N2/N3 |
| **D — Orkestr** | ishchi 3 | A (X2 uchun X0 yetarli, X1 uchun `kontrakt/namuna/uzatish.jsonl`, W1 uchun namuna KPI) | X2, X1, W1, dashboard | §5 X2/X1/W1 |
| **E — Integratsiya + demo** | hammasi | B, C, D | `demo.sh` boshdan-oxir, README, mijozga ko'rsatish | §6 demo 8/8 qadam o'tadi |

Oqimlar orasidagi bog'lanish **faqat kontrakt orqali** — B ishchisi C ni kutmaydi, chunki D1 dan shlyuzga xabar S-902 `shlyuz_client` orqali ketadi, shlyuz yo'q bo'lsa `ConnectionError` → jurnalga `shlyuz_yoq` va davom etadi (xabar yo'qolgani KPI da ko'rinadi). Xuddi shunday D ishchisi X0 sinov agenti bilan ishlaydi, haqiqiy D1 ni kutmaydi.

Oqim A ichki tartibi (2 kun, ketma-ket): (1) schemalar + namunalar → (2) `konfig.py`, `fayl.py`, `jurnal.py` → (3) `heartbeat/kpi/uzatish.py` → (4) `agent.py` skeleti + X0 → (5) adapter ABC + Mock* + generator → (6) `bin/inplus`, systemd shablon, `install.sh`. A ning 1-kuni oxirida schemalar **muzlatiladi** (tag `kontrakt-1.0`) — B/C/D shunda boshlashi mumkin, qolgan A ishlari 2-kunda tugaydi.

---

## 5. HAR AGENT

Umumiy: har agent `lib.agent.Agent` dan meros, `ish(self) -> dict(kpi)` ni yozadi. CLI: `python3 main.py [--bir-marta] [--sana 2026-09-19] [--rejim mock]`. Log: `data/jurnal/agent/<id>/<sana>.log` (stdlib logging, JSON satrlar). systemd: `Type=oneshot` + timer (yoki `Type=simple` + `Restart=on-failure` servis uchun), `EnvironmentFile=/opt/inplus/konfig/inplus.env`, `User=inplus`.

### D6 — Kurslar jadvalini o'qish (И0, timer 05:50)

- **Kirish**: `adapter.sheets.varaq(SHEETS_ID, "Jadval")` → 2D ro'yxat. Mock: `mock/sheets/jadval.csv`. Real: Google Sheets API v4 `values.get` (service account JSON, `SHEETS_SA_FAYL`).
- **Ish**: sarlavha qatorini kutilgan 12 ustun bilan solishtiradi (`kurs_id, nom, format, narx, davomiylik_oy, ustoz_id, guruh_id, boshlanish, tugash, kunlar, vaqt, xona, sigim`) → har qatorni parslaydi → validatsiya: sana haqiqiyligi, `tugash > boshlanish`, `kurs_id` regex, `sigim ≥ band`, xona+vaqt+kunlar to'qnashuvi, ustoz bir vaqtda 2 guruhda, narx > 0, dublikat guruh_id → `courses.json` (§2.2).
- **Chiqish**: `data/courses.json` (`holat != xato` bo'lsa), `data/courses/<sana>.json`, uzatish(berdi, `courses`, kimga `*`), KPI `{qator, kurs, guruh, xato, ogohlantirish}`; `xato > 0` → `shlyuz.yubor(S-902, direktor)`.
- **Mock → real nuqtasi**: faqat `adapter/sheets.py: RealSheets` + env `SHEETS_ID`, `SHEETS_SA_FAYL`. Mijozdan: jadval Sheet'ga service-account emailini «Viewer» qilib qo'shish. Ustun nomlari mijoz jadvaliga mos kelmasa — `konfig/sheets_ustun_xarita.json` (mijoz nomi → ichki nom), kodga tegilmaydi.
- **Qabul**: (1) mock csv 14 qatordan 12 kurs/guruh + 1 `xato` + 1 `ogohlantirish` chiqadi, `courses.json` **yangilanmaydi** (xato bor); (2) csv'da xatoli qator tuzatilsa → `holat: ogohlantirish`, fayl yangilanadi; (3) `kontrakt.tekshir("courses", …)` o'tadi; (4) uzatish+KPI+heartbeat yozilgan; (5) S-902 xabar shlyuz jurnalida ko'rinadi (yoki `shlyuz_yoq` KPI da).

### D1 — Sborshik dannyx (И0, timer 06:00; D6 dan keyin `After=inplus-d6.service`)

- **Kirish**: 3 adapter: `amocrm.lidlar(kundan=-90)`, `amocrm.xodimlar()`, `getcourse.talabalar()`, `getcourse.tolovlar(kundan=-30)`, `courses.oqi()`.
- **Ish**: har manbani alohida `try` — yiqilsa `manbalar.<x>.holat=eski` va kechagi paketdan shu bo'lim olinadi → normalizatsiya (telefon E.164, ID prefiks, bosqich xaritasi, `kurs_id` courses'da borligini tekshirish) → `statistika` → `kontrakt.tekshir("paket")` → atomik yozish + `joriy.json` symlink + `hash`.
- **Chiqish**: `data/paket/<sana>.json`, uzatish(berdi, `*`, `kutish_daq: 180`), KPI `{manba_ok, manba_eski, telefon_xato, kurs_id_topilmadi}`, manba yiqilsa S-900 → direktor.
- **Mock**: `MockAmoCRM` `mock/amocrm/*.json` ni o'qiydi, real API javob **formatida** (`_embedded.leads[]`, `custom_fields_values`) qaytaradi — shunda normalizatsiya kodi mock va realda **bir xil** sinaladi. Generator har kuni 3–8 lid qo'shib, 1–2 bosqich siljitadi (`--kun` argumenti) — demo «kunlar o'tishi» ni ko'rsatadi. `MockGetCourse` ham xuddi shunday (`export` javobi formatida).
- **Real nuqtasi**: `RealAmoCRM` (OAuth2 long-lived token, `GET /api/v4/leads?with=contacts&filter[updated_at][from]=…`, 250/sahifa, 7 req/s limit), `RealGetCourse` (`/pl/api/account/exports/…` — **asinxron**: export yaratish → `export_id` → poll 5–60 s → yuklash; shuning uchun D1 jadvali 06:00, SLA 30 daq). Env: `AMO_DOMEN, AMO_TOKEN, GC_DOMEN, GC_KALIT`. Bosqich xaritasi `amocrm_bosqich.json` mijoz voronkasidan to'ldiriladi (1 soatlik ish).
- **Qabul**: (1) mock 3 manbadan paket 400+ lid/260+ talaba, schema o'tadi, ≤ 15 s; (2) `INPLUS_MOCK_YIQIL=getcourse` env bilan ishga tushirilsa → `manbalar.getcourse.holat=eski`, paket baribir yoziladi, S-900 ketadi, exit 0; (3) 3 manba ham yiqilsa → exit 1, `joriy.json` o'zgarmaydi, heartbeat `xato`; (4) telefon `90 123 45 67` → `+998901234567`, `abc` → `null` + KPI `telefon_xato`; (5) `talabalar[].guruh_id` courses'da yo'q → `null` + KPI; (6) ikki marta ishga tushirilsa fayl idempotent (hash bir xil, uzatish 2 marta emas — `paket_id` bo'yicha).

### Shlyuz (N1 + N2 bitta servis, `inplus-shlyuz.service`, `Restart=always`)

Bitta jarayon, 2 thread: **HTTP** (`http.server.ThreadingHTTPServer`, 127.0.0.1:8471) va **navbat ishchisi** (1 s da SQLite'dan `navbatda` va `keyingi_urinish ≤ now` ni oladi). Heartbeat har 30 s.

`POST /yubor` tartibi (har rad jurnalga): (1) JSON schema `xabar` → (2) `skriptlar.json` da `skript_id` bor, `faol`, `kanal` ruxsat, `kimdan_agent` ruxsat → (3) `ozgaruvchilar` to'liq → matn render, SMS bo'lsa uzunlik ≤ `sms_uzunlik_max` (ortiq → rad `SMS_UZUN`) → (4) oq ro'yxat: mock — `oq_royxat.json` dagilar **faqat**; real — `paket.joriy` dagi talaba/lid/xodim manzillari + `oq_royxat.json`; `qora_royxat.json` → rad → (5) `idempotent_kalit` UNIQUE → bor bo'lsa `{"holat":"dublikat","xabar_id":<eski>}` (200, rad emas — idempotent) → (6) `dublikat_soat`: shu manzil+skript oxirgi N soatda yuborilgan → rad `DUBLIKAT` → (7) `bir_odamga_kunlik`, `kunlik_jami` → rad `LIMIT_*` → (8) `vaqt_oynasi` tashqarisi → `navbatda`, `keyingi_urinish` = oynaning boshlanishi (rad **emas**, kechiktiriladi; `muhimlik: kritik` bo'lsa darhol) → (9) INSERT + jurnal + uzatish(berdi, kimdan=agent, kimga=N1|N2, obyekt=xabar_id).

`GET /holat/<xabar_id>`, `GET /statistika` (dashboard uchun). Boshqa yo'l yo'q.

**N2 — Telegram** (И1):
- `adapter/telegram.py`: `Real` = `sendMessage` (`requests`, 10 s timeout, 429 → `retry_after` hurmat, 400 `chat not found`/`bot was blocked` → `xato`, urinish yo'q). `Mock` = `data/jurnal/xabar/mock_tg/<sana>.jsonl` ga yozadi + `provayder_id: "mock-tg-<n>"`.
- **Demo'da real rejimda ishlatiladi** — bot bepul: `@inplus_demo_bot` (BotFather), `TG_BOT_TOKEN`, `oq_royxat.telegram_id` = ishchi + mijoz vakili. Shlyuzning o'zida `INPLUS_REJIM=mock` bo'lsa ham `TG_REAL=1` env bilan N2 ni real qilish mumkin (kanal darajasidagi override — faqat TG uchun, SMS uchun yo'q).
- Muhim: bot faqat unga `/start` bosganga yozadi. `telegram.yangiliklar()` (`getUpdates`, 60 s timer `inplus-tg-optin`) `/start` bosganlarni `data/tg_optin.json` ga (`telefon` ↔ `telegram_id`, kontakt tugmasi orqali) yozadi; D1 keyingi paketda `telegram_id` ni shundan to'ldiradi. Bu 2-blok uchun ham kerak — hozir minimal.
- **Qabul**: (1) `inplus shlyuz yubor --kanal tg --skript S-999 --kimga xodim:X-001 --oz matn=salom` → telefonga xabar keladi, `holat: yuborildi`, `provayder_id = message_id`; (2) aynan shu buyruq 1 daq ichida qayta → `dublikat`, ikkinchi xabar **kelmaydi**; (3) `oq_royxat`da yo'q `telegram_id` → rad `OQ_ROYXAT`, jurnalda; (4) `S-001` bilan `sana` o'zgaruvchisiz → rad `OZGARUVCHI_YETISHMAYDI`; (5) bot bloklangan chat → `xato`, urinish 1, navbat tiqilmaydi; (6) internet uzilsa → `urinish++`, `keyingi_urinish = now + 2^n min` (max 5), keyin `xato`.

**N1 — SMS (ЕТС)** (И1):
- `adapter/sms_ets.py`: `Real` — ЕТС (Eskiz/Play Mobile/ЕТС — **mijoz shartnomasi qaysi bo'lsa**) HTTP API: token → `POST send` → `message_id`; `holat(id)` yetkazilganlik. Provayder aniq bo'lmagani uchun ABC uchta metod: `token()`, `yubor(telefon, matn, jonatuvchi)`, `holat(id)` — realizatsiya 1 fayl, ~80 qator, shartnoma kelgach 2–3 soat.
- `Mock` — `mock/ets_server.py` ga **haqiqiy HTTP** (127.0.0.1:8472): shunda retry/timeout/429 kodi mockda ham sinaladi. Server rejimlari env `ETS_MOCK_REJIM=ok|429|500|sekin`. Narx `narx_som: 95`.
- SMS **hech qachon** mock'dan tashqari real'ga «adashib» ketmasin: `Real` klass `INPLUS_REJIM=real` **va** `ETS_TOKEN` ikkalasisiz `RuntimeError`. Real rejimda ham `konfig/oq_royxat.json` da `sms_sinov_rejim: true` bo'lsa faqat oq ro'yxatdagi raqamlarga — mijozga topshirishning 1-haftasi shunday.
- Yetkazilganlik: navbat ishchisi `yuborildi` xabarlar uchun 10 daq keyin `holat(id)` → `yetkazildi | xato`. Provayderda status yo'q bo'lsa — `yuborildi` da qoladi (N3 hisobotda alohida ustun).
- **Qabul**: (1) mock ETS `ok` — `yuborildi` → 10 daq (test: `--tez`) `yetkazildi`; (2) `ETS_MOCK_REJIM=429` → 3 urinish eksponensial, keyin `ok` ga o'tkazilsa yuboriladi; (3) `500` → 5 urinishdan keyin `xato`, S-900 X2 ga; (4) 161 belgili matn → rad `SMS_UZUN`; (5) `vaqt_oynasi` tashqari (test: soatni `--hozir 22:30` bilan) → `navbatda`, `keyingi_urinish 09:00`; (6) `inplus shlyuz statistika` kanal/skript/holat kesimini beradi.

### N3 — Skriptlar reestri + post-audit (И0, timer 21:00 + `tekshir` qo'lda)

- **`tekshir`** (reestr o'zgarganda, git-hook/qo'lda): schema, `{…}` ↔ `ozgaruvchilar` tengligi, ID takrori, `arxiv` ga o'tgan skriptga `ruxsat_agentlar` bo'lsa ogoh, SMS matn uzunligi (o'zgaruvchilar 15 belgi deb) → xato bo'lsa exit 1 (shlyuz reestrni **yuklamaydi**, eskisini ishlatadi + S-900).
- **`audit`** (21:00): `jurnal/xabar/<sana>.jsonl` × `skriptlar.json` × `shlyuz.db` sverka: (a) jurnalda bor, DB da yo'q / aksincha; (b) `matn_tayyor` skript shabloniga **regex** bilan mos keladimi (shablon o'zgartirilgan bo'lsa tutadi); (c) skript bo'yicha son/rad sabablari/narx; (d) bir manzilga kuniga > limit (shlyuz o'tkazib yuborgan bo'lsa); (e) `ruxsat_agentlar` da yo'q agent yuborgan; (f) `yuborildi` da 24 soatdan ortiq qolganlar. Natija: `data/n3/<sana>.json` + `wiki/reestr/xabar_audit_<sana>.md` (W1 index'ga oladi) + KPI `{xabar_jami, yuborildi, yetkazildi, rad, xato, narx_som, nomuvofiq}`; `nomuvofiq > 0` → S-900 direktor.
- **Mock/real farqi yo'q** — faqat fayllar bilan ishlaydi.
- **Qabul**: (1) `skriptlar.json` da `{summa}` bor, `ozgaruvchilar` da yo'q → `tekshir` exit 1, aniq qator; (2) jurnalga qo'lda soxta satr qo'shilsa (DB da yo'q) → audit `nomuvofiq: 1`, sabab `JURNAL_DB_FARQ`; (3) 1 kunlik demo jurnal → hisobot jadvali (skript × holat) to'g'ri yig'iladi; (4) DB'da `matn_tayyor` qo'lda buzilsa → `SHABLON_FARQ`.

### X2 — Doktor (И1, `inplus-x2.service`, `Restart=always`)

- **Sikl (30 s)**: `agentlar.json` → har agent uchun `run/heartbeat/<id>.json` o'qiydi → qoida: (a) fayl yo'q va agent `timer` bo'lsa — `systemctl show inplus-<id>.timer -p NextElapseUSecRealtime` bilan hali ishga tushmaganini tekshiradi (insident emas); (b) `holat=xato` → `HB_XATO`; (c) `holat=ishlayapti` va `now - vaqt > sla_daq` → `HB_ESKI` (osilib qolgan: `systemctl kill` → restart); (d) `holat=tugadi` va `now > keyingi_kutilgan + sla_daq` → `HB_ESKI` (timer o'tib ketdi: `systemctl start`); (e) `service` turi: `systemctl is-active` + heartbeat ≤ 2 daq.
- **Harakat**: `systemctl restart|start inplus-<id>` (`sudoers`: `inplus ALL=(root) NOPASSWD: /bin/systemctl restart inplus-*, start inplus-*, kill inplus-*, is-active inplus-*, show inplus-*`). Qayta yoqish hisobi `data/x2/restart.json` — `max` (3) dan oshsa `RESTART_MAX` kritik → to'xtaydi, odamga (S-900 `muhimlik: kritik`). Insident 1 soatda 1 marta bir agent uchun (spam emas), yopilishi — heartbeat `ok` ga qaytganda `yopildi`.
- **Dashboard**: har siklda `data/dashboard.json` (§2.4 `kun` bloklari + heartbeat + ochiq insidentlar + shlyuz `/statistika`) → `www/index.html` (vanilla JS, 15 s da fetch, jadval: agent · holat · oxirgi · SLA · bugungi ishlar ok/xato · davomiylik · ochiq insident; rang yashil/sariq/qizil). nginx `/inplus/`. Basic-auth (`htpasswd`) — mijoz ma'lumoti bor.
- **O'zini kim kuzatadi**: `inplus-x2.service` `WatchdogSec=120` + `sd_notify` (`systemd-notify` chaqiruvi yoki `socket` ga `WATCHDOG=1`), `Restart=always`. W1 kunlik xulosada «X2 restart soni» bor.
- **Mock/real farqi yo'q**. Demo'da `X0` sinov agenti (5 daq, 10% yiqiladi) ni «davolaydi».
- **Qabul**: (1) `systemctl kill -s KILL inplus-x0` (ishlayotganda) → ≤ 60 s da insident `HB_ESKI` + restart + TG xabar S-900; (2) X0 ni 4 marta ketma-ket yiqitish → `RESTART_MAX`, kritik xabar, 5-marta restart **qilmaydi**; (3) agent o'z vaqtida ishlab tugasa — hech qanday insident; (4) X2 ning o'zini `kill -9` → systemd 2 daq ichida ko'taradi, `data/x2/restart.json` da o'z-o'zi restart ko'rinadi; (5) dashboard 8 agentni rang bilan ko'rsatadi, basic-auth so'raydi; (6) `agentlar.json` ga yangi `X9` qo'shilsa → keyingi siklda kuzatuvga kiradi, kod o'zgarmaydi.

### X1 — Zanjirlar auditori (И0, timer 22:00 + `--sana` bilan istalgan kun)

- **Kirish**: `data/uzatish/<sana>.jsonl`, `data/kpi/*/<sana>.json`, `agentlar.json`, kod daraxti.
- **Tekshiruvlar** (har biri `kod` bilan insident): `UZ_KUTILDI` — `berdi` bor, `kutilgan_uzatish` bo'yicha kerakli `oldi` yo'q (`kimga:*` bo'lsa `agentlar.json` da `oqiydi: [tur]` bo'lgan **faol** agentlar ro'yxati); `UZ_HASH` — `berdi.hash ≠ oldi.hash` (agent eskisini o'qigan); `UZ_SONI`; `UZ_YETIM` — `oldi` bor, `berdi` yo'q (kim yozgan?); `KPI_YOQ` — agent bugun ishlashi kerak edi (timer jadvali), KPI yo'q; `KPI_NISBAT` — `agentlar[id].kutilgan_nisbat` (masalan `"chiqdi.lidlar == kirdi.amocrm"`) buzilgan; `KPI_XATO` — `xato_soni > 0`; `SHLYUZ_CHETLAB` — **statik grep**: `agents/**/*.py` ichida `api.telegram.org|sendMessage|smtplib|/send` bo'lsa (shlyuzdan tashqari) → jiddiy; `HB_YOQ` — KPI bor, heartbeat hech qachon bo'lmagan (skeletdan o'tmagan agent).
- **Chiqish**: `data/x1/<sana>.json` (agent × tekshiruv matritsasi), `data/insident/` ga satrlar, `wiki/jurnal/zanjir_<sana>.md` jadval (agent · berdi · oldi · farq · KPI holati), KPI `{uzatish_jami, buzilgan, agent_tekshirildi, yashil}`; buzilgan > 0 → S-900 direktor (1 ta xabar, ro'yxat bilan).
- **Real/mock farqi yo'q**.
- **Qabul**: (1) `kontrakt/namuna/uzatish_buzilgan.jsonl` (5 holat: kutildi, hash, soni, yetim, toza) → aynan 4 insident, kodlari to'g'ri; (2) to'liq mock kun (D6→D1→X0×N→shlyuz) → `buzilgan: 0`; (3) `agents/x0_sinov/main.py` ga vaqtincha `requests.post("https://api.telegram.org…")` qo'shilsa → `SHLYUZ_CHETLAB`; (4) D1 ni o'chirib kun o'tkazilsa → `KPI_YOQ D1`; (5) jadval wiki'da o'qiladigan.

### W1 — Xotira agenti (И1, timer 23:00 + `qayta` qo'lda)

- **Wiki manbasi**: `agentlar.json` → `wiki/reestr/agentlar.md` (jadval); `skriptlar.json` → `wiki/reestr/skriptlar.md`; har agent papkasidagi `SOP.md` (ishchi yozadi, shablon A da: maqsad · kirish · chiqish · qanday ishga tushirish · yiqilsa nima qilish · kimga aytish) → `wiki/agentlar/<id>.md`; KPI+insident+N3+X1 → `wiki/jurnal/<sana>.md` kunlik xulosa; `data/insident` → `wiki/insident/<sana>.md`.
- **Arxiv**: `data/{uzatish,kpi,insident,jurnal}` 30 kundan eski → `data/arxiv/<oy>.tar.gz`; `data/paket/` 14 kundan eski → `arxiv/`. Shlyuz DB 90 kun (`DELETE` + `VACUUM`, jurnal jsonl qoladi).
- **HTML**: `markdown` pip paketi (yengil) → `wiki/_html/` + `index.html` (daraxt), nginx `/inplus/wiki/`. Qidiruv yo'q (grep yetarli); 3-blokda kerak bo'lsa `lunr` static.
- **Kunlik xulosa** (S-901, direktor, TG): 1 xabar: paket statistikasi + agentlar ok/jami + xabarlar yuborildi/rad + ochiq insidentlar.
- **Real/mock farqi yo'q**.
- **Qabul**: (1) `inplus ishga W1` → `wiki/_html/index.html` ochiladi, 8 agent SOP + 2 reestr + bugungi jurnal bor; (2) SOP.md o'zgartirilsa → keyingi ishga tushishda wiki yangilanadi; (3) 31 kunlik soxta `data/kpi` yaratilsa (`tests/`) → eng eskisi tar.gz ga tushadi, `data/` dan yo'qoladi, arxivdan o'qish `inplus arxiv oqi <sana>` ishlaydi; (4) S-901 TG ga keladi, raqamlar `dashboard.json` bilan bir xil.

### X0 — Sinov agenti (A yozadi, doim qoladi)

5 daq timer; `random(urug=vaqt) < 0.1` → `raise`, aks holda 1–20 s uxlab KPI `{sinov: 1}` yozadi, `data/sinov/<sana>.jsonl` ga satr + uzatish(berdi, kimga X1). X1 uni `oldi` qiladi. **Maqsad**: X2/X1/W1 ni haqiqiy agentlarsiz ham har kuni sinab turadi; prod'da ham qoladi (kanareyka).

---

## 6. DEMO SSENARIYSI (mijoz oldida, ~12 daqiqa)

Tayyorgarlik (oldindan): `bin/install.sh --demo` (Mac'da `INPLUS_ILDIZ=~/inplus-demo`, systemd o'rniga `bin/inplus ishga` — Mac'da `launchd` kerak emas, demo qo'lda), `INPLUS_REJIM=mock`, `TG_REAL=1`, mijoz vakili botga `/start` bosgan, `oq_royxat` ga uning `telegram_id`. `reset_mock.sh` — `data/` tozalanadi, generator `--kun 0`.

`bin/demo.sh` qadam-baqadam (`--pauza` bilan har qadamda Enter kutadi), ekranda nima ko'rinadi:

| # | Buyruq | Ekranda | Mijozga gap |
|---|---|---|---|
| 1 | `inplus rejim` | `rejim: mock · TG: real · ETS: mock(8472) · ildiz: …` | «Hozir sizning bazalaringiz yo'q — taqlid. Ulanganda bitta qator o'zgaradi.» |
| 2 | `inplus ishga D6` | `14 qator → 12 guruh · 1 XATO (9-qator: 31.09.2026) · 1 ogoh (xona A-2 to'qnashuv) · courses.json YANGILANMADI` + TG'ga S-902 keladi | «Jadvaldagi xatoni odam ko'rmasdan tizim tutdi.» Keyin `mock/sheets/jadval.csv` da sanani tuzatib qayta: `courses.json yangilandi (12 kurs)`. |
| 3 | `inplus ishga D1` | `amocrm 412 · getcourse 268 · sheets 12 → paket 2026-09-19.json (1.9 MB, 9 s) · schema OK · hash 9f2c…` | «Har ertalab 06:00 — shu paket. 133 agent shundan o'qiydi, hech kim CRM'ga o'zi kirmaydi.» `inplus paket korsat --qarzdorlar 5` → 5 qarzdor jadval. |
| 4 | `INPLUS_MOCK_YIQIL=getcourse inplus ishga D1` | `getcourse XATO (timeout) → kechagi nusxa · paket QISMAN · S-900 → direktor` + TG'da ⚠️ xabar | «Manba yiqilsa — tizim to'xtamaydi, odamga aytadi.» |
| 5 | `inplus shlyuz yubor --kanal tg --skript S-001 --kimga xodim:X-001 --oz ism=Bekzod kurs="Buxgalter noldan" summa="1 200 000" sana=1-oktyabr` ×2 | 1-chi: `x-…-0001 navbatda → yuborildi (message_id 88)` — telefonda xabar; 2-chi: `dublikat (x-…-0001)` — xabar **kelmaydi** | «Hamma xabar bitta eshikdan: tasdiqlangan matn, oq ro'yxat, dublikat kesildi.» Keyin `--kimga telefon:+998900000099` → `rad OQ_ROYXAT`. |
| 6 | `inplus shlyuz yubor --kanal sms --skript S-001 …` → `inplus shlyuz jurnal --bugun` | mock ЕТС: `yuborildi (mock-ets-17, 95 so'm)`; jadval: kanal × holat × narx | «SMS shartnoma kelgach — shu yerda real raqam va real narx.» |
| 7 | `inplus ishga X0 --yiqil` (yoki serverda `systemctl kill`) → 30–60 s | X2 logi: `HB_XATO X0 → restart → ok · insident i-…-0003` + TG ⚠️; brauzerda `http://…/inplus/` — X0 qizil → yashil | «135 agentdan kimdir yiqilsa — doktor ko'taradi, sizga bir qator xabar.» |
| 8 | `inplus ishga X1 && inplus ishga N3 && inplus ishga W1` → brauzer `/inplus/wiki/` | X1: `uzatish 14 · buzilgan 0 · agent 8/8 yashil` (yoki 4-qadamdan keyin `UZ_ESKI` bitta), N3: `xabar 4 · yuborildi 2 · rad 2 · nomuvofiq 0`; wiki'da bugungi jurnal, 8 SOP, skriptlar reestri; TG'da S-901 kunlik xulosa | «Kechqurun: kim kimga nima berdi — sverka; wiki o'zi yoziladi.» |

Demo'dan keyin mijozga qoladi: `README.md` + `wiki/` + «real'ga o'tish ro'yxati» (§7.3).

---

## 7. RISK VA CHEKLOVLAR

### 7.1 Mock ↔ real farqi (nima demo'da sinalmaydi)

| Joy | Mock'da | Real'da boshqacha | Chora |
|---|---|---|---|
| amoCRM | statik JSON, cheksiz | OAuth2 token 24 soat (refresh kerak), 7 req/s, 250/sahifa, `custom_fields` har akkauntda boshqa ID | `RealAmoCRM` da refresh + pagination A da yoziladi, lekin **maydon xaritasi** (`telefon` qaysi custom_field_id?) faqat mijoz akkauntida aniqlanadi — 2–4 soat sozlash |
| GetCourse | JSON darhol | export **asinxron** (5–60 s, ba'zan daqiqalar), API kuniga limit, maydon nomlari ruscha va o'zgaruvchan | D1 SLA 30 daq; export yiqilsa `eski`. Talaba↔lid bog'lash (`amo:` ↔ `gc:`) — **telefon orqali**, 100% emas (mock'da 100%) |
| Sheets | csv | quota 60 req/daq (bizga yetadi), service-account ulanish, mijoz ustunlarni o'zgartirib turadi | `sheets_ustun_xarita.json` + D6 validatsiya aynan shuning uchun |
| SMS ЕТС | 8472 mock, hamma ok | provayder **noma'lum** (API/narx/jonatuvchi nomi/moderatsiya shablonlari — O'zbekistonda SMS shablonlar oldindan tasdiqlanadi!), yetkazilganlik statusi bo'lmasligi mumkin | `skriptlar.json` = provayderga topshiriladigan shablonlar ro'yxati — **shu formatda** beriladi; `Real` 1 fayl, 2–3 soat |
| Telegram | real | real, lekin: bot faqat `/start` bosganga yoza oladi, `telegram_id` ni telefon orqali topib bo'lmaydi | opt-in oqimi (N2 da `tg_optin`) — talabalar botga kirishi kerak (GetCourse'da havola/QR). Bu **2-blok ishi**, 1-blokda faqat xodimlar + test |
| Hajm | 400 lid | mijozda bo'lishi mumkin 20–50 ming lid tarixi | D1 `kundan=-90`, qolgani `arxiv/` — birinchi yuklash alohida `--toliq` rejim |
| Vaqt | `--hozir`, `--sana` bilan | haqiqiy timerlar, tungi ishlar | serverda 3 kun «jim rejim» (xabarlar faqat oq ro'yxatga) — keyin yoqiladi |

### 7.2 Texnik risklar

- **Kontrakt o'zgarishi** — eng katta risk. Chora: `versiya` + `kontrakt/CHANGELOG.md`; 1.x da faqat qo'shish; X1 har kuni `paket` ni schema bilan qayta tekshiradi. 2-blokdan boshlab kontrakt o'zgarishi = alohida vazifa, 3 agent egasi tasdig'i.
- **Bitta server** — SPOF. 1-blokda qabul qilinadi; `data/` kunlik `rsync` boshqa joyga (`inplus-zaxira.timer`, W1 ga qo'shiladi, 1 soat ish).
- **SQLite + 2 thread** — `check_same_thread=False`, WAL rejimi, bitta yozuvchi (navbat ishchisi), HTTP faqat INSERT. 135 agent ham shlyuzga HTTP orqali — sekundiga 10–50 so'rov SQLite uchun mayda.
- **systemd huquqlari** — X2 `sudo systemctl` faqat `inplus-*` ga (sudoers qatori). Boshqa hech narsa.
- **Shaxsiy ma'lumot** — paketda telefon/ism. `data/` `chmod 750 inplus:inplus`, nginx basic-auth, backup shifrlangan (`age` yoki `gpg`). Mijozga ЗРУ-547 (shaxsiy ma'lumotlar) haqida bir qator eslatma: server O'zbekistonda bo'lishi kerak.
- **Vaqt zonasi** — hamma joyda `Asia/Tashkent`, `datetime.now(TZ)`; `utcnow()` taqiq (X1 grep qo'shiladi: `UTCNOW`).
- **Mac demo vs Linux prod** — Mac'da systemd yo'q: `bin/inplus ishga` bir xil kod, faqat X2 ning `systemctl` qismi Mac'da `--simulyatsiya` (jarayonni o'zi ishga tushiradi). Demo'ni **serverda** ko'rsatish afzal (SSH + brauzer).

### 7.3 Mijozdan kerak (real'ga o'tish ro'yxati — demo'dan keyin beriladi)

1. amoCRM: integratsiya (long-lived token) + voronka bosqichlari ro'yxati + telefon maydoni qaysi ekani.
2. GetCourse: API kaliti (`Настройки → API`) + guruh nomlari.
3. Google Sheets: jadval ID + service-account emailiga Viewer.
4. SMS: provayder nomi + API hujjat + jonatuvchi nomi + shablonlarni moderatsiyaga topshirish (`skriptlar.json` dan).
5. Telegram: BotFather'dan bot (biz yaratamiz, mijoz nomida) + xodimlar `/start`.
6. Server: Ubuntu 22.04+, 2 vCPU / 4 GB / 40 GB, O'zbekistonda, SSH; nginx bor.
7. Direktor `telegram_id` (S-900/901 uchun) + oq ro'yxat uchun 3–5 test raqami.

Har biri kelganda **qaysi fayl o'zgaradi**: 1–4 → `konfig/inplus.env` + 1 adapter `Real*` sinovi (`inplus adapter sinov amocrm`); 5 → env; 6 → `install.sh`; 7 → `oq_royxat.json`. Agent kodiga tegilmaydi — bu §1 qoidasi 1 ning maqsadi.

### 7.4 1-blokka KIRMAYDI (ataylab)

- Talabalar uchun TG opt-in oqimi to'liq (faqat xodimlar) — 2-blok.
- Dashboard'da grafik/tarix — faqat bugungi jadval.
- Wiki qidiruv, wiki'ni TG'dan tahrirlash.
- amoCRM'ga **yozish** (faqat o'qish). Yozuvchi agentlar 2+ blokda, o'z kontrakti bilan.
- Ko'p server / navbat brokeri / Docker — kerak emas, mijoz steki shu.

---

## 8. Tekshiruv ro'yxati «1-blok TAYYOR»

- [ ] `pytest` 4 test fayli yashil (kontrakt, adapter mock, shlyuz, X1).
- [ ] `demo.sh` 8 qadam pauzasiz o'tadi (`--avto`), oxirida `buzilgan: 0`, TG'da 5 xabar (S-902, S-900, S-001, S-900 X0, S-901).
- [ ] Serverda 24 soat ishlab: D6 05:50 · D1 06:00 · X0 288 marta (≈29 yiqilish, hammasi davolangan) · N3 21:00 · X1 22:00 · W1 23:00 — dashboard hammasi yashil, `RESTART_MAX` yo'q.
- [ ] `agentlar.json` ga `X9` (bo'sh agent, skeletdan) qo'shish — 10 daqiqada kuzatuv/audit/wiki'da paydo bo'ladi, hech qayerda kod o'zgarmaydi. **Bu 2-blok uchun asosiy sinov.**
- [ ] README: «yangi agent qanday yoziladi» 1 sahifa + `agents/_shablon/`.
- [ ] Har agent papkasida `SOP.md`.
