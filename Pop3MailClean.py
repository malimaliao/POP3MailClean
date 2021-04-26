# -*- coding:utf-8 -*-
# -*- 人生苦短，Python当歌

# flask web db
from __future__ import with_statement
from contextlib import closing
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash

# pop3
import poplib
from email.parser import Parser
from parser import ParserError

# SocketIO
from flask_socketio import SocketIO, emit

# 线程
from threading import Lock
# 线程池
from multiprocessing.dummy import Pool as ThreadPool

# os
import os
import platform
import datetime

# ini
from configobj import ConfigObj

# SMTP
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import parsedate_to_datetime, formatdate, parsedate

# 固定参数
_MC_name = 'POP3MailClean'
_MC_version = '2.2'
_MC_version_time = '2021-04-26'
_MC_config_file = 'config.ini'
_MC_config_ini_obj = ConfigObj(_MC_config_file, encoding='UTF8')
_socket_task_timer = 3  # 每个账号之间隔时间，秒
_socket_io_name_space = '/mc_socket_io'  # socket io命名空间
_socket_task_account_data = dict()  # socket io task 任务列表
_socket_async_mode = 'threading'  # socket工作模式，threading、eventlet、gevent

DATABASE_dir = 'db'  # 数据应用目录
DATABASE = DATABASE_dir + os.sep + 'data.db'  # 本软件的数据库文件
DATABASE_default = DATABASE_dir + os.sep + 'default.db'  # 本软件的数据库文件

app = Flask(__name__)
app.config.from_object(__name__)
socketio = SocketIO(app)

_thread = None
lock = Lock()

app.config.from_envvar('FLASKR_SETTINGS', silent=True)
app.config['SECRET_KEY'] = 'oiiog23vroen34'  # flask会话所需，防止csrf跨站所需秘钥变量，暂时没什么用


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


def create_init_db():
    # 通过sql脚本提交方式，初始化并建立一个数据库
    print('--- 创建初始数据库 ---')
    with closing(connect_db()) as db:
        with app.open_resource(DATABASE_dir + os.sep + 'init.sql') as f:
            sql = f.read().decode('utf-8')
            db.cursor().executescript(sql)
        db.commit()


def copy_default_db():
    print('--- 映像默认数据库 ---')
    if platform.system().lower() == 'windows':
        os.system('copy '+DATABASE_default+' '+DATABASE)
    elif platform.system().lower() == 'linux':
        os.system('cp '+DATABASE_default+' '+DATABASE)


@app.before_request
def before_request():
    g.db = connect_db()


@app.after_request
def after_request(response):
    g.db.close()
    return response


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


# 127.0.0.1/
@app.route('/')
def system_index():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    global _socket_task_account_data
    _socket_task_account_data = dict()  # 防止用户在执行任务列表时跳转回来，以停止socket的任务列表在后台工作，此处重置任务列表为空数据
    return render_template('index.html')


# 127.0.0.1/help/
@app.route('/help/')
def show_help():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    return render_template('help.html', MC_version=_MC_version, MC_name=_MC_name)


# 127.0.0.1/account/
@app.route('/account/')
def show_list_account():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    global _socket_task_account_data
    _socket_task_account_data = dict()  # 防止用户在执行任务列表时跳转回来，以停止socket的任务列表在后台工作，此处重置任务列表为空数据
    cur = g.db.execute('SELECT mail_id,mail_user,mail_acount,mail_password,mail_keeptime,mail_status,do_time,do_ip FROM mail_accounts')
    data = cur.fetchall()
    sum = len(data)
    return render_template('list_account.html', account_list=data, account_sum=sum)


# 添加新条目
@app.route('/account/add', methods=['POST'])  # 只回应POST请求
def account_add():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    _post_user = request.form.get('mail_user')
    _post_login = request.form.get('mail_account')
    _post_pass = request.form.get('mail_password')
    _post_keep = request.form.get('mail_keeptime')  # 此处接收纯数值，否则会在执行SQL会报错
    if request.form.get('mail_status') == 'on':
        _post_status = 1
    else:
        _post_status = 0
    _post_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _post_ip = request.remote_addr
    print(_post_user, _post_login, _post_pass, _post_keep, _post_status, _post_time, _post_ip)
    # 验证账号是否有效
    account_test = query_account(_post_login, _post_pass)
    if account_test['login_status'] != 1:
        print('该账号验证不通过')
        flash(u'您刚才提交的账号登录验证不通过，请检查账号密码是否正确！', 'e_login_error')
    else:
        print('该账号验证通过，准备入库')
        g.db.execute('insert into mail_accounts (mail_user, mail_acount, mail_password, mail_keeptime, mail_status, do_time, do_ip) values (?, ?, ?, ?, ?, ?, ?)',[_post_user, _post_login, _post_pass, _post_keep, _post_status, _post_time, _post_ip])
        # 使用问号标记来构建 SQL 语句。否则，当使用格式化字符串构建 SQL 语句时， 应用容易遭受 SQL 注入。
        g.db.commit()
        flash(u'您刚才成功添加了一条新记录!', 'e_login_ok')   # 用flash()向下一个请求闪现一条信息
    return redirect(url_for('show_list_account'))   # 重定向，跳转


