from werkzeug import Request, Response
from werkzeug.serving import run_simple
from socket import socket
from threading import Timer,Lock
from openerp_client import ObjectInspector
import pprint
import json
import formatter
import shelve
import datetime 
import ast
            
class PosProxy:
    """
The PosProxy class listens for jsonrpc calls from the openerp POS. 
The main loop is the "application" function that is called upon an incoming request.
Requests are dispatched based upon the request path. 
    """
    config = {}

    def __init__(self):
        """
        This method will load the config file, and then loop over all of the printers configured within, setting up the predicate value for use later on.
        """
        self.config = json.load(open("config.json"))
        cookbook = open(self.config["cookbook"]).read()

        self.printers = {}
        for (p_name,printer) in self.config["printers"].iteritems():
            printer["formatter"] = formatter.Formatter(cookbook,"receipt",printer["col_width"],printer["destination"])
            active = printer["active"]
            try:
                if active:
                    predicate_str = printer.get("predicate")
                    if predicate_str:
                        predicate = eval(printer["predicate"])
                        if type(predicate) == type(lambda a:a):
                            printer["predicate"] = predicate
                        else:
                            raise ValueError("Predicate must be a function")
            except Exception as e:
                print "Error with predicate, disabling printer %s" % p_name
                print e
                active = False
                
            if active:
                self.printers[p_name] = printer
        self.vfd_formatter = formatter.Formatter(cookbook,"vfd_motd",self.config["vfd_col_width"],"vfd")
        self.vfd_motd()


    def run(self):
        """
        This is the main handler loop for incoming web requests. 
        """
        @Request.application
        def application(request):
            if request.path == "/pos/print_receipt":
                if request.method == "POST":
                    r = request.form.get("r")
                    if not r:
                        return Response("")
                    rpccall = json.loads(r)
                elif request.method == "GET":
                    r = request.args.get("r")
                    if not r:
                        return Response("")
                    rpccall = json.loads(r)
                receipt = rpccall["params"]["receipt"]
                self.print_receipt(receipt)
                return Response("")
            elif request.path == "/pos/reprint_receipt":
                r = request.args.get("receipt")
                if not r:
                    print "Empty receipt"
                    return Response("FAIL")
                receipt = ast.literal_eval(r)
                receipt["is_reprint"] = True
                self.print_receipt(receipt)
                return Response("OK")
            elif request.path == "/pos/display_product":
                #r = request.args.get("r")
                #rpc_call = json.loads(r)
                #name = rpc_call["params"]["name"]
                #price = rpc_call["params"]["price"]
                #discount = rpc_call["params"]["discount"]
                #self.vfd_cook("vfd_item",{"name":name,"price":price,"discount":discount}) , 
                return Response("")
            else:
                return Response("")
        run_simple("0.0.0.0",self.config["listen_port"],application)
    

            

    def print_receipt(self,receipt):
        """
        Print a receipt to all of the active printers.
        """
        self._print_receipt(receipt)
        change = receipt["total_paid"] - receipt["total_with_tax"]
        self.vfd_change(change)
        Timer(self.config["vfd_clear_after"],lambda : self.vfd_motd()).start()

    def _print_receipt(self,receipt):
        for (p_name,printer) in self.printers.iteritems():
            for receipt_type in printer["receipt_types"]:
                receipt["receipt_type"] = receipt_type
                do_print = True
                receipt_vals = printer["formatter"].prepare_receipt_vals(receipt)
                if printer.get("predicate"):
                    predicate = printer["predicate"]
                    do_print = predicate(receipt_vals)

                if do_print:
                    output = printer["formatter"].print_receipt(receipt_vals)
                    if printer["type"] == "local":
                        print "attempting to print to printer '%s' (%s)" % (p_name,receipt["receipt_type"])
                        try:
                            printer_file = open(printer["device"],"w")
                            printer_file.write(output)
                            printer_file.flush()
                            printer_file.close()

                        except Exception,e:
                            print e
                    elif printer["type"] == "network":
                        print "attempting to print to printer '%s' (%s)" % (p_name,receipt["receipt_type"])
                        try:
                            s = socket()
                            s.settimeout(5.0)
                            s.connect((printer["address"],printer["port"]))
                            s.sendall(output)
                            s.close()
                        except Exception,e:
                            print e
                else:
                    print "Did not print to %s, predicate was false" % p_name

    def vfd_display(self,line1="",line2=""):
        out = "\x1b\x40\x1f\x24\x01\x01%s\x1f\x24\x01%s" % (self.vfd_formatter.truncate(line1),
                                                            self.vfd_formatter.truncate(line2))
        f = open(self.config["vfd_device"],"w")
        f.write(out)
        f.flush()
        f.close()

    def vfd_cook(self,recipe="vfd_motd",vals={}):
        res = self.vfd_formatter.cook(recipe=recipe,vals=vals)
        res = filter(lambda a:a,res.split("\n"))
        line1 = res[0]
        if len(res) >= 2:
            line2 = res[1]
        else:
            line2 = ""
        self.vfd_display(line1,line2)

    def vfd_change(self,change):
        vals = {"change":"%.2f" % change}
        self.vfd_cook(recipe="vfd_change",vals=vals)

    def vfd_motd(self):
        self.vfd_cook()

if __name__ == "__main__":
    PosProxy().run()
