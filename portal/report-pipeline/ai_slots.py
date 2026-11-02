#!/usr/bin/env python3
"""분석 데이터(gen.pptx의 숫자·표·그래프 문구)를 근거로 AI(Foundry gpt-6-astra)가 보고서 문장만 작성.
서식(글꼴·굵기·크기·배치)은 건드리지 않는다. 근거 없는 숫자가 있으면 그 칸은 재작성 후에도 틀리면 초안으로 되돌린다.
usage: ai_slots.py slots-draft.json gen.pptx out-ai.json receipt.json"""
import sys, os, json, re, hashlib, urllib.request, urllib.parse, time
from pptx import Presentation
PROJECT = 'https://fd-ama-hermes-01.services.ai.azure.com/api/projects/PROJ-AMA-01'
MODEL = 'gpt-6-astra'
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def req(url, tok=None, payload=None, timeout=300):
    h = {'Accept': 'application/json'}
    if tok: h['Authorization'] = 'Bearer ' + tok
    else: h['Metadata'] = 'true'
    if payload is not None: h['Content-Type'] = 'application/json'
    try:
        r = OP.open(urllib.request.Request(url, data=payload, headers=h), timeout=timeout); return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'HTTP {e.code}: {e.read()[:400]!r}')
def token():
    ep = os.environ.get('IDENTITY_ENDPOINT')
    if ep:   # Container Apps 관리 ID
        q = ep + '?' + urllib.parse.urlencode({'resource': 'https://ai.azure.com', 'api-version': '2019-08-01'})
        r = OP.open(urllib.request.Request(q, headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=20)
        return json.loads(r.read())['access_token']
    return req('http://169.254.169.254/metadata/identity/oauth2/token?' + urllib.parse.urlencode({'api-version': '2018-02-01', 'resource': 'https://ai.azure.com'}))['access_token']
def facts_text(path):
    out = []
    def walk(shs):
        for sh in shs:
            if sh.shape_type == 6: walk(sh.shapes)
            elif sh.has_text_frame: out.append(sh.text_frame.text)
            elif sh.shape_type == 19:
                for r in sh.table.rows: out.append(' | '.join(c.text_frame.text for c in r.cells))
    for i, s in enumerate(Presentation(path).slides): out.append(f'[슬라이드 {i+1}]'); walk(s.shapes)
    return '\n'.join(out)
def nums(t): return {n.replace(',', '').rstrip('.') for n in re.findall(r'\d[\d,]*\.?\d*', t)}
def check(text, allowed):
    return sorted(n for n in nums(text) if n not in allowed and not (len(n) == 1))
RULES = os.environ.get('REPORT_RULES', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'WRITING-RULES.md'))
STYLE = open(RULES, encoding='utf-8').read()
def ask(tok, facts, items, feedback=''):
    body = {'FACTS': facts, 'SLOTS': {k: {'draft': v, 'max': int(len(v) * 1.1) + 12} for k, v in items.items()}}
    prompt = STYLE + '\n\n아래 JSON의 SLOTS 각 항목을 다시 써서, 키는 그대로 두고 값만 새 문장으로 채운 JSON 객체 하나만 출력하세요(설명·코드블록 금지).\n' + (feedback + '\n' if feedback else '') + json.dumps(body, ensure_ascii=False)
    pl = {'model': MODEL, 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}], 'max_output_tokens': 16000, 'store': False, 'stream': False, 'tools': [], 'tool_choice': 'none'}
    r = req(PROJECT + '/openai/v1/responses', tok, json.dumps(pl, ensure_ascii=False).encode(), timeout=540)
    txt = ''.join(c.get('text', '') for o in r.get('output', []) if o.get('type') == 'message' for c in o.get('content', []))
    m = re.search(r'\{.*\}', txt, re.S); return json.loads(m.group(0)), r, hashlib.sha256(prompt.encode()).hexdigest()
def write_slots(draft, facts, log=print):
    import socket
    host = PROJECT.split('/')[2]
    try: socket.create_connection((socket.getaddrinfo(host, 443, socket.AF_INET)[0][4][0], 443), timeout=6).close()
    except Exception as e: raise RuntimeError('AI endpoint unreachable: ' + type(e).__name__)
    allowed = nums(facts); tok = token(); out, receipt = {}, {'model': MODEL, 'rounds': []}
    pending = dict(draft); fb = ''
    for rnd in range(3):
        res, r, dg = ask(tok, facts, pending, fb)
        receipt['rounds'].append({'response_id': r.get('id'), 'model': r.get('model'), 'prompt_sha256': dg, 'usage': r.get('usage'), 'asked': len(pending), 'rules_sha256': hashlib.sha256(STYLE.encode()).hexdigest()})
        bad = {}
        for k in pending:
            t = (res.get(k) or '').strip(); lim = int(len(pending[k]) * 1.1) + 12
            v = check(t, allowed)
            if not t or len(t) > lim * 1.15 or v: bad[k] = (v, len(t), lim)
            else: out[k] = t
        if not bad: break
        pending = {k: draft[k] for k in bad}
        fb = '이전 시도에서 근거 없는 숫자 또는 글자 수 초과가 있었습니다: ' + json.dumps({k: {'근거없는숫자': v[0], '길이': v[1], 'max': v[2]} for k, v in bad.items()}, ensure_ascii=False) + ' FACTS에 있는 숫자만 쓰고 한도를 지키세요.'
        time.sleep(3)
    receipt['fallback_to_draft'] = sorted(set(draft) - set(out))
    for k in receipt['fallback_to_draft']: out[k] = draft[k]
    return out, receipt

if __name__ == '__main__':
    draft = json.load(open(sys.argv[1], encoding='utf-8')); facts = facts_text(sys.argv[2])
    out, receipt = write_slots(draft, facts)
    json.dump(out, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, indent=1); json.dump(receipt, open(sys.argv[4], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('ai slots', len(out) - len(receipt['fallback_to_draft']), 'fallback', len(receipt['fallback_to_draft']), 'rounds', len(receipt['rounds']))
