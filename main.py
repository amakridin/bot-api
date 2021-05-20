import json
from flask import Flask, request, render_template
from redis_data import redis_data
from os import path
from zbx import zbx
from db_data import db_data
from send2tamtam import send2tamtam
import requests
import shutil
import rand
import time
import math
from time import sleep
from datetime import datetime, timedelta
from get_params import get_config
from threading import Thread
import logging
from ast import literal_eval

logging.basicConfig(
    filename="logger.log",
    format="%(levelname)s %(asctime)s %(filename)s:%(lineno)s - %(funcName)20s() %(message)s",
    level=logging.INFO
)
LOG = logging.getLogger('root')
app = Flask(__name__)
grafana_alerts = {}  # {"alertid": "mid", ...}
zabbix_rules = []
zabbix_locks = []
zabbix_templates = {}
redis_host = get_config('redis_host')
redis_port = get_config('redis_port')
redis_password = get_config('redis_password')
redis_alarms = get_config('redis_alarms')
redis_cmdb = get_config('redis_cmdb')
redis_common = get_config('redis_common')
tt = send2tamtam(token=get_config('token'))
proxies = {'http': 'proxy.domain.ru:80', 'https': 'proxy.domain.ru:80'}
with open(path.join('sql', 'im.sql'), 'r', encoding='utf-8') as f:
    qr_im = f.read()


def load_api_rules(once: bool = False):
    while True:
        global zabbix_rules, zabbix_locks, zabbix_templates
        with db_data() as db:
            res = db.get_data("""
            select
              recordid,
              chat_id, 
              send_rule, 
              tmplt, 
              decode(logical,1,'AND',0,'OR') logical, 
              lvl, 
              type, 
              to_char(insert_date-5/24+minutes/24/60, 'yyyy-mm-dd hh24:mi:ss') time_end_utc, 
              importance 
            from bot_api_send_rules 
            where recordid!=0
              and is_act=1 
              and source_id = 1 
              and (type=1 or type=0 and insert_date+minutes/24/60>sysdate)""")
        if len(res) > 0:
            zabbix_rules.clear()
            zabbix_locks.clear()
            for row in res:
                if int(row['TYPE']) == 1:
                    zabbix_rules.append({'chat_id': row['CHAT_ID'], 'logical': row['LOGICAL'],
                                         'rules': row['SEND_RULE'].split("\n"),
                                         'lvl': row['LVL'].split("\n"),
                                         'tmplt': row['TMPLT'].split("\n"),
                                         'importance': row['IMPORTANCE'].split(",")})
                elif int(row['TYPE']) == 0:
                    zabbix_locks.append({'chat_id': row['CHAT_ID'], 'logical': row['LOGICAL'],
                                         'rules': row['SEND_RULE'].split("\n"),
                                         'lvl': row['LVL'].split("\n"),
                                         'tmplt': row['TMPLT'].split("\n"),
                                         'time_end_utc': row['TIME_END_UTC']})
            LOG.info("load_api_rules - refreshed")
        else:
            LOG.warning("load_api_rules - error read from database crm")
        with zbx() as z:
            zabbix_templates.clear()
            zabbix_templates = z.get_templates()
        if once:
            return
        time.sleep(1800)