# 删除条目
@app.route('/account/del', methods=['GET'])
def account_del():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    _post_id = request.args.get('id')
    _post_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _post_ip = request.remote_addr
    print(_post_id, _post_time, _post_ip)
    g.db.execute('DELETE FROM mail_accounts WHERE mail_id =' + _post_id)
    g.db.commit()
    flash('删除了一条记录')   # 用flash()向下一个请求闪现一条信息
    print('删除了一条记录')
    return redirect(url_for('show_list_account'))   # 重定向，跳转


# 读取条目
@app.route('/account/read', methods=['GET'])
def account_read():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    _post_id = request.args.get('id')
    cur = g.db.execute('SELECT * FROM mail_accounts WHERE mail_id =' + _post_id)
    data = cur.fetchall()
    one_data = data[0]
    return render_template('account.html', account_data=one_data)


# 更新条目
@app.route('/account/update', methods=['POST'])  # 只回应POST请求
def account_update():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    _post_id = request.form.get('mail_id')
    _post_user = request.form.get('mail_user')
    _post_login = request.form.get('mail_account')
    _post_pass = request.form.get('mail_password')
    _post_keep = request.form.get('mail_keeptime')  # 此处接收纯数值，否则会在执行SQL会报错
    if request.form.get('mail_status') == 'on':
        _post_status = 1
    else:
        _post_status = 0
    _post_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _post_ip = request.remote_addr
    print(_post_user, _post_login, _post_pass, _post_keep, _post_status, _post_time, _post_ip, _post_id)
    # 验证账号是否有效
    account_test = query_account(_post_login, _post_pass)
    if account_test['login_status'] != 1:
        print('修改的账号验证登录不通过！')
        flash(u'您刚才提交修改的账号登录验证不通过，请检查账号密码是否正确！', 'e_login_error')
    else:
        _post_data = [_post_user, _post_login, _post_pass, _post_keep, _post_status, _post_time, _post_ip, _post_id]
        g.db.execute('UPDATE mail_accounts SET mail_user=?, mail_acount=?, mail_password=?, mail_keeptime=?, mail_status=?, do_time=?, do_ip=? WHERE mail_id=?', _post_data)
        # 使用问号标记来构建 SQL 语句。否则，当使用格式化字符串构建 SQL 语句时， 应用容易遭受 SQL 注入。
        g.db.commit()
        flash(u'您刚才提交修改的账号已经成功!', 'e_login_ok')   # 用flash()向下一个请求闪现一条信息
        print('修改的记录提交成功')
    return redirect(url_for('show_list_account'))   # 重定向，跳转


# 127.0.0.1/status/
@app.route('/status/')
def show_list_account_status():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    global _socket_task_account_data
    _socket_task_account_data = dict()  # 防止用户在执行任务列表时跳转回来，以停止socket的任务列表在后台工作，此处重置任务列表为空数据
    cur = g.db.execute('SELECT mail_id,mail_user,mail_acount,mail_password,mail_keeptime,mail_status,do_time,do_ip FROM mail_accounts WHERE mail_status = 1')
    data = cur.fetchall()
    _email_list = []
    #print(data)
    for e in data:
        e_id = e[0]
        e_name = e[1]
        e_user = e[2]
        e_pass = e[3]
        e_keeptime = e[4]
        e_code = query_account(e_user, e_pass)
        if(e_code['login_status']==1):
            e_login_status = '成功'
        else:
            e_login_status = '出错'
        e_before_sum = e_code['before_sum']
        e_before_size = e_code['before_size']
        e_login_data = e_code['login_data']
        _email_list.append([e_id, e_name, e_user, e_pass, e_keeptime, e_before_sum, e_before_size, e_login_status, e_login_data])
    # print(_email_list)
    return render_template('list_status.html', email_list=_email_list, email_sum=len(_email_list))


# 单线程处理 作业输出
@app.route('/task/', methods=['POST'])
def show_task_work():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    if request.method == 'POST':
        global _socket_task_account_data
        id_list = request.form.getlist('id_list')
        _id_sql = ''
        _id_i = 0
        # 合并所需SQL多个ID
        for account_id in id_list:
            if _id_i == 0:
                _id_sql += 'mail_id=' + account_id
            else:
                _id_sql += ' or mail_id=' + account_id
            _id_i = _id_i + 1
        # 根据多个ID查询数据库数据
        account_cur = g.db.execute('SELECT * FROM mail_accounts WHERE ' + _id_sql)
        account_data = account_cur.fetchall()
        # 将数据库查到的指定多个ID的数据汇集并传递给_socket_task_account_data，交由socket的ws://协议在服务层工作
        _socket_task_account_data = account_data
        return render_template('list_task.html', post_id_list=id_list)
    else:
        return render_template('403.html')


