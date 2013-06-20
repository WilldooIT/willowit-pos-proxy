from osv import osv,fields

class ProductProduct(osv.osv):
    _inherit = "product.product"

    _columns = {
        "discount_program_online_6":fields.boolean("Pack of 6 Discount Programm Online"),
        "discount_program_in_store_6":fields.boolean("Pack of 6 Discount Program In Store"),
        "discount_program_online_12":fields.boolean("Pack of 12 Discount Program Online"),
        "discount_program_in_store_12":fields.boolean("Pack of 12 Discount Program In Store"),
    }
