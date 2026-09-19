# IN PLUS — 1-BLOK «POYDEVOR» · TZ MOSLIK NAZORATI (QA)

> Sana: 2026-09-19 · Tekshirdi: QA/biznes-analitik
> Manba TZ (asosiy): ASL mijoz artefakti — «Фундамент» bloki (8 agent, 135 agentli taklifning poydevori)
> Ikkilamchi reja: `PLAN_BLOK1.md` (ichki build-reja, §2/§5/§6/§8 detallari)
> Implementatsiya: `~/inplus-demo/`
> Usul: kod o'qildi, `pytest` (73/73 ✅) yurgizildi, `bin/demo.sh` boshdan-oxir yurgizildi, kontrakt fayllari spec bilan solishtirildi, «X9 qo'shish» sinovi bajarildi.

Belgilar: ✅ bajarilgan · ◐ qisman · ❌ yo'q

---

## 1. ASL TZ — HAR AGENT MOSLIK MATRITSASI

Har agent uchun: Точка Б · tizimlar · avtonomiya (И0/И1) · «нужно от заказчика» → holat → dalil.

### STSENARIY 1 — Kunlik paket + jadval

| Agent | ASL TZ talab | Holat | Dalil |
|---|---|---|---|
| **D1** «Сборщик данных» | Точка Б: har ertalab yagona JSON-paket, undan HAMMA agent o'qiydi | ✅ | `data/paket/<sana>.json` + `joriy.json` symlink, atomik (`fayl.yoz`→`os.replace`), `paket.schema.json` bilan tekshiriladi. Demo 3-qadam: lid 400 · talaba 260 · hash. |
| | Tizimlar: amoCRM + GetCourse + Google Sheets + server | ✅ (mock) / ◐ (real) | 3 adapter (`adapter/{amocrm,getcourse,sheets}.py`), Mock* to'liq, Real* — skelet (`NotImplementedError`), systemd `inplus-d1.{service,timer}` bor. Real integratsiya mijoz dostupini kutadi. |
| | «ETL po raspisaniyu: API → JSON» | ✅ | `D1.ish()` har manbani alohida `try`, normalizatsiya (telefon E.164, ID prefiks, bosqich xaritasi), statistika, kontrakt. |
| | Avtonomiya И0 (ijrochi) | ✅ | `agentlar.json`: `"D1": {... "ijro": "И0"}` |
| | Нужно: API dostup amoCRM/GetCourse/Sheets + server | ◐ | `konfig/inplus.env` da bo'sh joylar (AMO_*, GC_*, SHEETS_*); «real'ga o'tish ro'yxati» `PLAN_BLOK1 §7.3`. Hozircha yo'q — mijozdan kutiladi (dizayn bo'yicha). |
| **D6** «Чтение расписания» | Точка Б: aktual jadval, validatsiya bilan | ✅ | `data/courses.json` + `courses.schema.json`; validatsiya: sana haqiqiyligi, tugash>boshlanish, regex, sigim≥band, xona/ustoz to'qnashuvi, dublikat guruh. Demo 2-qadam: xato tutildi, `courses.json` YOZILMADI, tuzatilgach yangilandi. |
| | Tizim: Google Sheets | ✅ (mock) / ◐ (real) | `adapter/sheets.py` MockSheets (csv) ✅, RealSheets skelet. |
| | И0 | ✅ | `agentlar.json` D6 `"ijro":"И0"` |

### STSENARIY 2 — Xabar shlyuzi (SMS + Telegram)