# 多线程处理 作业输出
@app.route('/task2/', methods=['POST'])
def show_task_work2():
    if not session.get('MC_system_user'):
        return redirect(url_for('system_login'))
    if request.method == 'POST':
        global _socket_task_account_data
        id_list = request.form.getlist('id_list')
        _id_sql = ''
        _id_i = 0
        _id_list = ''
        # 合并所需SQL多个ID
        for account_id in id_list:
            if _id_i == 0:
                _id_sql += 'mail_id=' + account_id
            else:
                _id_sql += ' or mail_id=' + account_id
            _id_i = _id_i + 1
            _id_list += account_id + ','
        print('用户提交清理ID列表为：' + _id_list)  # 1,2,3,4,5,
        # 根据多个ID查询数据库数据
        account_cur = g.db.execute('SELECT * FROM mail_accounts WHERE ' + _id_sql)
        account_data = account_cur.fetchall()
        # 将数据库查到的指定多个ID的数据汇集并传递给_socket_task_account_data，交由socket的ws://协议在服务层工作
        _socket_task_account_data = account_data
        return render_template('list_tasks.html', post_id_list=_id_list)
    else:
        return render_template('403.html')


# /login/
@app.route('/login/')
def system_login():
    return render_template('login.html', MC_version=_MC_version, MC_name=_MC_name)


# /login/
@app.route('/login/check', methods=['POST'])
def system_login_check():
    login_user = request.form.get('login_user')
    login_pass = request.form.get('login_pass')
    if login_user == _MC_config_ini_obj['flask']['login_user'] and login_pass == _MC_config_ini_obj['flask']['login_user']:
        session['MC_system_user'] = login_user
        session['MC_system_pass'] = login_pass
        return redirect(url_for('system_index'))
    else:
        flash('账号密码不正确！')  # 密码错误！
        return redirect(url_for('system_login'))


# /logout/
@app.route('/logout/')
def logout():
    global _socket_task_account_data
    _socket_task_account_data = dict()  # 防止用户在执行任务列表时跳转回来，以停止socket的任务列表在后台工作，此处重置任务列表为空数据
    session.pop('MC_system_user')  # 删除session
    session.pop('MC_system_pass')  # 删除session
    flash('您已退出登录！')  # 密码错误！
    return redirect(url_for('system_login'))


# 验证邮件账号登录状态
def query_account(login_user, login_pass):
    status = dict()
    try:
        poplib._MAXLINE = 1024 * 1024  # 防止报错: poplib.error_proto: line too long
        if _MC_config_ini_obj['pop3']['ssl_enable'] == '1':
            pop3_server = poplib.POP3_SSL(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['ssl_port'])
            print('pop3 ssl login:', login_user)
        else:
            pop3_server = poplib.POP3(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['port'])
            print('pop3 login:', login_user)
        pop3_server.user(login_user)
        pop3_server.pass_(login_pass)
        pop3_server_status = pop3_server.stat()  # 登录成功后返回消息：(7, 5917225)
        this_mail_sum = pop3_server_status[0]  # 邮件数量
        this_mail_size = "{:.2f}".format(pop3_server_status[1] / 1024 / 1024)  # 邮件大小，截取3位小数点
        mail_welcome = str(pop3_server.getwelcome())
        print('>>>>>>/status/:' + login_user + ' 登录成功：' + mail_welcome)
        status['login_status'] = 1
        status['login_data'] = str(mail_welcome)
        status['before_sum'] = this_mail_sum
        status['before_size'] = this_mail_size
        pop3_server.quit()
    except Exception as error:
        print('>>>>>>/status/:' + login_user + ' 登录出错：' + str(error))
        status['login_status'] = -1
        status['login_data'] = str(error)
        status['before_sum'] = 0
        status['before_size'] = 0
    return status