def send_to_chat_by_rule(msg, link, typ, id, severity, hostid, hostname):
    dt_utc = datetime.utcnow()
    update_rules = False
    with redis_data(db_name='redis_cmdb') as r:
        importance = "*" if r.get(hostname) is None else literal_eval(r.get(hostname)).get('importance')
    if typ == "zabbix":
        with zbx() as z:
            chats_to_send = []
            templates = []
            for row in zabbix_rules:
                rule_len = len(row['rules'])
                nn = 0
                for val in row['rules']:
                    if msg.upper().find(val.upper()) >= 0:
                        nn += 1
                lgcl = row['logical']
                if (rule_len == nn and lgcl == 'AND' or nn > 0 and lgcl == 'OR') \
                        and (severity in row['lvl'] or '*' in row['lvl']):
                    for val in row['tmplt']:
                        if val == '*':
                            if str(importance) in row['importance'] or row['importance'] == ['*']:
                                chats_to_send.append(row['chat_id'])
                        elif len(templates) == 0:
                            for zt in z.get_template_by_hostid(hostid):
                                templates.append(zt['name'])
                        else:
                            for elem in templates:
                                if elem.upper().find(val.upper()) >= 0:
                                    chats_to_send.append(row['chat_id'])
            chats_to_send = list(set(chats_to_send))
            for row in zabbix_locks:
                time_end_utc = datetime.strptime(row['time_end_utc'], '%Y-%m-%d %H:%M:%S')
                if dt_utc < time_end_utc:
                    rule_len = len(row['rules'])
                    nn = 0
                    for val in row['rules']:
                        if msg.upper().find(val.upper()) >= 0:
                            nn += 1
                    lgcl = row['logical']
                    if (rule_len == nn and lgcl == 'AND' or nn > 0 and lgcl == 'OR') \
                            and (severity in row['lvl'] or '*' in row['lvl']):
                        for val in row['tmplt']:
                            if val == '*':
                                try:
                                    chats_to_send.remove(row['chat_id'])
                                except Exception:
                                    pass
                            elif len(templates) == 0:
                                for zt in z.get_template_by_hostid(hostid):
                                    templates.append(zt['name'])
                            else:
                                for elem in templates:
                                    if elem.upper().find(val.upper()) >= 0:
                                        try:
                                            chats_to_send.remove(row['chat_id'])
                                        except Exception:
                                            pass
                else:
                    update_rules = True
            if importance != "*":
                msg = msg + "\nКритичность: " + str(importance)
            for ch in chats_to_send:
                res = tt.create_link(chat_id=ch, msg=msg, link_name="Просмотр проблемы в Zabbix", link=link)
                write_zabbix_alerts(id=id, mid=res['message']['body']['mid'])
            if update_rules:
                with redis_data() as r:
                    r.publish('action-channel', str({'action': 'ignore_rule'}))


def zabbix_thread(eventid: int, act: int, message: str):
    if act == 1:
        diag = f"\n\n*Диагностическая информация*\n{message}" if message != "" else ""
        with zbx() as z:
            res = z.get_event_detail(eventid=eventid, result=0)
        severity = int(res['result'][0]['severity'])
        trigger = res['result'][0]['objectid']
        descr = res['result'][0]['name']
        r_eventid = res['result'][0]['r_eventid']
        hostid = res['result'][0]['hosts'][0]['hostid']
        hostname = res['result'][0]['hosts'][0]['host']
        clock = res['result'][0]['clock']
        dt = datetime.fromtimestamp(int(clock))
        ret = descr
        if severity == 1:
            ret = '❕ Information\n' + ret
        elif severity == 2:
            ret = '❕ Warning\n' + ret
        elif severity == 3:
            ret = '❗ Уровень 5\n' + ret
        elif severity == 4:
            ret = '❗ Уровень 4\n' + ret
        elif severity == 5:
            ret = '❗ Уровень 3\n' + ret
        link = f"https://zabbix.domain.ru/tr_events.php?triggerid={trigger}&eventid={eventid}"
        if diag != "":
            with redis_data('redis_alarms') as r:
                r.set(f"zbx_diag_{eventid}", diag)
            mid_list = get_zabbix_mids(id=eventid)
            for mid0 in mid_list:
                chat_id0 = tt.get_message(mid=mid0)['recipient']['chat_id']
                tt.create_link(chat_id=chat_id0, msg='📊 Диагностическая информация', link_name='diagnostic',
                                link=f'http://bot-api.domain.ru:5002/zabbix_diag/{eventid}', reply_mid=mid0)
        else:
            send_to_chat_by_rule(msg=ret[0:3999], link=link, typ="zabbix", id=eventid, severity=severity, hostid=hostid, hostname=hostname)
    else:
        with redis_data('redis_alarms') as r:
            jsn = literal_eval(r.get(eventid))
        mids = jsn['mids']
        dtopen = jsn['timestamp']
        dtnow = datetime.utcnow() + timedelta(hours=3)
        dtnowstr = dtnow.strftime('%d.%m %H:%M')
        for mid in mids:
            msg = tt.get_message(mid=mid)
            chat_id = msg['recipient']['chat_id']
            text = '✅ Проблема ушла\n' + msg['body']['text'] + '\n\nРешено: ' + dtnowstr + '(мск)'
            link = msg['body']['attachments'][0]['payload']['buttons'][0][0]['url']
            link_name = msg['body']['attachments'][0]['payload']['buttons'][0][0]['text']
            tt.change_link(mid=mid, msg=text, link_name=link_name, link=link)
        r.delete(eventid)
        r.close()


