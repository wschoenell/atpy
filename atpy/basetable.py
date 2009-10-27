import numpy as np

from copy import copy
import string

from fitstable import FITSMethods, FITSSetMethods
from sqltable import SQLMethods, SQLSetMethods
from votable import VOMethods, VOSetMethods
from ipactable import IPACMethods
from autotable import AutoMethods

from exceptions import VectorException

import rechelper as rec

default_format = {}
default_format[None.__class__] = 16, '.9e'
default_format[np.bool_] = 5, 's'
default_format[np.int16] = 5, 'i'
default_format[np.int32] = 10, 'i'
default_format[np.int64] = 20, 'i'
default_format[np.float32] = 15, '.8e'
default_format[np.float64] = 24, '.17e'
default_format[np.str] = 0, 's'
default_format[np.string_] = 0, 's'
default_format[np.uint8] = 0, 's'
default_format[str] = 0, 's'
default_format[np.unicode_] = 0, 's'


class ColumnHeader(object):

    def __init__(self, dtype, unit=None, description=None, null=None, format=None):
        self.dtype = dtype
        self.unit = unit
        self.description = description
        self.null = null
        self.format = format

    def __repr__(self):
        s = "%s" % str(self.dtype)
        if self.unit:
            s += ", unit=%s" % str(self.unit)
        if self.null:
            s += ", null=%s" % str(self.null)
        if self.description:
            s +=", description=%s" % self.description
        return s


