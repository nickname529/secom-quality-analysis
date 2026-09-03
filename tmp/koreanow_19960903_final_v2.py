from pathlib import Path
p=Path('tmp/koreanow_19960903_final.py')
code=p.read_text(encoding='utf-8')
old="""'buenos':{\n   'urls':['https://wsrv.nl/?url=https%3A%2F%2Fupload.wikimedia.org%2Fwikipedia%2Fcommons%2Ff%2Ff6%2FBuenos_Aires_centre_ville_1992.jpg&output=jpg','https://cdn.loc.gov/service/pnp/npcc/19900/19935v.jpg'],\n   'page':'https://commons.wikimedia.org/wiki/File:Buenos_Aires_centre_ville_1992.jpg',\n   'file':'buenos_aires_1992.jpg','author':'FC Georgio','date':'1992','license':'CC BY 1.0',\n   'credit':'1992년 부에노스아이레스 실제사진 · FC Georgio · CC BY 1.0'}"""
new="""'buenos':{\n   'urls':['https://tile.loc.gov/storage-services/service/pnp/npcc/19900/19935v.jpg','https://cdn.loc.gov/service/pnp/npcc/19900/19935r.jpg'],\n   'page':'https://www.loc.gov/pictures/item/2016821513/',\n   'file':'buenos_aires_avenida_de_mayo.jpg','author':'National Photo Company Collection / Library of Congress','date':'1908-1919','license':'No known restrictions on publication',\n   'credit':'부에노스아이레스 실제 자료사진 · Library of Congress · 사건 현장 아님'}"""
if old not in code:
    raise RuntimeError('Buenos source block not found')
code=code.replace(old,new)
exec(compile(code,str(p),'exec'))
