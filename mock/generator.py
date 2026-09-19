#!/usr/bin/env python3
"""Mock ma'lumot generatori — DETERMINISTIK (urug bilan).

  python3 mock/generator.py --lid 400 --talaba 260 --urug 42 --kun 0

Yasaydi (real API JAVOB FORMATIDA):
  mock/amocrm/{leads,users,pipelines}.json
  mock/getcourse/{users,payments,groups}.json
  mock/sheets/jadval.csv   (14 qator: 12 guruh + 1 xato + 1 ogohlantirish)

getcourse.users/payments — REAL-KO'RINISHLI: talabaning `boshladi` sanasi va
to'lov sanasi `OXIRGI_KUN` dan orqaga oxirgi ~45 kunga DETERMINISTIK
tarqatilgan (hammasi bitta kunda emas), har talabaga `nps` maydoni (0..10,
ba'zilari javobsiz -> bo'sh qator) qo'shilgan, va talabalarning ~6% i
`holat="tashladi"` + `tolov.tolandi>0` bilan chiqadi (vozvrat manbai).

Ikki marta bir xil argument = bir xil chiqish.
"""
import os
import csv
import json
import random
import argparse
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

ILDIZ = Path(__file__).resolve().parents[1]

# Sanalar shundan orqaga hisoblanadi (repo konvensiyasi: demo/testlar SANA =
# "2026-09-19" ishlatadi, PLAN_BLOK1.md namunalari ham shu kun). Qattiq
# belgilangan — shunda "bir xil urug' -> bir xil natija" doim TO'G'RI bo'ladi
# (haqiqiy joriy sanaga bog'liq emas).
OXIRGI_KUN = date(2026, 9, 19)
MOCK = ILDIZ / "mock"

# "Hozir" — OXIRGI_KUN kunining peshin (UTC) lahzasi. amocrm lidlarining
# created_at/updated_at shundan orqaga/oldinga hisoblanadi (S4 «Menejer
# nazorati» reaksiya vaqtini shundan hisoblaydi — qattiq belgilangan,
# hozirgi joriy sanaga bog'liq emas -> determinizm saqlanadi).
_HOZIR_EPOCH = int(datetime(OXIRGI_KUN.year, OXIRGI_KUN.month, OXIRGI_KUN.day,
                            12, 0, tzinfo=timezone.utc).timestamp())

# amocrm menejerining reaksiya tezligi (soat oralig'i) — S4 nazorat agenti
# uchun menejerlar orasida real farq bo'lishi kerak (bir xil bo'lsa demo
# hech narsa ko'rsatmaydi): X-301 tez, X-302 o'rta (~1 kun), X-303 sekin.
MENEJER_REAKSIYA_SOAT = {
    301: (2, 6),
    302: (18, 30),
    303: (48, 72),
}

# --- kurs/guruh katalogi (sheets + getcourse coherent bo'lishi uchun) ---
KATALOG = [
    ("K-BUX-01", "Buxgalter noldan", "offline", 2400000, 3, "X-010",
     [("G-BUX-01-SEN", "A-1", "18:30-20:30", "du,chor,ju"),
      ("G-BUX-01-OKT", "A-1", "10:00-12:00", "se,pay")]),
    ("K-ENG-01", "Ingliz tili A1", "offline", 1500000, 4, "X-011",
     [("G-ENG-01-SEN", "B-1", "17:00-18:30", "du,chor"),
      ("G-ENG-01-OKT", "B-1", "19:00-20:30", "se,pay")]),
    ("K-SMM-01", "SMM boshlang'ich", "online", 1200000, 2, "X-012",
     [("G-SMM-01-SEN", "C-1", "20:00-21:30", "se,pay"),
      ("G-SMM-01-OKT", "C-1", "10:00-11:30", "du,ju")]),
    ("K-IT-01", "Dasturlash noldan", "offline", 3200000, 6, "X-013",
     [("G-IT-01-SEN", "D-1", "18:00-20:00", "du,chor,ju"),
      ("G-IT-01-OKT", "D-1", "14:00-16:00", "se,pay,shan")]),
    ("K-DIZ-01", "Grafik dizayn", "offline", 2100000, 3, "X-014",
     [("G-DIZ-01-SEN", "A-2", "18:30-20:30", "du,chor,ju")]),
    ("K-MAT-01", "Matematika", "offline", 900000, 5, "X-015",
     [("G-MAT-01-SEN", "E-1", "15:00-16:30", "se,pay")]),
]
# jami 10 valid guruh; 12 ga yetkazish uchun 2 ta qo'shamiz
QOSHIMCHA = [
    ("K-BUX-02", "Buxgalter PRO", "offline", 3000000, 3, "X-010",
     ("G-BUX-02-SEN", "F-1", "18:30-20:30", "du,chor")),
    ("K-ENG-02", "IELTS", "offline", 2800000, 4, "X-011",
     ("G-ENG-02-SEN", "B-2", "17:00-19:00", "se,pay,shan")),
]