class Table(FITSMethods, IPACMethods, SQLMethods, VOMethods, AutoMethods):

    def __init__(self, *args, **kwargs):
        '''
        Create a table instance

        Optional Arguments:

            If no arguments are given, and empty table is created

            If one or more arguments are given they are passed to the
            Table.read() method.
        '''

        self.reset()

        if 'name' in kwargs:
            self.table_name = kwargs.pop('name')
        else:
            self.table_name = None

        if len(args) + len(kwargs) > 0:
            self.read(*args, **kwargs)

        return

    def __getattr__(self, attribute):

        if attribute == 'names':
            return self.data.dtype.names
        elif attribute == 'units':
            print "WARNING: Table.units is depracated - use Table.columns to access this information"
            return dict([(name, self.columns[name].unit) for name in self.names])
        elif attribute == 'types':
            print "WARNING: Table.types is depracated - use Table.columns to access this information"
            return dict([(name, self.columns[name].type) for name in self.names])
        elif attribute == 'nulls':
            print "WARNING: Table.nulls is depracated - use Table.columns to access this information"
            return dict([(name, self.columns[name].null) for name in self.names])
        elif attribute == 'formats':
            print "WARNING: Table.formats is depracated - use Table.columns to access this information"
            return dict([(name, self.columns[name].format) for name in self.names])
        elif attribute == 'shape':
            return (len(self.data), len(self.names))
        elif attribute in self.names:
            return self.data[attribute]
        else:
            raise AttributeError(attribute)

    def __len__(self):
        if len(self.columns) == 0:
            return 0
        else:
            return len(self.data)

    def reset(self):
        '''
        Empty the table
        '''
        self.keywords = {}
        self.comments = []
        self.columns = {}
        self.data = None
        return

    def _raise_vector_columns(self):
        names = []
        for name in self.names:
            if self.data[name].ndim > 1:
                names.append(name)
        if names:
            names = string.join(names, ", ")
            raise VectorException(names)
        return

    def add_column(self, name, data, unit='', null='', description='', \
        format=None, dtype=None):
        '''
        Add a column to the table

        Required Arguments:

            *name*: [ string ]
                The name of the column to add

            *data*: [ numpy array ]
                The column data

        Optional Keyword Arguments:

            *unit*: [ string ]
                The unit of the values in the column

            *null*: [ same type as data ]
                The values corresponding to 'null', if not NaN

            *description*: [ string ]
                A description of the content of the column

            *format*: [ string ]
                The format to use for ASCII printing

            *dtype*: [ numpy type ]
                Numpy type to convert the data to. This is the equivalent to
                the dtype= argument in numpy.array
        '''

        data = np.array(data, dtype=dtype)
        dtype = data.dtype

        if dtype.type == np.object_:
            longest = len(max(data, key=len))
            data = np.array(data, dtype='|%iS' % longest)
            dtype = data.dtype

        if len(self.columns) > 0:
            newdtype = (name, data.dtype)
            self.data = rec.append_field(self.data, data, dtype=newdtype)
        else:
            self.data = np.rec.fromarrays([data], dtype=[(name, dtype)])

        if not format:
            format = default_format[dtype.type]

        if format[1] == 's':
            format = data.itemsize, 's'

        self.columns[name] = ColumnHeader(dtype, unit=unit, description=description, null=null, format=format)

        return

    def remove_column(self, remove_name):
        print "WARNING: remove_column is depracated - use remove_columns instead"
        self.remove_columns([remove_name])
        return

    def remove_columns(self, remove_names):
        '''
        Remove several columns from the table

        Required Argument:

            *remove_names*: [ list of strings ]
                A list containing the names of the columns to remove
        '''

        if type(remove_names) == str:
            remove_names = [remove_names]

        for remove_name in remove_names:
            self.columns.pop(remove_name)

        self.data = rec.drop_fields(self.data, remove_names)

        return

    def keep_columns(self, keep_names):
        '''
        Keep only specific columns in the table (remove the others)

        Required Argument:

            *keep_names*: [ list of strings ]
                A list containing the names of the columns to keep.
                All other columns will be removed.
        '''

        if type(keep_names) == str:
            keep_names = [keep_names]

        remove_names = list(set(self.names) - set(keep_names))

        if len(remove_names) == len(self.names):
            raise Exception("No columns to keep")

        self.remove_columns(remove_names)

        return

    def rename_column(self, old_name, new_name):
        '''
        Rename a column from the table

        Require Arguments:

            *old_name*: [ string ]
                The current name of the column.

            *new_name*: [ string ]
                The new name for the column
        '''

        if new_name in self.names:
            raise Exception("Column " + new_name + " already exists")

        if not old_name in self.names:
            raise Exception("Column " + old_name + " not found")

        pos = self.names.index(old_name)
        self.names = self.names[:pos] + (new_name, ) + self.names[pos+1:]

        self.columns[new_name] = self.columns[old_name]
        del self.columns[old_name]

        return

    def describe(self):
        '''
        Prints a description of the table
        '''

        if self.table_name:
            print "Table : " + self.table_name
        else:
            print "Table has no name"

        # Find maximum column widths
        len_name_max, len_unit_max, len_datatype_max, \
            len_formats_max = 4, 4, 4, 6

        for name in self.names:
            len_name_max = max(len(name), len_name_max)
            len_unit_max = max(len(str(self.columns[name].unit)), len_unit_max)
            len_datatype_max = max(len(str(self.columns[name].dtype)), \
                len_datatype_max)
            len_formats_max = max(len(self.columns[name].format), len_formats_max)

        # Print out table

        format = "| %" + str(len_name_max) + \
            "s | %" + str(len_unit_max) + \
            "s | %" + str(len_datatype_max) + \
            "s | %" + str(len_formats_max) + "s |"

        len_tot = len_name_max + len_unit_max + len_datatype_max + \
            len_formats_max + 13

        print "-"*len_tot
        print format % ("Name", "Unit", "Type", "Format")
        print "-"*len_tot

        for name in self.names:
            print format % (name, str(self.columns[name].unit), \
                str(self.columns[name].dtype), self.format(name))

        print "-"*len_tot

        return

    def row(self, row_number, python_types=False):
        '''
        Returns a single row

        Required arguments:

            *row_number*: [ integer ]
                The row number (the first row is 0)

        Optional Keyword Arguments:

            *python_types*: [ True | False ]
                Whether to return the row elements with python (True)
                or numpy (False) types.
        '''

        if python_types:
            row_data = list(self.data[row_number].tolist())
            for i, elem in enumerate(row_data):
                if elem <> elem:
                    row_data[i] = None
            return row_data
        else:
            return self.data[row_number]

    def rows(self, row_ids):
        '''
        Select specific rows from the table and return a new table instance

        Required Argument:

            *row_ids*: [ list | np.int array ]
                A python list or numpy array specifying which rows to select,
                and in what order.

        Returns:

            A new table instance, containing only the rows selected
        '''
        return self.where(np.array(row_ids,dtype=int))

    def where(self, mask):
        '''
        Select matching rows from the table and return a new table instance

        Required Argument:

            *mask*: [ np.bool array ]
                A boolean array with the same length as the table.

        Returns:

            A new table instance, containing only the rows selected
        '''

        new_table = self.__class__()

        new_table.table_name = copy(self.table_name)

        new_table.columns = copy(self.columns)
        new_table.keywords = copy(self.keywords)
        new_table.comments = copy(self.comments)

        new_table.data = self.data[mask]

        return new_table

    def format(self, name):
        '''
        Return the ASCII format of a given column

        Required Arguments:

            *name*: [ string ]
                The column name
        '''
        return str(self.columns[name].format[0]) + self.columns[name].format[1]

    def add_comment(self, comment):
        '''
        Add a comment to the table

        Required Argument:

            *comment*: [ string ]
                The comment to add to the table
        '''

        self.comments.append(comment.strip())
        return

    def add_keyword(self, key, value):
        '''
        Add a keyword/value pair to the table

        Required Arguments:

            *key*: [ string ]
                The name of the keyword

            *value*: [ string | float | integer | bool ]
                The value of the keyword
        '''

        if type(value) == str:
            value = value.strip()
        self.keywords[key.strip()] = value
        return


class TableSet(FITSSetMethods, SQLSetMethods, VOSetMethods, AutoMethods):

    _single_table_class = Table

    def __init__(self, *args, **kwargs):
        '''
        Create a table set instance

        Optional Arguments:

            If no arguments are given, an empty table set will be created.

            If one of the arguments is a list or a Table instance, then only
            this argument will be used.

            If one or more arguments are present, they are passed to the read
            method

        '''

        self.tables = []

        if len(args) == 1:

            arg = args[0]

            if type(arg) == list:
                for table in arg:
                    self.tables.append(table)
                    return

            elif isinstance(arg, TableSet):
                for table in arg.tables:
                    self.tables.append(table)
                    return

            # Pass arguments to read
            self.read(*args, **kwargs)

        return

    def __getattr__(self, attribute):

        for table in self.tables:
            if attribute == table.table_name:
                return table

        raise AttributeError(attribute)

    def append(self, table):
        '''
        Append a table to the table set

        Required Arguments:

            *table*: [ a table instance ]
                This can be a table of any type, which will be converted
                to a table of the same type as the parent set (e.g. adding
                a single VOTable to a FITSTableSet will convert the VOTable
                to a FITSTable inside the set)
        '''
        self.tables.append(table)
        return

    def describe(self):
        '''
        Describe all the tables in the set
        '''
        for table in self.tables:
            table.describe()
        return
