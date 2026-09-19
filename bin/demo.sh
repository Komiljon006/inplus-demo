#!/usr/bin/env bash
# IN PLUS — 1-blok «Poydevor» boshdan-oxir demo (8 qadam).
# Ishlatish:  bin/demo.sh            (avto, pauzasiz)
#             bin/demo.sh --pauza    (har qadamda Enter kutadi)
set -uo pipefail
ILDIZ="${INPLUS_ILDIZ:-$(cd "$(dirname "$0")/.." && pwd)}"
export INPLUS_ILDIZ="$ILDIZ" INPLUS_REJIM="${INPLUS_REJIM:-mock}" TG_REAL="${TG_REAL:-0}"
PY="$ILDIZ/.venv/bin/python"; [ -x "$PY" ] || PY=python3
INPLUS="$PY $ILDIZ/bin/inplus"
PAUZA="${1:-}"

qadam(){ echo; echo "══════════════════════════════════════════"; echo "  $*"; echo "══════════════════════════════════════════"; [ "$PAUZA" = "--pauza" ] && read -r -p "  ↵ Enter..."; }
j(){ "$PY" - "$@"; }   # inline python

# --- fon xizmatlar (ETS mock + shlyuz) ---
tozala(){ kill "${SHPID:-}" 2>/dev/null; pkill -f "mock/ets_server.py" 2>/dev/null; }
trap tozala EXIT
pkill -f "agents/shlyuz/main.py" 2>/dev/null; pkill -f "mock/ets_server.py" 2>/dev/null; sleep 1
rm -rf "$ILDIZ/data"/* "$ILDIZ/run"/* 2>/dev/null; mkdir -p "$ILDIZ/data" "$ILDIZ/run"
"$PY" "$ILDIZ/mock/ets_server.py" >/tmp/inplus_ets.log 2>&1 &
sleep 1
"$PY" "$ILDIZ/agents/shlyuz/main.py" >/tmp/inplus_shlyuz.log 2>&1 & SHPID=$!
sleep 2

qadam "1/8 · Rejim"
$INPLUS rejim
echo "  → Hozir mijoz bazasi yo'q — taqlid (mock). Ulanganda bitta qator o'zgaradi."

qadam "2/8 · D6 kurslar jadvali (xato tutiladi)"
"$PY" "$ILDIZ/mock/generator.py" --kun 0 >/dev/null 2>&1
$INPLUS ishga D6 >/dev/null 2>&1
if [ -f "$ILDIZ"/data/courses/*.xato.json ]; then
  j <<'PY'
import json,glob
d=json.load(open(sorted(glob.glob("data/courses/*.xato.json"))[-1]))
xs=d["validatsiya"]["xatolar"]
print(f"  ✗ courses.json YOZILMADI — {len(xs)} muammo:")
for x in xs: print(f"     qator {x['qator']}: {x['maydon']}={x['qiymat']} — {x['xabar']} [{x['daraja']}]")
print("  → Jadval xatosini odam ko'rmasdan tizim tutdi. Direktorga S-902 ketdi.")
PY
fi
echo "  … xatoni tuzatamiz (31.09 → 30.09) va qayta ishga tushiramiz:"
sed -i.bak 's/31\.09\.2026/30.09.2026/' "$ILDIZ/mock/sheets/jadval.csv"
$INPLUS ishga D6 >/dev/null 2>&1
j <<'PY'
import json
d=json.load(open("data/courses.json"))
print(f"  ✓ courses.json YANGILANDI — {len(d['kurslar'])} kurs, {sum(len(k['guruhlar']) for k in d['kurslar'])} guruh, holat: {d['validatsiya']['holat']}")
PY

qadam "3/8 · D1 kunlik paket (133 agent shundan o'qiydi)"
$INPLUS ishga D1 >/dev/null 2>&1
j <<'PY'
import json
d=json.load(open("data/paket/joriy.json"))
m={k:v['holat'] for k,v in d['manbalar'].items()}; s=d['statistika']
print(f"  ✓ paket {d['paket_id']} · hash {d['hash'][:14]}… · manba {m}")
print(f"     lid {s['lidlar']} · talaba {s['talabalar']} · qarzdor {s['qarzdorlar']} · qarz {s['qarz_jami']:,} so'm")
print("  → Har ertalab 06:00 shu paket. Hech kim CRM'ga o'zi kirmaydi.")
PY

qadam "4/8 · Manba yiqilsa — tizim to'xtamaydi"
INPLUS_MOCK_YIQIL=getcourse $INPLUS ishga D1 >/dev/null 2>&1
j <<'PY'
import json
d=json.load(open("data/paket/joriy.json"))
gc=d['manbalar']['getcourse']
print(f"  ⚠ getcourse: {gc['holat'].upper()} → {gc['xato']}")
print(f"     paket holati: {d.get('holat_umumiy')} (kechagi nusxa ishlatildi) · direktorga S-900 ketdi")
PY
$INPLUS ishga D1 >/dev/null 2>&1   # to'liq paketni tiklaymiz

qadam "5/8 · Xabar shlyuzi — bitta eshik, dublikat kesiladi"
echo "  → S-001 to'lov eslatmasi, direktorga TG:"
$INPLUS shlyuz yubor --kanal tg --skript S-001 --kimga xodim:X-303 \
  --oz ism=Bekzod kurs="Buxgalter noldan" summa="1 200 000" sana=1-oktyabr 2>&1 | sed 's/^/     /'
echo "  → aynan shu xabar QAYTA (dublikat kutiladi):"
$INPLUS shlyuz yubor --kanal tg --skript S-001 --kimga xodim:X-303 \
  --oz ism=Bekzod kurs="Buxgalter noldan" summa="1 200 000" sana=1-oktyabr 2>&1 | sed 's/^/     /'
echo "  → oq ro'yxatda yo'q raqam (rad kutiladi):"
$INPLUS shlyuz yubor --kanal sms --skript S-999 --kimga telefon:+998911111111 --oz matn=x 2>&1 | sed 's/^/     /'

qadam "6/8 · SMS (ЕТС mock — real narx shu yerda)"
$INPLUS shlyuz yubor --kanal sms --skript S-001 --kimga xodim:X-303 \
  --oz ism=Bekzod kurs="Buxgalter noldan" summa="1 200 000" sana=1-oktyabr 2>&1 | sed 's/^/     /'
sleep 3
echo "  → jurnal (kanal × holat × narx):"
$INPLUS shlyuz statistika 2>&1 | sed 's/^/     /'

qadam "7/8 · Agent yiqiladi → Doktor (X2) ko'taradi"
$INPLUS ishga X0 --yiqil >/dev/null 2>&1 || true
"$PY" "$ILDIZ/agents/x2_doktor/main.py" --bir-marta --simulyatsiya >/dev/null 2>&1
j <<'PY'
import json,glob
try:
  fs=sorted(glob.glob("data/insident/*.jsonl"))
  for l in open(fs[-1]):
    i=json.loads(l)
    if i["kim"]=="X2":
      print(f"  ⚕ X2: {i['agent']} {i['kod']} → {i['harakat']} → natija: {i['natija']}")
except Exception as e: print("  (insident yo'q)")
print("  → 135 agentdan kimdir yiqilsa — doktor davolaydi, sizga bir qator xabar.")
PY

# barcha faol agentlar ishga tushadi (X1 sverkasi to'liq bo'lishi uchun)
$INPLUS ishga S2 >/dev/null 2>&1
$INPLUS ishga S6 >/dev/null 2>&1
$INPLUS ishga X3 >/dev/null 2>&1
$INPLUS ishga S4 >/dev/null 2>&1

qadam "8/8 · Kechqurun sverkasi: X1 + N3 + W1"
$INPLUS ishga N3 >/dev/null 2>&1
$INPLUS ishga X1 >/dev/null 2>&1
$INPLUS ishga W1 >/dev/null 2>&1
j <<'PY'
import json,glob
x=json.load(open(sorted(glob.glob("data/x1/*.json"))[-1]))["jami"]
n=json.load(open(sorted(glob.glob("data/n3/*.json"))[-1])).get("kpi",{})
print(f"  ✓ X1 zanjir sverkasi: uzatish {x['uzatish']} · agent {x['agent_tekshirildi']} · yashil {x['yashil']} · buzilgan {x['buzilgan']} {x.get('kodlar',[])}")
print(f"     (KPI_XATO = 7-qadamda biz ataylab yiqitgan X0 — X2 davolagan)")
print(f"  ✓ N3 xabar auditi: jami {n.get('xabar_jami')} · yuborildi {n.get('yuborildi')} · rad {n.get('rad')} · narx {n.get('narx_som')} so'm · nomuvofiq {n.get('nomuvofiq')}")
print("  ✓ W1 wiki: wiki/_html/index.html (8 SOP + reestrlar + bugungi jurnal)")
PY
echo
echo "  Dashboard:  $ILDIZ/www/index.html   (data/dashboard.json — 8 agent, rangli)"
echo "  Wiki:       $ILDIZ/wiki/_html/index.html"
echo
echo "══════════════════════════════════════════"
echo "  DEMO TUGADI — 1-blok «Poydevor» ishlayapti (mock)."
echo "══════════════════════════════════════════"
