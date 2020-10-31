# upvar and up

import gdb
from gdb.FrameIterator import FrameIterator

# This is faster than gdb.lookup_symbol.
def find_var(frame, name):
    block = frame.block()
    while True:
        for sym in block:
            if sym.name == name:
                return sym.value(frame)
        if block.function:
            return None
        block = block.superblock
        
def find_type(frame, type_tag):
    block = frame.block()
    while block is not None:
        for sym in block:
            # quick heuristic to avoid a deep type comparison
            #if type_tag not in str(sym.type):
            #    continue
            if not (sym.is_valid and (sym.is_argument or sym.is_variable)):
                continue
            tags = all_type_tags(sym.type)
            if type_tag in tags[0]:
                v = sym.value(frame)
                for op in tags[1]:
                    v = op(v)
                yield v
        if block.function:
            pass
        block = block.superblock

def all_type_tags(gdb_type: gdb.Type, names=None, ops=None,seen=None) -> set:
  name_list = list(names or []) if isinstance(names, set) else names or []
  seen = seen or set([])
  ops = ops or []
  prev_type = None
  
  while prev_type != gdb_type:
    prev_type = gdb_type
    gdb_type = gdb_type.unqualified()
    if str(gdb_type) in seen:
        break
    seen.add(str(gdb_type))
    if gdb_type.tag is not None:
      print(" .. : <tag=%s>" %str(gdb_type.tag))
      name_list.append(gdb_type.tag)
    if gdb_type.name is not None:
      print(" .. : <name=%s>" % str(gdb_type.name))
      name_list.append(gdb_type.name)

    if gdb_type.code in \
       (gdb.TYPE_CODE_PTR, gdb.TYPE_CODE_REF, gdb.TYPE_CODE_RVALUE_REF,
        gdb.TYPE_CODE_ARRAY):
        print(" .. [%s].target() -> %s" % (str(gdb_type), 
          str(gdb_type.target())))
        gdb_type = gdb_type.target()
        ops.append(gdb.Value.referenced_value)
        
    elif gdb_type.code in \
      (gdb.TYPE_CODE_UNION, gdb.TYPE_CODE_STRUCT):
        next_base = next = None
        for field in gdb_type.fields():
            if field.type in (prev_type, gdb_type, None if prev_type is None else prev_type.pointer(), gdb_type.pointer()):
                continue
            if field.is_base_class:
                print(
                  f"   [%s].{field.name} ***BASE_CLASS*** {str(field.type)}"\
                    % (str(field.parent_type)))
            all_type_tags(field.type, names=name_list,
              ops=(ops + [
                (lambda v: v.cast(field.parent_type)[field])
              ]), seen=seen)
            
    elif gdb_type.code == gdb.TYPE_CODE_TYPEDEF:
        print(" [%s] typedef -> %s" % (str(gdb_type), 
          str(gdb_type.strip_typedefs())))
        ops.append(lambda v: v.cast(v.type.strip_typedefs()))
        gdb_type = gdb_type.strip_typedefs()
  return (set(name_list), ops)


class Upvar(gdb.Function):
    """$_upvar - find a variable somewhere up the stack

Usage:
    $_upvar(NAME, LIMIT)

This function searches up the stack for a variable.
NAME is a string, the name of the variable to look for.
Starting with the selected frame, each stack frame is searched
for NAME.  If it is found, its value is returned.

If NAME is not found, an error is raised.

LIMIT is a number that limits the number of stack frames searched.
If LIMIT is reached, the number 0 is returned.
"""

    def __init__(self):
        super(Upvar, self).__init__('_upvar')

    def invoke(self, name,  limit):
        name = str(name)
        for frame in FrameIterator(gdb.selected_frame()):
            if limit <= 0:
                return gdb.Value(0)
            limit = limit - 1
            val = find_var(frame, name)
            if val is not None:
                return val
            raise gdb.GdbError("couldn't find %s" % name)


class Up(gdb.Function):
    """$_up - move up the stack

Usage:
    $_up(N [ = 1])

Like 'up', but suitable for use in an expression.
The argument says how many frames to move 'up'.

Always returns 1."""

    def __init__(self):
        super(Up, self).__init__('_up')

    def invoke(self, n = 1):
        for frame in FrameIterator(gdb.selected_frame()):
            if n <= 0:
                frame.select()
                break
            n = n - 1
        return 1


class Var(gdb.Function):
    """$_var - fetch a variable

Usage:
    $_var(NAME)

Return the value of the variable named NAME in the selected frame.
This is generally most useful in conjunction with $_up."""

    def __init__(self):
        super(Var, self).__init__('_var')

    def invoke(self, name):
        val = find_var(gdb.selected_frame(), name)
        if val is not None:
            return val
        raise gdb.GdbError("couldn't find %s" % name)

Upvar()
Up()
Var()