def write_zabbix_alerts(id, mid):
    tm = datetime.timestamp(datetime.now())
    with redis_data('redis_alarms') as r:
        if r.get(str(id)) is not None:
            jsn = literal_eval(r.get(str(id)))
            jsn['mids'].append(mid)
            r.set(str(id), str(jsn))
        else:
            jsn = {"status": "open", "timestamp": f"{str(tm)}", "mids": [mid]}
            r.set(str(id), str(jsn))


def get_zabbix_mids(id):
    with redis_data('redis_alarms') as r:
        if r.get(str(id)) is not None:
            jsn = literal_eval(r.get(str(id)))
            r.close()
            return jsn['mids']
    return None

###############################################################
@app.route('/', methods=['GET'])
def hello_world():
    h = request.remote_addr
    return 'Yes, I am working at ' + h


@app.route('/zabbix_diag/<eventid>')
def zabbix_diag(eventid):
    with redis_data('redis_alarms') as r:
        data = r.get(f"zbx_diag_{eventid}").decode('utf-8')
    if data is None: data = 'По указанному событию информация отсутствует...'
    lst = '<div class="textwrapper"><textarea readonly rows="45" id="rules">'+data+'</textarea></div>'
    return render_template('diag.html', body=lst)


@app.route('/zabbix_alerts', methods=['GET'])
def show_zabbix_alerts():
    return 'none'


@app.route('/params', methods=['GET'])
def params():
    return "ZABBIX-RULES:<br>" + str(json.dumps(zabbix_rules, indent=4)).replace('\n', '<br>').replace(' ','&nbsp;') + "<br><br>" + \
           "ZABBIX-LOCKS:<br>" + str(json.dumps(zabbix_locks, indent=4)).replace('\n', '<br>').replace(' ','&nbsp;') + "<br><br>" + \
           "ZABBIX-TMPLT:<br>" + str(json.dumps(zabbix_templates, indent=4)).replace('\n', '<br>').replace(' ', '&nbsp;')


@app.route('/audit', methods=['POST'])
def audit():
    filenames = ''
    ff = open("inputjson.json", "a")
    for files in request.files:
        filenames = filenames + files
    ff.write(filenames)
    ff.write("\n")
    ff.close()
    return filenames