# 邮件单个清理函数 调试函数
def email_clean(login_user, login_pass, keep_day):
    status = dict()
    try:
        poplib._MAXLINE = 1024 * 1024  # 防止报错: poplib.error_proto: line too long
        if _MC_config_ini_obj['pop3']['ssl_enable'] == '1':
            pop3_server = poplib.POP3_SSL(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['ssl_port'])
        else:
            pop3_server = poplib.POP3(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['port'])
        pop3_server.user(login_user)
        pop3_server.pass_(login_pass)
        pop3_server_status = pop3_server.stat()  # 登录成功后返回消息：(7, 5917225)
        this_mail_sum = pop3_server_status[0]  # 邮件数量
        this_mail_size = "{:.2f}".format(pop3_server_status[1] / 1024 / 1024)  # 邮件大小，截取3位小数点
        mail_welcome = str(pop3_server.getwelcome())
        print(login_user + ' 登录成功 ' + mail_welcome)

        # 使用list()返回所有邮件的编号，默认为字节类型的串
        resp, mails, octets = pop3_server.list()
        print(">>>>  响应信息：", resp)
        clean_sum = 0
        for i in range(this_mail_sum):
            resp, mail_content, octets = pop3_server.retr(i + 1)
            # 可以获得整个邮件的原始文本:
            msg_content = Parser().parsestr(b'\r\n'.join(mail_content).decode("iso8859", ""))
            dateStr = msg_content.get("Date", "")
            print(">>>>  日期字符：", dateStr)
            # mail_date = dateutil.parser.parse(date_str)
            mail_date = parsedate_to_datetime(dateStr)  # 改进后的转化时间方式
            print('>>>>  当前邮件日期转化：', mail_date)
            try:
                # 判断多少天前的邮件
                if mail_date.date() <= datetime.datetime.now().date() - datetime.timedelta(days=keep_day):
                    print(">>>>  正在删除：第{}封，邮件日期：{} {}".format(i + 1, mail_date.date(), mail_date.time()))
                    pop3_server.dele(i + 1)
                    clean_sum = clean_sum + 1
                else:
                    break  # 跳出任务
            except ParserError:
                print(">>>>  正在删除：第{}封，邮件日期：没有".format(i + 1))
                pop3_server.dele(i + 1)
                clean_sum = clean_sum + 1
        status['login_status'] = 1
        status['login_data'] = str(mail_welcome)
        status['before_sum'] = this_mail_sum
        status['before_size'] = this_mail_size
        status['after_sum'] = clean_sum
        print(">>>>  作业统计：当前账号共计删除{}封邮件".format(clean_sum))
        pop3_server.quit()
    except Exception as error:
        print(login_user + ' 登录或枚举邮件列表出错：' + str(error))
        status['login_status'] = -1
        status['login_data'] = str(error)
        status['before_sum'] = 0
        status['before_size'] = 0
        status['after_sum'] = 0
    return status


# 自动作业报告
def email_report(task_accoun_data = None):
    # mail_msg = '<p>Python 邮件发送测试...</p><p><a href="http://www.baidu.com">这是一个链接</a></p>'
    # 采用html模板
    with open('templates/email.html', 'r', encoding='UTF-8') as f:
        html_code = f.read()
        html_list = ''
        html_i = 1
        for zhanghao in _socket_task_account_data:
            html_list += '<tr><td bgcolor="#ffffff" style="padding: 10px 20px 5px 20px; color: #555555; font-family: Arial, sans-serif; font-size: 15px; line-height: 24px;"><b>' + str(html_i) + '.</b>' + zhanghao[1] + '【' + zhanghao[2] + '】</td>'
            html_i = html_i + 1
        html_txt = html_code.replace('<!--$list-->', html_list)
        mail_msg = html_txt.replace('<!--$datatime-->', str(datetime.datetime.now()))
    message = MIMEText(mail_msg, "html", "utf-8")
    # 标准邮件需要三个头部信息： From, To, 和 Subject
    message["From"] = _MC_config_ini_obj['report']['mail_from']  # 对应发件人
    message["To"] = ','.join(_MC_config_ini_obj['report']['mail_to'].split[','])  # 对应收件人列表
    if len(_MC_config_ini_obj['report']['mail_cc'].split[',']) > 0:
        message["Cc"] = ','.join(_MC_config_ini_obj['report']['mail_cc'].split[','])  # 对应收件人列表
    message['Subject'] = Header(_MC_name + '任务报告', 'utf-8')  # 邮件主题
    try:
        if _MC_config_ini_obj['smtp']['ssl_enable'] == '1':
            smtpObj = smtplib.SMTP_SSL(_MC_config_ini_obj['smtp']['host'], int(_MC_config_ini_obj['smtp']['ssl_port']))
        else:
            smtpObj = smtplib.SMTP()
            smtpObj.connect(_MC_config_ini_obj['smtp']['host'], int(_MC_config_ini_obj['smtp']['port']))
        smtpObj.login(_MC_config_ini_obj['smtp']['login_user'], _MC_config_ini_obj['flask']['login_pass'])
        smtpObj.sendmail(_MC_config_ini_obj['report']['mail_from'], _MC_config_ini_obj['report']['mail_to'].split[','], message.as_string())
        print("已尝试邮件发送报告")
        smtpObj.quit()
    except smtplib.SMTPException:
        print("Error: 无法发送邮件报告")


