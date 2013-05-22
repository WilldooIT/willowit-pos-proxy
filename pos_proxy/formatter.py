import sys
import re
from cStringIO import StringIO

test = {u'cashier': u'POS User',
                          u'change': 0,
                          u'client': None,
                          u'company': {u'company_registry': False,
                                       u'contact_address': u'\n\n  \n',
                                       u'email': False,
                                       u'name': u'Premium Importers',
                                       u'phone': "555-5555",
                                       u'vat': False,
                                       u'website': u'www.premiumimporters.com.sg'},
                          u'currency': {u'id': 38,
                                        u'position': u'after',
                                        u'symbol': u'$'},
                          u'date': {u'date': 25,
                                    u'day': 5,
                                    u'hour': 8,
                                    u'minute': 43,
                                    u'month': 0,
                                    u'year': 2013},
                          u'invoice_id': None,
                          u'name': u'Order 1359063770780',
                          u'orderlines': [{u'discount': 0,
                                           u'price': 26.57,
                                           u'price_with_tax': 28.4299,
                                           u'price_without_tax': 26.57,
                                           u'product_description': u'Colour: Brick Red\n\nAromatics: Black Plum, wild blackcurrant and soft soy sauce characters. Seasoned oak overtones.\n\nPalate: Dark current and red fruits are showing through here with hints of eucalypt and American oak.',
                                           u'product_description_sale': u'Colour: Brick Red\n\nAromatics: Black Plum, wild blackcurrant and soft soy sauce characters. Seasoned oak overtones.\n\nPalate: Dark current and red fruit',
                                           u'product_name': u'Genesis Barossa Shiraz',
                                           u'quantity': 1,
                                           u'tax': 1.8599000000000001,
                                           u'unit_name': u'Unit(s)'},
                                          {u'discount': 0,
                                           u'price': 17.48,
                                           u'price_with_tax': 18.703600000000002,
                                           u'price_without_tax': 17.48,
                                           u'product_description': u'A true vintage style sparkling made from hand picked and whole bunch pressed Pinot Noir followed by at least 5 years lees aging.',
                                           u'product_description_sale': u'A true vintage style sparkling made from hand picked and whole bunch pressed Pinot Noir followed by at least 5 years lees aging.',
                                           u'product_name': u' Cosham Methode Champenoise',
                                           u'quantity': 1,
                                           u'tax': 1.2236000000000002,
                                           u'unit_name': u'Unit(s)'},
                                          {u'discount': 0,
                                           u'price': 19.57,
                                           u'price_with_tax': 20.939900000000002,
                                           u'price_without_tax': 19.57,
                                           u'product_description': u'Pretty aroma of strawberries and  red cherries.\nThe palate displays a soft, creamy entry with flavours of strawberries and cream leading to the more savoury flavours of tart cherry and spice.  The palate has great intensity and length making this and excellent food wine.',
                                           u'product_description_sale': u'Pretty aroma of strawberries and  red cherries.\nThe palate displays a soft, creamy entry with flavours of strawberries and cream leading to the more s',
                                           u'product_name': u'Rowanston on the Track 2010 Sparkling Pinot',
                                           u'quantity': 1,
                                           u'tax': 1.3699000000000001,
                                           u'unit_name': u'Unit(s)'}],
                          u'paymentlines': [{u'amount': 68.073399999999992,
                                             u'journal': u'POS Eftpos (SGD)'}],
                          u'shop': {u'name': u'Premium Importers'},
                          u'total_paid': 68.073399999999992,
                          u'total_tax': 4.4534000000000002,
                          u'total_with_tax': 68.073399999999992,
                          u'total_without_tax': 63.619999999999997} 
COL_WIDTH=42

