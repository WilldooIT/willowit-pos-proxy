# -*- coding: utf-8 -*-

from osv import fields, osv


class res_partner(osv.osv):
    """Extend base res.partner.
    """
    _inherit = 'res.partner'

    _columns = {
        # Add custom Wineries columns
        'winery' : fields.boolean('Signed Up Winery'),
        'wine_company_name': fields.char('Company Name', size=128),
        'wine_gi_zone': fields.char('GI Zone', size=256),
        'wine_gi_region': fields.char('GI Region', size=256),
        'wine_gi_subregion': fields.char('GI Subregion', size=256),
        'wine_vineyards': fields.text('Vineyards'),
        'wine_site_facilities': fields.text('Site Facilities'),
        'wine_prod_organic_wine': fields.boolean('Product Organic Wine'),
        'wine_cellar_door': fields.boolean('Cellar Door'),

        'reactivate' : fields.boolean('Reactivate Partner'),
        'type': fields.selection( [ ('default','Default'),('invoice','Invoice'), ('delivery','Delivery'), ('contact','Contact'), ('other','Other'),
                                    ('head office', 'Head Office'), ('winery', 'Winery'), ('ceo', 'CEO'),('ceo2', 'CEO2'),('winemaker', 'Winemaker'),('marketer', 'Marketer'), 
                                  ],
                                  'Address Type', help="Used to select automatically the right address according to the context in sales and purchases documents."),
        'url': fields.char('URL', size=240),
    }

    def write(self, cr, uid, ids, values, context=None):
        result = super(res_partner,self).write(cr, uid, ids, values, context=context)
        if values.get('reactivate'):
            cr.execute('UPDATE res_partner ' \
                        'SET active = true ' \
                        'WHERE id IN %s',
                    (tuple(ids),))
            
        return result
