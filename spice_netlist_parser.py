#!/usr/bin/python

import os
import re

from netlist import *

################################################################

def spice_netlist_parser (ls_spice_netlist_fpath, ls_nmos_name='NCH_MAC NCH_MAC_PSVT NCH_MAC_NSVT NCH_HVT_MAC NCH_LVT_MAC'.split(), ls_pmos_name='PCH_MAC PCH_MAC_PSVT PCH_MAC_NSVT PCH_HVT_MAC PCH_LVT_MAC'.split()):
    """
    >> class design_t()
    """

    design = design_t()

    # prepare mos module
    ls_nmos_name = [name.lower() for name in ls_nmos_name]
    ls_pmos_name = [name.lower() for name in ls_pmos_name]
    for mos_name in (ls_nmos_name + ls_pmos_name):
        mos = design.add_module(mos_name.lower())
        assert mos

        mos.is_hierarchical = False
        mos.is_basic = True

        mos.add_port('d', 'bidirection')
        mos.add_port('g', 'bidirection')
        mos.add_port('b', 'bidirection')
        mos.add_port('s', 'bidirection')
        mos.add_param('l', 28e-9)
        mos.add_param('w', 28e-9)
        mos.add_param('m', 1)

    # global
    design.global_wires = dict()

    #===========================================================
    # read all spice netlist file into memory (ls_raw)
    #   and remove comment, concate lines
    ls_raw = list() # content = (line, fpath_idx, line_idx)

    for (fpath_idx, fpath) in enumerate(ls_spice_netlist_fpath):
        assert os.path.isfile(fpath), 'Cannot find spice netlist file %s' % fpath
        f = open(fpath, 'r')

        for (line_idx, line) in enumerate(f):
            # remove spice style comment
            line = re.sub(r'\*.*', '', line.strip())
            line = re.sub(r'\$.*', '', line.strip())

            if (len(line) == 0):
                continue

            ls_raw.append((line.strip(), fpath_idx, line_idx))

        f.close()

    #===========================================================
    # concate lines into full statement and save into memory (ls_stmt)
    ls_stmt = list() # content = (stmt, fpath_idx, begin_line_idx, end_line_idx)

    stmt = ''
    for (line, fpath_idx, line_idx) in reversed(ls_raw):
        if (line[0] == r'+'):
            line = ' ' + line[1:]
            if (len(stmt) == 0):
                # no previous found continue line
                end_line_idx = line_idx
                stmt = line
            else:
                # with previous found continue line
                stmt = line + stmt
        else:
            # current line is not a continue line
            begin_line_idx = line_idx
            if (len(stmt) == 0):
                # no previous found continue line
                end_line_idx = line_idx
                stmt = line
            else:
                # with previous found continue line
                stmt = line + stmt

            ls_stmt.append((stmt, fpath_idx, begin_line_idx, end_line_idx))

            stmt = ''

    ls_stmt.reverse()

    #===========================================================
    # parse statement
    module = None
    for (stmt, fpath_idx, begin_line_idx, end_line_idx) in ls_stmt:
        stmt = stmt.replace(r"'", " ' ")
        stmt = stmt.replace(r'=', ' = ')
        stmt = re.sub(r'\s+', ' ', stmt)

        ls_tk = stmt.lower().split()

        first = ls_tk[0]
        #-------------------------------------------------------
        # parse subckt title
        if (first == '.subckt'):
            module_name = ls_tk[1]
            try:
                idx_equal = ls_tk.index('=')
                ls_port_name = ls_tk[2:idx_equal-1]
                ls_param_tk = ls_tk[idx_equal-1:]
            except:
                ls_port_name = ls_tk[2:]
                ls_param_tk = list()

            assert module == None
            module = design.add_module(module_name)

            # port
            for port_name in ls_port_name:
                module.add_port(port_name, 'bidirection')

            # param
            for (param_name, param_value) in parse_param_token(ls_param_tk):
                module.add_param(param_name, param_value)

            module.ls_instance_tk = list()

        #-------------------------------------------------------
        # parse module end
        elif (first == '.ends'):
            assert module != None
            module = None

        #-------------------------------------------------------
        # parse instance
        elif (first[0] == 'x') or (first[0] == 'm'):
            # save for later process
            module.ls_instance_tk.append((ls_tk, fpath_idx, begin_line_idx, end_line_idx))

        #-------------------------------------------------------
        # parse special
        elif (first[0] == '.'):
            #TODO param, option, global
            if (first == '.global'):
                for wire_name in ls_tk[1:]:
                    wire = wire_t(wire_name, None)
                    wire.is_global = True
                    design.global_wires[wire.name] = wire
            elif (first == '.param'):
                pass
            elif (first == '.option'):
                pass
            else:
                print 'Warning: Statement is not supported at line (%d to %d) in file (%s) \"%s\"' % (begin_line_idx+1, end_line_idx+1, ls_spice_netlist_fpath[fpath_idx], stmt)

        #-------------------------------------------------------
        else:
            print 'Warning: Statement is not supported at line (%d to %d) in file (%s) \"%s\"' % (begin_line_idx+1, end_line_idx+1, ls_spice_netlist_fpath[fpath_idx], stmt)


    #===========================================================
    # process instance statement token
    for module in design.modules.values():
        if (module.is_basic):
            continue

        for (ls_tk, fpath_idx, begin_line_idx, end_line_idx) in module.ls_instance_tk:

            instance_name = ls_tk[0]

            try:
                idx_equal = ls_tk.index('=')
                master_module_name = ls_tk[idx_equal-2]
                ls_pin_connect = ls_tk[1:idx_equal-2]
                ls_param_tk = ls_tk[idx_equal-1:]
            except:
                master_module_name = ls_tk[-1]
                ls_pin_connect = ls_tk[1:-1]
                ls_param_tk = list()

            # instance's master module
            assert master_module_name in design.modules.keys(), 'Error: instance\'s master module (%s) is not defined at line (%s) of file (%s)' % (master_module_name, begin_line_idx+1, ls_spice_netlist_fpath[fpath_idx])

            master_module = design.modules[master_module_name]

            instance = instance_t(instance_name, module, master_module)

            module.instances[instance.name] = instance

            # instance's pin connect
            assert len(ls_pin_connect) == len(instance.master_module.ls_port), '(PIN) %s; (PORT)%s' % (ls_pin_connect, instance.master_module.ports.keys())

            for (connect_name, port) in zip(ls_pin_connect, instance.master_module.ls_port):
                if not instance.connect_pin(port.name, connect_name):
                    module.add_wire(connect_name)
                    assert instance.connect_pin(port.name, connect_name)
#                     print 'Error: connection of instance\'s pin (%s) failed' % instance.pins[port.name].full_name

            # instance's parameter
            for (param_name, param_value) in parse_param_token(ls_param_tk):
                instance.add_param(param_name, param_value)

        del module.ls_instance_tk

    #===========================================================
    # module.is_hierarchical
    for module in design.modules.values():
        module.is_hierarchical = False
        for instance in module.instances.values():
            if not instance.master_module.is_basic:
                module.is_hierarchical = True
                break

    return design


def parse_param_token (ls_tk):
    '>> (name, value)'
    ls_param = list()
    while len(ls_tk) > 0:
        name = ls_tk.pop(0)
        assert ls_tk.pop(0) == '=', ls_tk
        try:
            next_idx_equal = ls_tk.index('=')
            value = ''.join(ls_tk[:next_idx_equal-1])
            ls_tk = ls_tk[next_idx_equal-1:]
        except:
            value = ''.join(ls_tk)
            ls_tk = list()
        value = value.strip("'")

        ls_param.append((name, value))

    return ls_param

if __name__ == '__main__':
    spice_netlist_parser(['./mrvl/r4nlvit.spi'])

    print 'DONE'