'''
# socket 连接时的响应，及捆绑事件，采用线程处理(这个IO没有命名空间，即全局)
@socketio.on("connect")
def MailClean_io_connect_1():
    print('web socket io 连接')
    global _thread
    with lock:
        if _thread is None:
            _thread = socketio.start_background_task(target=clean_account_list)  # 此处target=绑定socket连接时的事件

# socket 断开
@socketio.on('disconnect')
def MailClean_io_exit_1():
    print('web socket io 断开')
'''


# socket 连接命名空间 /mc_socket_io 后，响应及捆绑事件
@socketio.on('connect', namespace=_socket_io_name_space)
def MailClean_io_connect():
    print('io 连接命名空间 /mc_socket_io')
    # emit('MC_io', {'status': 'IO 已连接'})


# socket 断开命名空间：/mc_socket_io
@socketio.on('disconnect', namespace=_socket_io_name_space)
def MailClean_io_exit():
    print('io 断开命名空间：/mc_socket_io')
    # emit('MC_io', {'status': 'IO 已断开'})


# 单线程响应socket server_task 批量清理账号列表
@socketio.on('server_task', namespace=_socket_io_name_space)
def io_task_run(data):
    print('单线程响应清理作业任务')
    global _socket_task_account_data
    io_task_status = data.get('msg')  # 通过 socket 在 _socket_io_name_space 空间接收到的前端传递的任务信号，
    if io_task_status == 'stop':
        _socket_task_account_data = dict()  # 传递了停止信号 重置账号任务列表为空(此处重置了，因此前面需要引用全局变量可写)
    # 检测当前内存中 _socket_task_account_data 即 IO清理的账号任务列表是否有任务
    if len(_socket_task_account_data) < 1:
        print('投递消息给前端：空任务', _socket_io_name_space)
        socketio.emit('MC_io', {'status': 'IO清理任务数量：空'}, namespace=_socket_io_name_space)
    else:
        print('投递消息给前端：执行任务数：' + str(len(_socket_task_account_data)),_socket_io_name_space)
        socketio.emit('MC_io', {'status': 'IO清理任务数量：' + str(len(_socket_task_account_data))}, namespace=_socket_io_name_space)
        socketio.emit("MC_io", {'title': '正在执行作业中，请稍后……'}, namespace=_socket_io_name_space)
        socketio.emit("MC_io", {'gif': '<i class="fa fa-cog fa-spin fa-4x"></i>'}, namespace=_socket_io_name_space)
        # >>>>>>>>>>>>>>>>>>>> 批量任务执行 启动 >>>>>>>>>>>>>>>>>>>>>>>>
        _account = dict()  # 临时账号
        _n = 0  # 临时计数器
        for account in _socket_task_account_data:
            if len(_socket_task_account_data) < 1:  # 拦截器1
                print('IO后台清理任务被终止：for_account_list')
                socketio.emit("MC_io", {'title': 'IO任务被用户强行终止！'}, namespace=_socket_io_name_space)
                socketio.emit("MC_io", {'gif': ' '}, namespace=_socket_io_name_space)
                break
            _account['id'] = account[0]
            _account['name'] = account[1]
            _account['user'] = account[2]
            _account['pass'] = account[3]
            _account['keep'] = account[4]
            _account['delete_sum'] = 0
            # pop3 login
            try:
                poplib._MAXLINE = 1024 * 1024  # 防止报错: poplib.error_proto: line too long
                if _MC_config_ini_obj['pop3']['ssl_enable'] == '1':
                    pop3_server = poplib.POP3_SSL(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['ssl_port'])
                else:
                    pop3_server = poplib.POP3(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['port'])
                pop3_server.user(_account['user'])
                pop3_server.pass_(_account['pass'])
                pop3_server_status = pop3_server.stat()  # 登录成功后返回消息：(7, 5917225)
                this_mail_sum = pop3_server_status[0]  # 邮件数量
                this_mail_size = "{:.2f}".format(pop3_server_status[1] / 1024 / 1024)  # 邮件大小，截取3位小数点
                mail_welcome = str(pop3_server.getwelcome())
                print(_account['user'] + ' 登录成功' + mail_welcome)
                _account['login_welcome'] = str(mail_welcome)
                _account['before_sum'] = this_mail_sum
                _account['before_size'] = this_mail_size
                # 清除工作 开始
                resp, mails, octets = pop3_server.list()
                print(">>>>  响应信息：", resp)
                task_i = 0
                for i in range(this_mail_sum):
                    if len(_socket_task_account_data) < 1:  # 拦截器2
                        print('IO后台清理任务被终止：for_mail_list')
                        break
                    # 可以获得整个邮件的原始文本:
                    resp, mail_content, octets = pop3_server.retr(i + 1)
                    try:
                        msg_content = Parser().parsestr(b'\r\n'.join(mail_content).decode("iso8859", ""))
                        date_str = msg_content.get("Date", "")
                        print(">>>>  当前邮件日期字符：", date_str)
                        # Wed, 27 Mar 2019 13:30:04 +0800 (GMT+08:00) 这种时间出现时，使用dateutil.parser.parse会报错
                        # mail_date = dateutil.parser.parse(date_str)
                        mail_date = parsedate_to_datetime(date_str)  # 改进后的转化时间方式
                        print('>>>>  当前邮件日期转化：', mail_date)
                        # 判断多少天前的邮件
                        if mail_date.date() <= datetime.datetime.now().date() - datetime.timedelta(days=_account['keep']):
                            # 执行任务
                            print(_account['user'] + ">>>>  正在删除：第{}封，日期：{} {}".format(i + 1, mail_date.date(), mail_date.time()))
                            socketio.emit("MC_io", {'data': '正在删除：' + _account['user'] + '账号中的第<span class="text-danger">' + str(i + 1) + '</span>封邮件，日期：' + str(mail_date.date()) + ' ' + str(mail_date.time())}, namespace=_socket_io_name_space)
                            pop3_server.dele(i + 1)
                            task_i = task_i + 1
                        else:
                            break  # 跳出任务
                    except ParserError:
                        print(_account['user'] + ">>>>  正在删除：第{}封，日期：没有".format(i + 1))
                        socketio.emit("MC_io", {'data': '正在删除' + _account['user'] + '账号中的第' + str(i + 1) + '封邮件，日期：空'}, namespace=_socket_io_name_space)
                        pop3_server.dele(i + 1)
                        task_i = task_i + 1
                # 清除工作 完毕
                _account['login_status'] = '完成'
                _account['delete_sum'] = task_i
                print(_account['user'] + ">>>>  清理完成：共计删除{}封邮件".format(task_i))
                socketio.emit("MC_io", {'data': _account['user'] + ': clean_success'}, namespace=_socket_io_name_space)
                pop3_server.quit()
            except Exception as error:
                print(_account['user'] + ' 登录或在枚举邮件列表中出错：' + str(error))
                _account['login_status'] = '异常'
                _account['login_welcome'] = str(error)
                _account['before_sum'] = 0
                _account['before_size'] = 0
                _account['delete_sum'] = 0
            # pop3 logout
            _n = _n + 1
            if _n == len(_socket_task_account_data):
                print('全部处理完毕！')
                socketio.emit("MC_io", {'title': '全部处理完毕！MailClean:task_end'}, namespace=_socket_io_name_space)
                socketio.emit("MC_io", {'gif': '<i class="fa fa-smile fa-4x"></i>'}, namespace=_socket_io_name_space)
                if _MC_config_ini_obj['task']['mail_enable'] == '1':
                    email_report(_socket_task_account_data)
            # 将本账号的清理数据投递给 MC_task_print
            socketio.emit("MC_task_print", _account, namespace=_socket_io_name_space)
            socketio.sleep(_socket_task_timer)
        # >>>>>>>>>>>>>>>>>>>> 批量任务执行 结束 >>>>>>>>>>>>>>>>>>>>>>>>


