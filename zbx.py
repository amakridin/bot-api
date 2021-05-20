import requests
from datetime import datetime
zbx_user = 'user'
zbx_pass = 'password'
url_init = 'https://zabbix.domain.ru/api_jsonrpc.php'


class zbx:
    def __init__(self):
        headers = {'content-type': 'application/json-rpc'}
        json_init = {"jsonrpc": "2.0",
                     "method": "user.login",
                     "params": {
                         "user": zbx_user,
                         "password": zbx_pass},
                     "id": 1}
        res = requests.post(url_init, json=json_init, verify=False, headers=headers).json()
        self.token = None
        if res.get('result'):
            self.token = res['result']

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()

    def get_templates(self):
        res = {}
        json_init = {
            "jsonrpc": "2.0",
            "method": "template.get",
            "params": {"output": "extend"},
            "auth": self.token,
            "id": 1}
        for row in self.__get_request(json_init=json_init)['result']:
            res[row['templateid']] = row['name']
        return res

    def get_template_by_hostid(self, hostid):
        json_init = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {
                "output": ["hostid"],
                "selectParentTemplates": ["templateid", "name"],
                "hostids": hostid
            },
            "id": 1,
            "auth": self.token}
        return self.__get_request(json_init=json_init)['result'][0]['parentTemplates']

    def get_event_detail(self, eventid, result=1):
        ret = []
        json_init = {
            "jsonrpc": "2.0",
            "method": "event.get",
            "params": {
                "output": "extend",
                "selectRelatedObject": "extend",
                "selectHosts": "extend",
                "select_alerts": "extend",
                "eventids": eventid},
            "auth": self.token,
            "id": 1}
        answ = self.__get_request(json_init=json_init)
        if result == 1:
            for i in range(len(answ['result'])):
                for hh in range(len(answ['result'][i]['hosts'])):
                    if answ['result'][i]['hosts'][hh]['status'] == str(0):
                        ret.append({'hostid': answ['result'][i]['hosts'][hh]['host'],
                                   'hostname': answ['result'][i]['hosts'][hh]['host'],
                                   'triggerid': answ['result'][i]['relatedObject']['triggerid'],
                                   'clock': str(datetime.fromtimestamp(int(answ['result'][i]['clock'])))})
            return ret
        else:
            return answ

    def get_host_list(self, host='', templateid=0):
        ret = []
        json_init = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {"output": ["hostid", "host"]},
            "auth": self.token,
            "id": 1}
        if templateid > 0:
            json_init["params"]["templateids"] = templateid
        if len(host) > 0 and len(host) == len(host.replace('%', '')):
            json_init["params"]["filter"] = {"host": [host]}
        for row in self.__get_request(json_init=json_init)['result']:
            dic = {'host_id': row['hostid'], 'host': row['host']}
            if len(host) > len(host.replace('%', '')):
                if row['host'].replace(host.replace('%', ''), '') != row['host']:
                    ret.append(dic)
            else:
                ret.append(dic)
        return ret

    def get_itemvalue_by_key(self, key, filter=''):
        ret = []
        json_init = {
            "jsonrpc": "2.0",
            "method": "item.get",
            "params": {"output": ["hostid", "lastvalue"], "search": {"name": key}},
            "id": 1,
            "auth": self.token}
        answ = self.__get_request(json_init=json_init)
        for i in range(len(answ['result'])):
            dic = {}
            if filter is not '':
                if str(answ['result'][i]['lastvalue']).lower().find(filter.lower()) >= 0:
                    dic['hostid'] = answ['result'][i]['hostid']
                    dic['value'] = answ['result'][i]['lastvalue']
                    ret.append(dic)
            else:
                dic['hostid'] = answ['result'][i]['hostid']
                dic['value'] = answ['result'][i]['lastvalue']
                ret.append(dic)
        return ret

    def activate_monitoring(self, hostid, on_off):
        # on_off - on/off
        if on_off.lower() not in ('on', 'off'):
            return None
        if on_off == 'on':
            json_init = {
                "jsonrpc": "2.0",
                "method": "host.update",
                "params": {"hostid": hostid, "status": 0},
                "auth": self.token,
                "id": 1}
        else:
            json_init = {
                "jsonrpc": "2.0",
                "method": "host.update",
                "params": {"hostid": hostid, "status": 1},
                "auth": self.token,
                "id": 1}
        return self.__get_request(json_init=json_init)

    def get_host_param(self, hosts, output, templateid=0):
        # hosts  has type of list [], ex: hosts=["hostname1","hostname2"]
        # output has type of list [], ex: output=["hostid","name","status"]
        ret = []
        json_init = {
            "jsonrpc": "2.0",
            "method": "host.get",
            "params": {"filter": {"host": hosts}, "output": output},
            "auth": self.token, "id": 1}
        if templateid > 0:
            json_init['params']['templateids'] = str(templateid)
        answ = self.__get_request(json_init=json_init)
        for row in answ['result']:
            dic = {}
            for param in output:
                dic[param] = row[param]
            ret.append(dic)
        return ret

    def close_connection(self):
        if self.token:
            headers = {'content-type': 'application/json-rpc'}
            json_init = {"jsonrpc": "2.0",
                         "method": "user.logout",
                         "params": [],
                         "id": 1,
                         "auth": self.token}
            res = requests.post(url_init, json=json_init, verify=False, headers=headers).json()
            if res.get('result'):
                return True
            else:
                return False
        else:
            return False

    def __get_request(self, json_init):
        headers = {'content-type': 'application/json-rpc'}
        rez = requests.post(url=url, json=json_init, verify=False, headers=headers)
        return rez.json()


