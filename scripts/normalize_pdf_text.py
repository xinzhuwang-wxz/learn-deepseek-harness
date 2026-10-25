#!/usr/bin/env python3
"""Repair Chromium/Noto CJK compatibility-radical ToUnicode mappings.

Only text extraction maps change; page geometry, glyph IDs, streams, and visual
appearance remain untouched. Compatibility radicals such as U+2F8F are mapped
to their standard CJK equivalents so exact Chinese search/copy works.
Requires pypdf for this optional post-export quality correction.
"""
from pathlib import Path
import re,sys,unicodedata
from pypdf import PdfReader,PdfWriter
from pypdf.generic import DecodedStreamObject,NameObject

HEX=r'<([0-9A-Fa-f]+)>'

def normalize_target(value):
    try:text=bytes.fromhex(value).decode('utf-16-be')
    except (ValueError,UnicodeError):return value.upper()
    output=''.join(unicodedata.normalize('NFKC',ch) if 0x2F00<=ord(ch)<=0x2FDF or 0xF900<=ord(ch)<=0xFAFF else ch for ch in text)
    return output.encode('utf-16-be').hex().upper()

def bfchars(pairs):
    chunks=[]
    for i in range(0,len(pairs),100):
        batch=pairs[i:i+100]
        chunks.append(str(len(batch))+' beginbfchar\n'+'\n'.join('<'+a+'> <'+b+'>' for a,b in batch)+'\nendbfchar')
    return '\n'.join(chunks)

def rewrite_cmap(text):
    changed=0
    def char_block(match):
        nonlocal changed
        pairs=[]
        for a,b in re.findall(HEX+r'\s*'+HEX,match[1]):
            new=normalize_target(b);changed+=new!=b.upper();pairs.append((a,new))
        return bfchars(pairs)
    def range_block(match):
        nonlocal changed
        pairs=[]
        for m in re.finditer(HEX+r'\s*'+HEX+r'\s*(<([0-9A-Fa-f]+)>|\[([^\]]*)\])',match[1],re.S):
            start,end=int(m[1],16),int(m[2],16)
            if m[4]:
                base=int(m[4],16);width=len(m[4]);values=[f'{base+n:0{width}X}' for n in range(end-start+1)]
            else:values=re.findall(HEX,m[5])
            if len(values)!=end-start+1:raise ValueError('Unsupported CMap range')
            for n,b in enumerate(values):
                new=normalize_target(b);changed+=new!=b.upper();pairs.append((f'{start+n:0{len(m[1])}X}',new))
        return bfchars(pairs)
    result=re.sub(r'\d+\s+beginbfchar\s*(.*?)\s*endbfchar',char_block,text,flags=re.S)
    result=re.sub(r'\d+\s+beginbfrange\s*(.*?)\s*endbfrange',range_block,result,flags=re.S)
    return result,changed

def normalize(path):
    reader=PdfReader(path);writer=PdfWriter();writer.clone_document_from_reader(reader)
    seen=set();fixed=0;fonts=0
    for page in writer.pages:
        for fontref in page['/Resources'].get('/Font',{}).values():
            font=fontref.get_object();identity=(getattr(fontref,'idnum',None),getattr(fontref,'generation',None))
            if identity in seen:continue
            seen.add(identity)
            if '/ToUnicode' not in font:continue
            old=font['/ToUnicode'].get_object().get_data().decode('ascii')
            new,count=rewrite_cmap(old)
            if count:
                stream=DecodedStreamObject();stream.set_data(new.encode('ascii'))
                font[NameObject('/ToUnicode')]=writer._add_object(stream)
                fonts+=1;fixed+=count
    if fixed:
        temp=path.with_suffix('.normalized.tmp.pdf')
        with temp.open('wb') as f:writer.write(f)
        temp.replace(path)
    return {'normalized_mappings':fixed,'affected_fonts':fonts,'pages':len(reader.pages)}
if __name__=='__main__':
    import json
    print(json.dumps(normalize(Path(sys.argv[1])),indent=2))
