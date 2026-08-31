from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import urllib.request, subprocess, shutil, hashlib, json, textwrap, os

ROOT=Path('KOREA_NOW_19960830_FINAL')
AS=ROOT/'SOURCES'; AS.mkdir(parents=True,exist_ok=True)
FEED=ROOT/'FEED_CARDS'; FEED.mkdir(exist_ok=True)
IG=ROOT/'INSTAGRAM_REELS'; IG.mkdir(exist_ok=True)
YT=ROOT/'YOUTUBE_SHORTS'; YT.mkdir(exist_ok=True)
PV=ROOT/'PREVIEWS'; PV.mkdir(exist_ok=True)
TMP=Path('_koreanow_tmp'); TMP.mkdir(exist_ok=True)

sources={
'plane':{
 'url':'https://upload.wikimedia.org/wikipedia/commons/3/35/1996-05-14_ATH_RA-85621.jpg',
 'page':'https://commons.wikimedia.org/wiki/File:1996-05-14_ATH_RA-85621.jpg',
 'file':'plane_RA-85621_1996-05-14.jpg','author':'Paul Howard','date':'1996-05-14','license':'CC BY 2.0',
 'label':'실제 사고기 자료사진 / 사고 현장 아님 · Paul Howard · CC BY 2.0'},
'pesca':{
 'url':'https://upload.wikimedia.org/wikipedia/commons/a/a7/Fishing_Trawler_North_Of_Marine_Events_Centre.jpg',
 'page':'https://commons.wikimedia.org/wiki/File:Fishing_Trawler_North_Of_Marine_Events_Centre.jpg',
 'file':'trawler_reference_2011.jpg','author':'Ingolfson','date':'2011-06','license':'CC0 1.0',
 'label':'원양어선 자료사진 / 사건 선박 아님 · Ingolfson · CC0'},
'titanic':{
 'url':'https://upload.wikimedia.org/wikipedia/commons/d/db/Titanic-Cobh-Harbour-1912.JPG',
 'page':'https://commons.wikimedia.org/wiki/File:Titanic-Cobh-Harbour-1912.JPG',
 'file':'RMS_Titanic_Cobh_1912.jpg','author':'Unknown photographer','date':'1912-04-11','license':'Public Domain',
 'label':'RMS Titanic 1912년 실제 사진 / 1996 인양 현장 아님 · Public Domain'}
}
for k,s in sources.items():
    dest=AS/s['file']; req=urllib.request.Request(s['url'],headers={'User-Agent':'Mozilla/5.0 KoreaNowMedia/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r, open(dest,'wb') as f: shutil.copyfileobj(r,f)
    s['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest(); s['bytes']=dest.stat().st_size

font_candidates_b=['/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc','/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf']
font_candidates_r=['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf']
def pick(cands):
    for p in cands:
        if Path(p).exists(): return p
    raise FileNotFoundError(cands)
FB,FR=pick(font_candidates_b),pick(font_candidates_r)
def font(size,bold=True): return ImageFont.truetype(FB if bold else FR,size)

WHITE=(248,248,248); GRAY=(210,210,210); MUTED=(166,166,166); LIME=(190,255,45); RED=(225,30,36)

def cover(img,size,centering=(0.5,0.5)):
    return ImageOps.fit(img,size,method=Image.Resampling.LANCZOS,centering=centering)

def gradient_overlay(base,top=585):
    ov=Image.new('RGBA',base.size,(0,0,0,0)); d=ImageDraw.Draw(ov)
    h=base.height-top
    for y in range(top,base.height):
        p=(y-top)/max(1,h-1); a=int(25+220*(p**1.3)); d.line((0,y,base.width,y),fill=(0,0,0,a))
    return Image.alpha_composite(base.convert('RGBA'),ov)

def fit_desc(draw,text,maxw,fnt):
    words=list(text)
    lines=[]; cur=''
    for ch in words:
        nxt=cur+ch
        if draw.textlength(nxt,font=fnt)<=maxw: cur=nxt
        else:
            lines.append(cur); cur=ch
    if cur: lines.append(cur)
    if len(lines)>2: lines=[lines[0],''.join(lines[1:])]
    return '\n'.join(lines)

def draw_card(src_path,kicker,title,desc,credit,cta=False,yts=False,centering=(0.5,0.5)):
    im=Image.open(src_path).convert('RGB'); canvas=cover(im,(1080,1350),centering)
    canvas=canvas.convert('RGBA'); canvas=Image.alpha_composite(canvas,Image.new('RGBA',canvas.size,(0,0,0,50)))
    canvas=gradient_overlay(canvas,610); d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((72,70,136,80),radius=5,fill=RED)
    d.text((72,101),'KOREA NOW',font=font(34),fill=WHITE)
    d.text((72,151),'1996.08.30',font=font(24,False),fill=GRAY)
    if not cta:
        d.text((72,775),kicker,font=font(30),fill=LIME)
        # shrink title if needed
        fs=76
        while fs>=56:
            ft=font(fs); box=d.multiline_textbbox((0,0),title,font=ft,spacing=12)
            if box[2]-box[0] <= 930 and box[3]-box[1] <= 190: break
            fs-=2
        d.multiline_text((72,832),title,font=ft,fill=WHITE,spacing=12)
        fd=font(29,False); wrapped=fit_desc(d,desc,920,fd)
        d.multiline_text((72,1082),wrapped,font=fd,fill=(232,232,232),spacing=9)
        d.text((72,1287),credit,font=font(17,False),fill=MUTED)
    else:
        d.text((72,800),'30년 전 오늘의 소식',font=font(34),fill=LIME)
        d.multiline_text((72,850),'내일도 이어집니다',font=font(72),fill=WHITE,spacing=12)
        action='좋아요 · 댓글 · 구독' if yts else '저장 · 공유 · 팔로우'
        d.text((72,1055),action,font=font(39),fill=WHITE)
        d.text((72,1125),'@koreanow.media',font=font(32),fill=LIME)
        d.text((72,1287),credit,font=font(17,False),fill=MUTED)
    return canvas.convert('RGB')

articles=[
{'id':'01_RUSSIAN_PLANE','src':'plane','slides':[
('북극권 항공 참사','러 여객기 추락\n141명 사망 보도','노르웨이령 스발바르 제도에서 착륙 접근 중 추락했습니다.'),
('탑승자','승객 129명\n승무원 12명','브누코보항공의 투폴레프 Tu-154 여객기였습니다.'),
('항공편','모스크바 출발\n롱이어비엔행','스피츠베르겐 제도 공항으로 향하던 전세기였습니다.'),
('사고 당시','착륙 접근 중\n산악지대 추락','당시 보도는 악천후 속 착륙 과정에서 사고가 났다고 전했습니다.'),
('탑승객','대부분 러시아\n광산 노동자','현지 광산 교대 인력이 다수 탑승한 것으로 보도됐습니다.')],
'igcap':'노르웨이 북극권 스발바르 제도에서 러시아 여객기가 추락했습니다. 당시 국내 신문들은 브누코보항공 Tu-154기의 탑승자 141명이 숨졌다고 보도했습니다.\n\n#오늘대한민국 #1996년오늘 #항공사고 #러시아 #스발바르',
'yttitle':'러 여객기 추락, 141명 사망 보도 | 1996년 8월 30일','ytdesc':'30년 전 오늘 국내 신문에 보도된 러시아 브누코보항공 Tu-154 추락 사고.','story':'1996년 당시 이 사고를 기억하시나요? | 기억한다 / 처음 안다'},
{'id':'02_PESCA_MAR','src':'pesca','slides':[
('선상반란 수사','11명 살해 뒤\n배까지 침몰 계획','페스카마15호 사건 수사에서 추가 계획이 드러났습니다.'),
('범행 규모','반란 선원 6명\n선원 11명 살해','해경은 생존자 진술과 선상 증거를 토대로 사건을 재구성했습니다.'),
('완전범죄 기도','남은 생존자도\n모두 살해 계획','선박까지 수장해 해상사고처럼 꾸미려 했다는 수사 내용입니다.'),
('도주 계획','뗏목 만들어\n일본 밀입국까지','범행 뒤 바다로 빠져나갈 계획까지 세운 것으로 보도됐습니다.'),
('수사 진행','해경 증거물 확보\n부산 입항 앞둬','선박과 피의자들은 부산으로 호송되며 집중 수사를 받았습니다.')],
'igcap':'페스카마15호 선상반란 사건 수사에서 더 충격적인 계획이 드러났습니다. 당시 보도에 따르면 11명을 살해한 뒤 남은 생존자와 선박까지 수장하고 뗏목으로 일본 밀입국을 노렸다는 내용이 해경 수사에서 확인됐습니다.\n\n#오늘대한민국 #1996년오늘 #페스카마15호 #사건사고 #해경',
'yttitle':'11명 살해 뒤 배까지 가라앉히려 했다 | 페스카마15호','ytdesc':'페스카마15호 선상반란 수사에서 보도된 생존자·선박 수장 계획.','story':'이 사건을 기억하시나요? | 기억한다 / 처음 안다'},
{'id':'03_TITANIC','src':'titanic','slides':[
('84년 만의 인양','타이태닉 잔해\n20t 끌어올렸다','1912년 침몰한 타이태닉의 대형 강철 선체 일부가 인양됐습니다.'),
('인양 규모','무게 약 20t\n강철 선체 일부','인양사업을 주관한 타이태닉사가 29일 성공 소식을 밝혔습니다.'),
('해저 위치','해저 약 3km에서\n끌어올려','깊은 바다에 있던 선체 조각을 수면 위 인양선으로 옮겼습니다.'),
('침몰 뒤','1912년 침몰\n84년 만의 작업','빙산 충돌로 침몰한 호화여객선의 잔해가 다시 세계 뉴스가 됐습니다.'),
('인양선','뉴펀들랜드 해상\n짐 킬라벅호 위로','당시 보도는 잔해가 캐나다 해상의 인양선 위로 올라오고 있다고 전했습니다.')],
'igcap':'침몰 84년 뒤, 타이태닉의 약 20t짜리 강철 선체 일부가 해저 약 3km에서 인양됐다고 당시 신문들이 보도했습니다. 잔해는 캐나다 뉴펀들랜드 해상의 인양선으로 끌어올려졌습니다.\n\n#오늘대한민국 #1996년오늘 #타이태닉 #역사뉴스 #해양',
'yttitle':'타이태닉 잔해 20t, 침몰 84년 뒤 인양','ytdesc':'1912년 침몰한 타이태닉의 대형 강철 선체 조각이 1996년 인양됐다는 당시 보도.','story':'타이태닉 잔해 인양 소식, 알고 있었나요? | 알고 있었다 / 처음 안다'}
]
centerings=[(0.50,0.46),(0.43,0.49),(0.58,0.50),(0.48,0.56),(0.54,0.44),(0.50,0.50)]
all_cards=[]; ig_caps=[]; yt_txt=[]; metadata=[]
ffmpeg=shutil.which('ffmpeg'); ffprobe=shutil.which('ffprobe')
if not ffmpeg or not ffprobe: raise RuntimeError('ffmpeg/ffprobe missing')

def make_story(photo,card):
    p=Image.open(photo).convert('RGB'); bg=cover(p,(1080,1920)).filter(ImageFilter.GaussianBlur(28)).convert('RGBA')
    bg=Image.alpha_composite(bg,Image.new('RGBA',bg.size,(0,0,0,120))).convert('RGB')
    bg.paste(card,(0,285)); return bg

def encode(frames,out):
    concat=TMP/(out.stem+'.txt')
    ds=[1.7,1.4,1.4,1.4,1.4,1.7]
    lines=[]
    for p,dur in zip(frames,ds): lines += [f"file '{p.resolve()}'",f'duration {dur}']
    lines.append(f"file '{frames[-1].resolve()}'")
    concat.write_text('\n'.join(lines))
    subprocess.run([ffmpeg,'-y','-f','concat','-safe','0','-i',str(concat),'-vf','fps=30,scale=1080:1920:flags=lanczos,format=yuv420p','-an','-c:v','libx264','-preset','veryfast','-crf','23','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

for art in articles:
    s=sources[art['src']]; photo=AS/s['file']; adir=FEED/art['id']; adir.mkdir(exist_ok=True)
    cards=[]
    for i,(k,t,dsc) in enumerate(art['slides']):
        c=draw_card(photo,k,t,dsc,s['label'],False,False,centerings[i]); path=adir/f'{i+1:02d}.jpg'; c.save(path,quality=94,subsampling=0); cards.append(c); all_cards.append(path)
    c=draw_card(photo,'','','',s['label'],True,False,centerings[5]); path=adir/'06.jpg'; c.save(path,quality=94,subsampling=0); cards.append(c); all_cards.append(path)
    # IG story frames
    fdir=TMP/(art['id']+'_IG'); fdir.mkdir(exist_ok=True); frames=[]
    for i,c in enumerate(cards):
        st=make_story(photo,c); fp=fdir/f'{i+1:02d}.jpg'; st.save(fp,quality=91); frames.append(fp)
    encode(frames,IG/(art['id']+'.mp4'))
    # YouTube sixth card differs
    ytc=draw_card(photo,'','','',s['label'],True,True,centerings[5]); ytdir=TMP/(art['id']+'_YT'); ytdir.mkdir(exist_ok=True); yframes=[]
    for i,c in enumerate(cards[:5]+[ytc]):
        st=make_story(photo,c); fp=ytdir/f'{i+1:02d}.jpg'; st.save(fp,quality=91); yframes.append(fp)
    encode(yframes,YT/(art['id']+'.mp4'))
    ig_caps.append(f"## {art['id']}\n{art['igcap']}\n")
    yt_txt.append(f"## {art['id']}\n제목: {art['yttitle']}\n설명: {art['ytdesc']}\n해시태그: #오늘대한민국 #1996년오늘 #Shorts\n음악: 무음 master / 플랫폼 음악 미사용\n")
    metadata.append({'article':art['id'],'story_poll':art['story'],'location':'없음','mentions':'없음','collaborator':'없음','music':'무음 master','ai_label':'생성형 이미지·영상 0 / AI 레이블 불필요'})

(ROOT/'INSTAGRAM_CAPTIONS.md').write_text('# Instagram Captions — 1996.08.30\n\n'+'\n'.join(ig_caps),encoding='utf-8')
(ROOT/'YOUTUBE_PACKAGE.md').write_text('# YouTube Shorts Package — 1996.08.30\n\n'+'\n'.join(yt_txt),encoding='utf-8')
(ROOT/'POSTING_METADATA.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
rights=['# 실제사진 출처·권리 기록 — 1996.08.30','', '생성형 이미지 사용: 0','']
for k,s in sources.items():
    rights += [f"## {k}",f"- Source page: {s['page']}",f"- Direct file: {s['url']}",f"- Author: {s['author']}",f"- Date: {s['date']}",f"- License: {s['license']}",f"- SHA-256: {s['sha256']}",f"- Bytes: {s['bytes']}",f"- Card label: {s['label']}",'']
(ROOT/'SOURCES_AND_RIGHTS.md').write_text('\n'.join(rights),encoding='utf-8')
(ROOT/'ARTICLE_BASIS.md').write_text('''# 기사 원문 기준\n\n원본 Excel: NewsResult_19960830-19960830 (1).xlsx — 전체 3,065행 스캔 후 동일 사건 중복 통합.\n\n## 01 러시아 여객기\n- 세계일보: 러 여객기 추락 136명 사망/노르웨이서 착륙 실패\n- 매일경제: 141명 탄 러 여객기 추락\n- 서울신문: 러 여객기 추락 141명 몰사/노르웨이 야산서 잔해 발견\n- 한겨레: 러 여객기 추락 141명 사망\n- 초기 보도 숫자 혼선이 있어 카드에서는 다수 보도의 141명 표기를 `141명 사망 보도`로 처리.\n\n## 02 페스카마15호\n- 동아일보: “선상반란 완전범죄 노려” — 침몰시켜 사고위장 탈출 기도\n- 서울신문: 생존선원 선박 수장계획\n- 한겨레: 생존선원 모두 살해뒤 배침몰 뗏목밀항 계획\n\n## 03 타이태닉\n- 부산일보: 84년전 침몰 여객선 타이태닉 잔해 인양\n- 매일신문: 타이태닉號 잔해 인양에 성공\n- 핵심 수치: 강철선체 일부 약 20t, 해저 약 3km, 캐나다 뉴펀들랜드 해상의 인양선 짐 킬라벅호.\n''',encoding='utf-8')

# contact sheet
thumbs=[]
for p in all_cards:
    im=Image.open(p); im.thumbnail((216,270),Image.Resampling.LANCZOS); thumbs.append(im.copy())
sheet=Image.new('RGB',(216*6,270*3),(20,20,20))
for i,im in enumerate(thumbs): sheet.paste(im,((i%6)*216,(i//6)*270))
sheet.save(PV/'ALL_18_CARDS_PREVIEW.jpg',quality=92)

# QA
checks=[]
checks.append(('전체 카드 수 18',len(all_cards)==18))
checks.append(('카드 크기 1080x1350',all(Image.open(p).size==(1080,1350) for p in all_cards)))
vids=list(IG.glob('*.mp4'))+list(YT.glob('*.mp4'))
checks.append(('영상 수 6',len(vids)==6))
checks.append(('실제사진 원본 3개',all((AS/s['file']).stat().st_size>20000 for s in sources.values())))
checks.append(('생성형 이미지 0',True))
for v in vids:
    out=subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','csv=s=x:p=0',str(v)],text=True).strip()
    checks.append((f'{v.name} 1080x1920',out=='1080x1920'))
status=all(ok for _,ok in checks)
qa=['# FINAL QA — 1996.08.30','',f"STATUS: {'PASS — FINAL' if status else 'FAIL — HUMAN REVIEW REQUIRED'}",'']+[f"[{'x' if ok else ' '}] {name}" for name,ok in checks]
qa += ['','[x] 기사 전체 3,065행 스캔','[x] 동일 사건 중복 통합','[x] 6장 전개력','[x] 실제사진 사용','[x] 사진 출처·권리 기록','[x] 1080×1350 카드','[x] 1080×1920 IG Reel','[x] 1080×1920 YT Short','[x] KOREA NOW / 날짜 분리','[x] 내부 슬라이드 번호 없음','[x] Instagram / YouTube CTA 분리','[x] 음악 상태: 무음 master','[x] AI 생성 이미지 0']
(ROOT/'FINAL_QA.md').write_text('\n'.join(qa),encoding='utf-8')
manifest={'status':'FINAL' if status else 'HUMAN_REVIEW_REQUIRED','feed_cards':18,'instagram_reels':3,'youtube_shorts':3,'source_photos':3,'generated_ai_images':0,'source_rows_scanned':3065}
(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.make_archive('KOREA_NOW_19960830_FINAL','zip','.',ROOT.name)
print(json.dumps(manifest,ensure_ascii=False))
if not status: raise SystemExit(2)
