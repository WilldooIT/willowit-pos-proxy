# -*- coding: utf-8 -*-
# While purchase and stock are not true dependencies, they have been included so that we can put entries on their submenus.


{
    "name": "WEXI - Wine Classifications",
    "version": "1.0",
    "depends": ["base_willow",
                "product",
                "purchase", "stock"],
    "author": "Richard deMeester - Willow IT",
    "category": "Wexi",
    "description": """Changes to allow products for Products to be classified as wines and associated classifications""",
    'data': [
             "security/wine_classifications_security.xml", "security/ir.model.access.csv",
             "product_view.xml", "wine_regions_view.xml", "wine_types_view.xml",
             "data/wexi.wine.type.csv",
             ],
    "demo": [],
    "test": [],
    "installable": True,
    "active": False,
}
