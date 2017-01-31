# -*- coding: utf-8 -*-
"""
    Module housing the "abstract" directive CsvFigureDirective.
    This directive is meant to produce more complex figures via a csv-table-like syntax
    which might be more convenient than using external files.
    CsvFigureDirective extends `docutils.parsers.rst.directives.tables` **and**
    `docutils.parsers.rst.directives.images.Figure`. It returns a figure node (wrapping a csvtable
    node) which should not be replaced by other node types, as refs, captions and other stuff
    within the document need to recognize this node as a figure. What can (and usually,
    **needs to**) be modified by subclasses is the wrapped table node, because this class does not
    provide any hint how the cell values should be converted to images: subclasses can thus
    access the nodes with `CsvFigureDirective.itertable` and usually
    (but not always) replace the csvtable node with one or more image nodes
    CsvFigureDirective.replace_self(...))

    :see: imggrid.py
    mapfig.py
"""

from docutils import nodes
from docutils.parsers.rst.directives.tables import CSVTable
from docutils.parsers.rst.directives.images import Figure
from docutils.nodes import Text


class CsvFigureDirective(CSVTable, Figure):
    """
    Directive that encapsulates a CsvTable into a Figure.
    Not intended to be used directly as rst directive. See mapfig and imggrid for
    subclasses
    Returns a figure node wrapping a csvtable and a potential caption, plus
    all messages generated by superclasses, if any
    """

    # these two members copied from CSVTable, needs to be set otherwise
    # seems that those of images.Figure are used. The result is that the title (caption)
    # is correctly parsed and whitespaces are not splitted
    required_arguments = CSVTable.required_arguments
    """Number of required directive arguments."""

    optional_arguments = CSVTable.optional_arguments
    """Number of optional arguments after the required arguments."""

    option_spec = Figure.option_spec.copy()  # @UndefinedVariable
    option_spec.update(CSVTable.option_spec.copy())

    def run(self):
        # First, let the CSVTable constructor handle all kind of parsing, including errors
        # (e.g., when we disabled the feature to load from file in sphinx, if a :file: has been
        # provided)

        # remove the title, if any: the title is actually the caption of the wrapping figure
        # Need to set to the empty list (See tables.Table directive)
        caption_text = self.arguments[0]
        self.arguments = []

        # parse using superclass
        csvtable_nodes = CSVTable.run(self)  # run super CSV Table to catch potential errors
        # the first node is the table node, then potential messages (see superclass)
        csvtable_node = csvtable_nodes[0]
        csv_messages = csvtable_nodes[1:]

        # Now execute the figure directive
        self.content = None  # the content will be translated as caption. Problem is, if we do not
        # have content we should add the caption anyways. So let's do it manually
        # need to restore the arguments list to a parsable Figure element. Its value is useless,
        # just set it to avoid trhowing errors (see images.Figure directive)
        self.arguments = ['']
        fig_nodes = Figure.run(self)
        # set the caption "manually":
        fig_node = fig_nodes[0]
        fig_messages = fig_nodes[1:]
        caption = None
        if self.arguments and caption_text:
            txt = Text(caption_text)
            caption = nodes.caption(caption_text, '', *[txt])
            caption.parent = fig_node  # sphinx complains if we do not set it ...

        fig_node.children = [csvtable_node]
        csvtable_node.parent = fig_node  # set the parent, as in general is good
        # (e.g. it might be used to allow remove the item from its parent)
        if caption:
            fig_node.children.append(caption)

        return [fig_node] + csv_messages + fig_messages

    def get_table_node(self, run_nodes):
        """ Returns the csv table node inside the figure node. You can use
        node.replace_self(...) if you want, e.g., replace the table node with a standard image
        :param nodes: the value returned by self.run()
        """
        fig_node = run_nodes[0]
        csvtable_node = fig_node.children[0]  # fig_node.children[1:] might be messages appended,
        return csvtable_node

    def _itercolspecs(self, run_nodes):  # FIXME: USED?
        """ Returns an iterator over the parsed csv table yieilding in turn the 'colspec' nodes
        making up the columns specifier. Each of them holds info about the given column.
        The length of the returned iterator (as list) is the number of columns. Each of these
        elements is translated into a COL tag (in latex, it seems to be simply ignored in current
        sphinx version 1.4.1)
        :param nodes: the value returned by self.run()
        """
        fig_node = run_nodes[0]
        csvtable_node = fig_node.children[0]  # it might have messages appended, the first child
        # is our node resulting from self.run above
        for cspec in csvtable_node.traverse(nodes.colspec):
            yield cspec

    def itertable(self, run_nodes):
        """ Returns an iterator over the parsed csv table yieilding in turn the tuple
        row (integer)
        col (integer)
        isRowHeader (boolean)
        isStubColumn (boolean) (stub column are like row headers but for columns)
        cell_node (node object - most likely Element object - or None),
        cell_node.rawsource (string or None)
        REMEMBER: cell_node CAN BE NONE!
        :param nodes: the value returned by self.run()
        """
        csvtable_node = self.get_table_node(run_nodes)

        # superclass parses csv in order to normalize cells, so the table obtained
        # is already normalized and well formatted. Empty strings are added in case

        # csvtable_node has two children: the first is the title, then the tgroup
        tgroup_node = csvtable_node.children[-1]
        # tgroup has several colplec's nodes as children, the next-to-last is the thead node,
        # the last one is the tbody
        tbody_node = tgroup_node.children[-1]
        table_body_rows = tbody_node.children
        thead_node = tgroup_node.children[-2]
        table_head_rows = []
        if isinstance(thead_node, nodes.thead):
            table_head_rows = thead_node.children

        header_rows_num = len(table_head_rows)
        data = table_head_rows + table_body_rows
        stub_columns_num = self.options.get('stub-columns', 0)
        for row_num, row in enumerate(data):
            for col_num, entry in enumerate(row.children):
                # In principle, entry.children is a single paragraph node holding the
                # cell text. But sometimes cells have more children, i.e. providing a "^"
                # puts in the
                # cell a system_message warning that ^ is a reserved symbols for titles
                # (or something so) preceeding the paragraph with the text as last element
                # So get last element (index [-1])
                try:
                    yield row_num, col_num, row_num < header_rows_num, \
                                col_num < stub_columns_num, \
                                entry.children[-1], entry.children[-1].rawsource
                except IndexError as _:
                    yield row_num, col_num, row_num < header_rows_num, \
                                col_num < stub_columns_num, \
                                None, None