
# Parent tree
# design
# |---> module
#       |-----> port/wire
#       |-----> instance
#               |-----> pin

class design_t:
    def __init__(self):
        self.modules = dict()

    def add_module(self, module_name):
        if (module_name in self.modules.keys()):
            print 'Error: module (%s) already exisits' % module_name
            return None
        m = module_t(module_name, self)
        self.modules[m.name] = m
        return m


class module_t:
    def __init__(self, name, design):
        self.name = name

        self.ports = dict()
        self.ls_port = list() # port in order (important to spice netlist)

        self.wires = dict()

        self.instances = dict()

        self.params = dict()

        self.is_hierarchical = True # True: if all instances are basic elements

        self.is_basic = False # basic elements like NMOS/PMOS

        self.full_name = self.name

        self.parent_design = design

    def add_port(self, port_name, direction):
        if (port_name in self.ports.keys()):
            print 'Error: port (%s) in module (%s) already exists' % (port_name, self.full_name)
            return None
        p = port_t(port_name, self, direction)
        self.ports[p.name] = p
        self.ls_port.append(p)
        return p

    def add_wire(self, wire_name):
        if (wire_name in self.wires.keys()):
            print 'Error: wire (%s) in module (%s) already exists' % (wire_name, self.full_name)
            return None
        w = wire_t(wire_name, self)
        self.wires[w.name] = w
        return w

    def add_instance(self, instance_name, master_module):
        if (instance_name in self.instances.keys()):
            print 'Error: instance (%s) in module (%s) already exists' % (instance_name, self.full_name)
            return None
        n = instance_t(instance_name, self, master_module)
        self.instances[n.name] = n
        return n

    def add_param(self, param, default_value):
        if (param in self.params.keys()):
            print 'Error: param (%s) in module (%s) already exists' % (param, self.full_name)
            return 0
        self.params[param] = default_value
        return 1

#     def __eq__(self, other):
#         equal = True
#         if not (self.name == other.name):
#             equal = False
#         if not __eq_dict__(self.ports, other.ports):
#             equal = False
#         if not __eq_dict__(self.instances, other.instances):
#             equal = False
#         if not __eq_dict__(self.wires, other.wires):
#             equal = False
# 
#         if not equal:
#             print 'Error: modules (%s != %s) donot match' % (self, other)
# 
#         return equal

class instance_t:
    'instance of module'
    def __init__(self, name, parent_module, master_module):
        self.name = name
        self.parent_module = parent_module
        self.pins = dict()

        self.master_module = master_module
        self.params = dict()

        self.full_name =  '%s.%s' % (self.parent_module.name, self.name)

        for master_port in self.master_module.ports.values():
            p = pin_t(master_port, self)
            self.pins[p.name] = p

    def connect_pin(self, pin_name, connect_name):
        assert pin_name in self.pins.keys()

        # find connect
        m = self.parent_module
        if (connect_name in m.ports.keys()):
            connect = m.ports[connect_name]
        elif (connect_name in m.wires.keys()):
            connect = m.wires[connect_name]
        elif (connect_name in m.parent_design.global_wires.keys()):
            connect = m.parent_design.global_wires[connect_name]
        else:
#             print 'Error: cannot find port or wire (%s) in module (%s) for instance (%s)' % (connect_name, m.name, self.name)
            return False

        self.pins[pin_name].ls_connect.append(connect)
        connect.ls_connect.append(self)
        return True

    def add_param(self, param, value):
        if param not in self.master_module.params.keys():
            'Error: param (%s) doesnot exist in module (%s)' % (param, self.master_module.name)
        self.params[param] = value

#     def __eq__(self, other):
#         equal = True
#         if (not self.name == other.name) or (not self.parent_module.name == other.parent_module.name) or (not self.master_module.name == other.master_module.name):
#             equal = False
#         if not __eq_dict__(self.pins, other.pins):
#             equal = False
# 
#         if not equal:
#             print 'Error: instances (%s != %s) donot match' % (self, other)
# 
#         return equal

