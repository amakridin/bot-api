import redis
from get_params import get_config


class redis_data:
    def __init__(self, db_name: str = ''):
        redis_host = get_config('redis_host')
        redis_port = get_config('redis_port')
        redis_password = get_config('redis_password')
        redis_db = 0 if db_name == '' else get_config(db_name)
        self.con = redis.Redis(host=redis_host, port=redis_port, db=redis_db, password=redis_password)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.con.close()

    def get_data(self, key: str):
        return self.con.get(name=key).decode()

    def set_data(self, key: str, value: str):
        return self.con.set(name=key, value=value)

    def delete_data(self, key):
        return self.con.delete(key) == 1

    def publish(self, channel: str, msg: str):
        return self.con.publish(channel=channel, message=msg)

    def subscribe(self, channel: str):
        p = self.con.pubsub()
        p.subscribe(channel)
        while True:
            msg = p.get_message(ignore_subscribe_messages=True, timeout=60)
            if msg:
                return {'channel': msg['channel'].decode(), 'data': msg['data'].decode()}
if __name__ == "__main__":
    with redis_data("redis_common") as r:
        print(r.subscriptions("common"))