| Agent | ASL TZ talab | Holat | Dalil |
|---|---|---|---|
| **N1** «Отправка SMS (ЕТС)» | Точка Б: xabar tasdiqlangan skript bilan ketdi, **amoCRM va jurnalga yozildi**, dubl/limit kesildi | ◐ | Jurnal + SQLite navbat ✅ (`data/jurnal/xabar/*.jsonl`, `data/shlyuz.db`). **amoCRM'ga yozish — ❌** (`PLAN_BLOK1 §7.4` da ataylab keyingi blokka qoldirilgan). |
| | «HTTP-shlyuz s ocheredyu, idempotentnostyu i jurnalom» | ✅ | `agents/shlyuz/main.py`: 127.0.0.1:8471, `X-Idempotency-Key`, SQLite navbat, 9-qadamli qabul. Test `shlyuz_test.py` 15/15. |
| | Idempotentlik/limit/oq ro'yxat/skript ID | ✅ | 9 qadam: schema→skript→ozgaruvchi→oq/qora→idempotent→dublikat_soat→limit→vaqt_oynasi→INSERT. |
| | Tizim: ЕТС SMS shlyuzi | ✅ (mock) / ◐ (real) | `adapter/sms_ets.py`: Mock HAQIQIY HTTP (`mock/ets_server.py` 8472, retry/429/500 sinaladi), Real skelet + xavfsizlik qulf (`INPLUS_REJIM=real` + `ETS_TOKEN` bo'lmasa `RuntimeError`). |
| | И1 (yarim avtonom) | ✅ | SHLYUZ `"ijro":"И1"` |
| | Нужно: SMS-provayder shartnomasi | ◐ | Kutiladi (dizayn bo'yicha); `skriptlar.json` = moderatsiyaga topshiriladigan shablonlar. |
| **N2** «Отправка Telegram» | Точка Б: xabar ketdi, amoCRM+jurnalga yozildi | ◐ | Jurnal ✅, amoCRM ❌ (yuqoridagidek). |
| | Tizim: Telegram Bot API | ✅ | `adapter/telegram.py` Mock (`mock_tg/*.jsonl`) + Real (`sendMessage`, 429 `retry_after`, blok→xato). `TG_REAL=1` kanal override. |
| | И1 | ✅ | SHLYUZ ichida (N1+N2 birlashgan) |
| **N3** «Реестр + пост-аудит» (КОНТРОЛЁР) | Точка Б: reestr + jurnal sverkasi | ✅ | `n3_reestr/main.py`: `tekshir` (sintaksis, `{…}`↔ozgaruvchilar, ID takror, arxiv, SMS uzunlik) + `audit` (jurnal×skript×db: JURNAL_DB_FARQ, SHABLON_FARQ, RUXSAT_BUZILDI, LIMIT_OSHIB, ESKI_YUBORILDI). |
| | И0, kontrolyor | ✅ | N3 `"ijro":"И0"`, timer 21:00. Demo 8-qadam: nomuvofiq 0. |

### STSENARIY 3 — Nazorat (doktor, auditor, xotira)

| Agent | ASL TZ talab | Holat | Dalil |
|---|---|---|---|
| **X2** «Доктор-ИИ» | Точка Б: yiqilgan qayta yoqiladi; **hamma agentni ishga tushirish/kuzatish platformasi** | ✅ | `x2_doktor/main.py`: 30s sikl, heartbeat qoidalari (HB_XATO/HB_ESKI), `systemctl` (Linux) yoki simulyatsiya (Mac), `RESTART_MAX` kritik, `data/dashboard.json`. Demo 7-qadam: X0 yiqildi→HB_XATO→davolandi. Test `test_x2_x0_ni_davolaydi`, `test_x2_restart_max_toxtaydi` ✅. |
| | Tizim: monitoring/orkestrator | ✅ | `agentlar.json` reestridan HAR agentni kuzatadi; dashboard 8+ agent rangli. |
| | И1 (o'rta murakkab) | ✅ | X2 `"ijro":"И1"`, service `Restart=always`, `WatchdogSec` (systemd unit). |
| | Нужно: server | ◐ | systemd unit + sudoers qatori hujjatlashgan; Mac demoda simulyatsiya. |
| **X1** «Аудитор цепочек» (КОНТРОЛЁР) | Точка Б: KPI jadvali, «А отдал ≠ Б получил» topiladi; **yagona uzatish+KPI format hammadan oldin** | ✅ | Uzatish/KPI kontraktlari Oqim A da (birinchi). `x1_auditor/main.py`: UZ_KUTILDI/UZ_HASH/UZ_SONI/UZ_YETIM/KPI_YOQ/KPI_NISBAT/KPI_XATO/SHLYUZ_CHETLAB/HB_YOQ. Test `test_x1_uzatish_zanjiri_buzilgan_kodlarni_topadi`, `test_x1_shlyuz_chetlab_grep` ✅. |
| | И0, kontrolyor | ✅ | X1 `"ijro":"И0"`, timer 22:00. |
| **W1** «Агент памяти» | Точка Б: SOP va reestrlar wiki'da, jurnal, arxiv | ✅ | `w1_xotira/main.py`: `agentlar.md`/`skriptlar.md` reestr, har agent `SOP.md`→wiki, kunlik jurnal, insident, md→html, 30/14 kunlik arxiv (tar.gz). Test `test_w1_wiki_yaratadi`, `test_w1_arxiv_va_oqish` ✅. |
| | Tizim: fayllar/Markdown | ✅ | Markdown + `markdown` paketi → `wiki/_html/`. |
| | И1; tasdiqlaydi: Adiba | ✅ (И1) | W1 `"ijro":"И1"`. «Adiba tasdiqlaydi» — jarayon eslatmasi, kodga aloqasi yo'q. |

**Avtonomiya (И0/И1) yakuniy tekshiruvi:** ASL TZ ↔ `agentlar.json` — D1 И0 ✅ · D6 И0 ✅ · N1/N2(SHLYUZ) И1 ✅ · N3 И0 ✅ · X2 И1 ✅ · X1 И0 ✅ · W1 И1 ✅. **Hammasi mos.**

---

## 2. KONTRAKTLAR (PLAN_BLOK1 §2.1–2.9) — 8/8

| # | Schema | Holat | Izoh |
|---|---|---|---|
| 2.1 | `paket.schema.json` | ✅ | Barcha bloklar (manbalar, kurslar_ref, lidlar, talabalar, tolovlar, xodimlar, statistika), `additionalProperties:false`, `holat_umumiy` enum, `*_id` prefiks pattern (`^(amo\|gc\|sh):`), telefon E.164, bosqich/holat enumlar — spec bilan mos. |
| 2.2 | `courses.schema.json` | ✅ | validatsiya.holat enum (ok/ogohlantirish/xato), kurs_id/guruh_id regex, guruh maydonlari, xatolar[] tuzilishi — mos. |
| 2.3 | `uzatish.schema.json` | ✅ | uzatish_id, yonalish (berdi/oldi), tur (fayl/xabar/buyruq), hash, soni, kutish_daq — mos. |
| 2.4 | `kpi.schema.json` | ✅ | ishlar[] (kirdi/chiqdi/kpi majburiy), kun agregat bloki — mos. `lib/kpi.py` `kun` ni har yozishda qayta hisoblaydi. |
| 2.5 | `heartbeat.schema.json` | ✅ | holat enum (boshladi/ishlayapti/tugadi/xato), pid, keyingi_kutilgan — mos. |
| 2.6 | `konfig/agentlar.json` | ✅ | Spec'dagi 8 agent + `kutilgan_nisbat`, `kutilgan_uzatish` qo'shilgan (X1 uchun kerak). |
| 2.7 | `skript.schema.json` + `skriptlar.json` | ✅ | skript_id `^S-\d{3}$` (mijoz o'zgartirsa YANGI ID — S-001a taqiq), `{…}`↔ozgaruvchilar N3 `tekshir` da. |
| 2.8 | `xabar.schema.json` + shlyuz | ✅ | So'rov formati, rad sabablari, SQLite `xabarlar` jadvali + 2 indeks — mos. |
| 2.9 | `insident.schema.json` | ✅ | kod enum (HB_*, UZ_*, KPI_*, SHLYUZ_CHETLAB, RESTART_MAX, UTCNOW) — mos. |

Har schema uchun `namuna/<nom>_{ok,xato}.json` bor (test `kontrakt_test.py` 3/3 ✅). **Kam yoki spec'ga zid maydon topilmadi.**

---

## 3. §8 «1-BLOK TAYYOR» CHECKLIST

| Band | Holat | Dalil |
|---|---|---|
| `pytest` 4 test fayli (kontrakt, adapter mock, shlyuz, X1) yashil | ✅ (naming ◐) | 73/73 o'tadi. Fayllar: `kontrakt_test.py`, `adapter_mock_test.py`, `shlyuz_test.py`, X1 esa `orkestr_test.py` ichida (§3 daraxti `x1_test.py` degan edi — funksional to'liq, faqat nom boshqa). Qo'shimcha: `data_test.py`(D1/D6), `blok2_test.py`, `tahlil_test.py`. |
| `demo.sh` 8 qadam o'tadi, oxirida **buzilgan: 0**, TG'da 5 xabar | ◐ | 8 qadam boshdan-oxir o'tadi ✅. LEKIN oxirida **buzilgan: 4** (X0 KPI_XATO + S2/S6/X3 KPI_YOQ), 0 emas. Pastga qarang («MOS KELMAYDI» #1). |
| Serverda 24 soat ishlash | N/A | Mac demoda tekshirib bo'lmaydi; systemd unitlar + timerlar bor, prod sinovi mijoz serverida. |
| `agentlar.json` ga X9 qo'shish → 10 daqiqada kuzatuv/audit/wiki'da, kod o'zgarmaydi | ✅ | Sinaldi: X9 qo'shildi → X2 dashboard'da darhol paydo bo'ldi (`X9 in dashboard: True`), hech qanday kod o'zgarmadi. |
| README «yangi agent qanday» + `agents/_shablon/` | ✅ | README §«Yangi agent qanday yoziladi» (5 qadam) + `agents/_shablon/{main.py,SOP.md}` bor. |
| Har agent papkasida `SOP.md` | ✅ | 11/11 papkada SOP.md (8 blok-1 + 3 qo'shimcha + shablon). |

---

## 4. QOLIB KETGAN (ASL TZ da bor, implementatsiyada yo'q)

1. **amoCRM'ga xabar yozish (❌).** ASL TZ N1/N2 Точка Б: «сообщение ... записано **в amoCRM** и журнал». Implementatsiya faqat jurnal + SQLite'ga yozadi. amoCRM'ga event yozish yo'q. *Sabab:* `PLAN_BLOK1 §7.4` da 1-blokdan ataylab chiqarilgan («amoCRM'ga yozish 2+ blokda»). — **Hujjatlashgan, lekin ASL TZ Точка Б sini to'liq bermaydi.**
2. **Real adapterlar (◐).** amoCRM/GetCourse/Sheets/ЕТС ning `Real*` klasslari `NotImplementedError` skelet. Demo mock ustida ishlaydi; real integratsiya mijoz dostupini (API kalit/token/service-account/shartnoma) kutadi. — **Dizayn bo'yicha (mock demo), lekin «нужно от заказчика» hali bajarilmagan.**
3. **Talabalar uchun TG opt-in oqimi (◐).** Hozir faqat xodimlar + test raqamlar. `PLAN_BLOK1 §7.4` bo'yicha 2-blok. `adapter/telegram.py` da `yangiliklar()` bor, lekin to'liq `tg_optin` oqimi ulanmagan.

---

## 5. MOS KELMAYDI / TO'QNASHADIGAN

1. **Demo «buzilgan: 0» buzilgan (◐→conflict).** §8 va §6 8-qadam oxirida `buzilgan: 0` kutiladi. HAQIQAT: `buzilgan: 4`:
   - `X0 KPI_XATO` — 7-qadamda ataylab yiqitilgan X0 ning muvaffaqiyatsiz ishi KPI'da qoladi (X2 davolagan bo'lsa ham). Bu demo ssenariysining o'ziga xos, §8 «0» bilan ziddiyatli.
   - `S2/S6/X3 KPI_YOQ` — bu 3 tasi **qo'shimcha agentlar** `agentlar.json` ga qo'shilgani uchun (jadval vaqti o'tgan, lekin demoda ishga tushmagan) X1 ularni «bugun ishlamagan» deb belgilaydi. *Ya'ni: qo'shimchalar poydevorni sindirmaydi, lekin demo yakunidagi «buzilgan: 0» ko'rsatkichini buzadi.*
2. **`S-900 ruxsat_agentlar` spec'dan kengroq.** `PLAN_BLOK1 §2.7`: `["X2","X1","D1","D6"]`. Implementatsiya: `["X2","X1","D1","D6","N3","SHLYUZ"]`. N3 va SHLYUZ o'z ichki xatolarida S-900 yuboradi (kodda hujjatlashgan). Additive (versiya 1.x mos), lekin spec matni bilan aynan teng emas.
3. **`xodim_id` pattern real rejimda yiqilishi mumkin (latent risk).** Schema: `xodim_id` = `^X-\d{3}$` (3 xona). Mock user_id lar 301/302/303 → «X-301» o'tadi. LEKIN real amoCRM user_id — katta int (masalan 3141592) → «X-3141592» pattern'ga TUSHMAYDI → `paket.tekshir` xato → D1 real rejimda yiqiladi. Mock demo o'tadi, real yo'lda tuzatish kerak (pattern kengaytirish yoki xodim_id generatsiyasini o'zgartirish).
4. **Test fayl nomi.** §3 daraxti `x1_test.py` deydi; amalda X1 testlari `orkestr_test.py` da. Funksional to'liq, faqat nom.
5. **`demo.sh` bayrog'i.** §8 `--avto` deydi; amalda bayroqsiz = avto, `--pauza` = pauza. Funksional teng, nom farqi.

---

## 6. QO'SHIMCHA (1-blok TZ dan TASHQARI — TZ ga qarshi hisoblanmaydi)

- **S2 «Sotuv voronkasi», S6 «Qarzdorlar eslatmasi» (2-blok), X3 «Analitika» (tahlil).** To'liq yozilgan + testlar (`blok2_test.py` 7/7, `tahlil_test.py` 10/10). Hammasi FAQAT `paket.oqi()` orqali o'qiydi, xabarni faqat `shlyuz_client` orqali yuboradi — poydevor kontraktini to'g'ri iste'mol qiladi, arxitekturani **buzmaydi** (aksincha, poydevor ishlashini isbotlaydi).
- **Poydevorga yagona ta'siri:** ular `agentlar.json` da ro'yxatga olingani uchun X1/X2/W1 ularni ham qamrab oladi → to'liq bo'lmagan demo kunida `KPI_YOQ` (sariq) chiqadi (yuqorida «MOS KELMAYDI» #1). Bu **krash emas**, sariq belgi.
- Boshqa qo'shimchalar: `www/index.html` dashboard, `wiki/_html/`, `mock/generator.py` deterministik, `bin/inplus` CLI.

---

## 7. YAKUN

**Kontraktlar:** 8/8 ✅ · **ASL TZ agentlari:** D6·N3·X2·X1·W1 ✅ (5), D1 ✅mock/◐real, N1·N2 ◐ (amoCRM logi yo'q) · **Avtonomiya И0/И1:** 8/8 ✅ · **§8 checklist:** 4 ✅ / 1 ◐ (demo buzilgan≠0) / 1 N/A (24 soat).

Umumiy hisob: **✅ ≈ 34 · ◐ ≈ 9 · ❌ ≈ 2** (amoCRM'ga yozish; to'liq real integratsiya).

### TZ BO'YICHA TAYYORLIK: **~92%** (mock demo yo'nalishi bo'yicha to'liq; real integratsiya va amoCRM-log yo'nalishi ataylab keyingi bloklarga)

### TAYYORMI? **HA — mijozga MOCK DEMO ko'rsatishga tayyor.** Poydevor (kontrakt, skelet, shlyuz, orkestr, wiki, «yangi agent qo'shish» sinovi) to'liq ishlaydi.

**Topshirishdan oldin 3 ta kichik tuzatish tavsiya etiladi:**
1. Demo yakunidagi `buzilgan: 0` va'dasini haqiqatga moslash — yoki S2/S6/X3 ni demo `agentlar.json` idan ajratish, yoki demo matnida «X0 KPI_XATO + qo'shimcha agentlar KPI_YOQ = kutilgan» deb izohlash.
2. `xodim_id` schema pattern'ini real amoCRM user_id (uzun int) uchun kengaytirish — aks holda real rejimda D1 yiqiladi.
3. ASL TZ «записано в amoCRM» bandini mijozga ochiq aytish: 1-blokda jurnal+DB, amoCRM-yozuv keyingi blokda (§7.4).
