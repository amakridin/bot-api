import json
import requests

proxies = {'http': 'proxy.domain.ru:3128', 'https': 'proxy.domain.ru:3128'}
smile_list = {'@emergency@': '🚑',
              '@health_ok@': '😎',
              '@health_middle@': '🤧',
              '@health_bad@': '🤒',
              '@on@':'✅',
              '@off@': '✖️',
              '@mood_good@':'👍',
              '@mood_bad@':'👎'}


class send2tamtam:
    def __init__(self, token: str):
        self.token = token

    def simple_message(self, chat_id, msg):
        json_init = {"text": f"{msg}"}
        url_init = f'https://botapi.tamtam.chat/messages?chat_id={chat_id}&access_token={self.token}'
        return requests.post(url_init, data=json.dumps(json_init), proxies=proxies).json()

    def create_link(self, chat_id, msg, link_name='', link='', links=[], reply_mid=''):
        link_list = []
        if link != '':
            link_list = [[{"type": "link", "text": f"{link_name}", "url": f"{link}", "intent": "default"}]]
        elif links != []:
            for row in links:
                link_list.append(
                    [{"type": "link", "text": f"{row['link_name']}", "url": f"{row['link']}", "intent": "default"}])
        if reply_mid == '':
            json_init = {"text": f"{msg}",
                         "attachments": [{"type": "inline_keyboard", "payload": {"buttons": link_list}}]}
        else:
            json_init = {"text": f"{msg}", "link": {"type": "reply", "mid": f"{reply_mid}"},
                         "attachments": [{"type": "inline_keyboard", "payload": {
                             "buttons": [
                                 [{"type": "link", "text": f"{link_name}", "url": f"{link}", "intent": "default"}]]}}]}
        url_init = f'https://botapi.tamtam.chat/messages?chat_id={chat_id}&access_token={self.token}'
        return requests.post(url_init, data=json.dumps(json_init), proxies=proxies).json()

    def get_message(self, mid):
        url_init = f"https://botapi.tamtam.chat/messages/{mid}/?access_token={self.token}"
        return requests.get(url_init, proxies=proxies).json()

    def change_link(self, mid, msg, link_name, link):
        json_init = {"text": f"{msg}", "attachments": [{"type": "inline_keyboard", "payload": {
            "buttons": [[{"type": "link", "text": f"{link_name}", "url": f"{link}", "intent": "default"}]]}}]}
        url_init = f"https://botapi.tamtam.chat/messages?message_id={mid}&access_token={self.token}"
        return requests.put(url_init, data=json.dumps(json_init), proxies=proxies).json()

    def link_message(self, chat_id, msg, mid, msg_type="reply"):
        """
        :param chat_id:
        :param msg:
        :param mid:
        :param msg_type: forward / reply
        :return:
        """
        json_init = {"text": f"{msg}", "link": {"type": msg_type, "mid": f"{mid}"}}
        url_init = f'https://botapi.tamtam.chat/messages?chat_id={chat_id}&access_token={self.token}'
        return requests.post(url_init, data=json.dumps(json_init), proxies=proxies).json()

    def send_image(self, chat_id, msg, img_name, link_name='', link=''):
        url = f'https://botapi.tamtam.chat/uploads?type=image&access_token={self.token}'
        ret = requests.post(url=url, verify=False, proxies=proxies)
        jsn = json.loads(ret.content)
        url_load = jsn['url']
        files = {'request_file': open(img_name, 'rb')}
        r = requests.post(url=url_load, files=files, proxies=proxies, verify=False)
        ret = json.loads(r.content)
        for key in (ret['photos'].keys()):
            url_token = ret['photos'][key]['token']
            if link_name == '':
                json_init = {"text": f"{msg}", "attachments": [{"type": "image", "payload": {"token": f"{url_token}"}}]}
            else:
                json_init = {"text": f"{msg}", "attachments": [{"type": "image", "payload": {"token": f"{url_token}"}},
                                                               {"type": "inline_keyboard", "payload": {"buttons": [[{
                                                                                                                        "type": "link",
                                                                                                                        "text": f"{link_name}",
                                                                                                                        "url": f"{link}",
                                                                                                                        "intent": "default"}]]}}]}
            url_init = f'https://botapi.tamtam.chat/messages?chat_id={chat_id}&access_token={self.token}'
            json_ret = requests.post(url_init, data=json.dumps(json_init), proxies=proxies).json()
            return json_ret