# 多线程响应socket server_task2 批量清理账号列表
@socketio.on('server_task2', namespace=_socket_io_name_space)
def io_task_run2(data):
    global _socket_task_account_data
    io_task_status = data.get('msg')  # 在 _socket_io_name_space 空间接收到的前端传递的任务信号，
    print('接收消息来自前端：', io_task_status)
    if io_task_status == 'stop':
        _socket_task_account_data = []
    # 检测当前socket是否传递清理ID
    if len(_socket_task_account_data) < 1:
        print('投递消息给前端：空任务', _socket_io_name_space)
        socketio.emit('MC_io2', {'status': '清理任务：任务是空的'}, namespace=_socket_io_name_space)
        socketio.emit("MC_io2", {'title': '当前没有清理作业任务'}, namespace=_socket_io_name_space)
    else:
        print('投递消息给前端：执行任务数：' + str(len(_socket_task_account_data)), _socket_io_name_space)
        socketio.emit('MC_io2', {'status': '清理任务：' + str(len(_socket_task_account_data)) + '个线程任务'}, namespace=_socket_io_name_space)
        socketio.emit("MC_io2", {'title': '正在执行清理作业中，请稍后……'}, namespace=_socket_io_name_space)
        socketio.emit("MC_io2", {'gif': '<i class="fa fa-cog fa-spin fa-4x"></i>'}, namespace=_socket_io_name_space)
        # 创建线程池
        pool = ThreadPool()
        pool.map(thread_clean_account, _socket_task_account_data)
        pool.close()
        pool.join()
        #  输出结束
        socketio.emit('MC_io2', {'status': '清理任务：已经结束！'}, namespace=_socket_io_name_space)
        socketio.emit("MC_io2", {'title': '全部处理完毕！MailClean:task_end'}, namespace=_socket_io_name_space)
        socketio.emit("MC_io2", {'gif': '<i class="fa fa-smile fa-4x"></i>'}, namespace=_socket_io_name_space)
        if _MC_config_ini_obj['task']['mail_enable'] == '1':
            email_report(_socket_task_account_data)


