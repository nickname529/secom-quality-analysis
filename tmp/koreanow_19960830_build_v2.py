from pathlib import Path
p=Path('tmp/koreanow_19960830_build.py')
code=p.read_text(encoding='utf-8')
repl={
'https://upload.wikimedia.org/wikipedia/commons/3/35/1996-05-14_ATH_RA-85621.jpg':'https://commons.wikimedia.org/wiki/Special:Redirect/file/1996-05-14_ATH_RA-85621.jpg',
'https://upload.wikimedia.org/wikipedia/commons/a/a7/Fishing_Trawler_North_Of_Marine_Events_Centre.jpg':'https://commons.wikimedia.org/wiki/Special:Redirect/file/Fishing_Trawler_North_Of_Marine_Events_Centre.jpg',
'https://upload.wikimedia.org/wikipedia/commons/d/db/Titanic-Cobh-Harbour-1912.JPG':'https://commons.wikimedia.org/wiki/Special:Redirect/file/Titanic-Cobh-Harbour-1912.JPG'
}
for a,b in repl.items(): code=code.replace(a,b)
exec(compile(code,str(p),'exec'))
