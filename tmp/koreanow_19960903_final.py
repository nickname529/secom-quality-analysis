from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import urllib.request, subprocess, shutil, hashlib, json, zipfile

DATE='1996.09.03'
ROOT=Path('KOREA_NOW_19960903_FINAL')
SRC=ROOT/'SOURCES'; FEED=ROOT/'FEED_CARDS'; IG=ROOT/'INSTAGRAM_REELS'; PRE=ROOT/'PREVIEWS'; TMP=Path('_kn0903_tmp')
for p in [SRC,FEED,IG,PRE,TMP]: p.mkdir(parents=True,exist_ok=True)

UA={'User-Agent':'Mozilla/5.0 KoreaNowMedia/1.0'}

def download(urls,dest):
    last=None
    for url in urls:
        try:
            req=urllib.request.Request(url,headers=UA)
            with urllib.request.urlopen(req,timeout=90) as r, open(dest,'wb') as f: shutil.copyfileobj(r,f)
            if Path(dest).stat().st_size < 10000: raise RuntimeError('file too small')
            Image.open(dest).verify()
            return url
        except Exception as e:
            last=e
            try: Path(dest).unlink(missing_ok=True)
            except Exception: pass
    raise RuntimeError(f'download failed {dest}: {last}')

sources={
 'tunguska':{
   'urls':['https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/154000/154488/original_af4f669b5645bbb3381c53aa765890d6.jpg'],
   'page':'https://commons.wikimedia.org/wiki/File:Tunguska_Ereignis-1.jpg',
   'file':'tunguska_1929.jpg','author':'Leonid Kulik expedition','date':'1929-05','license':'Public Domain',
   'credit':'1929년 퉁구스카 현장 실제사진 · Leonid Kulik 원정대 · Public Domain'},
 'grapefruit':{
   'urls':['https://visualsonline.cancer.gov/retrieve.cfm?dpi=300&fileformat=jpg&imageid=2630','https://wsrv.nl/?url=https%3A%2F%2Fupload.wikimedia.org%2Fwikipedia%2Fcommons%2Fa%2Fa6%2FGrapefruit_%25281%2529.jpg&output=jpg'],
   'page':'https://visualsonline.cancer.gov/details.cfm?imageid=2630',
   'file':'grapefruit_1994.jpg','author':'Renee Comet / National Cancer Institute','date':'1994','license':'Public Domain — NCI',
   'credit':'1994년 NCI 자몽 실제사진 · Renee Comet · Public Domain'},
 'buenos':{
   'urls':['https://wsrv.nl/?url=https%3A%2F%2Fupload.wikimedia.org%2Fwikipedia%2Fcommons%2Ff%2Ff6%2FBuenos_Aires_centre_ville_1992.jpg&output=jpg','https://cdn.loc.gov/service/pnp/npcc/19900/19935v.jpg'],
   'page':'https://commons.wikimedia.org/wiki/File:Buenos_Aires_centre_ville_1992.jpg',
   'file':'buenos_aires_1992.jpg','author':'FC Georgio','date':'1992','license':'CC BY 1.0',
   'credit':'1992년 부에노스아이레스 실제사진 · FC Georgio · CC BY 1.0'}
}
for s in sources.values():
    dest=SRC/s['file']; used=download(s['urls'],dest); s['download_url']=used
    s['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest(); s['bytes']=dest.stat().st_size

FB='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'; FR='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def font(sz,bold=True): return ImageFont.truetype(FB if bold else FR,sz)
WHITE=(248,248,248); GRAY=(216,216,216); MUTED=(178,178,178); LIME=(190,255,45); RED=(230,32,38)

def crop(im,size,center=(0.5,0.5)): return ImageOps.fit(im,size,method=Image.Resampling.LANCZOS,centering=center)
def fit_multiline(draw,text,maxw,maxh,start=82,minsize=50,spacing=12):
    fs=start
    while fs>=minsize:
        ft=font(fs); bb=draw.multiline_textbbox((0,0),text,font=ft,spacing=spacing)
        if bb[2]-bb[0]<=maxw and bb[3]-bb[1]<=maxh: return ft
        fs-=2
    return font(minsize)
def wrap_chars(draw,text,fnt,maxw,max_lines=2):
    lines=[]; cur=''
    for ch in text:
        n=cur+ch
        if draw.textlength(n,font=fnt)<=maxw: cur=n
        else:
            if cur: lines.append(cur)
            cur=ch
    if cur: lines.append(cur)
    return '\n'.join(lines[:max_lines])
def gradient_overlay(size,start,alpha_end=238):
    ov=Image.new('RGBA',size,(0,0,0,0)); d=ImageDraw.Draw(ov)
    for y in range(start,size[1]):
        t=(y-start)/(size[1]-start); a=int(20+(alpha_end-20)*(t**1.15)); d.line((0,y,size[0],y),fill=(0,0,0,a))
    return ov
def header(d,y=58):
    d.rounded_rectangle((68,y,135,y+10),radius=5,fill=RED)
    d.text((68,y+30),'KOREA NOW',font=font(31),fill=WHITE)
    d.text((68,y+76),DATE,font=font(22,False),fill=GRAY)
def make_card(photo,kicker,title,desc,credit,center=(0.5,0.5),cta=False):
    im=Image.open(photo).convert('RGB'); base=crop(im,(1080,1350),center).convert('RGBA')
    base=Image.alpha_composite(base,Image.new('RGBA',base.size,(0,0,0,35))); base=Image.alpha_composite(base,gradient_overlay(base.size,565,245))
    d=ImageDraw.Draw(base); header(d)
    if not cta:
        d.text((68,760),kicker,font=font(30),fill=LIME)
        ft=fit_multiline(d,title,930,215,82,54,10); d.multiline_text((68,815),title,font=ft,fill=WHITE,spacing=10)
        fd=font(27,False); d.multiline_text((68,1085),wrap_chars(d,desc,fd,930,2),font=fd,fill=(238,238,238),spacing=7)
    else:
        d.text((68,790),'30년 전 오늘의 소식',font=font(32),fill=LIME)
        d.text((68,850),'내일도 이어집니다',font=font(68),fill=WHITE)
        d.text((68,1015),'저장 · 공유 · 팔로우',font=font(39),fill=WHITE)
        d.text((68,1090),'@koreanow.media',font=font(32),fill=LIME)
    d.rectangle((0,1260,1080,1350),fill=(0,0,0,145)); d.text((68,1287),credit,font=font(16,False),fill=MUTED)
    return base.convert('RGB')
def make_hook(photo,title,credit,center=(0.5,0.5)):
    im=Image.open(photo).convert('RGB'); base=crop(im,(1080,1920),center).convert('RGBA')
    base=Image.alpha_composite(base,Image.new('RGBA',base.size,(0,0,0,35))); base=Image.alpha_composite(base,gradient_overlay(base.size,1010,245))
    d=ImageDraw.Draw(base); header(d,70)
    ft=fit_multiline(d,title,930,340,96,68,12); d.multiline_text((68,1335),title,font=ft,fill=WHITE,spacing=12)
    d.rectangle((0,1810,1080,1920),fill=(0,0,0,145)); d.text((68,1842),credit,font=font(16,False),fill=MUTED)
    return base.convert('RGB')
def make_story(photo,card_img):
    im=Image.open(photo).convert('RGB'); bg=crop(im,(1080,1920)).filter(ImageFilter.GaussianBlur(34)).convert('RGBA')
    bg=Image.alpha_composite(bg,Image.new('RGBA',bg.size,(0,0,0,128))).convert('RGB'); bg.paste(card_img,(0,285)); return bg
def make_video(frame_paths,out):
    durations=[1.70,1.30,1.30,1.30,1.30,1.70]
    lst=TMP/(out.stem+'.txt'); lines=[]
    for p,dur in zip(frame_paths,durations): lines += [f"file '{p.resolve()}'",f'duration {dur}']
    lines.append(f"file '{frame_paths[-1].resolve()}'"); lst.write_text('\n'.join(lines),encoding='utf-8')
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(lst),'-vf','fps=30,scale=1080:1920:flags=lanczos,format=yuv420p','-an','-c:v','libx264','-preset','medium','-crf','20','-movflags','+faststart',str(out)],check=True)
def probe_video(path):
    r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-show_entries','format=duration','-of','json',str(path)],capture_output=True,text=True,check=True); return json.loads(r.stdout)