ISMLAR = ["Dilnoza", "Bekzod", "Madina", "Jasur", "Nilufar", "Sardor", "Kamola",
          "Aziz", "Feruza", "Rustam", "Malika", "Otabek", "Shahnoza", "Ulugbek",
          "Gulnora", "Sherzod", "Dilfuza", "Akmal", "Zarina", "Farrux"]
FAMILIYA = ["Karimova", "Rahimov", "Yusupova", "Toshmatov", "Islomova", "Aliyev",
            "Nazarova", "Qodirov", "Saidova", "Ergashev", "Yo'ldosheva", "Xolmatov"]
KANALLAR = ["instagram", "telegram", "veb", "tavsiya", "reklama"]

# NPS (0..10) og'irliklari — realistik taqsimot: ko'pchilik javob bermaydi
# (null og'irligi baland), javob berganlar orasida promoter ozroq ko'proq
# (haqiqiy ta'lim biznesida odatiy musbat-ammo-mo''tadil NPS ko'rinishi
# uchun) — sof taqsimot, aniq bir ball hardcode qilinmagan.
NPS_QIYMATLAR = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, None]
NPS_OGIRLIK = [1, 1, 1, 1, 1, 1, 1, 4, 4, 6, 6, 15]


def _telefon(rng, buzuq=False):
    if buzuq:
        return rng.choice(["90 123 45 67", "998 90 111 22 33", "abc", "", "+7 916 000 00 00"])
    op = rng.choice(["90", "91", "93", "94", "95", "97", "99", "88", "33"])
    return "+998" + op + "".join(str(rng.randint(0, 9)) for _ in range(7))


def _ism(rng):
    return rng.choice(ISMLAR) + " " + rng.choice(FAMILIYA)


