from os import path
def get_query(query_name):
    qr = ""
    db = "crm"
    with open(path.join("sql",query_name), encoding="utf-8") as f: qr = f.read()
    qr = qr.splitlines()
    if qr[0].find("@") >= 0:
        db = qr[0].replace("@","")
        qr.pop(0)
    qr = "\n".join(qr)
    return {"query": qr, "db_name": db}

