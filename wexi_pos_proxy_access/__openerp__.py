# -*- coding: utf-8 -*-
# While purchase and stock are not true dependencies, they have been included so that we can put entries on their submenus.


{
    "name": "WEXI - pos_proxy access",
    "version": "1.0",
    "depends": ["base_willow",
                "point_of_sale"],
    "author": "Thomas Cook - Willow IT",
    "category": "Wexi",
    "description": """Provides access to a pos_proxy running on a point of sale machine to code running on the server.""",
    'data': [
             "pos_proxy_access_view.xml",
             ],
    "demo": [],
    "test": [],
    "installable": True,
    "active": False,
}
