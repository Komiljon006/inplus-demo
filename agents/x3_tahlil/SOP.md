# SOP — X3 Analitika hisoboti

> W1 shu faylni `wiki/agentlar/X3.md` ga oladi.

## Maqsad
Joriy paketdagi (D1 chiqishi) barcha xom ma'lumotdan — lidlar, talabalar,
to'lovlar, xodimlar — mijozga ko'rsatiladigan analitikani HAQIQIY hisoblab
chiqaradi: kunlik tushum, kurs bo'yicha daromad, menejerlar konversiyasi,
orqada qolayotgan talabalar, NPS, 4 haftalik prognoz, vozvrat. Hech qanday
raqam qo'lda/hardcode kiritilmaydi — hammasi paketdan hisoblanadi.

## Kirish (nimadan o'qiydi)
- `paket.oqi("X3")` — joriy paket (`data/paket/joriy.json`): `lidlar`,
  `talabalar`, `tolovlar`, `xodimlar` bo'limlari. Boshqa hech narsa
  o'qilmaydi (kurs nomi ham paketning o'zidagi `talaba.xom.guruh_nom`
  dan olinadi — `courses.json` alohida o'qilmaydi).

## Chiqish (nima yozadi)
- `data/tahlil.json` — joriy hisobot (versiya, sana, kunlik_tushum,
  kurs_daromadi, menejerlar, orqada, nps, prognoz, vozvrat).
- KPI: `jami_tushum`, `kunlar`, `kurslar`, `menejerlar`, `orqada_soni`,
  `nps_ball`, `vozvrat_soni`, `vozvrat_summa` (+ `kirdi.lidlar/talabalar/
  tolovlar`, `chiqdi.tahlil/kunlar/kurslar/menejerlar/orqada`).
- Xabar YUBORMAYDI (И0 — faqat hisobot).

## Hisoblash mantig'i (qisqacha)
- `kunlik_tushum` — `tolovlar[].summa` sana bo'yicha yig'indi, tartiblangan.
- `kurs_daromadi` — `talabalar[].tolov.jami` kurs_id bo'yicha yig'indi,
  kamayish tartibida.
- `menejerlar` — `lidlar[]` menejer_id bo'yicha; `sotildi` = bosqich
  "sotildi" soni; `konv` = sotildi/lid; ism/rol `xodimlar[]` dan.
- `orqada` — holat=faol va (davomat_foiz<60 YOKI progress_foiz<25).
- `nps` — `talaba.xom.nps` dan: 9-10 promoter, 7-8 passiv, 0-6 kritik,
  javob bermaganlar hisobga kirmaydi; ball=(promoter-kritik)/javob*100.
- `prognoz` — kunlik_tushum kalendar qatoriga tiklanib (bo'sh kunlar=0),
  sof Python eng kichik kvadratlar chiziqli regressiyasi bilan keyingi
  4 haftaga proyeksiya qilinadi (tashqi kutubxona yo'q).
- `vozvrat` — holat=tashladi va tolov.tolandi>0 bo'lgan talabalar.

## Qanday ishga tushiriladi
```
bin/inplus ishga X3
# yoki
python3 agents/x3_tahlil/main.py --bir-marta --sana 2026-09-19 --rejim mock
```
Jadval: `konfig/agentlar.json` → `X3.jadval` (D1 dan keyin).

## Yiqilsa nima qilish
- Sabab deyarli doim: `data/paket/joriy.json` yo'q yoki schema xato — avval
  D1 ni ishga tushiring (`bin/inplus ishga D1`).
- Heartbeat `xato`, exit != 0. X2 avtomat qayta yoqadi.
- Log: `data/jurnal/agent/X3/<sana>.log`.

## Kimga aytish
- Egasi: `konfig/agentlar.json` → `X3.egasi` (X-001). Kritik holat yo'q
  (И0, faqat hisobot) — S-900 yubormaydi.
