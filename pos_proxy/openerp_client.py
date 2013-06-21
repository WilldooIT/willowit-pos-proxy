import xmlrpclib
import io


class ObjectInspector(object):
    HOST = "localhost"
    PORT = 8999
    uid = None  
    url = None
    obj = None
    def __init__(self,db,username,password,obj):
        self.USER = username
        self.PASS = password
        self.DB = db
        self.url = "http://%s:%d/xmlrpc/" % (self.HOST,self.PORT)
        self.login()
        self.obj = obj
        self.refresh()

    def pointTo(self,obj):
        self.obj = obj
        self.refresh()
    def execute(self,*args):
        object_proxy = xmlrpclib.ServerProxy(self.url + "object")
        return object_proxy.execute(self.DB,self.uid,self.PASS,*args)
    def call(self,*args):
        object_proxy = xmlrpclib.ServerProxy(self.url + "object")
        return object_proxy.execute(self.DB,self.uid,self.PASS,self.obj,*args)
        

    def login(self):
        common_proxy = xmlrpclib.ServerProxy(self.url + "common")
        self.uid = common_proxy.login(self.DB,self.USER,self.PASS)
        print "Login successful. UID: %d" % self.uid

    def refresh(self):
        self.cols = self.execute(self.obj,"fields_get")
    
    def search(self,domain=[]):
        return self.execute(self.obj,"search",domain)
    
    def read(self,ids="auto",fields=[]):
        if ids == "auto":
            ids = self.search()
        return self.execute(self.obj,"read",ids,fields)
    
    def write(self,ids,vals):
         return self.execute(self.obj,"write",ids,vals)

    def printTable(self,ids="auto",fields=[]):
        self.refresh()
        header = ""
        body = ""

        if fields == []:
            fields = self.cols.keys()

        for col in fields:
            header = header + col + "\t"
        header = header + "\n"
        header = header + ("=" * len(header.expandtabs()))
        print header

        rows = self.read(fields=self.cols.keys())
        for row in rows:
            for cell in fields:
                body = body + str(row[cell]) + "\t"     
            body = body +  "\n"

        print body





    