# 接收一个账号，并对该账号进行清理，输出socket给前端
def thread_clean_account(account):
    print('处理作业线程：', account)
    _account = dict()
    _account['id'] = account[0]
    _account['name'] = account[1]
    _account['user'] = account[2]
    _account['pass'] = account[3]
    _account['keep'] = account[4]
    _account['delete_sum'] = 0
    socketio.emit("MC_io2", {'id': _account['id']}, namespace=_socket_io_name_space)
    # pop3 login
    try:
        poplib._MAXLINE = 1024 * 1024  # 防止报错: poplib.error_proto: line too long
        if _MC_config_ini_obj['pop3']['ssl_enable'] == '1':
            pop3_server = poplib.POP3_SSL(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['ssl_port'])
        else:
            pop3_server = poplib.POP3(_MC_config_ini_obj['pop3']['host'], _MC_config_ini_obj['pop3']['port'])
        pop3_server.user(_account['user'])
        pop3_server.pass_(_account['pass'])
        pop3_server_status = pop3_server.stat()  # 登录成功后返回消息：(7, 5917225)
        this_mail_sum = pop3_server_status[0]  # 邮件数量
        this_mail_size = "{:.2f}".format(pop3_server_status[1] / 1024 / 1024)  # 邮件大小，截取3位小数点
        mail_welcome = str(pop3_server.getwelcome())
        print(_account['user'] + ' 登录成功' + mail_welcome)
        _account['login_welcome'] = str(mail_welcome)
        _account['before_sum'] = this_mail_sum
        _account['before_size'] = this_mail_size
        # 清除工作 开始
        resp, mails, octets = pop3_server.list()
        print(">>>>  响应信息：", resp)
        task_i = 0
        for i in range(this_mail_sum):
            if len(_socket_task_account_data) < 1:  # 拦截器2
                print('IO后台清理任务被终止：for_mail_list')
                break
            # 可以获得整个邮件的原始文本:
            resp, mail_content, octets = pop3_server.retr(i + 1)
            try:
                msg_content = Parser().parsestr(b'\r\n'.join(mail_content).decode("iso8859", ""))
                date_str = msg_content.get("Date", "")
                print(">>>>  当前邮件日期字符：", date_str)
                # Wed, 27 Mar 2019 13:30:04 +0800 (GMT+08:00) 这种时间出现时，使用dateutil.parser.parse会报错
                # mail_date = dateutil.parser.parse(date_str)
                mail_date = parsedate_to_datetime(date_str)  # 改进后的转化时间方式
                print('>>>>  当前邮件日期转化：', mail_date)
                # 判断多少天前的邮件
                if mail_date.date() <= datetime.datetime.now().date() - datetime.timedelta(days=_account['keep']):
                    print(
                        _account['user'] + ">>>>  正在删除：第{}封，日期：{} {}".format(i + 1, mail_date.date(), mail_date.time()))
                    socketio.emit("MC_io2", {'id': _account['id'], 'data': '清理作业：' + '正在删除：' + _account['user'] + '中的第' + str(i + 1) + '封邮件，日期：' + str(mail_date.date()) + ' ' + str(mail_date.time())}, namespace=_socket_io_name_space)
                    pop3_server.dele(i + 1)
                else:
                    break  # 跳出任务
            except ParserError:
                print(_account['user'] + ">>>>  正在删除：第{}封，日期：没有".format(i + 1))
                socketio.emit("MC_io2", {'id': _account['id'], 'data': '清理作业：' + '正在删除' + _account['user'] + '中的第' + str(i + 1) + '封邮件，日期：空'}, namespace=_socket_io_name_space)
                pop3_server.dele(i + 1)
        # 清除工作 完毕
        _account['login_status'] = '完成'
        _account['delete_sum'] = task_i
        print(_account['user'] + ">>>>  清理完成：共计删除{}封邮件".format(task_i))
        socketio.emit("MC_io2", {'id': _account['id'], 'data': '清理作业：' + _account['user'] + ' 处理完毕.'}, namespace=_socket_io_name_space)
        pop3_server.quit()
    except Exception as error:
        print(_account['user'] + ' 登录或在枚举邮件列表中出错：' + str(error))
        _account['login_status'] = '异常'
        _account['login_welcome'] = str(error)
        _account['before_sum'] = 0
        _account['before_size'] = 0
        _account['delete_sum'] = 0
    # pop3 logout
    # 将本账号的清理数据投递给 MC_task_print
    socketio.emit("MC_task2_print", _account, namespace=_socket_io_name_space)
    socketio.sleep(_socket_task_timer)