def gen_amocrm(rng, n_lid, kun):
    statuslar = [(140, "yangi"), (141, "aloqa"), (142, "konsultatsiya"),
                 (143, "sinov_dars"), (144, "tolov_kutish"), (146, "sotildi"),
                 (147, "yoqotildi"), (145, "qayta")]
    pipeline_id = 7712
    # kun ta'siri: har kun 3-8 lid qo'shiladi
    qoshimcha = sum(rng.randint(3, 8) for _ in range(kun))
    jami = n_lid + qoshimcha
    kurslar = [k[0] for k in KATALOG] + [q[0] for q in QOSHIMCHA]
    # realistik voronka (funnel): yuqorida ko'p, pastga tomon kamayadi. Deterministik,
    # rng ni iste'mol qilmaydi (boshqa maydonlar o'zgarmasin uchun i bo'yicha taqsimlanadi).
    ulush = [(140, 0.22), (141, 0.18), (142, 0.15), (143, 0.12),
             (144, 0.10), (146, 0.12), (145, 0.06), (147, 0.05)]
    bosqich_list = []
    for sid, pr in ulush:
        bosqich_list += [sid] * round(jami * pr)
    while len(bosqich_list) < jami:
        bosqich_list.append(140)
    bosqich_list = bosqich_list[:jami]
    leads = []
    for i in range(jami):
        buzuq = (i % 97 == 0) or (i % 89 == 3)  # ~ bir necha buzuq telefon
        st_id = bosqich_list[i]

        # created_at: OXIRGI_KUN (_HOZIR_EPOCH) dan orqaga oxirgi ~30 kunga
        # deterministik tarqatilgan (i bo'yicha, bir xil kun i%30 orqali
        # takrorlanadi -> har kunga ~jami/30 lid, bitta kunga to'planmaydi).
        kun_orqaga = i % 30
        created = _HOZIR_EPOCH - kun_orqaga * 86400

        menejer_id = rng.choice([301, 302, 303])

        # javobsiz («hech kim tegmagan»): faqat bosqich="yangi" (140) da
        # mantiqiy — boshqa bosqichga o'tgan lidga kamida bitta aloqa bo'lgan
        # deb hisoblanadi. "Yangi" to'plamining ~25% i (i%4==0, deterministik)
        # oxirgi_aloqa=yaratildi bilan qoldiriladi (S4 shuni "javobsiz" deydi).
        if st_id == 140 and i % 4 == 0:
            updated = created
        else:
            lo_soat, hi_soat = MENEJER_REAKSIYA_SOAT.get(menejer_id, (2, 6))
            reaksiya_daq = rng.randint(lo_soat * 60, hi_soat * 60)
            # kelajakka chiqib ketmasin (bugun yaratilgan lidga sekin menejer
            # ham "hozir"dan keyingi vaqtda javob bera olmaydi) — lekin
            # kamida 5 daqiqa farq qoldiramiz, aks holda bugungi yangi lid
            # tasodifan created==updated ("javobsiz") bo'lib qolib, ataylab
            # tanlangan (i % 4 == 0) to'plamni buzadi.
            qolgan_s = max(300, _HOZIR_EPOCH - created)
            updated = created + min(reaksiya_daq * 60, qolgan_s)

        leads.append({
            "id": 48000 + i,
            "name": _ism(rng),
            "price": rng.choice([0, 1200000, 1500000, 2400000, 3200000]),
            "status_id": st_id,
            "pipeline_id": pipeline_id,
            "created_at": created,
            "updated_at": updated,
            "responsible_user_id": menejer_id,
            "custom_fields_values": [
                {"field_code": "PHONE", "field_id": 264911,
                 "values": [{"value": _telefon(rng, buzuq), "enum_code": "WORK"}]},
                {"field_code": "KURS", "field_id": 264920,
                 "values": [{"value": rng.choice(kurslar)}]},
                {"field_code": "KANAL", "field_id": 264921,
                 "values": [{"value": rng.choice(KANALLAR)}]},
            ],
            "_embedded": {"tags": [{"id": 1, "name": rng.choice(["sentyabr", "chegirma", "vip"])}]},
        })
    users = [
        {"id": 301, "name": "Madina", "email": "madina@inplus.uz", "phone": "+998901112233"},
        {"id": 302, "name": "Jasur", "email": "jasur@inplus.uz", "phone": "+998901112244"},
        {"id": 303, "name": "Direktor", "email": "dir@inplus.uz", "phone": "+998900000001"},
    ]
    pipelines = {"_embedded": {"pipelines": [{
        "id": pipeline_id, "name": "Sotuv voronkasi",
        "_embedded": {"statuses": [{"id": s, "name": n} for s, n in statuslar]}}]}}
    leads_env = {"_page": 1, "_embedded": {"leads": leads}}
    users_env = {"_embedded": {"users": users}}
    return leads_env, users_env, pipelines


