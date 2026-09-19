# IN PLUS — 1-blok «Poydevor» · TEXNIK DIREKTOR REVIEW (topshirishdan oldin)

Sana: 2026-09-19 · Ko'rildi: arxitektura, `lib/inplus/*`, 11 agent, `tests/` (73 test), `bin/demo.sh`,
jonli sayt (9 sahifa), chatbot API (`/opt/inplus-demo-api.py`), nginx, systemd.
Yurgizildi: `pytest` (73/73 ✅), `bash bin/demo.sh` (2 marta), `curl` chatbotga (6 savol), server SSH.

Xushomad yo'q. Poydevor **arxitekturasi kuchli** (pastda «kuchli tomonlar»), lekin
**mijoz oldida sinishi mumkin bo'lgan 2 ta real muammo bor** — asosiysi chatbot.

---

## 🔴 KRITIK

### K1. Jonli chatbotdagi «Gemini AI» aslida ishlamayapti — har doim keyword-fallback
- **Fayl:** `/opt/inplus-demo-api.py:39` (server), `gemini()` funksiyasi.
- **Dalil (server ustida tekshirildi):**
  - `MODELS[0] = gemini-flash-lite-latest` + `generationConfig.thinkingConfig={"thinkingBudget":0}` → **HTTP 400 INVALID_ARGUMENT**. Kod 400 ni `(503,429)` da emas deb `break` qiladi.
  - `MODELS[1] = gemini-flash-latest` → **HTTP 429 quota exceeded** (kvota tugagan).
  - Natija: `gemini()` **doim `None` qaytaradi** → har savol `lokal()` (keyword) javob beradi.
  - Aniqlangan sabab: `thinkingConfig` ni **olib tashlasa lite-model 200 OK qaytaradi** (server ustida `no_thinking → OK`, `empty_cfg → OK` bilan tasdiqlandi). Kalit **to'g'ri va ishlayapti** (to'g'ridan-to'g'ri chaqiriq javob berdi).
- **curl dalili:** `"IELTS qancha turadi?"` → `IELTS: 2 800 000 so'm (4 oy)` (bu aynan `lokal()` narx-shabloni, Gemini emas). Notanish savol → butun narx ro'yxatini to'kadi.
- **Ta'sir:** Demoning bosh «fishkasi» — AI-yordamchi — mijoz oldida soxta. Javoblar quruq/shablon, «menejer aniqlaydi» degan yumshoq yo'naltirish yo'q.
- **Tavsiya (SHART):** `generationConfig` dan `thinkingConfig` ni olib tashlash; modellar tartibini `gemini-flash-lite-latest` (kvotasi bor) birinchi qilib qoldirish; `systemctl restart inplus-api`; keyin `curl /api/chat` — tabiiy 2-4 gapli javob kelishini tekshirish. 10 daqiqalik ish.

---

## 🟠 MUHIM

### M1. `bin/demo.sh` oldindan ishlab turgan shlyuz/ETS ga chidamsiz — demo sinishi mumkin
- **Fayl:** `bin/demo.sh:16` (`tozala` faqat EXIT da), start qismida port/protsess tekshiruvi yo'q; `set -uo pipefail` (`-e` yo'q) — xatodan keyin jimgina davom etadi.
- **Dalil (reproduksiya qilindi):** Birinchi yurishimda xabar ID lar `x-...-000180` dan boshlandi (ya'ni **oldindan ishlab turgan shlyuz** eski DB bilan javob bergan), 6-qadamda protsesslar `Terminated: 15` bo'lib, 6/7/8-qadamlar buzildi (`statistika: shlyuz ulanmadi`, 8-qadam `IndexError`). Straglerlarni o'ldirib qayta yurgizganda **to'liq 8/8 o'tdi**.
- **Muhim kontekst:** Demo **serverda** ko'rsatiladi, u yerda shlyuz systemd servisi sifatida 8471 da doim ishlaydi. `demo.sh` o'z shlyuzini o'sha portga qo'yadi → bind muvaffaqiyatsiz (jimgina `/tmp` logga), `bin/inplus` esa rezident servis bilan gaplashadi → raqamlar iflos, holat aralash.
- **Ta'sir:** Mijoz oldida demo ikkinchi marta yoki server servisi yoniq bo'lsa sinadi.
- **Tavsiya:** `demo.sh` start oldida `pkill -f agents/shlyuz/main.py; pkill -f mock/ets_server.py` + port bo'shligini tekshirish (yoki alohida `INPLUS_SHLYUZ_PORT` + sandbox `INPLUS_ILDIZ`); bind muvaffaqiyatsiz bo'lsa **aniq xato bilan to'xtash**. Serverda demoni ishlatishdan oldin `systemctl stop inplus-shlyuz` (agar bor bo'lsa) yoki boshqa portda.