@app.route('/grafana', methods=['POST'])
def grafana():
    chat_ids = []
    jsn = request.json
    tags = jsn.get('tags')
    if tags is not None:
        by_chat_list = tags.get('chat_list')
        if by_chat_list:
            chat_ids = by_chat_list.replace(' ', '').split(',')
    with open('json/inputgrafana.txt', 'a') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {jsn}\n")
    imgpth = jsn.get('imageUrl')
    msg = jsn.get('message') if jsn.get('message') else ''
    link = jsn['ruleUrl']
    state = jsn['state']
    ruleid = jsn['ruleId']
    rulename = jsn['ruleName']
    link_name = 'Перейти в Grafana'
    evalMatches = ''
    for mtch in jsn['evalMatches']:
        evalMatches += f"{mtch['metric']} = {mtch['value']}\n"
    if evalMatches != '':
        msg = msg + '\n' + evalMatches
    time.sleep(5)
    fname = "temp/" + rand.rand_num_char(10) + ".png"
    if imgpth is not None:
        response = requests.get(url=imgpth, verify=False, stream=True, proxies=proxies)
        with open(fname, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response
    if state in ('ok', 'no_data'):
        for chat_id in chat_ids:
            tt.link_message(chat_id=chat_id, msg=f'✅ {rulename}\nПроблема ушла', mid=grafana_alerts[ruleid][chat_id])
        grafana_alerts.pop(ruleid)
    elif state == 'alerting' and str(rulename).find('AIR') < 0:
        for chat_id in chat_ids:
            if imgpth is not None:
                res = tt.send_image(chat_id=chat_id, msg='❗ ' + rulename + '\n' + msg, img_name=fname, link_name=link_name, link=link)
            else:
                res = tt.create_link(chat_id=chat_id, msg='❗ ' + rulename + '\n' + msg, link_name=link_name, link=link)
            mid = res['message']['body']['mid']
            if grafana_alerts.get(ruleid) is None:
                grafana_alerts[ruleid] = {chat_id: mid}
            else:
                grafana_alerts[ruleid][chat_id] = mid
    return "Ok"


@app.route('/jira', methods=['POST', 'PUT'])
def jira():
    json_in=request.json
    issuekey = request.args.get('issuekey','')
    with open(f"temp/{issuekey}.json", "w") as ff:
        ff.write(json.dumps(json_in))
    return "Ok"


@app.route('/zabbix', methods=['POST'])
def zabbix():
    eventid = int(request.form.get('eventid', 0))
    act = int(request.form.get('act', 0))
    message = request.form.get('message', '')
    zabbix_thread(eventid, act, message)
    return f"You've sent eventid - {eventid} ({act})"


@app.route('/prometheus', methods=['POST'])
def prometheus():
    json_in = request.json
    with open(f"temp/prometheus.json", "w") as ff:
        ff.write(json.dumps(json_in))
    return "Ok"


@app.route('/git', methods=['POST'])
def git():
    print(request.headers.get('Content-Type'))
    json_in = request.json
    with open(f"temp/git.json", "w") as ff:
        ff.write(json.dumps(json_in))
    return "Ok"

@app.route('/fsm', methods=['POST'])
def fsm():
    json_in = request.json
    with open(f"temp/fsm.json", "w") as ff:
        ff.write(json.dumps(json_in))
    return "Ok"

@app.route('/qfsm', methods=['POST'])
def qfsm():
    #{"type": "new/old", "source": "im", "vals": ["", "", "", ...]}
    json_in = request.json
    with open(f"temp/qfsm.json", "a") as ff:
        ff.write(json.dumps(json_in))
        ff.write("\n")
    qr = ""
    if json_in['source'] == "im": qr = qr_im
    if qr != "":
        for v in json_in['vals']:
            res = []
            try:
                with db_data(db_name='fsm') as db_fsm:
                    res = db_fsm.get_data(query=qr.replace('@ID@', v))
            except Exception as ex:
                LOG.critical(ex.__str__())
            if len(res) > 0:
                im_status = res[0]['STATUS']
                im_msg = res[0]['MSG']
                im_href = res[0]['HREF']
                status = '❗' if im_status == 'opened' else '✅ Решено\n'
                if json_in['type'] == "new":
                    res = tt.create_link(chat_id=-75098403045397, msg=status + im_msg, link_name='Посмотреть подробности',
                                            link=im_href)
                    with redis_data('redis_alarms') as r:
                        r.set(f"fsm_{v}", res['message']['body']['mid'])
                else:
                    with redis_data('redis_alarms') as r:
                        mid = r.get(f"fsm_{v}")
                    tt.change_link(mid=mid, msg=status + im_msg, link_name='Посмотреть подробности',
                                            link=im_href)
                    if im_status == 'closed':
                        with redis_data('redis_alarms') as r:
                            r.delete(f"fsm_{v}")
        return {"status": "Ok"}
    else:
        return {"error": "source is wrong, available values: im"}


@app.route('/zabbix-monitoring', methods=['POST'])
def monitoring():
    host_in = request.form.get('host','')
    switch_in = request.form.get('switch','')

    if host_in.strip() == '':
        return json.loads('{"error": "host is empty"}')
    elif str(switch_in).strip() == '' or str(switch_in).strip().lower() not in('on','off'):
        return json.loads('{"error":"switch allows values only on, off"}')
    else:
        try:
            with zbx() as z:
                host_list = []
                ret = z.get_host_list(host=host_in)
                if len(ret) == 0:
                    return {"error":"host not found"}
                for i in range(len(ret)):
                    host_list.append(ret[i]['hostid'])
                ret = z.get_itemvalue_by_key(key='Сервер БД', filter=host_in)
                for i in range(len(ret)):
                    host_list.append(ret[i]['hostid'])
                for i in range(len(host_list)):
                    z.activate_monitoring(hostid=host_list[i], on_off='off')
            return {"status":"ok"}
        except Exception:
            return {"error": "network error"}

# curl -X POST "http://127.0.0.1:5000/key-value/mh-params?hostname=test&oraclient=1"
# curl -X GET "http://127.0.0.1:5000/key-value/mh-params?hostname=test"

@app.route('/check-zabbix-monitoring/<host_in>', methods=['GET'])
def check_zabbix_monitoring(host_in):
    if host_in is None or host_in.strip() == '':
        return {"error": "host is empty"}
    else:
        try:
            with zbx() as z:
                ret = z.get_host_param(hosts=[host_in], output=['status'])
            if len(ret) > 0:
                val = ret[0].get("status")
                if val is None: val = "Unknown host"
                elif val == "0": val = "Activated"
                elif val == "1": val = "Deactivated"
                ret = {"status": val}
            else:
                ret = {"status": "Unknown host"}
            return ret
        except Exception:
            return {"error": "network error"}

# curl -X POST "http://127.0.0.1:5000/key-value/mh-params?hostname=test&oraclient=1"
# curl -X GET "http://127.0.0.1:5000/key-value/mh-params?hostname=test"

@app.route('/me', methods=['GET'])
def me():
    return request.remote_addr


@app.route('/key-value/<folder>', methods=['GET','POST'])
def common(folder):
    with redis_data('redis_common') as r:
        if request.method == 'POST':
            key = request.form.get('key','')
            value = request.form.get('value','')
            token = request.form.get('token','')

            if key != '' and value !='-' and token != '':
                r.set(folder+':'+key, value)
                return 'ok'
            else:
                return 'Wrong POST-method. Expecting: curl -X POST "http://API-HOST:API-PORT/key-value/YOUR-KEY-STORAGE?key=YOUR-KEY&value=YOUR-VALUE"'
        elif request.method == 'GET':
            key = request.args.get('key', '')
            if key != '':
                res = r.get(folder+':'+key)
                return res if res else "ERROR: key not found!"
            else:
                return 'Wrong GET-method. Expecting: curl -X GET "http://API-HOST:API-PORT/key-value/YOUR-KEY-STORAGE?key=YOUR-KEY"'


@app.route('/tamtam/<method>', methods=['GET','POST'])
def tamtam(method):
    if method == "send_message":
        chats = None
        msg = None
        link = None
        link_name = None
        links = None
        prm_type = str(request.headers.get('Content-type')).strip().lower()
        if request.method == 'POST':
            if prm_type.strip().lower() == 'application/json':
                chats = request.json.get('chat_list')
                msg = request.json.get('msg')
                link = request.json.get('link')
                link_name = request.json.get('link_name')
                links = request.json.get('links')
            else:
                chats = max(request.form.get('chat_list',''), request.args.get('chat_list',''))
                msg = max(request.form.get('msg',''), request.args.get('msg',''))
                link = max(request.form.get('link',''), request.args.get('link',''))
                link_name = max(request.form.get('link_name',''), request.args.get('link_name',''))
                links = max(request.form.get('links',''), request.args.get('links',''))
        else:
            msg = request.args.get('msg','')
            chats = request.args.get('chat_list','')
            link = request.args.get('link', '')
            link_name = request.args.get('link_name', 'go to link')
        err = False
        ret = {}
        if isinstance(chats, list):
            chat_list = chats
        else:
            chat_list = str(chats).replace('(', '').replace(')', '').replace('[', '').replace(']', '').split(",")
        res = ''
        try:
            res = msg.encode('iso-8859-1').decode('utf-8')
            # res = msg.encode('utf-8')
        except Exception:
            res = msg
        if res.strip() == '': err = True
        if err == False:
            for chat_id in chat_list:
                if chat_id != "":
                    l = 4000
                    # l = 10
                    iters = math.ceil(len(res) / l)
                    for nn in range(iters):
                        if link != '' and link is not None and nn == iters-1:
                            ret[chat_id] = (tt.create_link(chat_id=chat_id, msg=res[nn * l:(nn + 1) * l], link_name=link_name, link=link))
                        elif links is not None and nn == iters-1:
                            ret[chat_id] = (tt.create_link(chat_id=chat_id, msg=res[nn * l:(nn + 1) * l], links=links))
                        else:
                            ret[chat_id] = (tt.simple_message(chat_id=chat_id, msg=res[nn * l:(nn + 1) * l]))
                            sleep(1)
                else:
                    err = True
        if err:
            return "<div>Ключи:<br> chat_list - список чатов куда отправляем сообщение. Разделитель - запятая<br> msg - текст отправляемого сообщения</div>"
        else:
            return ret


def subscriptions(channel):
    with redis_data() as r:
        msg = r.subscribe(channel=channel)
        if msg:
            res = literal_eval(msg)['data']
            if res['action'] == 'ignore_rule':
                with db_data() as db:
                    db.ins_data("insert into t_subscriber_log values(sysdate, 'ignore_rule')")
                load_api_rules(once=True)
            elif res['action'] == 'refresh':
                load_api_rules(once=True)


@app.route('/gitlab-notify', methods=['POST'])
def gitlab_notify():
    json_data = request.get_json(force=True)

    allowed_actions = ('reopen', 'open', 'merge', 'close', 'approved', 'unapproved')
    mr_status_emoji = "🙏"
    chat_id = None
    check_mr_state = False
    chat_notify = False
    for arg in request.args:
        if arg == 'chat_id':
            chat_id = request.args['chat_id']

        if arg == 'check_mr_state':
            if request.args['check_mr_state'].lower() == 'true':
                check_mr_state = True

    if 'event_type' in json_data.keys() and json_data['event_type'] == 'merge_request':

        mr = json_data['object_attributes']
        project_name = json_data['project']['name']


        if 'action' in mr.keys() and mr['action'] in allowed_actions:

            user = json_data['user']['email']
            mr_status = mr['merge_status']
            mr_url = mr['url']
            target_branch = mr['target_branch']
            source_branch = mr['source_branch']
            mr_title = mr['title']
            mr_state = None

            msg_user = "User: {user}\n".format(user=user)

            if mr['action'] == 'close':
                mr_state = 'Merge request closed'
                mr_status_emoji = '❌'
                chat_notify = True

            elif mr['action'] in ('open', 'reopen'):
                mr_state = '{mr_action} merge request'.format(mr_action=mr['action'].capitalize())
                mr_status_emoji = '❗'
                chat_notify = True

            elif mr['action'] == 'merge':
                mr_state = 'Merged'
                mr_status_emoji = '✅🍻'
                chat_notify = True

            elif check_mr_state and mr['action'] == 'approved' and mr_status == 'can_be_merged':
                mr_state = 'Can be merged'
                mr_status_emoji = '☑'
                msg_user = None
                chat_notify = True

            elif check_mr_state and mr['action'] == 'unapproved' and mr_status == 'can_be_merged':
                mr_state = 'Merge request unapproved'
                mr_status_emoji = '🚫'
                chat_notify = True

            msg_state="{mr_status_emoji} *{mr_state}*\n".format(mr_status_emoji=mr_status_emoji, mr_state=mr_state)
            msg_project="Project: {mr_project}\n".format(mr_project=project_name)
            msg_title="Merge: {mr_title}\n".format(mr_title=mr_title)
            msg_branches="Branches: *{src_branch}* -> *{trg_branch}*\n".format(src_branch=source_branch,
                                                                             trg_branch=target_branch)


            full_msg = "{state}{project}{user}{title}{branches}".format(state=msg_state,
                                                                        project=msg_project,
                                                                        user=msg_user if msg_user else '',
                                                                        title=msg_title,
                                                                        branches=msg_branches)

            if chat_notify and chat_id:
                tt.create_link(chat_id=chat_id, msg=full_msg, link=mr_url, link_name="Merge request")
    return 'OK'


if __name__ == "__main__":
    Thread(target=subscriptions, args=('action-channel',)).start()
    Thread(target=load_api_rules).start()
    app.run(host='0.0.0.0', port=5009)