def gen_getcourse(rng, n_talaba):
    guruhlar_katalog = []
    for k in KATALOG:
        for g in k[6]:
            guruhlar_katalog.append((k[0], g[0], k[1]))
    for q in QOSHIMCHA:
        guruhlar_katalog.append((q[0], q[6][0], q[1]))
    # "tashladi" tasodifiy ro'yxatdan CHIQARILGAN — vozvrat manbai bo'lgan
    # "tashladi + tolandi>0" ulushini pastda ANIQ ~5-8% qilib boshqarish uchun
    # (tasodifiy + majburiy qo'shilsa ulush nazoratsiz shishib ketardi).
    holatlar = ["faol", "faol", "faol", "tugatdi", "muzlatilgan"]

    users_rows = []
    payments_rows = []
    for i in range(n_talaba):
        uid = 10800 + i
        buzuq = (i % 71 == 5)
        # ~5% talaba katalogda yo'q guruhda (guruh_id null test)
        if i % 41 == 0:
            kurs_id, guruh_kod, guruh_nom = ("K-XXX-99", "NOMALUM", "Eski guruh")
        else:
            kurs_id, guruh_kod, guruh_nom = rng.choice(guruhlar_katalog)
        jami = rng.choice([900000, 1200000, 1500000, 2400000, 3200000])
        tolandi = rng.choice([0, jami // 2, jami])
        holat = rng.choice(holatlar)

        # DETERMINISTIK sana tarqatish: talaba oxirgi ~45 kun ichida
        # boshlagan (bir xil urug' -> bir xil kun, hammasi bitta kunda emas).
        kun_orqaga_boshladi = rng.randint(0, 44)
        boshladi_sana = (OXIRGI_KUN - timedelta(days=kun_orqaga_boshladi)).isoformat()

        # ~7% talaba (18/260) kursni tashlab ketgan, LEKIN to'lov qilib
        # ulgurgan — vozvrat (qaytarish) uchun real manba. Deterministik
        # (i bo'yicha, urug'ga bog'liq emas -> ulush doim ~5-8%).
        if i % 15 == 0:
            holat = "tashladi"
            if tolandi == 0:
                tolandi = jami // 2

        # NPS (0..10): ba'zilari javob bermagan (bo'sh -> null). Deterministik,
        # og'irlikli (NPS_OGIRLIK) — realistik javob stavkasi + taqsimot.
        nps_pick = rng.choices(NPS_QIYMATLAR, weights=NPS_OGIRLIK, k=1)[0]
        nps_qiymat = str(nps_pick) if nps_pick is not None else ""

        users_rows.append([
            str(uid), _ism(rng), _telefon(rng, buzuq),
            f"user{uid}@mail.ru", guruh_kod, guruh_nom, kurs_id,
            holat, boshladi_sana, str(jami), str(tolandi),
            str(rng.randint(0, 100)), str(rng.randint(0, 100)),
            str(rng.randint(100000000, 999999999)) if i % 3 == 0 else "",
            nps_qiymat,
        ])
        # ba'zi talaba uchun to'lov(lar) — to'lov sanasi boshlaganidan keyin
        # (yoki bir kunda), shu bilan oxirgi ~45 kunga tarqaladi.
        if tolandi > 0:
            kun_orqaga_tolov = rng.randint(0, kun_orqaga_boshladi)
            tolov_sana = (OXIRGI_KUN - timedelta(days=kun_orqaga_tolov)).isoformat()
            payments_rows.append([f"p:{55000 + i}", str(uid), str(tolandi),
                                  "UZS", tolov_sana, "payme", kurs_id, "1-qism"])
    users_export = {
        "success": True,
        "info": {"export_id": 900001, "rows_count": len(users_rows)},
        "data": {
            "fields": ["user_id", "ism", "telefon", "email", "guruh_kod", "guruh_nom",
                       "kurs_id", "holat", "boshladi", "jami", "tolandi",
                       "davomat_foiz", "progress_foiz", "telegram_id", "nps"],
            "rows": users_rows,
        },
    }
    payments_export = {
        "success": True,
        "info": {"export_id": 900002, "rows_count": len(payments_rows)},
        "data": {
            "fields": ["tolov_id", "user_id", "summa", "valyuta", "sana", "usul",
                       "kurs_id", "izoh"],
            "rows": payments_rows,
        },
    }
    groups = {
        "success": True,
        "data": {
            "fields": ["guruh_kod", "guruh_nom", "kurs_id"],
            "rows": [[g[1], g[2], g[0]] for g in guruhlar_katalog],
        },
    }
    return users_export, payments_export, groups


def gen_sheets():
    """14 qatorli CSV: 12 valid guruh + 1 xato (31.09) + 1 ogoh (A-2 to'qnashuv)."""
    ustunlar = ["kurs_id", "nom", "format", "narx", "davomiylik_oy", "ustoz_id",
                "guruh_id", "boshlanish", "tugash", "kunlar", "vaqt", "xona", "sigim"]
    qatorlar = []
    for k in KATALOG:
        kurs_id, nom, fmt, narx, oy, ustoz, guruhlar = k
        for g in guruhlar:
            guruh_id, xona, vaqt, kunlar = g
            qatorlar.append([kurs_id, nom, fmt, str(narx), str(oy), ustoz,
                             guruh_id, "01.09.2026", "30.11.2026", kunlar, vaqt,
                             xona, "20"])
    for q in QOSHIMCHA:
        kurs_id, nom, fmt, narx, oy, ustoz, g = q
        guruh_id, xona, vaqt, kunlar = g
        qatorlar.append([kurs_id, nom, fmt, str(narx), str(oy), ustoz,
                         guruh_id, "01.09.2026", "30.11.2026", kunlar, vaqt, xona, "20"])
    # endi 12 valid qator bor
    assert len(qatorlar) == 12, len(qatorlar)
    # 1 XATO: mavjud bo'lmagan sana 31.09.2026 (9-qator emas — oxirida, aniqligi uchun)
    qatorlar.append(["K-MAT-02", "Fizika", "offline", "1000000", "4", "X-015",
                     "G-MAT-02-SEN", "31.09.2026", "30.11.2026", "du,chor",
                     "15:00-16:30", "E-2", "18"])
    # 1 OGOHLANTIRISH: G-DIZ-01-SEN bilan bir xona (A-2), bir vaqt, bir kun -> to'qnashuv
    qatorlar.append(["K-DIZ-02", "Veb dizayn", "offline", "2500000", "3", "X-014",
                     "G-DIZ-02-SEN", "01.09.2026", "30.11.2026", "du,chor,ju",
                     "18:30-20:30", "A-2", "16"])
    return ustunlar, qatorlar


def yoz_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="IN PLUS mock generatori (deterministik)")
    ap.add_argument("--lid", type=int, default=400)
    ap.add_argument("--talaba", type=int, default=260)
    ap.add_argument("--urug", type=int, default=42)
    ap.add_argument("--kun", type=int, default=0, help="demo: kun o'tishi (lid qo'shiladi)")
    args = ap.parse_args(argv)

    rng = random.Random(args.urug)
    leads, users, pipelines = gen_amocrm(rng, args.lid, args.kun)
    gc_users, gc_pay, gc_groups = gen_getcourse(rng, args.talaba)
    ustunlar, qatorlar = gen_sheets()

    yoz_json(MOCK / "amocrm" / "leads.json", leads)
    yoz_json(MOCK / "amocrm" / "users.json", users)
    yoz_json(MOCK / "amocrm" / "pipelines.json", pipelines)
    yoz_json(MOCK / "getcourse" / "users.json", gc_users)
    yoz_json(MOCK / "getcourse" / "payments.json", gc_pay)
    yoz_json(MOCK / "getcourse" / "groups.json", gc_groups)

    csv_p = MOCK / "sheets" / "jadval.csv"
    csv_p.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(ustunlar)
        w.writerows(qatorlar)

    print(f"amocrm.leads   : {len(leads['_embedded']['leads'])} lid")
    print(f"getcourse.users: {gc_users['info']['rows_count']} talaba")
    print(f"sheets.jadval  : {len(qatorlar)} qator (sarlavhasiz) — 12 guruh + 1 xato + 1 ogoh")
    print(f"urug={args.urug} kun={args.kun} -> {MOCK}")


if __name__ == "__main__":
    main()