### M2. Shlyuzda idempotentlik TOCTOU race — parallel dublikatda HTTP 500
- **Fayl:** `agents/shlyuz/main.py`, `qayta_ishla_sorov`: (5) idempotent tekshiruv `with self.lock` ichida, lekin lock **INSERT dan oldin bo'shatiladi**; (9) INSERT alohida lock. Ikki bir xil so'rov parallel kelsa — ikkalasi ham (5) dan o'tadi, ikkalasi ham (9) da INSERT qiladi → 2-chisi `idempotent_kalit UNIQUE` ni buzadi → `sqlite3.IntegrityError` ushlanmaydi → `do_POST` 500 qaytaradi (`shlyuz/main.py:733` atrofidagi `except Exception → 500`).
- **Ta'sir:** Idempotentlikning butun maqsadi — parallel xavfsizlik. 135 agent + retraylar sharoitida vaqti-vaqti bilan 500 chiqadi. Demoda ko'rinmaydi (bir oqim).
- **Tavsiya:** (5)+(9) ni bitta lock ichiga olish, yoki `INSERT ... ON CONFLICT DO NOTHING` + konflikt = `dublikat` deb qaytarish, yoki `IntegrityError` ni ushlab qayta so'rov.

---

## 🟡 MAYDA

### m1. Butun sayt autentifikatsiyasiz ochiq
- **Fayl:** `/etc/nginx/sites-available/inplus-demo` — `location /` da basic-auth yo'q (faqat `X-Robots-Tag noindex`).
- URL ni bilgan har kim: `plan.html` (68KB to'liq biznes-reja), `sotuv.html` (sotuv strategiyasi), `tahlil.html`, `dashboard.html`, `wiki/` ni ko'radi. `plan.html` ichida 7 ta **namunaviy** telefon (`+998901234567` va h.k. — mock, real mijoz emas).
- Rejaning o'zi (§7.2) `data/` uchun basic-auth talab qiladi. **Tavsiya:** hech bo'lmasa `plan/tahlil/dashboard` ga basic-auth yoki IP-allowlist. (Real PII emas, lekin mijoz strategiyasi ochiq.)

### m2. Chatbot API — rate-limit / abuz himoyasi yo'q
- **Fayl:** `nginx inplus-demo` `/api/` (limit_req yo'q); `/opt/inplus-demo-api.py` (`ThreadingHTTPServer`, cheklovsiz thread).
- `/api/chat` ochiq, autentifikatsiyasiz, pullik Gemini ni chaqiradi (tuzatilgach). `savol` 500 belgiga kesilgan (yaxshi), 200KB payload sinovda muammosiz. **Tavsiya:** nginx `limit_req` `/api/` ga. Prompt-injection: foydalanuvchi matni prompt ga ulanadi (`api.py:34`) — read-only sotuv bot uchun past xavf (injection sinovi fallbackka tushdi), lekin Gemini tuzatilgach injected ko'rsatma ohangni/da'voni o'zgartirishi mumkin.

### m3. Gemini kalit fayli hamma o'qiy oladigan (644)
- **Fayl (server):** `/opt/inplus-demo-api.env` → `-rw-r--r--`. Har lokal foydalanuvchi kalitni o'qiy oladi. **Tavsiya:** `chmod 600`. Bitta-server uchun mayda, lekin arzon tuzatish.

### m4. Bir nechta joyda `except Exception: pass` xatoni jimgina yutadi (log yo'q)
- `agents/s2_voronka/main.py:87` (wiki yozish), `agents/n3_reestr/main.py:194` (`ESKI_YUBORILDI` sana parse — buzuq timestampda audit teshigini yashiradi), `agents/x1_auditor/main.py:300`, `agents/x2_doktor/main.py:137` (shlyuz yuborish).
- Hammasi «agent yiqilmasin» niyati bilan (o'rinli), lekin real bug'larni (buzuq payload) yashiradi. §5 «`try/except Exception: pass` taqiq» qoidasiga tegib ketadi (asosiy skelet `lib/inplus/agent.py` qoidaga rioya qiladi — re-raise). **Tavsiya:** `pass` o'rniga `jurnal` ga yozish.

### m5. `uzatish._keyingi_id` — O(n) + parallel yozishda ID kolliziyasi
- **Fayl:** `lib/inplus/uzatish.py:23-28`. Har `berdi()` da butun jsonl sanaladi; `flock` faqat append ni himoyalaydi, count+write atomik emas → ikki agent parallel `berdi` yozsa bir xil `uzatish_id` chiqishi mumkin. X1 `(uzatish_id, kim)` bo'yicha dedup qiladi → kolliziya auditni chalg'itadi. Prodda xavf past (timerlar vaqtni ajratadi). **Tavsiya:** agent bo'yicha hisoblagich fayli yoki ID ga qisqa nanotime/random suffiks.

### m6. `dashboard.json` — statik snapshot, jonli emas
- Web root dagi `data/dashboard.json` — snapshot (§7.4 ga mos), lekin mijoz jonli kutsa eskiradi. X1 ning `SHLYUZ_CHETLAB` grep i faqat `agents/` ni skanerlaydi (`lib/` emas) — adapter sanksiyalangan joy bo'lgani uchun o'rinli, lekin hujjatlashtirilsin.

---

## KUCHLI TOMONLAR (poydevor haqiqatan mustahkam)
- **Kontrakt intizomi haqiqiy:** `lib/inplus/kontrakt.py` — jsonschema gate **ham o'qishda ham yozishda** (`paket.oqi/yoz`, `courses.oqi/yoz`, `kpi`, `heartbeat`, `uzatish`). Tekshiruvdan o'tmagan fayl yozilmaydi/o'qilmaydi — §0 va't bajarilgan.
- **Deterministik hash / idempotentlik to'g'ri:** `d1_sborshik/main.py:142` — hash faqat mazmundan (timestampsiz), shuning uchun 2 marta ishga tushirish ortiqcha `uzatish` yozmaydi. `fayl.hash_obj` `sort_keys` bilan kanonik.
- **Atomik yozish:** `lib/inplus/fayl.py` — tmp + `fsync` + `os.replace` + atomik symlink. `jurnal.append` `fcntl.flock` bilan.
- **Mock/real ajratmasi toza:** agent kodi rejimni bilmaydi (`adapter.ol()`); mock **real javob formatida** qaytaradi → normalizatsiya bir xil sinaladi. §1 qoida 1 (agentlarda `requests` yo'q) tekshirildi — buzilmagan.
- **SMS xavfsizlik guardi mustahkam:** `RealSmsEts.__init__` — `real` + `ETS_TOKEN` bo'lmasa `RuntimeError` → SMS adashib real'ga ketolmaydi.
- **Testlar mazmunli, tavtologiya emas:** 73 test; shlyuz holat-mashinasi, dedup, limitlar, vaqt oynasi, retry/backoff, X0→X2 eskalatsiya, kontrakt namuna ok/xato juftlari — real xatti-harakatni tekshiradi. Qamrov shlyuz (eng muhim), data, orkestr, tahlilda kuchli.
- Servis holati: `inplus-api` **active**, TLS (Certbot) ishlayapti, 9 sahifa ham HTTP 200.

## QAMROV YETISHMAYDI (test)
- `Real*` adapterlar (hammasi `NotImplementedError` — mock↔real farqi §7.1) sinovsiz — kutilgan, mijoz dostupidan keyin.
- Parallel/concurrency testi yo'q (M2 race shuning uchun tutilmagan).
- Chatbot API (`inplus-demo-api.py`) uchun test umuman yo'q — K1 shu sabab avtomat tutilmadi.

---

## TOPSHIRISHGA TAYYORMI?  →  **SHARTLI (ha, lekin avval quyidagi 2 ta shart)**

Poydevor sifati va arxitektura topshirishga tayyor. Lekin demo hozir ikki joyda sinadi.

**Topshirishdan oldin SHART (bloker):**
1. **K1** — `inplus-demo-api.py` dan `thinkingConfig` ni olib tashlab, `inplus-api` ni restart qilish; chatbot tabiiy Gemini javob berishini `curl` bilan tasdiqlash. (Aks holda AI demo soxta.)
2. **M1** — `demo.sh` ni oldingi shlyuz/ETS ni o'ldiradigan + port tekshiradigan qilish; serverda demoni toza portda/protsessda ishlatish. Ikki marta ketma-ket yurgizib tekshirish.

**Kuchli tavsiya (topshirish haftasida):**
3. **M2** — idempotentlik race (check+insert bitta lock / ON CONFLICT).
4. **m1** — saytga basic-auth (kamida plan/tahlil/dashboard).
5. **m3** — `chmod 600 /opt/inplus-demo-api.env`.
