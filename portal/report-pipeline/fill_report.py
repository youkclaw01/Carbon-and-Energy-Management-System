#!/usr/bin/env python3
"""AMA 종합 분석 보고서: 사용자 템플릿(글꼴·굵기·크기·배치 고정) + 분석 데이터 + AI 작성 문장.
usage: fill_report.py gen.pptx out.pptx [--ai slots.json]   |   fill_report.py gen.pptx --slots-out slots.json
gen.pptx = 포털이 최신 분석 데이터로 만든 보고서(숫자·표·그래프의 원천)."""
import sys, json, copy, re
from pptx import Presentation
import os
TPL = os.environ.get('REPORT_TEMPLATE', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Carbon-Energy-Management-Template.pptx'))

def walk(shapes):
    for sh in shapes:
        yield sh
        if sh.shape_type == 6:
            yield from walk(sh.shapes)

def paras(sh):
    return list(sh.text_frame.paragraphs) if sh.has_text_frame else []

def set_para(p, text):
    runs = p.runs
    if not runs:
        r = p.add_run(); r.text = text; return
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)

def occ_index(slide):
    """이름+등장 순번 -> 도형"""
    seen, out = {}, {}
    for sh in walk(slide.shapes):
        k = seen.get(sh.name, 0); seen[sh.name] = k + 1
        out[(sh.name, k)] = sh
    return out

# ── AI 슬롯 정의: 슬라이드 인덱스(0부터) 기준 ──
DETAIL = [4, 7, 9, 11, 13, 15]            # 설명·자료 장표(Text 도형 2문단)
GRAPH = [5, 6, 8, 10, 12, 14, 16, 17]     # 그래프 장표
def slots_of(gen):
    S = {}
    s = gen.slides
    for sh in walk(s[1].shapes):
        if sh.name == 'Opinion panel': S['s2.headline'] = sh.text_frame.text
    for sh in walk(s[2].shapes):
        m = re.fullmatch(r'ES(\d)', sh.name)
        if m: S[f's3.ES{m.group(1)}'] = [p for p in paras(sh) if p.text.strip()][-1].text
    items = [sh for sh in walk(s[3].shapes) if sh.name.startswith('Item ')]
    for i, sh in enumerate(items): S[f's4.item{i}'] = sh.text_frame.text
    for si in DETAIL:
        for sh in walk(s[si].shapes):
            if sh.name == 'Text':
                for pi, p in enumerate([p for p in paras(sh) if p.text.strip()]): S[f's{si+1}.text{pi}'] = p.text
    for si in GRAPH:
        notes = [sh for sh in walk(s[si].shapes) if sh.name.startswith('Note ')]
        for ni, sh in enumerate(notes):
            ps = [p for p in paras(sh) if p.text.strip()]; label = ps[0].text
            if label in ('핵심 지표', 'Key metrics'): continue
            S[f's{si+1}.note.{label}'] = ps[1].text if len(ps) > 1 else ''
    return S

