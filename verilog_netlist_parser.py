
import os
import re

from netlist import *

################################################################

def verilog_netlist_parser (ls_verilog_netlist_fpath):

    #-------------------------------------------------------
    # read all verilog netlist file into memory (ls_raw), and remove comment
    ls_raw = list() # content = (line, fpath_idx, line_idx)

    for (fpath_idx, fpath) in enumerate(ls_verilog_netlist_fpath):
        assert os.path.isfile(fpath), 'Cannot find verilog netlist file %s' % fpath
        f = open(fpath, 'r')

        is_mline_comment = False
        for (line_idx, line) in enumerate(f):
            line = re.sub(r'//.*', '', line.strip()) # single line // comment
            line = re.sub(r'/\*.*\*/', '', line) # single line /* */ comment

            # multi line /* */ comment
            if (is_mline_comment == False):
                # not in multi line /* */ comment
                (line, n) = re.subn(r'/\*.*', '', line) # find the beginning of /*
                if (n > 0):
                    is_mline_comment = True
            else:
                # already in multi line /* */ comment
                (line, n) = re.subn(r'.*\*/', '', line) # find the end of */
                if (n > 0):
                    is_mline_comment = False # found, so end multi-line comment
                else:
                    line = '' # not found, still in multi-line comment

            ls_raw.append((line.strip(), fpath_idx, line_idx))

        f.close()

    #-------------------------------------------------------
    # concate lines into full statement and save into memory (ls_stmt)
    ls_stmt = list() # content = (stmt, fpath_idx, begin_line_idx, end_line_idx)

    is_ignore = False
    stmt = ''
    for (line, fpath_idx, line_idx) in ls_raw:
        if (is_ignore) or (len(line) == 0):
            continue

        # unsupported keyword
        if (line.startswith('`')):
            continue

        # specify is ignored
        if (line == 'specify'):
            is_ignore = True
            continue
        if (line == 'endspecify'):
            is_ignore = False
            continue

        # endmodule
        if (line == 'endmodule'):
            ls_stmt.append((line, fpath_idx, line_idx, line_idx))
            continue

        # concate lines not end with ;
        if (len(stmt) == 0):
            # no history
            if (line.endswith(';')):
                # no following
                ls_stmt.append((line, fpath_idx, line_idx, line_idx))
            else:
                # with following
                stmt = line
                begin_line_idx = line_idx
        else:
            # with history
            if (line.endswith(';')):
                # no following
                ls_stmt.append((stmt + ' ' + line, fpath_idx, begin_line_idx, line_idx))
                stmt = ''
            else:
                # with following
                stmt += ' ' + line

#     for stmt in ls_stmt:
#         print stmt

    #-------------------------------------------------------
    # parse statement
    modules = dict()
    module = None
    for (stmt, fpath_idx, begin_line_idx, end_line_idx) in ls_stmt:
        stmt = stmt.replace(r'(', ' ( ')
        stmt = stmt.replace(r')', ' ) ')
        stmt = stmt.replace(r',', ' , ')
        stmt = stmt.replace(r'[', ' [ ')
        stmt = stmt.replace(r']', ' ] ')
        stmt = stmt.replace(r':', ' : ')
        stmt = re.sub(r'\s+', ' ', stmt)

        ls_tk = stmt.lower().split()

        first = ls_tk[0]
        #-------------------------------------------------------
        # parse module title
        if (first == 'module'):
            module_name = ls_tk[1]
            assert ls_tk[2] == '(', stmt
            ls_port_name = (''.join(ls_tk[3:-2])).split(',')
            assert ls_tk[-2] == ')', stmt
            assert ls_tk[-1] == ';', stmt

            assert module == None
            module = module_t(module_name)
            modules[module.name] = module

            module.buses = dict()

        #-------------------------------------------------------
        # parse module end
        elif (first == 'endmodule'):
            assert module != None
            module = None

        #-------------------------------------------------------
        # parse port
        elif (first in ('input', 'output')):
            assert ls_tk[-1] == ';', stmt
            direction = first
            (left, right, low, high, width, ls_port_name) = __parse_net_definition__(ls_tk)

            for port_name in ls_port_name:
                module.buses[port_name] = (left, right, low, high, width)
                if (width == 1):
                    port = port_t(port_name, module, direction)
                    module.ports[port_name] = port
                else:
                    for idx in range(low, high+1):
                        port_name = '%s[%d]' % (port_name, idx)
                        port = port_t(port_name, module, direction)
                        module.ports[port_name] = port

        #-------------------------------------------------------
        # parse wire
        elif (first == 'wire'):
            assert ls_tk[-1] == ';', stmt
            (left, right, low, high, width, ls_wire_name) = __parse_net_definition__(ls_tk)

            for wire_name in ls_wire_name:
                module.buses[wire_name] = (left, right, low, high, width)
                if (width == 0):
                    wire = wire_t(wire_name, module, direction)
                    module.wires[wire_name] = wire
                else:
                    for idx in range(low, high+1):
                        wire_name = '%s[%d]' % (wire_name, idx)
                        wire = wire_t(wire_name, module, direction)
                        module.wires[wire_name] = wire

        #-------------------------------------------------------
        # parse instance
        else:
            master_module_name = ls_tk[0]
            instance_name = ls_tk[1]
            assert ls_tk[2] == '(', stmt
            assert ls_tk[-2] == ')', stmt
            assert ls_tk[-1] == ';', stmt

            ls_pin_connection = list()
            for s in (''.join(ls_tk[3:-2])).split(','):
                s = s.replace(' ', '')
                m = re.match(r'\.(\S\+)\((\S\+)\)', s)
                assert m, s
                pin_name = m.group(1)
                connection = m.group(2)
                ls_pin_connection.append((pin_name, connection))

            instance = instance_t(instance_name, module)
            instance.master_module_name = master_module_name
            instance.ls_pin_connection = ls_pin_connection

            module.instances[instance_name] = instance

    #-------------------------------------------------------
    # solve instance reference and connection
    for module in modules.values():
        for instance in module.instances.values():
            instance.master_module = modules[instance.master_module_name]

            for (pin_name, connection) in instance.ls_pin_connection:
                # expand pin_name
                ls_pin_name = filter(lambda x: x.startswith(pin_name), instance.master_module.ports.keys())
                # expand connection
                if (not connection.startswith('{')):
                    # not concate net
                else:
                    # concate net
                    pass

