import random
def rand_num(len):
    return get_rand("0123456789", len)
def rand_num_char(len):
    return get_rand("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", len)
def rand_num_char_symb(len):
    return get_rand("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+", len)
def get_rand(str, len):
    psw = ""
    for i in range(len):
        p = random.choice(list(str))
        psw = psw + p
    return psw