from osv import osv,fields
from tools import DEFAULT_SERVER_DATE_FORMAT
import time
class ProductPackaging(osv.osv):
    _inherit = "product.packaging"

    def _check_ean_key(self, cr, uid, ids, context=None):
        return True
    
    def _get_price_for_package(self,cr,uid,ids,field,args,context=None):
        res = {}
        pricelist_item_obj = self.pool.get("product.pricelist.item")
        pricelist_obj = self.pool.get("product.pricelist")
        pricelist_version_obj = self.pool.get("product.pricelist.version")
        irp_obj = self.pool.get("ir.property")

        for pack in self.browse(cr,uid,ids,context=context):
            pricelist_id = irp_obj.get(cr,uid,"property_product_pricelist","res.partner",context=context).id
            pack_qty = True and pack.qty or 1
            pack_price = pricelist_obj.price_get(cr,uid,[pricelist_id],
                                                pack.product_id.id,pack_qty,False,
                                                {"uom":pack.product_id.uom_id.id,
                                                "date": time.strftime(DEFAULT_SERVER_DATE_FORMAT)})[pricelist_id]
            res[pack.id] = pack_price
        return res

    _columns = {
        "pack_price":fields.function(_get_price_for_package,type="float",string="Package Price"),
        "type_name":fields.related("ul","name",type="string",string="Package Name")
    }
    _constraints = [(_check_ean_key, 'Error: Invalid ean code', ['ean'])]