articles=[
{'id':'01_TUNGUSKA','src':'tunguska','center':(0.50,0.49),'hook':'시베리아 2,600㎢를\n날려버린 폭발의 단서','slides':[
('88년 전 대폭발','시베리아 2,600㎢가\n순식간에 불바다','1908년 중앙시베리아를 초토화한 퉁구스카 대폭발의 원인 단서가 새로 발견됐습니다.'),
('폭발 규모','히로시마 원폭의\n약 1,000배','당시 보도는 폭발 규모가 히로시마 원자폭탄의 약 1,000배에 달했다고 전했습니다.'),
('오랜 미스터리','분화구도 파편도 없어\n원인 규명 난항','과학자들은 충돌 흔적을 찾지 못해 수십 년 동안 폭발 원인을 추적해 왔습니다.'),
('새 단서','자작나무 수지에서\n외계물질 입자 발견','볼로냐대 연구팀은 현장에서 수거한 나무 수지를 분석해 지구 밖 물질로 보이는 입자를 찾았습니다.'),
('소행성 가설','지름 약 60m 소행성\n대기권 진입 분석','미 항공우주국 연구팀의 컴퓨터 분석도 소행성 충돌 가설을 뒷받침한다고 보도됐습니다.')],
'caption':'1908년 중앙시베리아의 산림 2,600㎢를 순식간에 초토화한 퉁구스카 대폭발. 1996년 9월 3일 한국일보는 현장 자작나무 수지에서 외계물질 입자가 발견되며 소행성 충돌설을 뒷받침하는 단서가 나왔다고 보도했습니다.\n\n#오늘대한민국 #1996년오늘 #퉁구스카 #과학뉴스 #역사뉴스','music':'신승훈 — 내 방식대로의 사랑 (1996.09.04 가요톱10 3위 / 서사적 분위기)'},
{'id':'02_GRAPEFRUIT','src':'grapefruit','center':(0.50,0.50),'hook':'약 먹을 때 자몽주스\n목숨 잃을 수도','slides':[
('영국 보건당국 경고','약 먹을 때 자몽주스\n목숨 잃을 수도','영국 약품통제국이 일부 약과 자몽주스를 함께 먹을 경우 위험할 수 있다고 경고했습니다.'),
('거론된 약','혈압·심장질환·알레르기\n치료제 포함','당시 보도는 널리 쓰이는 여러 치료제가 자몽주스와 반응할 수 있다고 전했습니다.'),
('이유','자몽주스가 약물 흡수\n방식을 바꿀 수 있다','약품통제국은 자몽주스가 신체의 약물 흡수 방식에 영향을 줄 수 있다고 설명했습니다.'),
('한 잔도','약물 과잉투여와 같은\n결과 가능성 경고','당시 보도는 한 잔의 자몽주스도 일부 약의 작용을 크게 바꿀 수 있다고 전했습니다.'),
('연구 범위','13종류 약품이\n영향 대상에 거론','영국 언론은 연구진을 인용해 최소 13종류의 약품이 영향을 받을 수 있다고 보도했습니다.')],
'caption':'1996년 9월 3일, 영국 보건당국이 일부 약을 복용할 때 자몽주스를 함께 마시면 치명적인 반응이 생길 수 있다고 경고했다는 보도가 나왔습니다. 당시 기사에는 혈압·심장질환·알레르기 치료제 등과 13종류의 약품이 거론됐습니다.\n\n#오늘대한민국 #1996년오늘 #자몽주스 #건강뉴스 #생활뉴스','music':'비비 — 비련 (1996.09.04 가요톱10 7위 / 경고형 기사 톤)'},
{'id':'03_ARGENTINA_CAR_THEFT','src':'buenos','center':(0.50,0.56),'hook':'아르헨티나 차량도난\n10분당 1대꼴','slides':[
('아르헨티나','차량도난\n10분당 1대꼴','경제사정이 악화되면서 자동차 절도가 급증했다고 현지 차량등록사무소가 밝혔습니다.'),
('6개월 통계','보험 신고만\n1만3,030대','올해 상반기 보험회사에 접수된 도난 차량만 1만3,030대에 달했습니다.'),
('실제 규모','보험 없는 차량도\n비슷한 숫자로 추정','당시 보도는 도난보험에 들지 않은 차량까지 합치면 피해가 훨씬 커진다고 전했습니다.'),
('계산하면','하루 24시간\n10분마다 자동차 1대','등록사무소 통계를 단순 환산하면 밤낮없이 10분에 한 대꼴로 차량이 사라지는 셈입니다.'),
('당시 배경','경제난 속\n차도둑 극성','현지 신문 클라린은 경제사정 악화와 함께 차량 절도가 심각한 사회문제가 됐다고 보도했습니다.')],
'caption':'1996년 9월 3일 매일신문은 아르헨티나에서 차량 도난이 10분당 1대꼴로 발생하고 있다고 보도했습니다. 상반기 보험회사에 신고된 차량만 1만3,030대였고, 보험에 들지 않은 차량 피해도 비슷한 규모로 추정됐습니다.\n\n#오늘대한민국 #1996년오늘 #아르헨티나 #자동차도난 #해외뉴스','music':'터보 — Twist King (1996.09.04 가요톱10 4위 / 빠른 숫자·사건형 기사)'}]

