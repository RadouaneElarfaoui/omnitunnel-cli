#VPN Configuration for inwi
---
vps.alfredo.qzz.io:80@alfred0:alfred0

GET /cdn-cgi HTTP/1.1 [lf]Host:dev-guest-cf.pscp.tv[lf][lf]ACL / HTTP/1.1 [lf]Host: [host] [crlf]Connection:[lf]Upgrade: Websocket[lf][lf]

canary-guest-cf.pscp.tv:8880

---
---

#VPN Configuration for IAM
---
vps.alfredo.qzz.io:80@alfred0:alfred0

GET / HTTP/1.1[crlf]Host: [host][crlf]Connection: Upgrade[crlf]Upgrade: websocket[crlf][crlf]

crazygames.ro:443

[host]