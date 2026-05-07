from __future__ import annotations
import csv, io, os, re
from collections import Counter
from typing import Dict, List, Tuple
import jieba, pdfplumber, requests
from bs4 import BeautifulSoup
from docx import Document
from flask import Flask, jsonify, render_template, request
from pypinyin import lazy_pinyin, Style
from werkzeug.utils import secure_filename

app=Flask(__name__); app.config['MAX_CONTENT_LENGTH']=16*1024*1024
BASE_DIR=os.path.dirname(os.path.abspath(__file__)); DATA_DIR=os.path.join(BASE_DIR,'data')
LEVEL_RANK={'第1級':1,'第1*級':2,'第2級':3,'第2*級':4,'第3級':5,'第3*級':6,'第4級':7,'第4*級':8,'第5級':9}
RANK_LEVEL={v:k for k,v in LEVEL_RANK.items()}
COMMON=set('的 了 是 在 有 和 跟 與 也 就 都 很 會 要 可以 不 沒 我 你 他 她 們 這 那 一 個 到 去 來 說 看 做'.split())
SYN={'學習':'讀書、練習、研習','老師':'教師、師長','學生':'學習者、同學','課文':'文章、文本','語法':'句型、文法','練習':'操練、反覆做','重要':'關鍵、主要','活動':'任務、課堂活動','文化':'風俗、生活方式','問題':'疑問、題目','知道':'了解、明白','喜歡':'喜愛','漂亮':'美麗','容易':'簡單','困難':'不容易、艱難','經驗':'經歷、體驗','討論':'商量、交流','介紹':'說明、推薦','理解':'了解、明白','影響':'作用、改變','環境':'周遭、生活空間'}

