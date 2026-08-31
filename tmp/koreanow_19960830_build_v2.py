from pathlib import Path
p=Path('tmp/koreanow_19960830_build.py')
code=p.read_text(encoding='utf-8')
repl={
"https://upload.wikimedia.org/wikipedia/commons/3/35/1996-05-14_ATH_RA-85621.jpg":"https://www.aviationfanatic.com/images/150/1503911263Aeropark_Tu-154_B-2.jpg",
"https://commons.wikimedia.org/wiki/File:1996-05-14_ATH_RA-85621.jpg":"https://www.aviationfanatic.com/ent_show.php?ent=20&P_ID=5137",
"plane_RA-85621_1996-05-14.jpg":"tu154_aeropark_balint_toth.jpg",
"'author':'Paul Howard','date':'1996-05-14','license':'CC BY 2.0'":"'author':'Bálint Tóth','date':'2017-08-28','license':'CC BY 4.0'",
"실제 사고기 자료사진 / 사고 현장 아님 · Paul Howard · CC BY 2.0":"Tu-154 자료사진 / 사고기·사고 현장 아님 · Bálint Tóth · CC BY 4.0",
"https://upload.wikimedia.org/wikipedia/commons/a/a7/Fishing_Trawler_North_Of_Marine_Events_Centre.jpg":"https://tile.loc.gov/image-services/iiif/service:pnp:highsm:44600:44618/full/pct:25/0/default.jpg",
"https://commons.wikimedia.org/wiki/File:Fishing_Trawler_North_Of_Marine_Events_Centre.jpg":"https://www.loc.gov/item/2017881433/",
"trawler_reference_2011.jpg":"trawler_highsmith_LOC_2017.jpg",
"'author':'Ingolfson','date':'2011-06','license':'CC0 1.0'":"'author':'Carol M. Highsmith','date':'2017','license':'No known restrictions on publication'",
"원양어선 자료사진 / 사건 선박 아님 · Ingolfson · CC0":"트롤어선 자료사진 / 페스카마15호·사건 현장 아님 · Carol M. Highsmith · Library of Congress",
"https://upload.wikimedia.org/wikipedia/commons/d/db/Titanic-Cobh-Harbour-1912.JPG":"https://cdn.loc.gov/service/pnp/cph/3b00000/3b04000/3b04400/3b04419r.jpg",
"https://commons.wikimedia.org/wiki/File:Titanic-Cobh-Harbour-1912.JPG":"https://www.loc.gov/pictures/item/2001704335/",
"RMS_Titanic_Cobh_1912.jpg":"RMS_Titanic_LOC_Bain.jpg",
"'author':'Unknown photographer','date':'1912-04-11','license':'Public Domain'":"'author':'Bain News Service / Library of Congress','date':'1911-1912','license':'No known restrictions on reproduction'",
"RMS Titanic 1912년 실제 사진 / 1996 인양 현장 아님 · Public Domain":"RMS Titanic 실제 자료사진 / 1996 인양 현장 아님 · Library of Congress · No known restrictions"
}
for a,b in repl.items():
    if a not in code:
        raise SystemExit('replacement target missing: '+a)
    code=code.replace(a,b)
exec(compile(code,str(p),'exec'))
