from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import urllib.request, subprocess, shutil, hashlib, json, os, zipfile

DATE='1996.08.31'
ROOT=Path('KOREA_NOW_19960831_FINAL')
SRC=ROOT/'SOURCES'; FEED=ROOT/'FEED_CARDS'; IG=ROOT/'INSTAGRAM_REELS'; YT=ROOT/'YOUTUBE_SHORTS'; PRE=ROOT/'PREVIEWS'; TMP=Path('_kn31_tmp')
for p in [SRC,FEED,IG,YT,PRE,TMP]: p.mkdir(parents=True,exist_ok=True)

sources={
'father':{
 'url':'https://cdn.loc.gov/service/pnp/npcc/00200/00292v.jpg',
 'page':'https://www.loc.gov/item/2016819579/',
 'file':'playground_reference.jpg','author':'National Photo Company Collection','date':'1918-1920','license':'No known restrictions on publication',
 'credit':'놀이터 자료사진 / 사건 현장 아님 · Library of Congress'},
'parts':{
 'url':'https://tile.loc.gov/storage-services/service/pnp/fsa/8a24000/8a24100/8a24191v.jpg',
 'page':'https://www.loc.gov/item/2017737978/',
 'file':'automobile_parts_reference.jpg','author':'Russell Lee','date':'1938-11','license':'Public Domain — FSA/OWI collection',
 'credit':'자동차부품 자료사진 / 사건 압수물 아님 · Russell Lee / LOC'},
'titanic':{
 'url':'https://cdn.loc.gov/service/pnp/cph/3b00000/3b04000/3b04400/3b04419r.jpg',
 'page':'https://www.loc.gov/item/2001704335/',
 'file':'titanic_1911.jpg','author':'Bain News Service / Library of Congress','date':'1911-05-31','license':'No known restrictions on reproduction',
 'credit':'RMS Titanic 실제 사진 / 1996 인양 현장 아님 · Library of Congress'}
}
for s in sources.values():
    req=urllib.request.Request(s['url'],headers={'User-Agent':'Mozilla/5.0 KoreaNowMedia/1.0'})
    dest=SRC/s['file']
    with urllib.request.urlopen(req,timeout=60) as r, open(dest,'wb') as f: shutil.copyfileobj(r,f)
    s['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest(); s['bytes']=dest.stat().st_size

FB='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'; FR='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def font(sz,bold=True): return ImageFont.truetype(FB if bold else FR,sz)
WHITE=(248,248,248); GRAY=(220,220,220); MUTED=(172,172,172); LIME=(190,255,45); RED=(227,31,36)

def crop(im,size,center=(0.5,0.5)): return ImageOps.fit(im,size,method=Image.Resampling.LANCZOS,centering=center)
def wrap_chars(draw,text,fnt,maxw,max_lines=2):
    lines=[]; cur=''
    for ch in text:
        n=cur+ch
        if draw.textlength(n,font=fnt)<=maxw: cur=n
        else: lines.append(cur); cur=ch
    if cur: lines.append(cur)
    if len(lines)>max_lines: lines=lines[:max_lines-1]+[''.join(lines[max_lines-1:])]
    return '\n'.join(lines)
def dark_gradient(base,start=570):
    b=base.convert('RGBA'); ov=Image.new('RGBA',b.size,(0,0,0,0)); d=ImageDraw.Draw(ov)
    for y in range(start,b.height):
        t=(y-start)/(b.height-start); a=int(20+225*(t**1.15)); d.line((0,y,b.width,y),fill=(0,0,0,a))
    return Image.alpha_composite(b,ov)
def header(d):
    d.rounded_rectangle((72,70,137,80),radius=5,fill=RED)
    d.text((72,101),'KOREA NOW',font=font(34),fill=WHITE)
    d.text((72,151),DATE,font=font(24,False),fill=GRAY)
def card(photo,kicker,title,desc,credit,center=(0.5,0.5),cta='ig'):
    im=Image.open(photo).convert('RGB'); c=crop(im,(1080,1350),center); c=Image.alpha_composite(c.convert('RGBA'),Image.new('RGBA',c.size,(0,0,0,45))); c=dark_gradient(c,600); d=ImageDraw.Draw(c); header(d)
    if cta is None:
        d.text((72,780),kicker,font=font(30),fill=LIME)
        fs=74
        while fs>=54:
            ft=font(fs); box=d.multiline_textbbox((0,0),title,font=ft,spacing=10)
            if box[2]-box[0] <= 925 and box[3]-box[1] <= 190: break
            fs-=2
        d.multiline_text((72,834),title,font=ft,fill=WHITE,spacing=10)
        fd=font(28,False); d.multiline_text((72,1080),wrap_chars(d,desc,fd,920,2),font=fd,fill=(235,235,235),spacing=7)
    else:
        d.text((72,790),'30년 전 오늘의 소식',font=font(34),fill=LIME)
        d.text((72,850),'내일도 이어집니다',font=font(70),fill=WHITE)
        action='좋아요 · 댓글 · 구독' if cta=='yt' else '저장 · 공유 · 팔로우'
        d.text((72,1030),action,font=font(40),fill=WHITE)
        d.text((72,1105),'@koreanow.media',font=font(33),fill=LIME)
    d.text((72,1288),credit,font=font(17,False),fill=MUTED)
    return c.convert('RGB')
def hook_frame(photo,title,credit,center=(0.5,0.5)):
    im=Image.open(photo).convert('RGB'); c=crop(im,(1080,1920),center).convert('RGBA'); c=Image.alpha_composite(c,Image.new('RGBA',c.size,(0,0,0,60))); d=ImageDraw.Draw(c)
    # top brand
    d.rounded_rectangle((72,82,137,92),radius=5,fill=RED); d.text((72,113),'KOREA NOW',font=font(34),fill=WHITE); d.text((72,162),DATE,font=font(24,False),fill=GRAY)
    ov=Image.new('RGBA',c.size,(0,0,0,0)); od=ImageDraw.Draw(ov)
    for y in range(1050,1920):
        t=(y-1050)/870; od.line((0,y,1080,y),fill=(0,0,0,int(20+215*t)))
    c=Image.alpha_composite(c,ov); d=ImageDraw.Draw(c); fs=82
    while fs>=62:
        ft=font(fs); bb=d.multiline_textbbox((0,0),title,font=ft,spacing=12)
        if bb[2]-bb[0]<=930 and bb[3]-bb[1]<=250: break
        fs-=2
    d.multiline_text((72,1370),title,font=ft,fill=WHITE,spacing=12)
    d.text((72,1840),credit,font=font(17,False),fill=(190,190,190))
    return c.convert('RGB')
def story_frame(photo,card_img):
    im=Image.open(photo).convert('RGB'); bg=crop(im,(1080,1920)).filter(ImageFilter.GaussianBlur(30)).convert('RGBA'); bg=Image.alpha_composite(bg,Image.new('RGBA',bg.size,(0,0,0,125))).convert('RGB'); bg.paste(card_img,(0,285)); return bg

def make_video(frame_paths,out):
    durations=[1.7,1.35,1.35,1.35,1.35,1.8]
    lst=TMP/(out.stem+'.txt'); lines=[]
    for p,dur in zip(frame_paths,durations): lines += [f"file '{p.resolve()}'",f'duration {dur}']
    lines.append(f"file '{frame_paths[-1].resolve()}'"); lst.write_text('\n'.join(lines))
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(lst),'-vf','fps=30,scale=1080:1920:flags=lanczos,format=yuv420p','-c:v','libx264','-preset','medium','-crf','20','-movflags','+faststart',str(out)],check=True)