def load_vocab():
    vocab={}
    with open(os.path.join(DATA_DIR,'tbcl_vocab.csv'),encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            w=(r.get('word') or '').strip(); lv=(r.get('level') or '').strip()
            if w and lv: vocab[w]=lv
    char={}
    for w,lv in sorted(vocab.items(), key=lambda x:(LEVEL_RANK.get(x[1],99),len(x[0]))):
        if len(w)==1: char[w]=lv
    for w,lv in sorted(vocab.items(), key=lambda x:LEVEL_RANK.get(x[1],99)):
        for ch in w:
            if '\u4e00'<=ch<='\u9fff' and ch not in char: char[ch]=lv
    return vocab,char

def load_grammar():
    items=[]
    with open(os.path.join(DATA_DIR,'tbcl_grammar.csv'),encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            n=(r.get('name') or '').strip(); lv=(r.get('level') or '').strip(); pat=(r.get('pattern') or n).strip()
            if n and lv: items.append({'name':n,'level':lv,'pattern':pat})
    return items
VOCAB,CHAR=load_vocab(); GRAMMAR=load_grammar()
for w in VOCAB:
    if len(w)>=2:
        try: jieba.add_word(w)
        except Exception: pass

def rank(lv): return LEVEL_RANK.get(lv,99)
def file_text(fs):
    name=secure_filename(fs.filename or ''); ext=name.lower().rsplit('.',1)[-1] if '.' in name else ''; data=fs.read()
    if ext=='txt':
        for enc in ('utf-8','utf-8-sig','big5','cp950'):
            try: return data.decode(enc)
            except Exception: pass
        return data.decode('utf-8',errors='ignore')
    if ext=='pdf':
        parts=[]
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for p in pdf.pages: parts.append(p.extract_text() or '')
        return '\n'.join(parts)
    if ext=='docx':
        doc=Document(io.BytesIO(data)); return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError('目前支援 TXT、PDF、DOCX。')
def url_text(url):
    if not url.startswith(('http://','https://')): url='https://'+url
    r=requests.get(url,timeout=12,headers={'User-Agent':'Mozilla/5.0'}); r.raise_for_status(); soup=BeautifulSoup(r.text,'html.parser')
    for t in soup(['script','style','nav','footer','header','aside','form','button']): t.decompose()
    c=soup.find_all(['article','main','p','h1','h2','h3']); txt='\n'.join(x.get_text(' ',strip=True) for x in c)
    if len(txt)<100: txt=soup.get_text('\n',strip=True)
    return re.sub(r'\n{3,}','\n\n',txt).strip()
def sentences(text): return [s.strip() for s in re.split(r'(?<=[。！？!?])', re.sub(r'\s+',' ',text).strip()) if s.strip()]
def tokens(text): return [w.strip() for w in jieba.lcut(text) if w.strip() and not re.fullmatch(r'[\W_]+',w)]
def vocab_detect(text):
    counts=Counter(tokens(text)); found=[]; seen=set()
    for w,c in counts.most_common():
        if w in VOCAB and w not in seen:
            seen.add(w); found.append({'word':w,'level':VOCAB[w],'count':c,'synonyms':SYN.get(w,'可依語境補充'),'example':f'我覺得「{w}」和今天的課文內容有關。'})
    for w,lv in VOCAB.items():
        if len(w)>=2 and w not in seen and w in text:
            seen.add(w); found.append({'word':w,'level':lv,'count':text.count(w),'synonyms':SYN.get(w,'可依語境補充'),'example':f'請學生用「{w}」造一個完整句子。'})
        if len(found)>=180: break
    found.sort(key=lambda x:(rank(x['level']),-x['count'],x['word'])); return found
def gram_hit(text,pat):
    keys=[k.strip() for k in re.split(r'[|／/、,，\s]+',pat) if k.strip()] or [pat]
    return keys[0] in text if len(keys)==1 else all(k in text for k in keys)
def grammar_detect(text):
    found=[]; seen=set()
    for it in GRAMMAR:
        if it['name'] in seen: continue
        if gram_hit(text,it.get('pattern') or it['name']):
            seen.add(it['name']); found.append({'name':it['name'],'level':it['level'],'explanation':'文本中可能出現此語法形式，建議教師搭配原句說明其語意與語用功能。','example':f'請學生從課文中找出與「{it["name"]}」相關的句子。'})
    found.sort(key=lambda x:rank(x['level'])); return found[:40]
def infer_level(vocab,gram,sents):
    levels=[v['level'] for v in vocab]+[g['level'] for g in gram]
    if not levels: return '第2級'
    rs=sorted(rank(lv) for lv in levels if lv in LEVEL_RANK)
    if not rs: return '第2級'
    r=rs[min(len(rs)-1,int(len(rs)*.75))]
    avg=sum(len(s) for s in sents)/max(1,len(sents))
    if avg>35: r=min(9,r+1)
    if len(gram)>=5: r=min(9,r+1)
    return RANK_LEVEL.get(r,'第2級')
def new_words(vocab,level): return sorted([v for v in vocab if rank(v['level'])>=rank(level) and v['word'] not in COMMON], key=lambda x:(-rank(x['level']),-x['count'],x['word']))[:60]
def char_html(text):
    parts=[]
    for ch in text:
        if re.match(r'[，。！？、；：\s,.!?;:()\[\]（）「」『』《》]',ch): parts.append(ch); continue
        lv=CHAR.get(ch,'未收錄／待查'); py=' '.join(lazy_pinyin(ch,style=Style.TONE)) if '\u4e00'<=ch<='\u9fff' else ''
        parts.append(f'<span class="char" data-level="{lv}">{ch}<span class="tip"><b>{ch}｜{lv}</b>拼音：{py or "—"}<br>格式：&lt;span data-level="{lv}"&gt;{ch}&lt;/span&gt;</span></span>')
    return ''.join(parts)
def dialogue(text,vocab,gram):
    topic='、'.join(v['word'] for v in vocab[:3]) or '課文內容'; g=gram[0]['name'] if gram else '本課句型'
    return f'A：你覺得這篇課文主要在說什麼？\nB：我覺得它和「{topic}」有關。\nA：我們可以怎麼學這篇課文？\nB：可以先學生詞，再用「{g}」練習造句。'
def reading(text):
    ss=sentences(text)
    return ''.join(ss[:4]) if len(ss)>=3 else re.sub(r'\s+','',text)[:220]
def tasks(vocab,gram):
    vw='、'.join(v['word'] for v in vocab[:3]) or '本課生詞'; gp=gram[0]['name'] if gram else '本課句型'
    return [f'請學生找出課文中與「{vw}」相關的句子。',f'兩人一組，用「{gp}」設計一段短對話。','請學生用自己的生活經驗改寫課文中的一個情境。']
def exercises(vocab,gram):
    w1=vocab[0]['word'] if vocab else '本課生詞'; w2=vocab[1]['word'] if len(vocab)>1 else '課文'; gp=gram[0]['name'] if gram else '本課句型'
    return [{'type':'填空題','question':f'請用「{w1}」完成一個句子：我覺得＿＿＿很重要。','answer':w1},{'type':'造句題','question':f'請用「{w2}」造一個完整句子。','answer':'學生答案合理即可。'},{'type':'語法題','question':f'請找出或仿寫一個使用「{gp}」的句子。','answer':'依學生答案判斷。'},{'type':'閱讀理解','question':'本文主要在說明什麼？','answer':'能說出課文主題即可。'}]
def notes(level,vocab,gram):
    vt='、'.join(v['word'] for v in vocab[:6]) or '核心詞語'; gt='、'.join(g['name'] for g in gram[:4]) or '主要句型'
    return f'本課初步等級判定為「{level}」。生詞只列出等於或高於課文等級的詞，低於課文等級的詞不列入生詞。建議教學流程：一、先引導學生理解課文主題；二、講解生詞（如：{vt}）；三、說明語法點（如：{gt}）；四、進行任務活動；五、完成練習題。'
def analyze_text(text):
    text=text.strip(); ss=sentences(text); va=vocab_detect(text); gr=grammar_detect(text); lv=infer_level(va,gr,ss); nw=new_words(va,lv); rd=reading(text)
    return {'text':text,'lesson_level':lv,'sentence_count':len(ss),'all_vocab_count':len(va),'new_words_count':len(nw),'grammar_count':len(gr),'lesson_html':char_html(text),'reading_html':char_html(rd),'dialogue':dialogue(text,nw,gr),'new_words':nw,'grammar':gr,'reading':rd,'tasks':tasks(nw,gr),'exercises':exercises(nw,gr),'notes':notes(lv,nw,gr)}
@app.route('/')
def index(): return render_template('index.html')
@app.post('/analyze')
def analyze():
    try:
        typ=request.form.get('input_type','text'); text=''
        if typ=='text': text=request.form.get('text','')
        elif typ=='file':
            fs=request.files.get('file')
            if not fs: return jsonify({'error':'沒有收到檔案'}),400
            text=file_text(fs)
        elif typ=='url':
            url=request.form.get('url','')
            if not url: return jsonify({'error':'請輸入網址'}),400
            text=url_text(url)
        else: return jsonify({'error':'未知輸入方式'}),400
        if not text.strip(): return jsonify({'error':'沒有解析到文字內容'}),400
        return jsonify(analyze_text(text))
    except Exception as e: return jsonify({'error':str(e)}),500
@app.post('/local_assistant')
def local_assistant():
    data=request.get_json(force=True); req=data.get('request',''); ana=data.get('analysis') or {}; level=ana.get('lesson_level','待判斷'); nw=ana.get('new_words',[]); gr=ana.get('grammar',[]); ex=ana.get('exercises',[]); nt=ana.get('notes','')
    if '生詞' in req: ans='\n'.join([f'{v["word"]}（{v["level"]}）：{v.get("example","")}' for v in nw[:10]]) or '目前沒有偵測到符合規則的生詞。'
    elif '練習' in req: ans='\n\n'.join([f'{e["type"]}：{e["question"]}\n答案：{e["answer"]}' for e in ex])
    elif 'PPT' in req or '簡報' in req: ans='第1頁：課文主題與學習目標\n第2頁：課文內容與背景導入\n第3頁：生詞表與 TBCL 等級\n第4頁：生詞例句與近義詞\n第5頁：語法點講解\n第6頁：閱讀理解問題\n第7頁：課堂任務活動\n第8頁：練習題與課後作業'
    elif '備課' in req or '教案' in req: ans=nt
    else: ans=f'這份教材初步等級為「{level}」。建議先教生詞，再講語法點（'+('、'.join(g['name'] for g in gr[:5]) or '尚未偵測到明顯語法點')+'），最後做任務與練習。'
    return jsonify({'answer':ans})
if __name__=='__main__': app.run(debug=True,port=5000)
