---
customlog:
  -
    format: combined
    target: /etc/apache2/logs/domlogs/injul.com.do
  -
    format: "\"%{%s}t %I .\\n%{%s}t %O .\""
    target: /etc/apache2/logs/domlogs/injul.com.do-bytes_log
documentroot: /home/injuldom/public_html
group: injuldom
hascgi: 0
homedir: /home/injuldom
ifmodulealiasmodule:
  scriptalias:
    -
      path: /home/injuldom/public_html/cgi-bin/
      url: /cgi-bin/
ifmoduleincludemodule:
  directoryhomeinjuldompublichtml:
    ssilegacyexprparser:
      -
        value: " On"
ifmodulelogconfigmodule:
  ifmodulelogiomodule:
    customlog:
      -
        format: "\"%{%s}t %I .\\n%{%s}t %O .\""
        target: /usr/local/apache/domlogs/injul.com.do-bytes_log
ifmoduleuserdirmodule:
  ifmodulempmitkc:
    ifmoduleruidmodule: {}
include:
  -
    include: "\"/usr/local/apache/conf/userdata/*.conf\""
ip: 50.31.174.167
owner: i53nd1n
phpopenbasedirprotect: 1
phpversion: ea-php74
port: '80'
scriptalias:
  -
    path: /home/injuldom/public_html/cgi-bin
    url: /cgi-bin/
serveradmin: webmaster@injul.com.do
serveralias: mail.injul.com.do www.injul.com.do
servername: injul.com.do
ssl: '1'
usecanonicalname: 'Off'
user: injuldom
userdirprotect: ''