class Formatter():
    def __init__(self,cookbook,default_recipe,col_width=COL_WIDTH,destination="printer"):
        self.col_width = col_width
        self.default_recipe = default_recipe
        self.cookbook = self.prepare_cookbook(cookbook)
        self.destination = destination
        if destination == "printer":
            self.control_codes = {
                   "c_b_on":"\x1b!\x08",
                   "c_b_off":"\x1b!\x00",
                   "c_u_on":"\x1b!\x80",
                   "c_u_off":"\x1b!\x00",
                   "c_bu_on":"\x1b!\x88",
                   "c_f_big_on":"\x1d!\x11\x1db\x01",
                   "c_f_big_off":"\x1d!\x00",
                   "c_f_prestige":"\x1b\x6b\x03",
                   "c_f_sans":"\x1b\x6b\x01",
                   "c_cut":"\x1d\x56\x42\x04",
                   "c_open_draw":"\x1b\x70\x30\x37\x79",
                   "c_logo":"\x1d\x28\x4c\x06\x00\x30\x45ML\x01\x01"
            }
        else:
            self.control_codes = {}

    def line(self,c="-",width=None):
        width = width or self.col_width
        return c * width

    def truncate(self,line,col_width=None):
        col_width = col_width or self.col_width
        if len(line) > col_width:
            return line[:col_width]
        else:
            return line
        
    def center(self,line,col_width=None,_truncate=False,pad_char=" "):
        col_width = col_width or self.col_width
        if _truncate:
            line = self.truncate(line)

        margin = pad_char * int((col_width - len(line))/2)
        return margin + line + margin

    def right(self,line,col_width=None,_truncate=False,pad_char=" "):
        col_width = col_width or self.col_width
        if _truncate:
            line = self.truncate(line)
        
        padding = pad_char * (col_width - len(line))
        return padding + line

    def nl(self,char="\n"):
        return char

    def justify(self,lhs,rhs,col_width=None):
        col_width = col_width or self.col_width
        if len(lhs) + len(rhs) - 2 >= col_width:
            return lhs + self.nl() +  self.right(rhs)
        else:
            return lhs.strip() + self.right(rhs,col_width=col_width-len(lhs.strip()))

    def cookline(self,style='I',line1="",line2=""):
        #this function looks at the command (the first character) and 
        # lays out a line accordingly. Any symbols have already been expanded. 
        #Each command can have 0,1 or 2 arguments, separated by ::

        if len(style) > 0 and style[0] == "!":
            if line1 == "":
                return ""
            else:
                style = style[1:]
        elif style == 'O':
            if line2.strip() in ["","0","0.0",False,"false","False","null","None","undefined"]:
                return ""
            else:
                return self.center(line1) + self.nl()
        elif style == 'C':
            return self.center(line1) + self.nl()
        elif style == 'T':
            return "\x1d!\x11\x1db\x01" + self.center(line1,col_width=self.col_width/2) + "\x1d!\x00" + self.nl()
        elif style == 'R':
            return self.right(line1) + self.nl()
        elif style in  ['L','&']:
            return line1 + self.nl()
        elif style == 'J':
            return self.justify(line1.strip(),line2.strip()) + self.nl()
        elif style == 'N':
            return self.nl()
        elif style == '-':
            return self.line() + self.nl()
        elif style == "I":
            return line1
        else:
            return self.nl()

            
    def cook(self,cookbook=None,recipe=None,vals={}):
        recipe = recipe or self.default_recipe
        cookbook = cookbook or self.cookbook

        if self.destination=="printer":
            vals.update(self.control_codes)
        output = ""
        for raw_line in cookbook[recipe]:
            cmd = raw_line.split("::")
            if len(cmd) <= 1:
                output += apply(self.cookline,cmd)
                continue
            lines = cmd[1:]
            new_lines = []
            for line in lines:
                done = False
                new_line = ""
                while not done:
                    #scan the line for any symbols (words starting with @) and substitute for values from the receipt
                    result = re.search("@[a-z0-9_@]+",line)
                    if result:
                        sym = line[result.start()+1:result.end()]
                        if cmd[0] == "&" and sym in cookbook.keys():
                            #if the command (the first char) is an ampersand, then we take the symbol that we found and 
                            # apply the recipe from the cookbook with the symbols name to the value
                            # in vals ( which needs to be a list of dictionaries). 
                            new_line = [self.cook(cookbook,recipe=sym,vals=r_line) for r_line in  vals[sym]]
                            new_line = reduce(lambda a,b: a + b,new_line,"")
                            new_lines.append(new_line)
                            done = True
                            break
                        prefix = line[:result.start()]
                        suffix = line[result.end():]
                        if sym == "@":
                            new_line += prefix + "@"
                        else:
                            new_line += prefix + str(vals.get(sym,""))
                        line = suffix
                    else:
                        new_line += line
                        new_lines.append(new_line)
                        done = True
            output +=  apply(self.cookline,[cmd[0]] + new_lines)
        return output

    def prepare_cookbook(self,raw_cookbook):
        recipes = map(lambda a: a.splitlines(),filter(lambda b: b, raw_cookbook.split("//")))
        result = {}
        for recipe in recipes:
            result[recipe[0]] = filter(lambda a: a not in ["","\n"],recipe[1:]) 
        return result


                    
    def prepare_receipt_vals(self,receipt=test):
        vals = {}
        vals["company_name"] = receipt["company"]["name"]
        vals["company_website"] = receipt["company"]["website"]
        vals["company_phone"] = receipt["company"]["phone"]
        vals["lines"] = []
        for l in receipt["orderlines"]:
            line = {}
            line["qty"] = l["quantity"]
            line["name"] = self.truncate(l["product_name"].strip())
            line["unit"] = l["unit_name"]
            line["price_unit"] = "%.2f" % l["price"]
            line["line_subtotal"] = "%.2f" % l["price_without_tax"]
            line["discount"] = l["discount"]
            vals["lines"].append(line)
        vals["date"] = "%0.2d/%0.2d/%0.4d %0.2d:%0.2d" %   (receipt["date"]["date"],
                                                    receipt["date"]["month"]+1,
                                                    receipt["date"]["year"],
                                                    receipt["date"]["hour"],
                                                    receipt["date"]["minute"])
        
        vals["subtotal"] = receipt["total_without_tax"]
        vals["gst"] = "%.2f" % receipt["total_tax"]
        vals["ref"] = receipt["name"]
        vals["salesperson"] = receipt["cashier"]

        payment_lines = StringIO()
        vals["total"]  = "%.2f" % receipt["total_with_tax"]
        vals["total_paid"]  = "%.2f" % receipt["total_paid"]
        change_amt = receipt["total_paid"] - receipt["total_with_tax"]
        
        vals["change"] = "%.2f" % change_amt
        vals["payment_lines"] = []
        is_cash_sale = False
        for l in receipt["paymentlines"]:
            line = {}
            line["journal"] = l["journal"]
            if line["journal"] == "CASH (SGD)":
                is_cash_sale = True           
            line["amount"] = "%.2f" % l["amount"]
            vals["payment_lines"].append(line)
        vals["is_refund"] = receipt["transaction_mode"] == "refund"
        vals["is_adjustment"] = receipt["transaction_mode"]  in ["w_on","w_off"]
        vals["is_tasting"] = receipt["transaction_mode"]  == "tstng"
        vals["receipt_type"] = receipt["receipt_type"]
        vals["is_cash_sale"] = is_cash_sale 
        return vals


    def print_receipt(self,receipt):
        return self.cook(cookbook=self.cookbook,recipe="receipt",vals=self.prepare_receipt_vals(receipt))