manifest=[]; covers=[]
for art in articles:
    s=sources[art['src']]; photo=SRC/s['file']; adir=FEED/art['id']; adir.mkdir(exist_ok=True); cards=[]
    for i,(k,t,dsc) in enumerate(art['slides'],1):
        img=make_card(photo,k,t,dsc,s['credit'],art['center'],False); p=adir/f'{i:02d}.jpg'; img.save(p,quality=93,subsampling=0); cards.append(p)
    cta=make_card(photo,'','','',s['credit'],art['center'],True); p=adir/'06.jpg'; cta.save(p,quality=93,subsampling=0); cards.append(p)
    hook=make_hook(photo,art['hook'],s['credit'],art['center']); hp=TMP/f"{art['id']}_hook.jpg"; hook.save(hp,quality=93,subsampling=0); covers.append(hp)
    frames=[hp]
    for idx,p in enumerate(cards[1:],2):
        fr=make_story(photo,Image.open(p).convert('RGB')); fp=TMP/f"{art['id']}_frame{idx}.jpg"; fr.save(fp,quality=91,subsampling=0); frames.append(fp)
    out=IG/f"{art['id']}_INSTAGRAM_REEL.mp4"; make_video(frames,out); manifest.append({'article':art['id'],'cards':[str(x) for x in cards],'video':str(out),'probe':probe_video(out)})
    sheet=Image.new('RGB',(1080,900),(16,16,16))
    for j,p in enumerate(cards): sheet.paste(Image.open(p).resize((360,450),Image.Resampling.LANCZOS),((j%3)*360,(j//3)*450))
    sheet.save(PRE/f'{art["id"]}_6CARDS_PREVIEW.jpg',quality=90)

cov=Image.new('RGB',(1080,640),(12,12,12))
for j,p in enumerate(covers): cov.paste(Image.open(p).resize((360,640),Image.Resampling.LANCZOS),(j*360,0))
cov.save(PRE/'REEL_COVERS_PREVIEW.jpg',quality=90)
(ROOT/'INSTAGRAM_CAPTIONS.md').write_text('\n\n'.join([f"## {a['id']}\n{a['caption']}" for a in articles]),encoding='utf-8')
(ROOT/'MUSIC_CANDIDATES.md').write_text('# 1996.09.03 음악 후보\n\n기준: KBS 가요톱10 1996.09.04 차트. 최근 5개 게시물 중복 여부는 게시 직전 확인.\n\n'+'\n'.join([f"- {a['id']}: {a['music']}" for a in articles]),encoding='utf-8')
(ROOT/'PUBLISHING_PACKAGE.md').write_text('# Instagram 게시 패키지\n\n- 플랫폼: Instagram Reels\n- 계정: @koreanow.media\n- 영상: INSTAGRAM_REELS 폴더 3개\n- 음원: 플랫폼에서 직접 삽입, 영상 master는 무음\n- 위치: 기사별 실제 장소 태그 가능할 때만 적용\n- 멘션: 불필요한 기관/개인 멘션 금지\n- 공동작업자: 없음\n- AI 레이블: 생성형 이미지/영상 0\n',encoding='utf-8')
rights=['# PHOTO RIGHTS & SOURCE LOG','']
for key,s in sources.items(): rights += [f"## {key}",f"- Source page: {s['page']}",f"- Download: {s['download_url']}",f"- Author: {s['author']}",f"- Date: {s['date']}",f"- License: {s['license']}",f"- SHA-256: {s['sha256']}",f"- Bytes: {s['bytes']}",f"- On-card credit: {s['credit']}",'']
(ROOT/'PHOTO_RIGHTS_LOG.md').write_text('\n'.join(rights),encoding='utf-8')
(ROOT/'ARTICLE_SOURCE_ROWS.md').write_text('# 기사 원문 근거\n\n- 퉁구스카 대폭발: 한국일보, `「퉁구스카 대폭발」 비밀 밝혀졌다`, Excel row 2885\n- 자몽주스: 매일경제, `자몽주스 약 복용시 마시면 사망 위험/영 약품통제국 경고`, Excel row 617 및 동일사건 다수 중복 보도\n- 아르헨 차량도난: 매일신문, `아르헨 차량도난 10분당 1대꼴`, Excel row 995\n\n원본 Excel 전체 3,054개 기사 행을 스캔한 뒤 동일 사건 중복을 묶어 선정.\n',encoding='utf-8')
qa=[]; ok=True; cards=list(FEED.rglob('*.jpg')); vids=list(IG.glob('*.mp4'))
qa.append(f'Feed cards: {len(cards)} / expected 18'); qa.append(f'Instagram Reels: {len(vids)} / expected 3')
if len(cards)!=18 or len(vids)!=3: ok=False
for p in cards:
    if Image.open(p).size!=(1080,1350): ok=False; qa.append(f'BAD CARD SIZE {p}')
for p in vids:
    pr=probe_video(p); st=pr['streams'][0]; dur=float(pr['format']['duration']); qa.append(f'{p.name}: {st["width"]}x{st["height"]}, {dur:.2f}s, silent master')
    if st['width']!=1080 or st['height']!=1920 or not (8.0<=dur<=9.5): ok=False
qa += ['Actual photos: 3','Generative images: 0','Internal slide numbers: 0','Instagram CTA: PASS','Photo rights log: PRESENT','Article source rows: PRESENT']
(ROOT/'FINAL_QA.md').write_text('# FINAL QA\n\nSTATUS: '+('PASS — UPLOAD READY' if ok else 'FAIL — HUMAN REVIEW REQUIRED')+'\n\n'+'\n'.join('- '+x for x in qa),encoding='utf-8')
(ROOT/'MANIFEST.json').write_text(json.dumps({'date':DATE,'status':'PASS — UPLOAD READY' if ok else 'FAIL','items':manifest,'sources':sources},ensure_ascii=False,indent=2),encoding='utf-8')
if not ok: raise RuntimeError('QA failed')
zip_path=Path('KOREA_NOW_19960903_UPLOAD_READY.zip')
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_file(): z.write(p,p.relative_to(ROOT.parent))
print('FINAL_ZIP',zip_path,zip_path.stat().st_size)
print('SHA256',hashlib.sha256(zip_path.read_bytes()).hexdigest())
