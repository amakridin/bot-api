import redis
import os
from file_read_backwards import FileReadBackwards

def get_config(param):
    ret = ''
    with FileReadBackwards(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config'), encoding="utf-8") as f:
        for line in f:
            s = line.replace('\n', '')
            if s[0:1] != '#' and s[0:s.find(':')] == param:
                ret = s[s.find(':') + 1:].strip()
    if ret == '':
        ret = r.get("bot:"+param)
        if ret is not None:
            ret = ret.decode('utf-8')

    return ret

def get_login_by_user_id(user_id):
    from get_db_data import get_data
    f_login = ''
    for row in get_data(query=f"select lower(email) email from crm.v_bot_users a where chat_type = 1 and user_id={user_id}")['rows']:
        f_login = row['EMAIL']
        f_login = f_login[0:f_login.find('@')]
    return f_login
def get_email_by_user_id(user_id):
    from get_db_data import get_data
    f_login = ''
    for row in get_data(query=f"select lower(email) email from crm.v_bot_users a where chat_type = 1 and user_id={user_id}")['rows']:
        f_login = row['EMAIL']
    return f_login
def get_short_login_by_user_id(user_id):
    from get_db_data import get_data
    import ldap
    f_login = '#USER_NOT_FOUND'
    is_valid = 0
    for row in get_data(query=f"select lower(email) email, is_valid from crm.v_bot_users_all a where chat_type = 1 and user_id={user_id}")['rows']:
        f_login = row['EMAIL']
        is_valid = int(row['IS_VALID'])
        if is_valid == 0:
            f_login = "#USER_LOCKED"
        else:
            f_login = ldap.get_data(search_filter=f_login, attr='sAMAccountName')
    return f_login

def get_dialog_by_user_id(user_id):
    from get_db_data import get_data
    dialog = ''
    for row in get_data(query=f"select chat_id from crm.v_bot_users a where chat_type = 1 and user_id={user_id}")['rows']:
        dialog = row['CHAT_ID']
    return dialog

def get_root_id_by_user_id(user_id):
    from get_db_data import get_data
    root_id, root_id1 = -404, -404
    email = ""
    for row in get_data(query=f"select lower(email) email, nvl(root_id,-404) root_id from crm.v_bot_users a where chat_type = 1 and user_id={user_id}")['rows']:
        email = row['EMAIL']
        root_id1 = int(row['ROOT_ID'])
    if email not in('','None'):
        for row in get_data(query=f"select crm.f_bot_get_root_id('{email}') root_id from dual")['rows']:
            root_id = row['ROOT_ID']
    if int(root_id) == -404:
        return root_id1
    else:
        return root_id

r = redis.Redis(host=get_config('redis_host'), port=get_config('redis_port'), db=get_config('redis_common'), password=get_config('redis_password'))
###########################
if __name__ == "__main__":
    print(get_config('redis_common'))
    # print(get_login_by_user_id(592317409301))
    # print(get_email_by_user_id(592317409301))
    # print(get_short_login_by_user_id(592317409301))
    # print(get_root_id_by_user_id(580931735430))
    # print(get_dialog_by_user_id(592317409301))