# -*- coding: utf-8 -*-

{
    "name": "WEXI - Add Wineries details to Partners",
    "version": "1.0",
    "depends": [
                "partner_abn_acn"], # partner_abn_acn is an existing Willow module that adds the ABN & ACN. These are needed for Wineries.
    "author": "Douglas Parker - Willow IT",
    "category": "Wexi",
    "description": """Add WEXI Winery fields to OpenERP Partners and Partner Addresses.""",
    'data': [
             "partner_view.xml",
             ],
    "demo": [],
    "test": [],
    "installable": True,
    "active": False,
}
