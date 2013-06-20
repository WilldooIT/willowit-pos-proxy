from osv import fields, osv


#---------------------------------------------------------------------------------------------------------------

class WineRegion(osv.osv):

    _name = 'wexi.wine.region'

    _columns = {
                'name' : fields.char('Wine Region', 64, required=True),
                }


    def constraint_name_unique(self, cr, uid, ids, context=None):

        for region in self.browse(cr, uid, ids, context=context):
            if self.search(cr, uid, [('name', '=', region.name)], count=True, context=context) > 1:
                return  False
        return True


    _sql_constraints = [
                    ('name_uniq', 'unique (name)', 'Region names must be unique'),
                    ]

    _constraints = [
                    (constraint_name_unique, 'Region names must be unique', ['name']),
                    ]


WineRegion()


#---------------------------------------------------------------------------------------------------------------

class WineType(osv.osv):

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _name = "wexi.wine.type"
    _description = "Wine Types"
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Name'),
        'parent_id': fields.many2one('wexi.wine.type','Parent', select=True),
        'child_id': fields.one2many('wexi.wine.type', 'parent_id', string='Children'),
        'usage': fields.selection([('group','Grouping Only'), ('normal','Normal')], 'Usage'),
    }

    _defaults = {
        'usage' : lambda *a : 'normal',
    }

    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from wexi_wine_type where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error! You can not create recursive types.', ['parent_id'])
    ]

    def child_get(self, cr, uid, ids):
        return [ids]

WineType()





#---------------------------------------------------------------------------------------------------------------
#    To allow configuration from product maint, add link back to linked options file from product file

class ProductProductWineClass(osv.osv):

    _inherit = 'product.product'
    _name = 'product.product'


    _columns = {
                'is_wine' : fields.boolean('Product is a Wine Label'),
                'region_id' : fields.many2one("wexi.wine.region", "Wine Region", select = True),
                'type_id': fields.many2one('wexi.wine.type','Wine Type', domain="[('usage','=','normal')]", help="Select wine type"),
                'stored_region_id' : fields.integer('stored_region_id'),
                'stored_type_id' : fields.integer('stored_type_id'),
                }


    def on_change_is_wine(self, cr, uid, ids, is_wine, region_id, type_id, stored_region_id, stored_type_id, context=None):

        if context is None:
            context = {}

        if is_wine:
            result = {'value' : {'region_id' : stored_region_id or False, 'type_id' : stored_type_id or False}}
        else:
            result = {'value' : {'region_id' : False, 'type_id' : False, 'stored_region_id' : region_id, 'stored_type_id' : type_id}}

        return result


    def create(self, cr, uid, values, context=None):
        """ Needed as client does not pass the read_only values back - possibly fixed in v6.1?? """

        if 'is_wine' in values and not values['is_wine']:
            values['region_id'] = False
            values['type_id'] = False

        result = super(ProductProductWineClass,self).create(cr, uid, values, context=context)
        return result


    def write(self, cr, uid, ids, values, context=None):
        """ Needed as client does not pass the read_only values back - possibly fixed in v6.1?? """

        if 'is_wine' in values and not values['is_wine']:
            values['region_id'] = False
            values['type_id'] = False

        result = super(ProductProductWineClass,self).write(cr, uid, ids, values, context=context)
        return result


ProductProductWineClass()
