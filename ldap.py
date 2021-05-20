import ldap3
from get_params import get_config

ldap_root = 'DC=Domain,DC=ru'
login = get_config('login') + '@domain.ru'
passw = get_config('password')
ldap_server = get_config('ldap_server')
def __get_ldap_data(search_filter, attrs):
    server = ldap3.Server('ldap://{}'.format(ldap_server))
    with ldap3.Connection(server, user=login, password=passw) as conn:
        conn.search(ldap_root, search_filter, attributes=attrs)
        return conn.entries

def get_data(search_filter, attr, filter_attr='mail'):
    search_filter = f"(&({filter_attr}={search_filter}))"
    attrs = [attr]
    ret = __get_ldap_data(search_filter, attrs)
    if ret != []:
        ret = str(ret).splitlines()[1].strip()
        ret = ret[ret.find(':') + 1:].strip()
        return ret
    else:
        return



