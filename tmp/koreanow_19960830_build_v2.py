from pathlib import Path
p=Path('tmp/koreanow_19960830_build.py')
code=p.read_text(encoding='utf-8')
code=code.replace(
'https://upload.wikimedia.org/wikipedia/commons/a/a7/Fishing_Trawler_North_Of_Marine_Events_Centre.jpg',
'https://upload.wikimedia.org/wikipedia/commons/4/4d/Fishing_Trawler_North_Of_Marine_Events_Centre.jpg'
)
exec(compile(code,str(p),'exec'))