if __name__ == '__main__':
    if os.path.exists(DATABASE):
        print('------ 数据文件已就绪：' + DATABASE)
    else:
        print('--- 数据文件初始化 ---')
        create_init_db()
        # copy_default_db()
    if not os.path.exists(_MC_config_file):
        print('------ 配置文件初始化：' + DATABASE)
        _MC_config_ini_obj['flask'] = {}
        _MC_config_ini_obj['flask']['host'] = '0.0.0.0'
        _MC_config_ini_obj['flask']['port'] = '8088'
        _MC_config_ini_obj['flask']['debug'] = '1'
        _MC_config_ini_obj['flask']['login_user'] = 'admin'
        _MC_config_ini_obj['flask']['login_pass'] = 'admin'
        _MC_config_ini_obj['pop3'] = {}
        _MC_config_ini_obj['pop3']['host'] = '127.0.0.1'
        _MC_config_ini_obj['pop3']['port'] = '110'
        _MC_config_ini_obj['pop3']['ssl_enable'] = '1'
        _MC_config_ini_obj['pop3']['ssl_port'] = '995'
        _MC_config_ini_obj['smtp'] = {}
        _MC_config_ini_obj['smtp']['host'] = '127.0.0.1'
        _MC_config_ini_obj['smtp']['port'] = '25'
        _MC_config_ini_obj['smtp']['ssl_enable'] = '1'
        _MC_config_ini_obj['smtp']['ssl_port'] = '465'
        _MC_config_ini_obj['smtp']['login_user'] = 'test'
        _MC_config_ini_obj['smtp']['login_pass'] = '123456'
        _MC_config_ini_obj['task'] = {}
        _MC_config_ini_obj['task']['mail_enable'] = '0'
        _MC_config_ini_obj['report'] = {}
        _MC_config_ini_obj['report']['mail_from'] = 'test@163.com'
        _MC_config_ini_obj['report']['mail_to'] = "a1@qq.com,a2@qq.com"
        _MC_config_ini_obj['report']['mail_cc'] = "a1@163.com,a2@163.com"

        _MC_config_ini_obj.write()
        print('------ 首次运行初始化配置文件已完成，软件已自动停止运行并生成config.ini配置文件。请手动修改config配置各项参数后再次启动本软件即可正常运行！')
        exit(2)
    if _MC_config_ini_obj['flask']['host'] == '' \
            or _MC_config_ini_obj['flask']['port'] == '' \
            or _MC_config_ini_obj['flask']['login_user'] == '' \
            or _MC_config_ini_obj['flask']['login_pass'] == '' \
            or _MC_config_ini_obj['pop3']['host'] == '' \
            or _MC_config_ini_obj['pop3']['port'] == '' \
            or _MC_config_ini_obj['pop3']['ssl_enable'] == '' \
            or _MC_config_ini_obj['pop3']['ssl_port'] == '' \
            or _MC_config_ini_obj['task']['mail_enable'] == '':
        print('------ 发现无效配置文件：' + _MC_config_file)
        print('------ 配置文件必要参数项[flask]、[pop3]、[task]的各参数值都不能为空！')
        exit(3)
    if _MC_config_ini_obj['task']['mail_enable'] == '1':
        if _MC_config_ini_obj['smtp']['host'] == '' \
                or _MC_config_ini_obj['smtp']['port'] == '' \
                or _MC_config_ini_obj['smtp']['ssl_enable'] == '' \
                or _MC_config_ini_obj['smtp']['ssl_port'] == '' \
                or _MC_config_ini_obj['smtp']['login_user'] == '' \
                or _MC_config_ini_obj['smtp']['login_pass'] == '' \
                or _MC_config_ini_obj['report']['mail_from'] == '' \
                or _MC_config_ini_obj['report']['mail_to'] == '' \
                or _MC_config_ini_obj['report']['mail_cc'] == '':
            print('------ 配置文件发现无效配置：' + _MC_config_file)
            print('------ 因为开启了清理任务邮箱报告，因此配置文件中[smtp]及[report]的各项配置均不能为空！')
            exit(4)
    print('------ 配置文件已就绪：' + _MC_config_file)
    mc_flask_host = _MC_config_ini_obj['flask']['host']
    mc_flask_port = _MC_config_ini_obj['flask']['port']
    if _MC_config_ini_obj['flask']['debug'] == '1':
        mc_flask_debug = True
    else:
        mc_flask_debug = False
    socketio.run(app, host=mc_flask_host, port=int(mc_flask_port), debug=mc_flask_debug)
