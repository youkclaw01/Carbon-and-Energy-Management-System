#!/bin/sh
# nginx가 내부 앱 이름(KRX API)을 해석하도록 컨테이너의 DNS 서버를 resolver로 지정한다(외부 도구 없이 sh 내장 기능만 사용).
NS=127.0.0.11
while read k v rest; do if [ "$k" = "nameserver" ]; then NS=$v; break; fi; done < /etc/resolv.conf
echo "resolver $NS valid=30s ipv6=off;" > /tmp/resolver.conf
exec nginx -g 'daemon off;'