#===========================================================

def __parse_net_range__(ls_tk):
    'find net range definition in token list. >> (left, right, low, high, width)' # {{{
    idx_left = ls_tk.index(r'[')
    idx_right = ls_tk.index(r']')

    assert ls_tk[idx_left+1].isdigit(), ls_tk
    left = int(ls_tk[idx_left+1])
    if (ls_tk[idx_left+2] == ':'):
        assert ls_tk[idx_right-1].isdigit(), ls_tk
        right = int(ls_tk[idx_right-1])
    else:
        right = left

    if (left > right):
        low = right
        high = left
    else:
        low = left
        high = right

    width = high - low + 1

    return (left, right, low, high, width)
    # }}}

def __parse_net_definition__(ls_tk):
    ' >> (left, right, low, high, width, ls_net_name)' # {{{
    stmt = ' '.join(ls_tk)
    assert ls_tk[0] in ('input', 'output', 'wire', 'reg'), stmt
    assert ls_tk[-1] == ';', stmt

    if (ls_tk[1] == '['):
        (left, right, low, high, width) = __parse_net_range(ls_tk)
        assert width > 1, ls_tk
        ls_net_name = (''.join(ls_tk[6:-1)).split(',')
    else:
        ls_net_name = (''.join(ls_tk[1:-1])).split(',')

    return (left, right, low, high, width, ls_net_name)
    # }}}

def __expand_net__(ls_tk, ref_buses):
    "{ w0[2:0], w1, w2 } >> { w0[2], w0[1], w0[0], w1, w2[3], w2[2], w2[1], w2[0] }"
    ls_old_tk = list(ls_tk)
    ls_new_tk = list()

    while (len(ls_old_tk) > 0):
        if re.match(r'[a-z_][\w\[\]:]+', ls_old_tk[0]):
            net_name = ls_old_tk.pop(0)
            if (ls_old_tk[1] == r'[')
                # explicitly defined slice
                idx_right_bracket = ls_old_tk.index(r']')
                ls_tmp_tk = ls_old_tk[:idx_right_bracket+1]
                del ls_old_tk[:idx_right_bracket+1]

                (left, right, low, high, width) = __parse_net_range__(ls_tmp_tk)
                ls_new_tk += __expand_net_single__(net_name, left, right, low, high)

            else:
                # slice not defined, refer to ref_buses
                (left, right, low, high, width) = ref_buses[net_name]
                ls_new_tk += __expand_net_single__(net_name, left, right, low, high)
        else:
            ls_new_tk.append(ls_old_tk.pop(0))

def __expand_net_single__(net_name, left, right, low, high):
    ls_expanded_tk = list()
    ls_expanded_stmt = list()
    for idx in range(low, high+1):
        ls_expanded_stmt.append('%s [ %d ] ,' % (net_name, idx)

    if (left > right):
        ls_expanded_stmt.reverse()

    for stmt in ls_expanded_stmt:
        ls_expanded_tk += stmt.split()

    ls_expanded_tk.pop(-1) # remove the tail ','
    return ls_expanded_tk


def __expand_constant__(ls_tk):
    "[2'b01, wire0, 2'b10] >> [1'b0, 1'b1, wire0, 1'b1, 1'b0]"
    pass

def __parse_net_concate__(ls_tk):
    pass


if __name__ == '__main__':
#     verilog_netlist_parser(['./test/test.v'])