class net_t:
    'basic class for wire/port/pin'
    def __init__(self, name):
        self.name = name
        self.ls_connect = list()

class wire_t(net_t):
    'wire in module, connect to internal pin'
    type = 'wire'
    def __init__(self, name, parent_module):
        net_t.__init__(self, name)
        self.parent_module = parent_module
        self.ls_fanin = list()
        self.ls_fanout = list()

        self.is_global = False
        self.is_power = False
        self.is_ground = False

        if (self.parent_module is not None):
            self.full_name = '%s.%s' % (self.parent_module.name, self.name)
        else:
            self.full_name = self.name

class port_t(wire_t):
    'port of module, connect to internal pin'
    def __init__(self, name, parent_module, direction):
        wire_t.__init__(self, name, parent_module)

        assert direction in ['input', 'output', 'bidirection'], direction
        self.direction = direction

#     def __eq__(self, other):
#         if (not self.name == other.name) or (not self.parent_module.name == other.parent_module.name) or (not self.direction == other.direction):
#             print 'Error: ports (%s != %s) donot match' % (self, other)
#             return False
#         else:
#             return True

class pin_t(port_t):
    'pin of instance, connect to external port/wire'
    def __init__(self, master_port, parent_instance):
        net_t.__init__(self, master_port.name)
        self.master_port = master_port
        self.parent_instance = parent_instance

        self.full_name = '%s.%s.%s' % (self.parent_instance.parent_module.name, self.parent_instance.name, self.name)

#     def __eq__(self, other):
#         if (not self.name == other.name) or (not self.master_port.name == other.master_port.name) or (not self.parent_instance.name == other.parent_instance.name):
#             print 'Error: pins (%s != %s) donot match' % (self, other)
#             return False
#         else:
#             return true

################################################################
# compare 2 design/module
################################################################

def __eq_dict__(dict1, dict2):
    if (len(set(dict1.keys()) ^ set(dict2.keys())) > 0):
        return False

    for key in dict1.keys():
        if not (dict1[key] == dict2[port_name]):
            return False

    return True

################################################################
# statistics of module frequency
################################################################

def module_frequency (design, ls_top_module_name=list(), ls_filter_pattern=['*'], ls_ignore_pattern=list()):
    import fnmatch

    for module in design.modules.values():
        module.freq = 0
        module.is_top = True

    # find top module
    if (len(ls_top_module_name) == 0):
        for module in design.modules.values():
            for instance in module.instances.values():
                instance.master_module.is_top = False
        ls_top_module = filter(lambda x: x.is_top, design.modules.values())
    else:
        ls_top_module = list()
        for name in ls_top_module_name:
            if name not in design.modules.keys():
                print 'Error: given top module name (%s) doesnot exist'
            ls_top_module.append(design.modules[name])

    assert len(ls_top_module) > 0

    # module frequency
    while (len(ls_top_module) != 0):
        module = ls_top_module.pop()
        for instance in module.instances.values():
            if instance.master_module.is_basic:
                continue
            instance.master_module.freq += 1
            if instance.master_module.is_hierarchical:
                ls_top_module.append(instance.master_module)


    # apply filter pattern on module names
    ls_module_name = design.modules.keys()
    ls_module_name_filtered = list()
    for fp in ls_filter_pattern:
        ls_module_name_filtered += fnmatch.filter(ls_module_name, fp)
    st_module_name_filtered = set(ls_module_name_filtered)

    # apply ignore pattern on module names
    ls_module_name_ignored = list()
    for ip in ls_ignore_pattern:
        ls_module_name_ignored += fnmatch.filter(st_module_name_filtered, ip)
    st_module_name_ignored = set(ls_module_name_ignored)

    st_module_name = st_module_name_filtered - st_module_name_ignored

    ls_module = filter(lambda x: x.name in st_module_name, design.modules.values())
    ls_module.sort(key=lambda x: x.freq, reverse=True)

    print 'Statistics of module frequency'
    for module in ls_module:
        print '%-10s %d' % (module.name, module.freq)

    return ls_module
