from osv import osv, fields
import math

def check_ean(eancode):
    if not eancode:
        return True
    try:
        int(eancode)
    except:
        return False
    
    if len(eancode) in [12, 13]:
        oddsum=0
        evensum=0
        total=0
        eanvalue=eancode
        reversevalue = eanvalue[::-1]
        finalean=reversevalue[1:]

        for i in range(len(finalean)):
            if (not i%2):
                oddsum += int(finalean[i])
            else:
                evensum += int(finalean[i])
        total=(oddsum * 3) + evensum

        check = int(10 - math.ceil(total % 10.0)) %10

        if check != int(eancode[-1]):
            return False
        return True
    else:
        return False

class Product(osv.osv):
    _inherit = "product.product"
    

    def _check_ean_key(self, cr, uid, ids, context=None):
        for product in self.browse(cr, uid, ids, context=context):
            res = check_ean(product.ean13)
        return res
    _columns = {
        "ean13":fields.char("Barcode",size=13,help="Barcode")
    }

    _constraints = [(_check_ean_key,"Error, invalid barcode",['ean13'])]


