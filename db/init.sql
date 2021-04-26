--
-- 由SQLiteStudio v3.2.1 产生的文件 周一 六月 22 10:23:37 2020
--
-- 文本编码：UTF-8
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- 表：mail_accounts
DROP TABLE IF EXISTS mail_accounts;

CREATE TABLE mail_accounts (
    mail_id       INTEGER      PRIMARY KEY AUTOINCREMENT,
    mail_user     VARCHAR (30),
    mail_acount   VARCHAR (30) NOT NULL,
    mail_password VARCHAR (30) NOT NULL,
    mail_keeptime INT,
    mail_status   INT          NOT NULL,
    do_time       DATETIME,
    do_ip         VARCHAR (32) 
);


-- 表：mail_log
DROP TABLE IF EXISTS mail_log;

CREATE TABLE mail_log (
    clear_id      INTEGER       PRIMARY KEY AUTOINCREMENT,
    clear_account VARCHAR (30)  NOT NULL,
    clear_day     INT (10)      NOT NULL,
    before_size   VARCHAR (10),
    before_sum    VARCHAR (10),
    delete_sum    INT (10),
    login_status  INT (5),
    login_data    VARCHAR (255),
    do_ip         VARCHAR (32),
    do_time       DATETIME      NOT NULL
);


COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
