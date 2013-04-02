from osv import fields, osv
import tools
from tools import DEFAULT_SERVER_DATE_FORMAT
from PIL import Image
import StringIO
import io
import time


#---------------------------------------------------------------------------------------------------------------

class WexiImportClass(osv.osv):
    _name = 'wexi.import.class'
    _auto = False


    """
        data is a dictionary:
            {str_id : {'id' : ..,
                       'value' : ...,
                      }
            }
        str_id is a string value of the id on the central server
        'id' is the expected local id or False if we expect to create a new record
        and then come other values to update
        
        returns a dictionary:
            {str_id : id}
    """

    def bulk_write(self, cr, uid, model, create_allowed, data, context=None):
        model_obj = self.pool.get(model)
        result = {}
        for (k, values) in data.iteritems():
            obj_id = 'id' in values and values.pop('id') or False
            if obj_id and not model_obj.search(cr, uid, [('id', '=', obj_id)], context=context):
                obj_id = False

            if not obj_id and type(create_allowed) == type([]):
                obj_ids = model_obj.search(cr, uid, [(x, '=', values[x]) for x in create_allowed], context=context)
                if obj_ids:
                    obj_id = obj_ids[0]

            # values will be values we write to the object
            # stashed_values will be values that were passed in which we don't want to write, but may need in postprocess

            # do a preprocess, and remove any keys which can't be directly written
            stashed_values = self._preprocess(cr, uid, model, values, context=context)
            if obj_id:
                if values:
                    model_obj.write(cr, uid, [obj_id], values, context=context)
            elif create_allowed:
                values = self._newcode_defaults(cr, uid, model, values, stashed_values, context=context)
                if values:
                    obj_id = model_obj.create(cr, uid, values, context=context)
            # do a postprocess, which may need data which was written or stashed
            if obj_id:
                self._postprocess(cr, uid, obj_id, model, values, stashed_values, context=context)

            result[k] = obj_id
        return result


    """
        data is a dictionary:
            {str_id : [id, [l_ids]],
            }
        str_id is a string value of the id on the central server
        'id' is the expected local id
        'l_ids' are the expected link ids
        
        column is the many2many column name
    """
    def m2m_write(self, cr, uid, model, column, data, context=None):
        model_obj = self.pool.get(model)
        for (k, values) in data.iteritems():
            obj_id = values[0]
            if obj_id and model_obj.search(cr, uid, [('id', '=', obj_id)], context=context):
                model_obj.write(cr, uid, [obj_id], {column : [(6, 0, values[1])]}, context=context)
        return True


    """
        data is a list of ids to unlink
    """
    def bulk_unlink(self, cr, uid, model, data, context=None):
        self.pool.get(model).unlink(cr, uid, data, context=context)
        return True



    def _newcode_defaults(self, cr, uid, model, values, stashed_values, context=None):
        model_obj = self.pool.get(model)
        new_values = model_obj.default_get(cr, uid, model_obj.fields_get_keys(cr, uid, context=context), context=context)
        new_values.update(values)

        if model == 'product.product':
            if new_values.get('taxes_id'):
                new_values['taxes_id'] = [(6, 0, new_values['taxes_id'])]
            if new_values.get('supplier_taxes_id'):
                new_values['supplier_taxes_id'] = [(6, 0, new_values['supplier_taxes_id'])]

        return new_values


    def _preprocess(self, cr, uid, model, values, context=None):
        res = {}

        if model == "res.partner":
            if values.get("winery"):
                #Wineries need to be customers on central, but not on the store level.
                values["customer"] = False

        if model == "product.pricelist":
            if "currency_id" in values:
                res["currency_id"] = values.pop("currency_id")
            if "company_id" in values:
                res["company_id"] = values.pop("company_id")

        if model == "product.pricelist.version":
            if "items_id" in values:
                product_obj = self.pool.get("product.product")
                ppi_obj = self.pool.get("product.pricelist.item")
                
                ppi_item_ids = ppi_obj.search(cr,uid,[("price_version_id","=",values.get("id"))],context=context)
                ppi_obj.unlink(cr,uid,ppi_item_ids,context=context)
                
                    
        if model == 'product.product': 
            if "list_price" in values:
                res["list_price"] = values.pop("list_price")
            if 'seller_id' in values:
                res['seller_id'] = values.pop('seller_id')
            if 'new_qty' in values:
                res['new_qty'] = values.pop('new_qty')
            if "pos_categ_id" in values:
                res["pos_categ_id"] = False
                values.pop("pos_categ_id")
            #
            # this is version 7.0 code, but won't fall over for 6.1 as the field will not exist for 6.1
            #
            if 'image' in values:
                if not values.get('image'):
                    values['image'] = self.pool.get('product.product').default_get(cr, uid, 'image', context=context)
                else:
                    image_stream = io.BytesIO(values["image"].decode("base64"))
                    image = Image.open(image_stream)
                    if image.mode == "CMYK":
                        image = image.convert("RGB")
                    out_stream = StringIO.StringIO()

                    image.save(out_stream,"PNG")
                    values["image"] =  out_stream.getvalue().encode("base64")
        return res


    def _postprocess(self, cr, uid, id, model, values, stashed_values, context=None):

                

        if model == 'product.product':
            if 'seller_id' in stashed_values:
                partner_obj = self.pool.get('res.partner')
                supplierinfo_obj = self.pool.get('product.supplierinfo')
                product_obj = self.pool.get("product.product")
                seller_id = stashed_values['seller_id']
                if seller_id and partner_obj.search(cr, uid, [('id', '=', seller_id)], context=context):
                    if product_obj.browse(cr, uid, id, context=context).seller_id.id != seller_id:
                        supplierinfo_obj.unlink(cr, uid, supplierinfo_obj.search(cr, uid, [('product_id', '=', id)], context=context), context=context)

                        new_values = supplierinfo_obj.default_get(cr, uid, supplierinfo_obj.fields_get_keys(cr, uid, context=context), context=context)
                        new_values.update({'name' : seller_id, 'sequence' : 1, 'product_id' : id, 'min_qty' : 0})
                        supplierinfo_obj.create(cr, uid, new_values, context=context)
                else:
                    supplierinfo_obj.unlink(cr, uid, supplierinfo_obj.search(cr, uid, [('product_id', '=', id)], context=context), context=context)
                
            product_obj = self.pool.get("product.product")
            wine_type_obj = self.pool.get("wexi.wine.type")
            pos_category_obj = self.pool.get("pos.category")
            category_obj = self.pool.get("product.category")
            product = product_obj.browse(cr,uid,id,context=context)
            
            if "list_price" in stashed_values and not product.is_wine:
                product_obj.write(cr,uid,id,{"list_price":stashed_values["list_price"]},context=context)
                
            if not product.type_id:
                if product.categ_id:
                    def make_from_category(categ_id):
                        category = category_obj.browse(cr,uid,categ_id,context=context)
                        domain = [("name","=",category.name)]
                        if not category.parent_id:
                            domain.append(("parent_id","=",False))
                        cat_id = pos_category_obj.search(cr,uid,domain,context=context)
                        if cat_id:
                            return cat_id[0]
                        else:
                            if category.parent_id:
                                parent_id = make_from_category(category.parent_id.id)
                            else:
                                parent_id = False
                            return pos_category_obj.create(cr,uid,{"name":category.name,"parent_id":parent_id},context=context)
                    category_id = make_from_category(product.categ_id.id)
                
                else:
                    category_id = product_obj.default_get(cr,uid,["pos_categ_id"],context=context)["pos_categ_id"]
            else:
                category_id = product.type_id and pos_category_obj.search(cr,uid,[("name","=",product.type_id.name)],context=context) or False
                if category_id:
                    category_id.sort()
                    category_id.reverse()
                    category_id = category_id[0]
                else:
                    def make_from_wine_type(wt_id):
                        wt = wine_type_obj.browse(cr,uid,wt_id,context=context)
                        domain = [("name","=",wt.name)]
                        if not wt.parent_id:
                            domain.append(("parent_id","=",False))
                        cat_id = pos_category_obj.search(cr,uid,domain,context=context)
                        if cat_id:
                            return cat_id[0]
                        else:
                            if wt.parent_id:
                                parent_id = make_from_wine_type(wt.parent_id.id)
                            else:
                                parent_id = False
                            return pos_category_obj.create(cr,uid,{"name":wt.name,"parent_id":parent_id},context=context)
                    category_id = make_from_wine_type(product.type_id.id)
            product_obj.write(cr,uid,id,{"pos_categ_id":category_id},context=context)
                

            if 'new_qty' in stashed_values:
                product_obj = self.pool.get('product.product')
                warehouse_obj = self.pool.get("stock.warehouse")
                inventory_obj = self.pool.get("stock.inventory")
                inventory_line_obj = self.pool.get("stock.inventory.line")
                
                new_qty = stashed_values["new_qty"] or 0
                product = product_obj.browse(cr, uid, id, context=context)

                if product.qty_available != new_qty:
                    warehouse_ids = warehouse_obj.search(cr,uid,[],context=context)
                    
                    if warehouse_ids:
                        inventory_id = inventory_obj.create(cr , uid, {'name': ('COMMS_SYNC: %s') % tools.ustr(product.name)}, context=context)
                        line_data ={
                                    'inventory_id' : inventory_id,
                                    'product_qty' : new_qty,
                                    'location_id' : warehouse_obj.browse(cr, uid, warehouse_ids[0], context=context).lot_stock_id.id,
                                    'product_id' : id,
                                    'product_uom' : product.uom_id.id,
                                    }
                        inventory_line_obj.create(cr , uid, line_data, context=context)
                        inventory_obj.action_confirm(cr, uid, [inventory_id], context=context)
                        inventory_obj.action_done(cr, uid, [inventory_id], context=context)

        if model == "product.pricelist.version":
            irp_obj = self.pool.get("ir.property")
            product_obj = self.pool.get("product.product")
            pricelist_obj = self.pool.get("product.pricelist")
            if "items_id" in values:
                pricelist_id = values.get("pricelist_id")
                if pricelist_id == irp_obj.get(cr,uid,"property_product_pricelist","res.partner",context=context).id:
                    for product in product_obj.browse(cr,uid,product_obj.search(cr,uid,[("is_wine","=",True)],context=context),context=context):
                        
                        new_price = pricelist_obj.price_get(cr,uid,[pricelist_id],product.id,1.0,False,{"uom":product.uom_id.id,"date": time.strftime(DEFAULT_SERVER_DATE_FORMAT)})[pricelist_id]
                        product_obj.write(cr,uid,product.id,{"list_price":new_price},context=context)

        return True
