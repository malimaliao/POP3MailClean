//根据页面地址定义其active
function PagesClassActive() {
    //根据页面地址赋值active Start -----------------------------------
    var this_url = String(window.location.pathname);
    //link /
    if(this_url == '/' || this_url == '/index.py'){
        $("#sidebar_index").addClass('active');
    }
    //link /account/*
    if(this_url.search('^/account/') != -1){
        $("#sidebar_account").addClass('active');
    }
    //link /help/*
    if(this_url.search('^/help/') != -1){
        $("#sidebar_help").addClass('active');
    }
    //link /status/*
    if(this_url.search('^/status/') != -1){
        $("#sidebar_status").addClass('active');
    }
    //link /log/*
    if(this_url.search('^/log/') != -1){
        $("#sidebar_log").addClass('active');
    }
    //link /task/*
    if(this_url.search('^/task/') != -1){
        $("#sidebar_task").addClass('active');
        $("#sidebar_task").css('display','block');
    }
    //alert(this_url);
    //根据页面地址赋值active Stop -----------------------------------
}

// 新增JS 20200309

//显示时间
function showTime(){
    var now=new Date();
    var year=now.getFullYear();
    var month=now.getMonth()+1; //js获取的月份是从0开始；
    var day=now.getDate();
    var h=now.getHours();
    var m=now.getMinutes();
    var s=now.getSeconds();
    m=checkTime(m);
    s=checkTime(s);

    var weekday=new Array(7);
    weekday[0]="星期日";
    weekday[1]="星期一";
    weekday[2]="星期二";
    weekday[3]="星期三";
    weekday[4]="星期四";
    weekday[5]="星期五";
    weekday[6]="星期六";
    var w=weekday[now.getDay()]; //js获取的星期是0~6,0是星期天；
    document.getElementById("show_time").innerHTML=""+year+"年"+month+"月"+day+"日 "+w+"  "+h+":"+m+":"+s;
    t=setTimeout('showTime()',500)
}
//显示时间辅助函数
function checkTime(i){  //补位处理
    if(i<10)
    {
        i="0"+i;     //当秒分小于10时，在左边补0；
    }
    return i;
}