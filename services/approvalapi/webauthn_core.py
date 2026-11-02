"""WebAuthn(패스키·지문) 서버 측 검증 — 외부 라이브러리 없이 CBOR 최소 해석 + cryptography(ES256). 증명(attestation)은 none만 받고, 사용자 확인(UV: 지문·PIN)이 켜진 인증만 인정한다."""
import base64, hashlib, json, os, struct
class WaError(Exception):
    def __init__(self, status, code, msg=''): self.status, self.code, self.msg = status, code, msg
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def unb64u(s):
    try: return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
    except Exception: raise WaError(400, 'BAD_ENCODING', 'base64url 형식이 올바르지 않습니다.')
def cbor_decode(b, i=0, depth=0):
    """필요한 부분집합(정수·바이트열·문자열·배열·맵)만 해석. 깊이·길이 제한으로 악성 입력을 막는다."""
    if depth > 8 or i >= len(b): raise WaError(400, 'BAD_CBOR', 'CBOR이 올바르지 않습니다.')
    ib = b[i]; mt, ai = ib >> 5, ib & 31; i += 1
    if ai < 24: n = ai
    elif ai == 24: n = b[i]; i += 1
    elif ai == 25: n = struct.unpack('>H', b[i:i + 2])[0]; i += 2
    elif ai == 26: n = struct.unpack('>I', b[i:i + 4])[0]; i += 4
    else: raise WaError(400, 'BAD_CBOR', '지원하지 않는 CBOR 길이입니다.')
    if mt == 0: return n, i
    if mt == 1: return -1 - n, i
    if mt in (2, 3):
        if n > 4096 or i + n > len(b): raise WaError(400, 'BAD_CBOR', 'CBOR 길이 오류')
        v = bytes(b[i:i + n]); return (v if mt == 2 else v.decode()), i + n
    if mt == 4:
        if n > 32: raise WaError(400, 'BAD_CBOR', 'CBOR 배열이 너무 큽니다.')
        out = []
        for _ in range(n): v, i = cbor_decode(b, i, depth + 1); out.append(v)
        return out, i
    if mt == 5:
        if n > 32: raise WaError(400, 'BAD_CBOR', 'CBOR 맵이 너무 큽니다.')
        out = {}
        for _ in range(n): k, i = cbor_decode(b, i, depth + 1); v, i = cbor_decode(b, i, depth + 1); out[k] = v
        return out, i
    raise WaError(400, 'BAD_CBOR', '지원하지 않는 CBOR 형식입니다.')
def parse_auth_data(ad, need_attested):
    if len(ad) < 37: raise WaError(400, 'BAD_AUTHDATA', 'authenticatorData가 너무 짧습니다.')
    d = dict(rpIdHash=ad[:32], flags=ad[32], signCount=struct.unpack('>I', ad[33:37])[0])
    if need_attested:
        if not d['flags'] & 0x40 or len(ad) < 55: raise WaError(400, 'BAD_AUTHDATA', '자격 증명 데이터가 없습니다.')
        n = struct.unpack('>H', ad[53:55])[0]; d['credId'] = ad[55:55 + n]; key, _ = cbor_decode(ad, 55 + n); d['cose'] = key
    return d
def check_client(client_json, typ, challenge_b64u, origins):
    try: c = json.loads(client_json)
    except Exception: raise WaError(400, 'BAD_CLIENT_DATA', 'clientDataJSON이 올바르지 않습니다.')
    if c.get('type') != typ: raise WaError(400, 'BAD_TYPE', 'WebAuthn 요청 종류가 다릅니다.')
    if c.get('challenge') != challenge_b64u: raise WaError(400, 'BAD_CHALLENGE', '챌린지가 일치하지 않습니다.')
    if c.get('origin') not in origins: raise WaError(400, 'BAD_ORIGIN', '허용되지 않은 origin입니다.')
    return c
def cose_to_point(key):
    """ES256(P-256)만 허용. 반환: 비압축 점(0x04||x||y)."""
    if key.get(1) != 2 or key.get(3) != -7 or key.get(-1) != 1: raise WaError(400, 'UNSUPPORTED_KEY', 'ES256(P-256) 패스키만 지원합니다.')
    x, y = key.get(-2), key.get(-3)
    if not isinstance(x, bytes) or not isinstance(y, bytes) or len(x) != 32 or len(y) != 32: raise WaError(400, 'UNSUPPORTED_KEY', '공개키 형식이 올바르지 않습니다.')
    return b'\x04' + x + y
def verify_registration(client_json, attestation_object, challenge, rp_id, origins):
    check_client(client_json, 'webauthn.create', challenge, origins)
    att, _ = cbor_decode(attestation_object)
    if not isinstance(att, dict) or att.get('fmt') != 'none': raise WaError(400, 'UNSUPPORTED_ATTESTATION', 'attestation none만 지원합니다.')
    d = parse_auth_data(att['authData'], True)
    if d['rpIdHash'] != hashlib.sha256(rp_id.encode()).digest(): raise WaError(400, 'BAD_RPID', 'RP ID가 일치하지 않습니다.')
    if not d['flags'] & 0x01 or not d['flags'] & 0x04: raise WaError(400, 'UV_REQUIRED', '사용자 확인(지문·PIN)이 필요합니다.')
    return d['credId'], cose_to_point(d['cose']), d['signCount']
def verify_assertion(client_json, auth_data, signature, point, challenge, rp_id, origins, stored_count):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    check_client(client_json, 'webauthn.get', challenge, origins)
    d = parse_auth_data(auth_data, False)
    if d['rpIdHash'] != hashlib.sha256(rp_id.encode()).digest(): raise WaError(400, 'BAD_RPID', 'RP ID가 일치하지 않습니다.')
    if not d['flags'] & 0x01 or not d['flags'] & 0x04: raise WaError(401, 'UV_REQUIRED', '사용자 확인(지문·PIN)이 필요합니다.')
    try: ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point).verify(signature, auth_data + hashlib.sha256(client_json).digest(), ec.ECDSA(hashes.SHA256()))
    except Exception: raise WaError(401, 'BAD_SIGNATURE', '서명이 올바르지 않습니다.')
    if (d['signCount'] or stored_count) and d['signCount'] <= stored_count: raise WaError(401, 'CLONED_AUTHENTICATOR', '서명 카운터가 증가하지 않았습니다(복제 의심).')
    return d['signCount']
