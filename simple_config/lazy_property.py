def get_lazy_prop_attr_name(property_name):
    return '_lazy_' + property_name

def lazy_property(fn):
    attr_name = get_lazy_prop_attr_name(fn.__name__)
    @property
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazy_property

def force_lazy_prop_value(tgt_obj, tgt_lazy_prop_name, new_val):
    attr_name = get_lazy_prop_attr_name(tgt_lazy_prop_name)
    setattr(tgt_obj, attr_name, new_val)
