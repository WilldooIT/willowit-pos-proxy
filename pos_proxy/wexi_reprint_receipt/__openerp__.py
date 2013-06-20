# -*- coding: utf-8 -*-
# While purchase and stock are not true dependencies, they have been included so that we can put entries on their submenus.


{
    "name": "WEXI - Reprint POS Receipts",
    "version": "1.0",
    "depends": ["base_willow",
                "point_of_sale",
                "wexi_pos_proxy_access"],
    "author": "Thomas Cook - Willow IT",
    "category": "Wexi",
    "description": """Allows the reprinting of receipts to the POS Printer""",
    'data': [
             "reprint_receipt_view.xml",
             ],
    "demo": [],
    "test": [],
    "installable": True,
    "active": False,
}
