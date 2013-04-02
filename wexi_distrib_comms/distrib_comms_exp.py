from osv import fields, osv


PER_EXPORT = 100


#---------------------------------------------------------------------------------------------------------------

class WexiExportClass(osv.osv):
    _name = 'wexi.export.class'
    _auto = False


    """
        data is a list of ids to check and retrieve:

        returns a dictionary of dictionary values:
            {'str_id' : {values}, ]
    """

    def bulk_retrieve_by_ids(self, cr, uid, model, data, check_needed, context=None):
        model_obj = self.pool.get(model)
        result = {}
        for id in data:
            if id and not model_obj.search(cr, uid, [('id', '=', id)], context=context):
                result[str(id)] = False
            elif id:
                row = model_obj.browse(cr, uid, id, context=context)
                if not check_needed or row.pulled_centrally != 'sent':
                    result[str(id)] = model_obj.pull_columns(cr, uid, id, context=context)
                    model_obj.write(cr, uid, id, {'pulled_centrally' : 'sending'}, context=context)

        return result


    def bulk_retrieve_blanket(self, cr, uid, model, ignore_ids, context=None):
        model_obj = self.pool.get(model)
        result = {}

        for row in model_obj.browse(cr, uid, model_obj.search(cr, uid, ['&', '!', ('id', 'in', ignore_ids), '|', ('pulled_centrally', '!=', 'sent'), ('pulled_centrally', '=', False)], context=context), context=context):
            if len(result) >= PER_EXPORT:
                break
            if getattr(row, 'pull_needed', True):
                result[str(row.id)] = model_obj.pull_columns(cr, uid, row.id, context=context)

        model_obj.write(cr, uid, [int(k) for k in result.iterkeys()], {'pulled_centrally' : 'sending'}, context=context)

        return result


    def mark_sent(self, cr, uid, model, data, context=None):

        model_obj = self.pool.get(model)
        for id in data:
            if id and model_obj.search(cr, uid, [('id', '=', id)], context=context):
                row = model_obj.browse(cr, uid, id, context=context)
                if row.pulled_centrally == 'sending':
                    model_obj.write(cr, uid, row.id, {'pulled_centrally' : 'sent'}, context=context)
                    # if == sent, then we can leave it as sent
                    # if == '' then we MUST leave it as '' so it will re-send - it means it was changed in the meantime...
        return True
