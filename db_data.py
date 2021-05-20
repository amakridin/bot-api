import cx_Oracle as ora
import os
os.environ['NLS_LANG'] = 'American_America.AL32UTF8'
# use oracle client 32 bit
db_param = {
    	"crm": "user/pass@(db_tns)",
       "cmdb": "user/pass@(db_tns)",
       "fsm": "user/pass@(db_tns)"
       }

class db_data:
    def __init__(self, db_name=None, db_tns=None, db_user=None, db_pass=None):
        self._create_connection(db_name, db_tns, db_user, db_pass)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()
    def close_connection(self):
        self.con.commit()
        self.cur.close()
        self.con.close()
    def get_data(self, query):
        """
        returns data from database
        :param query: str
        :return: dict
        """
        self.query = query
        self.cur.execute(query)
        col_names = [row[0] for row in self.cur.description]
        dd = []
        for rez in self.cur:
            d = {}
            for i in range(len(rez)):
                d[col_names[i]] = str(rez[i])
            dd.append(d)
        return dd

    def set_data(self, query, commit=True, dict_binds={}):
        """
        insert, update or delete data
        :param query: (str) sql insert, update or delete command
        :return: Ok or error text
        """
        try:
            if len(dict_binds) > 0:
                self.cur.execute(query, dict_binds)
            else:
                self.cur.execute(query)
            if commit:
                self.con.commit()
            return 'Ok'
        except Exception as err:
            self.con.rollback()
            return err

    def commit(self):
        self.con.commit()



    def _create_connection(self, db_name=None, db_tns=None, db_user=None, db_pass=None):
        if db_pass is not None and db_tns is not None and db_user is not None and db_user.lower() == "sys":
            self.con = ora.connect(dsn=db_tns, user=db_user, password=db_pass, mode=ora.SYSDBA)
        elif db_pass is not None and db_tns is not None and db_user is not None and db_user.lower() != "sys":
            self.con = ora.connect(dsn=db_tns, user=db_user, password=db_pass)
        elif db_name is not None or db_name is None and db_tns is None and db_pass is None:
            db_par = db_param["crm" if db_name is None else db_name]
            self.con = ora.connect(db_par)
        self.cur = self.con.cursor()



if __name__ == "__main__":
    db = db_data()
    print(db.get_data("select * from dual"))
