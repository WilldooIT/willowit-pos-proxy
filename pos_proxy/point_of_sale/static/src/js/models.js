function openerp_pos_models(instance, module){ //module is instance.point_of_sale
    var QWeb = instance.web.qweb;

    // rounds a value with a fixed number of decimals.
    // round(3.141492,2) -> 3.14
    function round(value,decimals){
        var mult = Math.pow(10,decimals || 0);
        return Math.round(value*mult)/mult;
    }
    window.round = round;

    // rounds a value with decimal form precision
    // round(3.141592,0.025) ->3.125
    function round_pr(value,precision){
        if(!precision || precision < 0){
            throw new Error('round_pr(): needs a precision greater than zero, got '+precision+' instead');
        }
        return Math.round(value / precision) * precision;
    }
    window.round_pr = round_pr;

    
    // The PosModel contains the Point Of Sale's representation of the backend.
    // Since the PoS must work in standalone ( Without connection to the server ) 
    // it must contains a representation of the server's PoS backend. 
    // (taxes, product list, configuration options, etc.)  this representation
    // is fetched and stored by the PosModel at the initialisation. 
    // this is done asynchronously, a ready deferred alows the GUI to wait interactively 
    // for the loading to be completed 
    // There is a single instance of the PosModel for each Front-End instance, it is usually called
    // 'pos' and is available to all widgets extending PosWidget.

    module.PosModel = Backbone.Model.extend({
        initialize: function(session, attributes) {
            Backbone.Model.prototype.initialize.call(this, attributes);
            var  self = this;
            this.refund_mode_active = false
            this.session = session;                 
            this.ready = $.Deferred();                          // used to notify the GUI that the PosModel has loaded all resources
            this.flush_mutex = new $.Mutex();                   // used to make sure the orders are sent to the server once at time

            this.barcode_reader = new module.BarcodeReader({'pos': this});  // used to read barcodes
            this.proxy = new module.ProxyDevice();              // used to communicate to the hardware devices via a local proxy
            this.db = new module.PosLS();                       // a database used to store the products and categories
            this.db.clear('products','categories');
            this.debug = jQuery.deparam(jQuery.param.querystring()).debug !== undefined;    //debug mode 
            this.next_order_id = 0;

            // default attributes values. If null, it will be loaded below.
            this.set({
                'nbr_pending_operations': 0,    

                'currency':         {symbol: '$', position: 'after'},
                'shop':             null, 
                'company':          null,
                'user':             null,   // the user that loaded the pos
                'user_list':        null,   // list of all users
                'partner_list':     null,   // list of all partners with an ean
                'cashier':          null,   // the logged cashier, if different from user
                "table_list":           null,  

                'orders':           new module.OrderCollection(),
                //this is the product list as seen by the product list widgets, it will change based on the category filters
                'products':         new module.ProductCollection(), 
                'cashRegisters':    null, 

                'bank_statements':  null,
                'taxes':            null,
                'pos_session':      null,
                'pos_config':       null,
                'units':            null,
                'units_by_id':      null,

                'selectedOrder':    null,
            });

            this.get('orders').bind('remove', function(){ self.on_removed_order(); });
            
            // We fetch the backend data on the server asynchronously. this is done only when the pos user interface is launched,
            // Any change on this data made on the server is thus not reflected on the point of sale until it is relaunched. 
            // when all the data has loaded, we compute some stuff, and declare the Pos ready to be used. 
            $.when(this.load_server_data())
                .done(function(){
                    //self.log_loaded_data(); //Uncomment if you want to log the data to the console for easier debugging
                    self.ready.resolve();
                }).fail(function(){
                    //we failed to load some backend data, or the backend was badly configured.
                    //the error messages will be displayed in PosWidget
                    self.ready.reject();
                });
        },

        // helper function to load data from the server
        fetch: function(model, fields, domain, ctx){
            return new instance.web.Model(model).query(fields).filter(domain).context(ctx).all()
        },
        getNextId:function() {
            this.next_order_id += 1
            return this.next_order_id.toString()
        },
        // loads all the needed data on the sever. returns a deferred indicating when all the data has loaded. 
        load_server_data: function(){
            var self = this;

            var loaded = self.fetch('res.users',['name','company_id'],[['id','=',this.session.uid]]) 
                .then(function(users){
                    self.set('user',users[0]);

                    return self.fetch('res.company',
                    [
                        'currency_id',
                        'email',
                        'website',
                        'company_registry',
                        'vat',
                        'name',
                        'phone',
                        'partner_id',
                    ],
                    [['id','=',users[0].company_id[0]]]);
                }).then(function(companies){
                    self.set('company',companies[0]);

                    return self.fetch('res.partner',['contact_address'],[['id','=',companies[0].partner_id[0]]]);
                }).then(function(company_partners){
                    self.get('company').contact_address = company_partners[0].contact_address;

                    return self.fetch('res.currency',['symbol','position','rounding','accuracy'],[['id','=',self.get('company').currency_id[0]]]);
                }).then(function(currencies){
                    console.log('Currency:',currencies[0]);
                    self.set('currency',currencies[0]);

                    return self.fetch('product.uom', null, null);
                }).then(function(units){
                    self.set('units',units);
                    var units_by_id = {};
                    for(var i = 0, len = units.length; i < len; i++){
                        units_by_id[units[i].id] = units[i];
                    }
                    self.set('units_by_id',units_by_id);
                    
                    return self.fetch('product.packaging', null, null);
                }).then(function(packagings){
                    self.set('product.packaging',packagings);
                    
                    return self.fetch('res.users', ['name','ean13',"can_refund","can_adjust","can_discount"], [['ean13', '!=', false]]);
                }).then(function(users){
                    self.set('user_list',users);

                    return self.fetch('res.partner', ['name','ean13'], [['ean13', '!=', false]]);
                }).then(function(partners){
                    self.set('partner_list',partners);

                    return self.fetch('account.tax', ['amount', 'price_include', 'type']);
                }).then(function(taxes){
                    self.set('taxes', taxes);

                    return self.fetch(
                        'pos.session', 
                        ['id', 'journal_ids','name','user_id','config_id','start_at','stop_at'],
                        [['state', '=', 'opened'], ['user_id', '=', self.session.uid]]
                    );
                }).then(function(sessions){
                    self.set('pos_session', sessions[0]);

                    return self.fetch(
                        'pos.config',
                        ['name','journal_ids','shop_id','journal_id',
                         'iface_self_checkout', 'iface_led', 'iface_cashdrawer',
                         'iface_payment_terminal', 'iface_electronic_scale', 'iface_barscan', 'iface_vkeyboard',
                         'iface_print_via_proxy','iface_cashdrawer','state','sequence_id','session_ids'],
                        [['id','=', self.get('pos_session').config_id[0]]]
                    );
                }).then(function(configs){
                    var pos_config = configs[0];
                    self.set('pos_config', pos_config);
                    self.iface_electronic_scale    =  !!pos_config.iface_electronic_scale;  
                    self.iface_print_via_proxy     =  !!pos_config.iface_print_via_proxy;
                    self.iface_vkeyboard           =  !!pos_config.iface_vkeyboard; 
                    self.iface_self_checkout       =  !!pos_config.iface_self_checkout;
                    self.iface_cashdrawer          =  !!pos_config.iface_cashdrawer;

                    return self.fetch('sale.shop',[],[['id','=',pos_config.shop_id[0]]]);
                }).then(function(shops){
                    self.set('shop',shops[0]);
                    return self.fetch('pos.order.table',['name']);
                }).then(function(tables) {
                    self.set("table_list",tables);
                    return self.fetch('pos.wine.glass',['name','volume']);
                }).then(function(glass_sizes) {
                    self.set("glass_sizes",glass_sizes)
                    return self.fetch('product.packaging',['ean','product_id','qty','pack_price','type_name']);
                }).then(function(packagings){
                    self.db.add_packagings(packagings);

                    return self.fetch('pos.category', ['id','name','parent_id','child_id','image'])
                }).then(function(categories){
                    self.db.add_categories(categories);

                    return self.fetch(
                        'product.product', 
                        ['name', 'list_price','price','pos_categ_id', 'taxes_id', 'ean13', 
                         'to_weight', 'uom_id', 'uos_id', 'uos_coeff', 'mes_type', 'description_sale', 'description',
                         "discount_program_in_store_12","discount_program_in_store_6","volume","is_wine"],
                        [['sale_ok','=',true],['available_in_pos','=',true]],
                        {pricelist: self.get('shop').pricelist_id[0]} // context for price
                    );
                }).then(function(products){
                    self.db.add_products(products);

                    return self.fetch(
                        'account.bank.statement',
                        ['account_id','currency','journal_id','state','name','user_id','pos_session_id'],
                        [['state','=','open'],['pos_session_id', '=', self.get('pos_session').id]]
                    );
                }).then(function(bank_statements){
                    var journals = new Array();
                    _.each(bank_statements,function(statement) {
                        journals.push(statement.journal_id[0])
                    });
                    self.set('bank_statements', bank_statements);
                    return self.fetch('account.journal', undefined, [['id','in', journals]]);
                }).then(function(journals){
                    self.set('journals',journals);

                    // associate the bank statements with their journals. 
                    var bank_statements = self.get('bank_statements');
                    for(var i = 0, ilen = bank_statements.length; i < ilen; i++){
                        for(var j = 0, jlen = journals.length; j < jlen; j++){
                            if(bank_statements[i].journal_id[0] === journals[j].id){
                                bank_statements[i].journal = journals[j];
                                bank_statements[i].self_checkout_payment_method = journals[j].self_checkout_payment_method;
                            }
                        }
                    }
                    self.set({'cashRegisters' : new module.CashRegisterCollection(self.get('bank_statements'))});
                });
        
            return loaded;
        },

        // logs the usefull posmodel data to the console for debug purposes
        log_loaded_data: function(){
            console.log('PosModel data has been loaded:');
            console.log('PosModel: units:',this.get('units'));
            console.log('PosModel: bank_statements:',this.get('bank_statements'));
            console.log('PosModel: journals:',this.get('journals'));
            console.log('PosModel: taxes:',this.get('taxes'));
            console.log('PosModel: pos_session:',this.get('pos_session'));
            console.log('PosModel: pos_config:',this.get('pos_config'));
            console.log('PosModel: cashRegisters:',this.get('cashRegisters'));
            console.log('PosModel: shop:',this.get('shop'));
            console.log('PosModel: company:',this.get('company'));
            console.log('PosModel: currency:',this.get('currency'));
            console.log('PosModel: user_list:',this.get('user_list'));
            console.log('PosModel: user:',this.get('user'));
            console.log('PosModel.session:',this.session);
            console.log('PosModel end of data log.');
        },
        
        // this is called when an order is removed from the order collection. It ensures that there is always an existing
        // order and a valid selected order
        on_removed_order: function(removed_order){
            if( this.get('orders').isEmpty()){
                this.add_new_order();
            }
            this.set({ selectedOrder: this.get('orders').last() });
        },

        // saves the order locally and try to send it to the backend. 'record' is a bizzarely defined JSON version of the Order
        push_order: function(record) {
            this.db.add_order(record);
            this.flush();
        },

        //creates a new empty order and sets it as the current order
        add_new_order: function(){
            var order = new module.Order({pos:this});
            this.get('orders').add(order);
            this.set('selectedOrder', order);
            screen_selector.current_screen.set_button_visibility()
        },
        clear_current_order: function() {
            this.get("selectedOrder").destroy()
            this.set("cashier",null)
            selectedOrder = this.get("orders").first()
            this.set("selectedOrder",selectedOrder)
            screen_selector.current_screen.set_button_visibility(selectedOrder.get("cashier"))
        },
        // attemps to send all pending orders ( stored in the pos_db ) to the server,
        // and remove the successfully sent ones from the db once
        // it has been confirmed that they have been sent correctly.
        flush: function() {
            //TODO make the mutex work 
            //this makes sure only one _int_flush is called at the same time
            /*
            return this.flush_mutex.exec(_.bind(function() {
                return this._flush(0);
            }, this));
            */
            this._flush(0);
        },
        // attempts to send an order of index 'index' in the list of order to send. The index
        // is used to skip orders that failed. do not call this method outside the mutex provided
        // by flush() 
        _flush: function(index){
            var self = this;
            var orders = this.db.get_orders();
            self.set('nbr_pending_operations',orders.length);

            var order  = orders[index];
            if(!order){
                return;
            }
            //try to push an order to the server
            (new instance.web.Model('pos.order')).get_func('create_from_ui')([order])
                .fail(function(unused, event){
                    //don't show error popup if it fails 
                    event.preventDefault();
                    console.error('Failed to send order:',order);
                    self._flush(index+1);
                })
                .done(function(){
                    //remove from db if success
                    self.db.remove_order(order.id);
                    self._flush(index);
                });
        },

        scan_product: function(parsed_ean){
            var self = this;
            var product = this.db.get_product_by_ean13(parsed_ean.base_ean);
            var selectedOrder = this.get('selectedOrder');

            if(!product){
                return false;
            }

            if(parsed_ean.type === 'price'){
                selectedOrder.addProduct(new module.Product(product), {price:parsed_ean.value});
            }else if(parsed_ean.type === 'weight'){
                selectedOrder.addProduct(new module.Product(product), {quantity:parsed_ean.value, merge:false});
            }else{
                selectedOrder.addProduct(new module.Product(product), {quantity:product.qty,
                                                                        pack_price:product.pack_price,
                                                                        type_name:product.type_name,
                                                                        merge:true});
            }
            return true;
        },
    });

    module.CashRegister = Backbone.Model.extend({
    });

    module.CashRegisterCollection = Backbone.Collection.extend({
        model: module.CashRegister,
    });

    module.Product = Backbone.Model.extend({
        get_image_url: function(){
            return instance.session.url('/web/binary/image', {model: 'product.product', field: 'image', id: this.get('id')});
        },
    });

    module.ProductCollection = Backbone.Collection.extend({
        model: module.Product,
    });

    // An orderline represent one element of the content of a client's shopping cart.
    // An orderline contains a product, its quantity, its price, discount. etc. 
    // An Order contains zero or more Orderlines.
    module.Orderline = Backbone.Model.extend({
        initialize: function(attr,options){
            this.pos = options.pos;
            this.order = options.order;
            this.product = options.product;
            this.price   = options.product.get('price');
            this.quantity = 1;
            this.quantityStr = '1';
            this.discount = 0;
            this.discountStr = '0';
            this.discountNote = ""
            this.line_type_code = ""
            this.line_note = ""
            this.manual_discount = false;
            this.manual_price = false;
            this.type = 'unit';
            this.selected = false;
            this.glass = false;
            this.real_quantity = 0;
        },
        // sets a discount [0,100]%
        set_discount: function(discount,auto){
            this.set_discount_silent(discount,auto)
            if(discount == 0) {
                this.order.recalculateDiscount()
            }
            this.trigger("change")
        },
        set_discount_silent: function(discount,auto) {
            var disc = Math.min(Math.max(parseFloat(discount) || 0, 0),100);
            this.discount = disc;
            this.manual_discount = (disc != 0) && (auto == undefined || auto == false);
            if(this.manual_discount) {
                this.discountStr = '' + disc + '(M)';
            } else {
                this.discountStr = '' + disc;
            }
        },
        // returns the discount [0,100]%
        get_discount: function(){
            return this.discount;
        },
        get_discount_str: function(){
            return this.discountStr;
        },
        get_product_type: function(){
            return this.type;
        },
        // sets the quantity of the product. The quantity will be rounded according to the 
        // product's unity of measure properties. Quantities greater than zero will not get 
        // rounded to zero
        set_quantity: function(quantity){
            this.set_quantity_silent(quantity)
            this.order.recalculateDiscount()
        },
        set_quantity_silent: function(quantity) {
            if(quantity === 'remove'){
                this.order.removeOrderline(this);
                return;
            }else if(this.order.transaction_mode == "refund" || this.order.transaction_mode == "w_on") {
                quant = parseFloat(((0 - Math.abs(quantity)).toFixed(4)))
                this.quantity    = quant;
                this.quantityStr = '' + this.quantity;
            } else {    
                //var quant = Math.max(parseFloat(quantity) || 0, 0);
                var quant = Math.abs(parseFloat(quantity) || 0)
                var unit = this.get_unit();
                if(unit && unit.rounding > 0){
                    this.quantity    = Math.max(unit.rounding, Math.round(quant / unit.rounding) * unit.rounding);
                    this.quantityStr = this.quantity.toFixed(Math.max(0,Math.ceil(Math.log(1.0 / unit.rounding) / Math.log(10))));
                }else{
                    this.quantity    = quant;
                    this.quantityStr = '' + this.quantity;
                }
            }
            if(quantity !== "remove" && this.glass) {
                this.real_quantity = quantity / round((this.product.get("volume") / glass.volume),4)
            } else {
                this.real_quantity = this.quantity
            }
        },
        // return the quantity of product
        get_quantity: function(){
            return this.quantity;
        },
        get_quantity_str: function(){
            return this.quantityStr;
        },
        get_quantity_str_with_unit: function(){
            var unit = this.get_unit();
            if(unit && unit.name !== 'Unit(s)'){
                return this.quantityStr + ' ' + unit.name;
            }else{
                return this.quantityStr;
            }
        },
        // return the unit of measure of the product
        get_unit: function(){
            var unit_id = (this.product.get('uos_id') || this.product.get('uom_id'));
            if(!unit_id){
                return undefined;
            }
            unit_id = unit_id[0];
            if(!this.pos){
                return undefined;
            }
            return this.pos.get('units_by_id')[unit_id];
        },
        // return the product of this orderline
        get_product: function(){
            return this.product;
        },
        // selects or deselects this orderline
        set_selected: function(selected){
            this.selected = selected;
            this.trigger('change');
        },
        // returns true if this orderline is selected
        is_selected: function(){
            return this.selected;
        },
        // when we add an new orderline we want to merge it with the last line to see reduce the number of items
        // in the orderline. This returns true if it makes sense to merge the two
        can_be_merged_with: function(orderline){
            if( this.get_product().get('id') !== orderline.get_product().get('id')){    //only orderline of the same product can be merged
                return false;
            }else if(this.get_product_type() !== orderline.get_product_type()){
                return false;
            //}else if(this.get_discount() > 0){             // we don't merge discounted orderlines
            //    return false;
            }else if(this.price !== orderline.price){
                return false;
            } else if(this.glass || orderline.glass) {
                return false;
            }else{ 
                return true;
            }
        },
        merge: function(orderline){
                this.set_quantity(Math.abs(this.get_quantity()) + Math.abs(orderline.get_quantity()));
                self = this.order
                this.order.recalculateDiscount()
        },
        export_as_JSON: function() {
            if(this.glass == false) {
                qty = this.get_quantity()
                glass_qty = 0
                unit_price = this.get_unit_price()

            } else {
                qty = this.real_quantity
                glass_qty = this.get_quantity()
                unit_price = round(this.get_unit_price() * round((this.product.get("volume") / this.glass.volume),4),2)
            }   
            return {
                qty: qty,
                price_unit: unit_price,
                glass_id: this.glass && this.glass.id || false,
                glass_qty: glass_qty,
                discount: this.get_discount(),
                product_id: this.get_product().get('id'),
                line_type_code: this.line_type_code,
                line_note: this.line_note
            };
        },
        //used to create a json of the ticket, to be sent to the printer
        export_for_printing: function(){
            if(this.glass == false) {
                product_name = this.get_product().get("name")
            } else {
                product_name = this.glass.volume + "ml glass of " + this.get_product().get("name")
            }   
            return {
                quantity:           this.get_quantity(),
                unit_name:          this.get_unit().name,
                price:              this.get_unit_price(),
                discount:           this.get_discount(),
                notice:             this.discountNote,
                product_name:       product_name,
                price_display :     this.get_display_price(),
                price_with_tax :    this.get_price_with_tax(),
                price_without_tax:  this.get_price_without_tax(),
                tax:                this.get_tax(),
                product_description:      this.get_product().get('description'),
                product_description_sale: this.get_product().get('description_sale'),
            };
        },
        // changes the base price of the product for this orderline
        set_unit_price: function(price){
            this.manual_price = true;
            this.price = round(parseFloat(price) || 0, 2);
            this.trigger('change');
        },
        get_unit_price: function(){
            if(this.glass == false) {
                var rounding = this.pos.get('currency').rounding;
                return round_pr(this.price,rounding);
            } else {
                var rounding = this.pos.get('currency').rounding;
                price = Math.ceil(this.price * (this.glass.volume /  this.product.get("volume")) * 1.2)
                return round_pr(price,rounding);
            }
        },
        get_display_price: function(){
            var rounding = this.pos.get('currency').rounding;
            return round_pr(round_pr(this.get_unit_price() * this.get_quantity(),rounding) * (1 - this.get_discount()/100.0),rounding);
        },
        get_price_without_tax: function(){
            return this.get_all_prices().priceWithoutTax;
        },
        get_price_with_tax: function(){
            return this.get_all_prices().priceWithTax;
        },
        get_tax: function(){
            return this.get_all_prices().tax;
        },
        get_all_prices: function(){
            var self = this;
            var currency_rounding = this.pos.get('currency').rounding;
            var base = round_pr(this.get_quantity() * this.get_unit_price() * (1.0 - (this.get_discount() / 100.0)), currency_rounding);
            var totalTax = base;
            var totalNoTax = base;
            
            var product_list = this.pos.get('product_list');
            var product =  this.get_product(); 
            var taxes_ids = product.get('taxes_id');;
            var taxes =  self.pos.get('taxes');
            var taxtotal = 0;
            _.each(taxes_ids, function(el) {
                var tax = _.detect(taxes, function(t) {return t.id === el;});
                if (tax.price_include) {
                    var tmp;
                    if (tax.type === "percent") {
                        tmp =  base - round_pr(base / (1 + tax.amount),currency_rounding); 
                    } else if (tax.type === "fixed") {
                        tmp = round_pr(tax.amount * self.get_quantity(),currency_rounding);
                    } else {
                        throw "This type of tax is not supported by the point of sale: " + tax.type;
                    }
                    tmp = round_pr(tmp,currency_rounding);
                    taxtotal += tmp;
                    totalNoTax -= tmp;
                } else {
                    var tmp;
                    if (tax.type === "percent") {
                        tmp = tax.amount * base;
                    } else if (tax.type === "fixed") {
                        tmp = tax.amount * self.get_quantity();
                    } else {
                        throw "This type of tax is not supported by the point of sale: " + tax.type;
                    }
                    tmp = round_pr(tmp,currency_rounding);
                    taxtotal += tmp;
                    totalTax += tmp;
                }
            });
            return {
                "priceWithTax": totalTax,
                "priceWithoutTax": totalNoTax,
                "tax": taxtotal,
            };
        },
    });

    module.OrderlineCollection = Backbone.Collection.extend({
        model: module.Orderline,
    });

    // Every PaymentLine contains a cashregister and an amount of money.
    module.Paymentline = Backbone.Model.extend({
        initialize: function(attributes, options) {
            this.amount = 0;
            this.cashregister = options.cashRegister;
        },
        //sets the amount of money on this payment line
        set_amount: function(value){
            mode = self.pos.get("selectedOrder").transaction_mode
            amt = parseFloat(value) || 0;
            if(amt)
                this.amount = parseFloat(amt.toFixed(2))
            else
                this.amount = amt
            this.trigger('change');
        },
        // returns the amount of money on this paymentline
        get_amount: function(){
            return parseFloat(this.amount) || 0;
        },
        // returns the associated cashRegister
        get_cashregister: function(){
            return this.cashregister;
        },
        //exports as JSON for server communication
        export_as_JSON: function(){
            return {
                name: instance.web.datetime_to_str(new Date()),
                statement_id: this.cashregister.get('id'),
                account_id: (this.cashregister.get('account_id'))[0],
                journal_id: (this.cashregister.get('journal_id'))[0],
                amount: this.get_amount()
            };
        },
        //exports as JSON for receipt printing
        export_for_printing: function(){
            return {
                amount: this.get_amount(),
                journal: this.cashregister.get('journal_id')[1],
            };
        },
    });

    module.PaymentlineCollection = Backbone.Collection.extend({
        model: module.Paymentline,
    });
    

    // An order more or less represents the content of a client's shopping cart (the OrderLines) 
    // plus the associated payment information (the PaymentLines) 
    // there is always an active ('selected') order in the Pos, a new one is created
    // automaticaly once an order is completed and sent to the server.
    module.Order = Backbone.Model.extend({
        initialize: function(attributes){
            Backbone.Model.prototype.initialize.apply(this, arguments);
            this.set({
                creationDate:   new Date(),
                orderLines:     new module.OrderlineCollection(),
                paymentLines:   new module.PaymentlineCollection(),
                name:           "Order " + this.generateUniqueId(),
                client:         null,
                cashier:        null,
                scan_unlocked:  false,
                table:          null,
                num:            attributes.pos.getNextId(),
                is_takeaway:    false,
            });
            this.pos =     attributes.pos; 
            this.selected_orderline = undefined;
            this.screen_data = {};  // see ScreenSelector
            this.receipt_type = 'receipt';  // 'receipt' || 'invoice'
            this.transaction_mode = "normal";

            return this;
        },
        generateUniqueId: function() {
            return new Date().getTime();
        },
        addProduct: function(product, options){
            if(!self.get("scan_unlocked")) {
                alert("Please scan in to make a sale")
                return
            }
            options = options || {};
            var attr = product.toJSON();
            attr.pos = this.pos;
            attr.order = this;
            var line = new module.Orderline({}, {pos: this.pos, order: this, product: product});
            line.line_type_code = this.transaction_mode && this.transaction_mode.toUpperCase() || "NORMAL"
            if(options.quantity !== undefined){
                line.set_quantity(options.quantity);
            }
            if(options.price !== undefined){
                line.set_unit_price(options.price);
            }
            if(options.pack_price !== undefined) {
                line.set_unit_price(options.pack_price)
                //line.product.set("name", line.product.get("name") + " [as " + options.type_name + "]")
            }
            
            var last_orderline = this.getLastOrderline();
            if( last_orderline && last_orderline.can_be_merged_with(line) && options.merge !== false){
                last_orderline.merge(line);
            }else{
                this.get('orderLines').add(line);
            }
            this.selectLine(this.getLastOrderline());
            this.recalculateDiscount() 
            this.pos.proxy.message("display_product",{
                "name":line.product.get("name"),
                "price":line.price,
                "discount":line.discount,
                });
        },
        recalculateDiscount: function() {
            self = this;
            lines = this.get("orderLines")
            if(this.transaction_mode == "w_on" || this.transaction_mode == "w_off") {
                _.each(lines.models,function(line) {
                    line.set_discount_silent(0)
                    line.product = line.product.clone()
                    line.product.set("taxes_id",[])
                    
                    line.set_quantity_silent(Math.abs(line.quantity))
                    line.trigger("change")       
                })
            } else {
                totalQuantity = 0
                _.each(lines.models,function(line) {
                    if(line.glass == false) {
                        totalQuantity += Math.abs(line.quantity)
                    }
                    line.line_type_code = self.transaction_mode && self.transaction_mode.toUpperCase() || "NORMAL"
                    line.product.set("taxes_id",self.pos.db.get_product_by_id(line.product.id).taxes_id)
                })
                _.each(lines.models, function(line) {
                    if( (!line.manual_discount 
                         && (self.transaction_mode == "refund" 
                         || self.transaction_mode == "tstng")))  {
                        line.set_discount_silent(0,true);
                    } else if(line.glass == false) {
                        if( totalQuantity >= 12 &&
                            line.product.get("discount_program_in_store_12") && 
                            !line.manual_discount) {
                            line.set_discount_silent(15,true)
                        }
                        if( totalQuantity >= 6 &&
                            totalQuantity < 12 &&
                            line.product.get("discount_program_in_store_6") && 
                            !line.manual_discount) {
                            line.set_discount_silent(10,true)
                        } 
                        if(totalQuantity < 6 && !line.manual_discount) {
                            line.set_discount_silent(0,true)
                        }

                    }
                    line.set_quantity_silent(Math.abs(line.quantity))
                    line.trigger("change")       
                })
            }
        },
        removeOrderline: function( line ){
            this.get('orderLines').remove(line);
            this.selectLine(this.getLastOrderline());
            this.recalculateDiscount()
        },
        getLastOrderline: function(){
            return this.get('orderLines').at(this.get('orderLines').length -1);
        },
        addPaymentLine: function(cashRegister) {
            var paymentLines = this.get('paymentLines');
            var newPaymentline = new module.Paymentline({},{cashRegister:cashRegister});
            if(cashRegister.get('journal').type !== 'cash'){
                newPaymentline.set_amount( this.getDueLeft() );
            }
            paymentLines.add(newPaymentline);
        },
        getName: function() {
            return this.get('name');
        },
        getSubtotal : function(){
            return (this.get('orderLines')).reduce((function(sum, orderLine){
                return sum + orderLine.get_display_price();
            }), 0);
        },
        getTotalTaxIncluded: function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return parseFloat((sum + orderLine.get_price_with_tax()).toFixed(2));
            }), 0);
        },
        getDiscountTotal: function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return sum + (orderLine.get_unit_price() * (orderLine.get_discount()/100) * orderLine.get_quantity());
            }), 0);
        },
        getTotalTaxExcluded: function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return sum + orderLine.get_price_without_tax();
            }), 0);
        },
        getTax: function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return sum + orderLine.get_tax();
            }), 0);
        },
        getPaidTotal: function() {
            return (this.get('paymentLines')).reduce((function(sum, paymentLine) {
                amt =  parseFloat(((sum + paymentLine.get_amount()) || 0).toFixed(2)) 
                return amt
            }), 0);
        },
        getChange: function() {
            return parseFloat((this.getPaidTotal() - this.getTotalTaxIncluded()).toFixed(2));
        },
        getDueLeft: function() {
            return parseFloat((this.getTotalTaxIncluded() - this.getPaidTotal()).toFixed(2));
        },
        // sets the type of receipt 'receipt'(default) or 'invoice'
        set_receipt_type: function(type){
            this.receipt_type = type;
        },
        get_receipt_type: function(){
            return this.receipt_type;
        },
        // the client related to the current order.
        set_client: function(client){
            this.set('client',client);
        },
        get_client: function(){
            return this.get('client');
        },
        get_client_name: function(){
            var client = this.get('client');
            return client ? client.name : "";
        },
        // the order also stores the screen status, as the PoS supports
        // different active screens per order. This method is used to
        // store the screen status.
        set_screen_data: function(key,value){
            if(arguments.length === 2){
                this.screen_data[key] = value;
            }else if(arguments.length === 1){
                for(key in arguments[0]){
                    this.screen_data[key] = arguments[0][key];
                }
            }
        },
        //see set_screen_data
        get_screen_data: function(key){
            return this.screen_data[key];
        },
        // exports a JSON for receipt printing
        export_for_printing: function(){
            var orderlines = [];
            this.get('orderLines').each(function(orderline){
                orderlines.push(orderline.export_for_printing());
            });

            var paymentlines = [];
            this.get('paymentLines').each(function(paymentline){
                paymentlines.push(paymentline.export_for_printing());
            });
            var client  = this.get('client');
            var cashier = this.get("cashier") || this.pos.get('cashier') || this.pos.get('user');
            var company = this.pos.get('company');
            var shop    = this.pos.get('shop');
            var table   = this.get("table") && this.get("table").name;
            var order_number = this.get("num");
            var is_takeaway = this.get("is_takeaway")
            var date = new Date();
            return {
                table:  table,
                order_number: order_number,
                orderlines: orderlines,
                is_takeaway: is_takeaway,
                paymentlines: paymentlines,
                subtotal: this.getSubtotal(),
                total_with_tax: this.getTotalTaxIncluded(),
                total_without_tax: this.getTotalTaxExcluded(),
                total_tax: this.getTax(),
                total_paid: this.getPaidTotal(),
                total_discount: this.getDiscountTotal(),
                change: this.getChange(),
                name : this.getName(),
                client: client ? client.name : null ,
                invoice_id: null,   //TODO
                cashier: cashier ? cashier.name : null,
                date: { 
                    year: date.getFullYear(), 
                    month: date.getMonth(), 
                    date: date.getDate(),       // day of the month 
                    day: date.getDay(),         // day of the week 
                    hour: date.getHours(), 
                    minute: date.getMinutes() 
                }, 
                company:{
                    email: company.email,
                    website: company.website,
                    company_registry: company.company_registry,
                    contact_address: company.contact_address, 
                    vat: company.vat,
                    name: company.name,
                    phone: company.phone,
                },
                shop:{
                    name: shop.name,
                },
                currency: this.pos.get('currency'),
                transaction_mode: this.transaction_mode
            };
        },
        exportAsJSON: function() {
            var orderLines, paymentLines;
            orderLines = [];
            (this.get('orderLines')).each(_.bind( function(item) {
                return orderLines.push([0, 0, item.export_as_JSON()]);
            }, this));
            paymentLines = [];
            (this.get('paymentLines')).each(_.bind( function(item) {
                return paymentLines.push([0, 0, item.export_as_JSON()]);
            }, this));
            return {
                receipt_json: this.export_for_printing(),
                name: this.getName(),
                amount_paid: this.getPaidTotal(),
                amount_total: this.getTotalTaxIncluded(),
                amount_tax: this.getTax(),
                amount_return: this.getChange(),
                lines: orderLines,
                statement_ids: paymentLines,
                pos_session_id: this.pos.get('pos_session').id,
                partner_id: this.pos.get('client') ? this.pos.get('client').id : undefined,
                user_id: this.pos.get('cashier') ? this.pos.get('cashier').id : this.pos.get('user').id,
            };
        },
        getSelectedLine: function(){
            return this.selected_orderline;
        },
        selectLine: function(line){
            if(line){
                if(line !== this.selected_orderline){
                    if(this.selected_orderline){
                        this.selected_orderline.set_selected(false);
                    }
                    this.selected_orderline = line;
                    this.selected_orderline.set_selected(true);
                }
            }else{
                this.selected_orderline = undefined;
            }
        },
    });

    module.OrderCollection = Backbone.Collection.extend({
        model: module.Order,
    });

    /*
     The numpad handles both the choice of the property currently being modified
     (quantity, price or discount) and the edition of the corresponding numeric value.
     */
    module.NumpadState = Backbone.Model.extend({
        defaults: {
            buffer: "0",
            mode: "quantity"
        },
        appendNewChar: function(newChar) {
            var oldBuffer;
            oldBuffer = this.get('buffer');
            if (oldBuffer === '0') {
                this.set({
                    buffer: newChar
                });
            } else if (oldBuffer === '-0') {
                this.set({
                    buffer: "-" + newChar
                });
            } else {
                this.set({
                    buffer: (this.get('buffer')) + newChar
                });
            }
            this.trigger('set_value',this.get('buffer'));
        },
        deleteLastChar: function() {
            if(this.get('buffer') === ""){
                if(this.get('mode') === 'quantity'){
                    this.trigger('set_value','remove');
                }else{
                    this.trigger('set_value',this.get('buffer'));
                }
            }else{
                var newBuffer = this.get('buffer').slice(0,-1) || "";
                this.set({ buffer: newBuffer });
                this.trigger('set_value',this.get('buffer'));
            }
        },
        switchSign: function() {
            var oldBuffer;
            oldBuffer = this.get('buffer');
            this.set({
                buffer: oldBuffer[0] === '-' ? oldBuffer.substr(1) : "-" + oldBuffer
            });
            this.trigger('set_value',this.get('buffer'));
        },
        changeMode: function(newMode) {
            this.set({
                buffer: "0",
                mode: newMode
            });
        },
        reset: function() {
            this.set({
                buffer: "0",
                mode: "quantity"
            });
        },
        resetValue: function(){
            this.set({buffer:'0'});
        },
    });
}