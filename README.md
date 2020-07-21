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

更多配置参数可以在系统点击【使用帮助】查看详细使用帮助



---------------------------------

**更新记录**

v2.1：

* 1，新增poplib._MAXLINE，防止poplib.error_proto: line too long；
* 2，优化保留时间计算规则，其中邮件保留时间以当前时间起算，例如保留3天，今天是7月10号，则7月10日,7月9日，7月8日日期之外的邮件将会被删除。

v2.0

* 1，新增对SSL的支持；
* 2，新增多线程并发清理机制；
* 3，其他细节优化；


--------------------------------
本项目从本人gitee.com转移至github.com