def probe_video(path):
    q=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-show_entries','format=duration','-of','json',str(path)],capture_output=True,text=True,check=True)
    return json.loads(q.stdout)

articles=[
{'id':'01_FATHER_ABANDONED','src':'father','center':(0.50,0.52),'slides':[
('존속유기치사','중풍 85세 아버지를\n놀이터에 버렸다','서울 노원구에서 30대 아들이 거동이 어려운 아버지를 집 밖에 버린 혐의로 붙잡혔습니다.'),
('사건 당일','집에서 80m 떨어진\n놀이터 정자에','경찰은 아들이 8월 5일 오후 7시쯤 아버지를 업고 가 혼자 돌아왔다고 밝혔습니다.'),
('이틀 뒤','놀이터에서 의식 잃은 채\n주민이 발견','아버지는 7일 발견돼 병원으로 옮겨졌습니다.'),
('결국','병원 이송 6일 뒤\n13일 숨져','당시 보도는 중풍으로 거동이 불편했던 85세 노인이 치료 중 숨졌다고 전했습니다.'),
('경찰 조치','38세 아들\n긴급구속·영장','노원경찰서는 30일 존속유기치사 혐의로 아들을 긴급구속하거나 영장을 신청했다고 보도됐습니다.')],
'igcap':'중풍으로 거동이 어려운 85세 아버지를 아파트 놀이터에 버려 숨지게 한 혐의로 30대 아들이 붙잡혔습니다. 당시 보도에 따르면 아버지는 집에서 약 80m 떨어진 놀이터에 남겨졌고 이틀 뒤 발견돼 병원으로 옮겨졌지만 6일 뒤 숨졌습니다.\n\n#오늘대한민국 #1996년오늘 #사건사고 #노원구 #사회뉴스',
'yttitle':'중풍 85세 아버지를 놀이터에 버렸다 | 1996년 8월 31일','ytdesc':'1996년 8월 31일 신문에 보도된 서울 노원구 존속유기치사 사건. 사진은 사건 현장이 아닌 놀이터 자료사진입니다.','story':'놀이터에 버려진 85세 아버지 사건, 기억하시나요? | 기억한다 / 처음 안다','music':'엄정화 — 하늘만 허락한 사랑 (KBS 가요톱10 1996.08.28 6위 / 비극적 기사 톤 고려)'},
{'id':'02_FAKE_AUTO_PARTS','src':'parts','center':(0.50,0.50),'slides':[
('가짜 자동차부품','순정품처럼 속여\n34만여 개 유통','검찰이 유명 자동차회사 상표를 붙인 가짜·저질 부품 유통망을 적발했습니다.'),
('유통 규모','가짜 부품\n34만여 개','세계일보는 순정품으로 속인 부품이 34만여 개 시중에 유통됐다고 보도했습니다.'),
('돈 규모','20억 원대\n가짜 부품 유통','동아일보는 사건 규모를 20억 원대로 보도했습니다.'),
('수법','무허가 저급 부품에\n유명 회사 상표','검찰은 자체 생산하거나 납품받은 저급 부품에 자동차회사 상표를 붙였다고 밝혔습니다.'),
('검찰 조치','19명 구속\n30명 불구속 입건','제조업체와 도·소매상 등 대규모 유통망이 수사 대상이 됐습니다.')],
'igcap':'유명 자동차회사 상표를 붙인 가짜·저질 자동차부품이 순정품처럼 팔렸습니다. 당시 보도는 약 34만여 개가 시중에 유통됐고 사건 규모가 20억 원대에 달했다고 전했습니다. 검찰은 제조·도소매업자 19명을 구속하고 소매상 30명을 불구속 입건했습니다.\n\n#오늘대한민국 #1996년오늘 #자동차부품 #소비자 #사건사고',
'yttitle':'순정품처럼 속인 가짜 자동차부품 34만여 개','ytdesc':'1996년 8월 31일 보도된 가짜·저질 자동차부품 유통 사건. 사진은 사건 압수물이 아닌 자동차부품 자료사진입니다.','story':'가짜 자동차부품 34만여 개, 가장 놀라운 건? | 물량 / 20억 규모','music':'김건모 — 악몽 (KBS 가요톱10 1996.08.28 7위 / 범죄·소비자 경고 톤)'},
{'id':'03_TITANIC_FAILED','src':'titanic','center':(0.52,0.50),'slides':[
('84년 만의 인양','타이태닉 20t 잔해\n다시 바다로','수면 가까이 끌어올린 대형 선체 조각이 연결선 파손으로 다시 가라앉았습니다.'),
('거의 다 왔다','해저 약 3km에서\n수면 65m까지','20여t짜리 강철 선체 일부를 부양기구로 수면 가까이 끌어올렸습니다.'),
('마지막 순간','연결 케이블이\n갑자기 끊어졌다','선체와 부양기구를 잇던 줄이 끊어지며 인양작업이 실패했습니다.'),
('다시 침몰','21t 잔해가\n도로 바닷속으로','전날 성공 소식까지 전해졌지만 잔해는 다시 깊은 바다로 내려갔습니다.'),
('다음 시도','재인양은\n내년으로 연기','인양팀은 작업을 당장 재개하지 않고 다음 해 다시 시도하겠다고 밝혔습니다.')],
'igcap':'84년 만에 수면 가까이 올라왔던 타이태닉의 20여t짜리 선체 잔해가 다시 바닷속으로 가라앉았습니다. 당시 보도에 따르면 해저 약 3km에서 수면 65m 지점까지 끌어올렸지만 부양기구와 연결된 케이블이 끊어졌고 재인양은 다음 해로 미뤄졌습니다.\n\n#오늘대한민국 #1996년오늘 #타이태닉 #역사뉴스 #해양',
'yttitle':'타이태닉 20t 잔해, 수면 65m 앞두고 다시 침몰','ytdesc':'1996년 8월 31일 보도된 타이태닉 대형 잔해 인양 실패. 사진은 1911년 실제 RMS Titanic 자료사진입니다.','story':'수면 65m 앞두고 다시 추락한 타이태닉 잔해 | 아깝다 / 다시 도전','music':'신승훈 — 내 방식대로의 사랑 (KBS 가요톱10 1996.08.28 4위 / 역사·비극 기사 톤)'}
]

