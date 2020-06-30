# POP3MailClean

pop3 server mail clean.

本软件采用C/S架构，基于Python3 + Flask + Sqlite3环境部署，使用poplib、smtplib实现POP3服务器远程邮件账号的批量清理，并结合SocketIO 、HTML5技术输出实时清理状态。

**软件介绍**
POP3MailClean 基于Python3 + Flask + Sqlite3架构，通过pop3协议实现邮件服务器账号批量邮件清理。

**运行环境**
1，Python 3.7

2，Flask 1.1.1

3，flask-socketio 4.3.0

**使用说明**
系统运行后，通过浏览器（需支持HTML5浏览器）访问： http://127.0.0.1:8088

默认账号：admin，默认密码：admin

更多配置参数可以在系统点击【使用帮助】查看详细使用说明