def fill(gen_path, out_path, ai):
    gen = Presentation(gen_path); tpl = Presentation(TPL)
    assert len(gen.slides) == len(tpl.slides), (len(gen.slides), len(tpl.slides))
    for si, (gs, ts) in enumerate(zip(gen.slides, tpl.slides)):
        gmap, tmap = occ_index(gs), occ_index(ts)
        # (1) 데이터 복사: 같은 이름의 도형 -> 서식은 템플릿 것 그대로, 글자만 교체
        for key, tsh in tmap.items():
            name = key[0]
            if name in ('Footer', 'Nav left', 'Page', 'Title', 'Hero title', 'Text 5', 'Text 14') or name.startswith('TextBox'):
                continue                                   # 템플릿 고정 문구
            gsh = gmap.get(key)
            if gsh is None: continue
            if tsh.shape_type == 19 and gsh.shape_type == 19:
                for r, (tr, gr) in enumerate(zip(tsh.table.rows, gsh.table.rows)):
                    for c, (tc, gc) in enumerate(zip(tr.cells, gr.cells)):
                        ps = tc.text_frame.paragraphs; set_para(ps[0], gc.text_frame.text)
            elif tsh.has_text_frame and gsh.has_text_frame:
                tp = [p for p in paras(tsh) if p.text.strip()]; gp = [p for p in paras(gsh) if p.text.strip()]
                for p, g in zip(tp, gp): set_para(p, g.text)          # 빈 문단을 건너뛰고 내용 문단끼리 짝짓기
        # (2) 그래프 그림 교체
        tp = [sh for sh in walk(ts.shapes) if sh.shape_type == 13]; gp = [sh for sh in walk(gs.shapes) if sh.shape_type == 13]
        for a, b in zip(tp, gp):
            rid = a._element.blipFill.blip.rEmbed; ts.part.related_part(rid)._blob = b.image.blob
        # (3) Page 번호, 머리·바닥글은 템플릿 유지
    # (4) 표지·종합 의견 등 데이터 파생 문구
    tpl_s = tpl.slides
    # (5) AI 문장 반영
    if ai:
        ts = tpl.slides
        for sh in walk(ts[1].shapes):
            if sh.name == 'TextBox 19' and 's2.headline' in ai: set_para([p for p in paras(sh) if p.text.strip()][0], ai['s2.headline'])
        for sh in walk(ts[2].shapes):
            m = re.fullmatch(r'ES(\d)', sh.name)
            if m and f's3.ES{m.group(1)}' in ai: set_para([p for p in paras(sh) if p.text.strip()][-1], ai[f's3.ES{m.group(1)}'])
        items = [sh for sh in walk(ts[3].shapes) if sh.name.startswith('Item ')]
        for i, sh in enumerate(items):
            if f's4.item{i}' in ai: set_para([p for p in paras(sh) if p.text.strip()][0], ai[f's4.item{i}'])
        for si in DETAIL:
            for sh in walk(ts[si].shapes):
                if sh.name == 'Text':
                    for pi, p in enumerate([p for p in paras(sh) if p.text.strip()]):
                        k = f's{si+1}.text{pi}'
                        if k in ai: set_para(p, ai[k])
        for si in GRAPH:
            notes = [sh for sh in walk(ts[si].shapes) if sh.name.startswith('Note ')]
            gnotes = [sh for sh in walk(gen.slides[si].shapes) if sh.name.startswith('Note ')]
            for sh, gsh in zip(notes, gnotes):
                ps = [p for p in paras(sh) if p.text.strip()]; label = [p for p in paras(gsh) if p.text.strip()][0].text
                set_para(ps[0], label)                     # 라벨은 컨설팅 용어(템플릿 서식 유지)
                k = f's{si+1}.note.{label}'
                if k in ai and len(ps) > 1: set_para(ps[1], ai[k])
    else:
        for si in GRAPH:
            for sh, gsh in zip([s for s in walk(tpl.slides[si].shapes) if s.name.startswith('Note ')], [s for s in walk(gen.slides[si].shapes) if s.name.startswith('Note ')]):
                for p, g in zip([p for p in paras(sh) if p.text.strip()], [p for p in paras(gsh) if p.text.strip()]): set_para(p, g.text)
    # 발표 노트(내용 문단 모음)
    for i, sl in enumerate(tpl.slides):
        if i == 0: continue
        ts = []
        for sh in walk(sl.shapes):
            if sh.has_text_frame and sh.name not in ('Footer', 'Nav left', 'Page', 'Big number', 'Num 1', 'Num 2', 'Num 3', 'Num 4', 'Tag'):
                t = ' '.join(sh.text_frame.text.split())
                if t and not (len(t) <= 3 and t.isdigit()): ts.append(t)
        if ts: sl.notes_slide.notes_text_frame.text = ('발표 노트: ' + ' / '.join(ts))[:3800]
    tpl.save(out_path)

if __name__ == '__main__':
    a = sys.argv[1:]
    gen = Presentation(a[0])
    if '--slots-out' in a:
        json.dump(slots_of(gen), open(a[a.index('--slots-out') + 1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1); sys.exit()
    ai = json.load(open(a[a.index('--ai') + 1], encoding='utf-8')) if '--ai' in a else None
    fill(a[0], a[1], ai); print('filled', a[1])