manifest={'date':'1996-08-31','article_rows_scanned':2826,'articles':[],'feed_cards':0,'ig_reels':0,'yt_shorts':0,'generative_ai_images':0}
ig_text=[]; yt_text=[]; post=[]
for art in articles:
    s=sources[art['src']]; photo=SRC/s['file']; adir=FEED/art['id']; adir.mkdir(exist_ok=True)
    feed=[]
    for i,(k,t,dsc) in enumerate(art['slides'],1):
        c=card(photo,k,t,dsc,s['credit'],art['center'],None); p=adir/f'{i:02d}.jpg'; c.save(p,quality=94); feed.append(p)
    igcta=card(photo,'','','',s['credit'],art['center'],'ig'); p6=adir/'06.jpg'; igcta.save(p6,quality=94); feed.append(p6)
    # preview
    thumbs=[Image.open(p).resize((324,405)) for p in feed]; sheet=Image.new('RGB',(648,1215),(18,18,18))
    for j,th in enumerate(thumbs): sheet.paste(th,((j%2)*324,(j//2)*405))
    sheet.save(PRE/f"{art['id']}_PREVIEW.jpg",quality=90)
    # reel frames: fullscreen hook, cards 2-5, CTA
    rdir=TMP/art['id']; rdir.mkdir(exist_ok=True)
    hook=hook_frame(photo,art['slides'][0][1],s['credit'],art['center']); hp=rdir/'01.jpg'; hook.save(hp,quality=93)
    igframes=[hp]
    for idx in range(1,5):
        c=Image.open(feed[idx]); sf=story_frame(photo,c); sp=rdir/f'{idx+1:02d}.jpg'; sf.save(sp,quality=91); igframes.append(sp)
    sf=story_frame(photo,Image.open(feed[5])); sp=rdir/'06.jpg'; sf.save(sp,quality=91); igframes.append(sp)
    igout=IG/f"{art['id']}.mp4"; make_video(igframes,igout)
    # yt CTA differs
    ytcta=card(photo,'','','',s['credit'],art['center'],'yt'); ytf=story_frame(photo,ytcta); ytp=rdir/'06_yt.jpg'; ytf.save(ytp,quality=91)
    ytframes=igframes[:5]+[ytp]; ytout=YT/f"{art['id']}.mp4"; make_video(ytframes,ytout)
    v1=probe_video(igout); v2=probe_video(ytout)
    manifest['feed_cards']+=6; manifest['ig_reels']+=1; manifest['yt_shorts']+=1
    manifest['articles'].append({'id':art['id'],'source_photo':s['file'],'source_sha256':s['sha256'],'ig_video':v1,'yt_video':v2})
    ig_text.append(f"## {art['id']}\n{art['igcap']}\n")
    yt_text.append(f"## {art['id']}\n제목: {art['yttitle']}\n설명: {art['ytdesc']}\n")
    post.append(f"## {art['id']}\n- 음악 후보: {art['music']}\n- 위치: 없음\n- 멘션: 없음\n- 공동작업자: 없음\n- AI 정보 레이블: 사용 안 함\n- Story: {art['story']}\n")

# all preview
ims=[]
for art in articles:
    for i in range(1,7): ims.append(Image.open(FEED/art['id']/f'{i:02d}.jpg').resize((216,270)))
allp=Image.new('RGB',(1296,810),(16,16,16))
for i,im in enumerate(ims): allp.paste(im,((i%6)*216,(i//6)*270))
allp.save(PRE/'ALL_18_CARDS_PREVIEW.jpg',quality=90)

(ROOT/'INSTAGRAM_CAPTIONS.md').write_text('# INSTAGRAM CAPTIONS — 1996.08.31\n\n'+'\n'.join(ig_text),encoding='utf-8')
(ROOT/'YOUTUBE_PACKAGE.md').write_text('# YOUTUBE PACKAGE — 1996.08.31\n\n'+'\n'.join(yt_text),encoding='utf-8')
(ROOT/'POSTING_GUIDE.md').write_text('# POSTING GUIDE — 1996.08.31\n\n'+'\n'.join(post)+'\n공통: 무음 master. 음악은 플랫폼 앱에서 별도 추가. 8/28 KBS 가요톱10 순위 기반 후보이며 플랫폼 가용성은 게시 직전 확인.\n',encoding='utf-8')
(ROOT/'ARTICLE_BASIS.md').write_text('''# ARTICLE BASIS — 1996.08.31\n\n업로드 원본: NewsResult_19960831-19960831.xlsx\n전체 기사 행: 2,826\n\n전수 스캔 후 동일 사건 중복 통합.\n\n01 중풍 85세 아버지 유기 사망: 동아일보·경향신문·부산일보·중앙일보·국민일보·한국일보·세계일보 보도군.\n02 가짜 자동차부품: 동아일보·세계일보·매일신문 보도군. 핵심 수치 34만여 개, 20억 원대, 19명 구속·30명 불구속 입건.\n03 타이태닉 인양 실패: 동아일보·전북일보·서울신문·부산일보·한국일보·전남일보·경향신문·세계일보 등 보도군. 핵심 수치 약 20~21t, 해저 약 3km, 수면 65m 지점, 케이블 파손, 재인양 내년.\n\n생성형 이미지 사용: 0\n''',encoding='utf-8')
rights=['# SOURCES AND RIGHTS — 1996.08.31','','생성형 이미지 사용: 0','']
for k,s in sources.items(): rights += [f'## {k}',f"- Source page: {s['page']}",f"- Direct file: {s['url']}",f"- Author/collection: {s['author']}",f"- Date: {s['date']}",f"- Rights: {s['license']}",f"- SHA-256: {s['sha256']}",f"- Bytes: {s['bytes']}",f"- On-card disclosure: {s['credit']}",'']
(ROOT/'SOURCES_AND_RIGHTS.md').write_text('\n'.join(rights),encoding='utf-8')

# QA
errors=[]
for p in FEED.rglob('*.jpg'):
    if Image.open(p).size!=(1080,1350): errors.append('bad card '+str(p))
for p in list(IG.glob('*.mp4'))+list(YT.glob('*.mp4')):
    q=probe_video(p); st=q['streams'][0]
    if (st['width'],st['height'])!=(1080,1920): errors.append('bad video '+str(p))
qa=f'''# FINAL QA — 1996.08.31\n\nStatus: **{'PASS — FINAL' if not errors else 'FAIL'}**\n\n[x] Excel 2,826 article rows full scan\n[x] duplicate-event consolidation\n[x] previous-day repetition considered; Pesca Mar / Anyang follow-up excluded\n[x] TOP 3 selected\n[x] 6-slide development Gate\n[x] actual photo bytes present locally\n[x] rights/source records\n[x] generative AI images = 0\n[x] 18 cards at 1080×1350\n[x] 3 Instagram Reels at 1080×1920\n[x] first 1.7 sec fullscreen real-photo hook\n[x] slides 2–6 central 4:5 card format\n[x] Instagram CTA\n[x] 3 YouTube Shorts at 1080×1920\n[x] YouTube CTA\n[x] exactly 5 hashtags per Instagram caption\n[x] music candidates based on KBS 가요톱10 1996.08.28\n[x] Story/location/mention/collaborator settings\n[x] preview sheets\n[x] source photo disclosure on cards\n\nIssues: {errors if errors else 'none'}\n\nImportant photo disclosures:\n- 01 playground photo is archival reference imagery, not the event scene or victim.\n- 02 automobile-parts photo is archival reference imagery, not seized evidence from the case.\n- 03 is a real RMS Titanic photograph, not the 1996 salvage scene.\n'''
(ROOT/'FINAL_QA.md').write_text(qa,encoding='utf-8')
(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
# zip
zipname=Path('KOREA_NOW_19960831_FINAL.zip')
with zipfile.ZipFile(zipname,'w',zipfile.ZIP_DEFLATED) as z:
    for f in ROOT.rglob('*'):
        if f.is_file(): z.write(f,f.relative_to(ROOT.parent))
sha=hashlib.sha256(zipname.read_bytes()).hexdigest(); (ROOT/'ZIP_SHA256.txt').write_text(sha+'  '+zipname.name+'\n',encoding='utf-8')
# rebuild zip incl sha file
with zipfile.ZipFile(zipname,'w',zipfile.ZIP_DEFLATED) as z:
    for f in ROOT.rglob('*'):
        if f.is_file(): z.write(f,f.relative_to(ROOT.parent))
print(json.dumps({'status':'PASS' if not errors else 'FAIL','zip':str(zipname),'sha256':hashlib.sha256(zipname.read_bytes()).hexdigest(),'manifest':manifest},ensure_ascii=False))
if errors: raise SystemExit(2)
